"""UC16: màn hình hàng đợi chỉ cho người dùng tổ chức thấy và huỷ việc CỦA HỌ.

Worker dùng chung cho mọi tổ chức, nên `celery inspect` trả việc của cả nền
tảng. Trước 23/10/2026 endpoint trả nguyên danh sách đó cho biên tập viên của
bất kỳ tổ chức nào, và `/revoke` nhận mọi `task_id`. Các bài ở đây chốt:

  * ghi sổ chủ tác vụ thật sự được nối vào tín hiệu publish (gửi qua tín hiệu,
    không gọi thẳng hàm — gọi thẳng chỉ chứng minh hàm, không chứng minh dây)
  * người dùng tổ chức chỉ thấy việc của tổ chức đang làm việc; việc của tổ
    chức khác và việc vô chủ bị ẩn; sổ hỏng thì ẩn hết (fail-closed)
  * huỷ việc không phải của mình trả 404, lệnh huỷ KHÔNG được gửi đi, và lần
    bị từ chối được ghi lại — đúng kiểu hậu điều kiện của Chương 4
  * quản trị nền tảng thấy và huỷ được mọi việc
  * việc hỏng hẳn được ghi `task.failed`, và màn hình đọc lại đúng phạm vi

Toàn bộ chạy không cần Postgres hay Redis: các ranh giới ngoài (inspect, Redis,
nhật ký) được thay bằng bản giả ghi lại lời gọi.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException  # pyright: ignore[reportMissingImports]

from app import task_registry
from app.routers import processing_admin as pa
from app.tenant_context import in_system_scope, tenant_scope

TENANT_A = "truong-a"
TENANT_B = "truong-b"

EDITOR_A = {"id": "00000000-0000-0000-0000-00000000000a", "username": "bien_tap_a",
            "is_admin": False}
PLATFORM = {"id": "00000000-0000-0000-0000-0000000000ff", "username": "superadmin",
            "is_admin": True}


# --------------------------------------------------------------------------- bản giả


class _FakeRedis:
    def __init__(self, store=None, fail=False):
        self.store = dict(store or {})
        self.fail = fail
        self.set_calls = []

    def set(self, key, value, ex=None):
        if self.fail:
            raise ConnectionError("redis down")
        self.set_calls.append((key, value, ex))
        self.store[key] = value

    def mget(self, keys):
        if self.fail:
            raise ConnectionError("redis down")
        return [self.store.get(k) for k in keys]

    def llen(self, _name):
        return 0


def _task(tid, name="app.tasks.process_video", args="('x',)"):
    return {"id": tid, "name": name, "args": args, "time_start": 1.0}


@pytest.fixture
def broker(monkeypatch):
    """Hai worker; việc của A, của B và một việc nền tảng (không có chủ trong sổ)."""
    active = {"w1@host": [_task("t-a-run"), _task("t-b-run")]}
    reserved = {"w2@host": [_task("t-a-wait"), _task("t-sys", name="app.saas_tasks.rollup")]}
    revoked = []

    class _Inspect:
        def active(self):
            return active

        def reserved(self):
            return reserved

    class _Control:
        def inspect(self, timeout=None):
            return _Inspect()

        def revoke(self, task_id, terminate=False):
            revoked.append((task_id, terminate))

    from app.worker import celery_app

    monkeypatch.setattr(celery_app, "control", _Control())

    store = {
        f"{task_registry.KEY_PREFIX}t-a-run": TENANT_A,
        f"{task_registry.KEY_PREFIX}t-a-wait": TENANT_A,
        f"{task_registry.KEY_PREFIX}t-b-run": TENANT_B,
    }
    fake = _FakeRedis(store)
    monkeypatch.setattr(task_registry, "_client_singleton", fake)

    import redis  # pyright: ignore[reportMissingImports]

    monkeypatch.setattr(redis.Redis, "from_url", classmethod(lambda cls, *a, **k: _FakeRedis()))

    failures_seen = {}

    def _fake_failures(tenant):
        failures_seen["tenant"] = tenant
        return [], None

    monkeypatch.setattr(pa, "_recent_failures", _fake_failures)

    security = []
    monkeypatch.setattr(pa.activity, "log_security_event",
                        lambda action, **kw: security.append((action, kw)))

    return SimpleNamespace(revoked=revoked, redis=fake, security=security,
                           failures_seen=failures_seen)


def _ids(rows):
    return sorted(r.task_id for r in rows)


# --------------------------------------------------------------------------- sổ ghi


def test_record_owner_writes_with_ttl(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(task_registry, "_client_singleton", fake)

    assert task_registry.record_owner("t1", TENANT_A) is True
    assert fake.set_calls == [(f"{task_registry.KEY_PREFIX}t1", TENANT_A,
                               task_registry.TTL_SECONDS)]


def test_record_owner_never_raises_and_skips_empty(monkeypatch):
    monkeypatch.setattr(task_registry, "_client_singleton", _FakeRedis(fail=True))
    assert task_registry.record_owner("t1", TENANT_A) is False
    assert task_registry.record_owner(None, TENANT_A) is False
    assert task_registry.record_owner("t1", None) is False


def test_owners_of_maps_missing_to_none(monkeypatch):
    monkeypatch.setattr(task_registry, "_client_singleton",
                        _FakeRedis({f"{task_registry.KEY_PREFIX}t1": TENANT_A}))
    assert task_registry.owners_of(["t1", "t2"]) == {"t1": TENANT_A, "t2": None}
    assert task_registry.owners_of([]) == {}


# --------------------------------------------------------------------------- dây tín hiệu


def test_publish_signal_records_the_owner_for_a_tenant_task(monkeypatch):
    from celery.signals import before_task_publish

    from app.worker import TENANT_HEADER

    recorded = []
    monkeypatch.setattr(task_registry, "record_owner",
                        lambda tid, tenant: recorded.append((tid, tenant)))

    headers = {"id": "t-proto2", "task": "app.tasks.x"}
    with tenant_scope(TENANT_A):
        before_task_publish.send(sender="app.tasks.x", headers=headers, body=((), {}, {}))

    assert headers[TENANT_HEADER] == TENANT_A
    assert recorded == [("t-proto2", TENANT_A)]


def test_publish_signal_reads_the_id_from_the_body_on_protocol_1(monkeypatch):
    from celery.signals import before_task_publish

    recorded = []
    monkeypatch.setattr(task_registry, "record_owner",
                        lambda tid, tenant: recorded.append((tid, tenant)))

    with tenant_scope(TENANT_A):
        before_task_publish.send(sender="app.tasks.x", headers={}, body={"id": "t-proto1"})

    assert recorded == [("t-proto1", TENANT_A)]


def test_platform_work_is_not_recorded(monkeypatch):
    """System scope (fixture tự động của suite) không có chủ để ghi."""
    from celery.signals import before_task_publish

    recorded = []
    monkeypatch.setattr(task_registry, "record_owner",
                        lambda tid, tenant: recorded.append((tid, tenant)))

    assert in_system_scope()
    before_task_publish.send(sender="app.tasks.x", headers={"id": "t-sys"}, body=None)
    assert recorded == []


def test_failure_signal_writes_a_task_failed_audit_row(monkeypatch):
    from celery.signals import task_failure

    from app import audit

    rows = []
    monkeypatch.setattr(audit, "record", lambda action, **kw: rows.append((action, kw)) or True)

    class _Task:  # sender phải hashable — Celery dùng nó làm khoá bộ đệm
        name = "app.tasks.process_video"

    sender = _Task()
    task_failure.send(sender=sender, task_id="t-dead", exception=ValueError("x" * 500))

    assert len(rows) == 1
    action, kw = rows[0]
    assert action == "task.failed"
    assert kw["target_type"] == "task" and kw["target_id"] == "t-dead"
    assert kw["detail"]["name"] == "app.tasks.process_video"
    assert kw["detail"]["error"].startswith("ValueError: ")
    assert len(kw["detail"]["error"]) == 300


# --------------------------------------------------------------------------- ảnh chụp hàng đợi


def test_tenant_editor_sees_only_their_tenants_tasks(broker):
    with tenant_scope(TENANT_A):
        snap = pa.processing_snapshot(current_user=EDITOR_A)

    assert snap.task_scope == "tenant"
    assert _ids(snap.running) == ["t-a-run"]
    assert _ids(snap.reserved) == ["t-a-wait"]
    assert all(r.tenant_id == TENANT_A for r in snap.running + snap.reserved)
    assert broker.failures_seen["tenant"] == TENANT_A


def test_the_other_tenant_sees_the_mirror_image(broker):
    with tenant_scope(TENANT_B):
        snap = pa.processing_snapshot(current_user={**EDITOR_A, "username": "bien_tap_b"})

    assert _ids(snap.running) == ["t-b-run"]
    assert snap.reserved == []


def test_platform_admin_sees_every_task_with_its_owner(broker):
    with tenant_scope(TENANT_A):
        snap = pa.processing_snapshot(current_user=PLATFORM)

    assert snap.task_scope == "platform"
    assert _ids(snap.running) == ["t-a-run", "t-b-run"]
    assert _ids(snap.reserved) == ["t-a-wait", "t-sys"]
    owners = {r.task_id: r.tenant_id for r in snap.running + snap.reserved}
    assert owners == {"t-a-run": TENANT_A, "t-b-run": TENANT_B,
                      "t-a-wait": TENANT_A, "t-sys": None}
    # Việc HỎNG thì vẫn chỉ của tổ chức đang làm việc — router không mở system scope.
    assert broker.failures_seen["tenant"] == TENANT_A


def test_unreadable_registry_hides_everything_from_tenant_users(broker):
    broker.redis.fail = True
    with tenant_scope(TENANT_A):
        snap = pa.processing_snapshot(current_user=EDITOR_A)
    assert snap.running == [] and snap.reserved == []

    with tenant_scope(TENANT_A):
        snap = pa.processing_snapshot(current_user=PLATFORM)
    assert len(snap.running) == 2 and all(r.tenant_id is None for r in snap.running)


def test_api_key_is_never_platform_even_if_flagged(broker):
    key = {"id": "apikey:abc", "username": "apikey:voya_x", "is_admin": True,
           "auth_method": "api_key", "tenant_id": TENANT_A}
    import app.quota_deps as qd

    original = qd.working_tenant_of
    try:
        qd.working_tenant_of = lambda user: TENANT_A
        snap = pa.processing_snapshot(current_user=key)
    finally:
        qd.working_tenant_of = original
    assert snap.task_scope == "tenant"
    assert _ids(snap.running) == ["t-a-run"]


def test_no_working_tenant_is_refused(broker):
    # Fixture của suite đặt system scope: không có tổ chức đang làm việc.
    with pytest.raises(HTTPException) as exc:
        pa.processing_snapshot(current_user=EDITOR_A)
    assert exc.value.status_code == 403


# --------------------------------------------------------------------------- huỷ


def _revoke(user, task_id, tenant=TENANT_A, terminate=False):
    body = pa.RevokeBody(task_id=task_id, terminate=terminate)
    with tenant_scope(tenant):
        return pa.revoke_task(body, request=None, current_user=user)


def test_editor_can_revoke_their_own_task(broker):
    assert _revoke(EDITOR_A, "t-a-run", terminate=True) == {
        "task_id": "t-a-run", "terminated": True}
    assert broker.revoked == [("t-a-run", True)]
    assert [a for a, _ in broker.security] == ["processing.task_revoked"]


@pytest.mark.parametrize("task_id", ["t-b-run", "t-sys", "khong-ton-tai"])
def test_editor_cannot_revoke_a_task_that_is_not_theirs(broker, task_id):
    with pytest.raises(HTTPException) as exc:
        _revoke(EDITOR_A, task_id, terminate=True)

    # 404, không phải 403: không xác nhận rằng task_id đó có thật.
    assert exc.value.status_code == 404
    # Hậu điều kiện: lệnh huỷ không hề được gửi.
    assert broker.revoked == []
    assert [a for a, _ in broker.security] == ["processing.task_revoke_denied"]


def test_unreadable_registry_refuses_revocation(broker):
    broker.redis.fail = True
    with pytest.raises(HTTPException) as exc:
        _revoke(EDITOR_A, "t-a-run")
    assert exc.value.status_code == 404
    assert broker.revoked == []


def test_platform_admin_can_revoke_any_task(broker):
    _revoke(PLATFORM, "t-b-run")
    _revoke(PLATFORM, "t-sys")
    assert broker.revoked == [("t-b-run", False), ("t-sys", False)]


# --------------------------------------------------------------------------- việc hỏng


def test_tenant_failures_are_filtered_explicitly(monkeypatch):
    import app.storage.metadata_db as db

    calls = []

    def _fake_fetch(sql, params=()):
        calls.append((sql, params, in_system_scope()))
        return [{"action": "task.failed", "target_id": "t-1",
                 "detail": {"name": "app.tasks.process_video", "error": "OSError: disk"},
                 "created_at": "2026-10-23T00:00:00Z", "tenant_id": TENANT_A}]

    monkeypatch.setattr(db, "_fetch_all", _fake_fetch)

    with tenant_scope(TENANT_A):
        rows, err = pa._recent_failures(TENANT_A)

    assert err is None
    sql, params, system = calls[0]
    assert "tenant_id = %s" in sql and params == (TENANT_A,) and system is False
    # Giữ hình dạng mà giao diện đang đọc.
    assert rows == [{"action": "app.tasks.process_video", "target": "t-1",
                     "reason": "OSError: disk", "created_at": "2026-10-23T00:00:00Z",
                     "tenant_id": TENANT_A}]


def test_the_router_never_steps_outside_the_tenant_boundary():
    """Bất biến của dự án: đúng một router được dùng `system_scope` (sot_admin).

    Bản đầu của bản sửa này đọc việc hỏng của cả nền tảng cho quản trị nền tảng
    bằng `system_scope`, và `test_tenant_isolation` bắt được ngay. Chốt thêm ở
    đây để lý do nằm cạnh mã của UC16.
    """
    from pathlib import Path

    source = Path(pa.__file__).read_text(encoding="utf-8")
    assert "system_scope(" not in source


def test_unreadable_failure_log_is_reported_not_hidden(monkeypatch):
    import app.storage.metadata_db as db

    def _boom(sql, params=()):
        raise RuntimeError("db down")

    monkeypatch.setattr(db, "_fetch_all", _boom)
    rows, err = pa._recent_failures(TENANT_A)
    assert rows == [] and err and "db down" in err


def test_processingSnapshot_twoInspectCalls_waitTogetherNotInTurn(broker, monkeypatch):
    """Mỗi lệnh inspect đợi trọn hạn; nối tiếp thì trang tự làm mới mất 4 giây."""
    import threading

    from app.worker import celery_app

    cung_luc = threading.Barrier(2, timeout=5)

    class _Inspect:
        def active(self):
            cung_luc.wait()
            return {"w1@host": []}

        def reserved(self):
            cung_luc.wait()
            return {"w2@host": []}

    monkeypatch.setattr(celery_app.control, "inspect", lambda timeout=None: _Inspect())
    with tenant_scope(TENANT_A):
        anh_chup = pa.processing_snapshot(current_user=EDITOR_A)
    assert anh_chup.reachable is True
    assert anh_chup.workers == ["w1@host", "w2@host"]

"""Đường ĐỌC của nhật ký kiểm toán bền.

Bảng `audit_log` có từ schema v3, nhưng tới trước bản này **không có endpoint
nào** đọc nó: lối gọi duy nhất tới `list_audit_log` nằm trong một tệp test.
Một dấu vết kiểm toán không ai đọc được thì không trả lời được câu hỏi nào vào
lúc có người cần hỏi — nó chỉ là chi phí lưu trữ.

Ba nhóm khẳng định:
  1. Endpoint trả đúng hình dạng và lọc được theo tiền tố hành động.
  2. Nó là endpoint QUẢN TRỊ — không có `require_admin` thì không vào được.
  3. Một hành động thật ở mặt phẳng dữ liệu để lại dòng đọc được qua endpoint
     này. Đây là nhóm quan trọng nhất: hai nhóm trên vẫn xanh kể cả khi không
     có gì ghi vào bảng.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


#: Tenant mà request trong tệp này chạy dưới. Xem `client`.
SCOPE = "default"


@pytest.fixture
def client(monkeypatch):
    """Client quản trị CÓ PHẠM VI TENANT — và phần phạm vi mới là phần khó.

    Ghi đè `require_admin` là đủ để qua cửa xác thực, nhưng **không** đặt phạm
    vi: `TenantScopeMiddleware` tự đọc token trên request thật, không thấy ai,
    nên coi request là ẩn danh. Ẩn danh mà `PUBLIC_TENANT_ID` để trống thì
    request chạy ngoài mọi phạm vi, và RLS trả về 0 dòng — endpoint xanh, rỗng,
    và test khẳng định được đúng con số không.

    Bản đầu của tệp này mắc đúng bẫy đó. Sửa bằng cách đặt `public_tenant_id`,
    tức tái lập điều kiện thật: một quản trị viên đăng nhập luôn có
    `users.tenant_id`, nên request của họ luôn có phạm vi.

    `id` cố ý KHÔNG phải UUID. `audit_log.actor_user_id` có khoá ngoại tới
    `users`; một UUID bịa sẽ vi phạm khoá ngoại, `record()` nuốt lỗi, và mọi
    dòng biến mất. `audit.record` chuyển id không-phải-UUID thành NULL và giữ
    `actor_label` — đúng đường mà một lối gọi bằng khoá API đi.
    """
    from app.config import settings
    from app.main import app
    from app.auth import require_admin

    monkeypatch.setattr(settings, "public_tenant_id", SCOPE, raising=False)
    app.dependency_overrides[require_admin] = lambda: {
        "id": "kiemthu-khong-phai-uuid", "username": "kiemthu", "is_admin": True,
    }
    yield TestClient(app)
    app.dependency_overrides.pop(require_admin, None)


@pytest.fixture
def seeded():
    """Ghi vài dòng kiểm toán TRONG tenant mà request sẽ đọc, rồi dọn."""
    from app import audit
    from app.tenant_context import tenant_scope

    marker = uuid.uuid4().hex[:8]
    actions = [f"test.api.{marker}.mot", f"test.api.{marker}.hai"]
    with tenant_scope(SCOPE):
        for action in actions:
            assert audit.record(action, actor={"username": "nguoi-gieo"},
                                target_type="thu-nghiem", target_id=marker) is True

    yield marker, actions

    with system_scope("test cleanup: gỡ dòng kiểm toán"):
        for action in actions:
            db._execute("DELETE FROM audit_log WHERE action = %s", (action,))


def test_the_endpoint_returns_rows(client, seeded):
    marker, _ = seeded

    body = client.get("/api/v1/admin/audit-log",
                      params={"limit": 200, "action_prefix": f"test.api.{marker}"}).json()

    assert body["count"] == 2
    assert {r["action"] for r in body["events"]} == set(seeded[1])
    assert all(r["actor_label"] == "nguoi-gieo" for r in body["events"])


def test_the_endpoint_filters_by_action_prefix(client, seeded):
    marker, actions = seeded

    body = client.get("/api/v1/admin/audit-log",
                      params={"action_prefix": f"test.api.{marker}.mot"}).json()

    assert [r["action"] for r in body["events"]] == [actions[0]]


def test_newest_first(client, seeded):
    """Thứ tự không phải chuyện thẩm mỹ: người đọc một nhật ký kiểm toán gần
    như luôn hỏi "vừa có chuyện gì", và một bảng cũ-trước bắt họ cuộn tới cuối
    để trả lời câu hỏi thường gặp nhất."""
    marker, actions = seeded

    body = client.get("/api/v1/admin/audit-log",
                      params={"action_prefix": f"test.api.{marker}"}).json()

    ids = [r["audit_id"] for r in body["events"]]
    assert ids == sorted(ids, reverse=True)
    assert body["events"][0]["action"] == actions[1]


def test_the_endpoint_is_admin_only():
    """Không ghi đè `require_admin` thì phải bị chặn.

    Nhật ký kiểm toán liệt kê tên tài khoản, đối tượng bị tác động và băm
    nguồn. Mở nó cho người dùng thường là mở đúng danh sách mà một kẻ tấn công
    cần để biết ai đáng nhắm tới.
    """
    from app.main import app

    response = TestClient(app).get("/api/v1/admin/audit-log")

    assert response.status_code in (401, 403)


def test_a_real_purge_shows_up_in_the_endpoint(client, monkeypatch):
    """Hành động thật ở mặt phẳng dữ liệu phải để lại dòng đọc được.

    Cho tới bản này mặt phẳng dữ liệu không ghi kiểm toán gì cả: lần purge lớp
    `lop-thu-70eb62` ngày 2026-08-08 — xoá không hồi được trên dữ liệu sản
    xuất — không để lại dòng nào để tra ai đã làm.

    Không purge lớp thật ở đây. `sync_purge_class` bị thay bằng một hàm giả:
    thứ đang kiểm là *router có ghi kiểm toán khi thao tác thành công hay
    không*, và xoá dữ liệu thật để chứng minh chuyện đó là cái giá không cần
    trả — bộ test này chạy trên cơ sở dữ liệu THẬT.
    """
    from app.routers import classes as classes_router

    class_uid = f"gia-{uuid.uuid4().hex[:12]}"
    monkeypatch.setattr(classes_router, "sync_purge_class",
                        lambda uid: {"purged": True, "class_uid": uid,
                                     "op_id": f"class_purge_{uid}"})

    response = client.delete(f"/api/v1/classes/{class_uid}/purge")
    assert response.status_code == 200, f"{response.status_code}: {response.text[:300]}"
    assert response.json()["success"] is True

    body = client.get("/api/v1/admin/audit-log",
                      params={"action_prefix": "data.class.purge"}).json()
    mine = [r for r in body["events"] if r["target_id"] == class_uid]

    try:
        assert len(mine) == 1, "purge không để lại dòng kiểm toán"
        assert mine[0]["actor_label"] == "kiemthu"
        assert mine[0]["target_type"] == "class"
    finally:
        with system_scope("test cleanup: gỡ dòng kiểm toán của purge giả"):
            db._execute("DELETE FROM audit_log WHERE target_id = %s", (class_uid,))

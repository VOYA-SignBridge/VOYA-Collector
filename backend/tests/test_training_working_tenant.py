"""Huấn luyện đi theo tổ chức ĐANG LÀM VIỆC, hạn mức vẫn giữ tổ chức nhà.

Sự cố 18/10/2026: tài khoản `Minh67` có nhà ở `truong-chuyen-biet-soc-trang`,
đang làm việc ở VOYA (`default`, chuyển qua `POST /tenants/switch`). Thư viện nhãn
— đọc theo phạm vi request — thấy 8 lớp hoa-de / 988 mẫu. Trang huấn luyện đọc
theo `tenant_of(current_user)` (tổ chức NHÀ, vốn để tính hạn mức), thấy đúng một
lớp "Xin chào" 5 mẫu của trường, loại nó vì dưới sàn, rồi báo "Không đủ lớp để
chia cho hoa-de: còn 0 lớp".

Phạm vi request do `TenantScopeMiddleware` đặt từ `users.active_tenant_id` SAU
khi đã kiểm tư cách thành viên, nên đổi sang nó không mở thêm quyền nào.

Hạn mức: `training_jobs_*` đếm `WHERE tenant_id = <chủ job>`. Job thuộc tổ chức
đang làm việc, nên chỉ kiểm ở tổ chức nhà thì các job ấy không bao giờ được đếm
— xếp hàng không giới hạn. Vì vậy kiểm ở CẢ HAI.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app.routers.training as tr
import app.tenant_middleware as tm
from app.auth import get_current_user
from app.main import app

HOME = "truong-b"
WORKING = "default"

client = TestClient(app)


@pytest.fixture
def working_in_voya(monkeypatch):
    """Người dùng nhà ở `truong-b`, request mang phạm vi `default` (VOYA)."""
    monkeypatch.setattr(tm, "resolve_tenant", lambda cookie, bearer: WORKING)
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "8744d8f3-0000-4000-8000-000000000000", "username": "Minh67", "is_admin": True, "tenant_id": HOME}
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_operational_split_list_is_the_working_tenants(working_in_voya, monkeypatch):
    seen = []
    monkeypatch.setattr(tr, "_operational_splits", lambda tenant_id: seen.append(tenant_id) or [])
    r = client.get("/training/splits/operational")
    assert r.status_code == 200, r.text
    assert seen == [WORKING]


def test_dataset_info_counts_the_working_tenants_data(working_in_voya, monkeypatch):
    labels = [
        {"class_uid": "c-voya", "slug": "tom", "dialect": "hoa-de", "language": "vn", "tenant_id": WORKING},
        {"class_uid": "c-truong", "slug": "xin-chao", "dialect": "hoa-de", "language": "vn", "tenant_id": HOME},
    ]
    samples = ([{"sample_uid": f"v{i}", "class_uid": "c-voya", "tenant_id": WORKING} for i in range(3)]
               + [{"sample_uid": "t0", "class_uid": "c-truong", "tenant_id": HOME}])
    dialect_scope, provenance_scope = [], []
    monkeypatch.setattr(tr, "_load_samples_and_labels", lambda: (samples, labels))
    monkeypatch.setattr(tr, "_get_dialects_by_language",
                        lambda tenant_id=None: dialect_scope.append(tenant_id) or {"vn": ["hoa-de"]})
    monkeypatch.setattr(tr, "_split_provenance",
                        lambda **kw: provenance_scope.append(kw.get("tenant_id")) or tr.SplitProvenance())

    r = client.get("/training/dataset-info", params={"dialect": "hoa-de"})
    assert r.status_code == 200, r.text
    assert r.json()["total_samples"] == 3, "đang đếm dữ liệu của tổ chức nhà thay vì tổ chức đang làm việc"
    assert dialect_scope == [WORKING]
    assert provenance_scope == [WORKING]


def test_dataset_preparation_is_owned_by_the_working_tenant(working_in_voya, monkeypatch):
    import app.dataset_prep_tasks as dp

    reports, dispatched = [], []
    monkeypatch.setattr(tr, "assert_can_use_dialect", lambda d, uid: None)
    monkeypatch.setattr(dp, "create_pending_report", lambda run_id, **kw: reports.append(kw["tenant_id"]))
    monkeypatch.setattr(dp.prepare_dataset, "delay", lambda **kw: dispatched.append(kw["tenant_id"]))

    r = client.post("/training/dataset/prepare", json={"dialects": ["hoa-de"]})
    assert r.status_code == 200, r.text
    assert reports == [WORKING] and dispatched == [WORKING]


@pytest.mark.parametrize("owner,status", [(WORKING, 200), (HOME, 404)])
def test_preparation_report_is_readable_from_the_working_tenant(working_in_voya, monkeypatch, owner, status):
    import app.dataset_prep_tasks as dp

    monkeypatch.setattr(dp, "read_report", lambda run_id: {"run_id": run_id, "tenant_id": owner})
    r = client.get("/training/dataset/prepare/run-1")
    assert r.status_code == status, r.text


def test_start_checks_quota_at_home_and_at_the_working_tenant(working_in_voya, monkeypatch):
    checked = []

    def _guard(current_user, metric, *, adding=1, tenant_id=None):
        checked.append((metric, tenant_id))
        if (metric, tenant_id) == ("training_jobs_queued", WORKING):
            raise HTTPException(status_code=429, detail="stop sau khi kiểm hạn mức")

    async def _never_persist(*a, **kw):  # chốt chặn: không bao giờ tới bước tạo job
        raise HTTPException(status_code=418, detail="lọt qua hạn mức tới bước ghi job")

    monkeypatch.setattr(tr, "guard_quota", _guard)
    monkeypatch.setattr(tr, "_persist_job", _never_persist)
    r = client.post("/training/start", json={"model_type": "tcn", "epochs": 1})
    assert r.status_code == 429, r.text
    assert ("training_jobs_running", None) in checked and ("training_jobs_queued", None) in checked, \
        "hạn mức tổ chức nhà phải vẫn được kiểm"
    assert ("training_jobs_running", WORKING) in checked and ("training_jobs_queued", WORKING) in checked, \
        "job thuộc tổ chức đang làm việc — không kiểm ở đó là lọt hạn mức"


def test_guard_quota_can_target_an_explicit_tenant(monkeypatch):
    import app.quota_deps as qd

    seen = []
    monkeypatch.setattr(qd, "enforce", lambda tenant_id, metric, adding=1: seen.append(tenant_id))
    qd.guard_quota({"tenant_id": HOME}, "training_jobs_queued")
    qd.guard_quota({"tenant_id": HOME}, "training_jobs_queued", tenant_id=WORKING)
    assert seen == [HOME, WORKING]


def test_progress_websocket_uses_the_working_tenant(monkeypatch):
    """`TenantScopeMiddleware` không chạy cho WebSocket, nên endpoint tự đặt phạm vi.

    18/10/2026: nó lấy `user["tenant_id"]` (tổ chức NHÀ) trong khi job giờ thuộc tổ
    chức ĐANG LÀM VIỆC. Tra job trong phạm vi nhà thì không thấy, endpoint đóng kết
    nối trước `accept()` -> trình duyệt nhận 403 và màn hình kẹt ở "queued" dù
    trainer đã chạy. Phải dùng cùng nguồn với middleware HTTP (`_tenant_of_user`).
    """
    from app.tenant_context import current_tenant

    monkeypatch.setattr(tr, "get_user_from_token",
                        lambda token: {"id": "u-minh67", "username": "Minh67", "tenant_id": HOME})
    monkeypatch.setattr(tm, "_tenant_of_user", lambda user_id: WORKING)

    job = tr.TrainingJob(id="job-w", status="completed", config=tr.TrainingConfig(),
                         created_at="2026-10-18T00:00:00")
    seen_scopes = []

    async def _load(job_id):
        seen_scopes.append(current_tenant())
        return {"job": job, "tenant_id": WORKING} if current_tenant() == WORKING else None

    monkeypatch.setattr(tr, "_ensure_job_loaded", _load)
    monkeypatch.setattr("app.storage.metadata_db.list_training_metrics", lambda job_id: [])

    with client.websocket_connect("/training/ws/job-w?token=t") as ws:
        first = ws.receive_json()
    assert first["type"] == "status" and first["data"]["status"] == "completed"
    assert set(seen_scopes) == {WORKING}

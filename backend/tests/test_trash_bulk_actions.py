"""Thùng rác theo lô: khôi phục / xoá vĩnh viễn / dọn thùng.

Vì sao có tệp này
-----------------
16/08/2026 các `sync_*` một mẫu/một nhãn nhận `tenant_id` bắt buộc; `_bulk()`
vẫn gọi `fn(i)` trần. TypeError bị `except Exception` trong `_bulk` nuốt, và
route trả `{"success": true, "message": "Đã khôi phục 0 mẫu."}`. Không test nào
gọi tới `_bulk`, nên lỗi sống một tháng (phát hiện 15/09/2026 khi chạy thử vòng
đời trên stack thật). Ba điều được khoá ở đây:

1. `_bulk` truyền phạm vi tenant của request cho từng `sync_*`.
2. Một id hỏng không chặn các id còn lại (đúng hợp đồng ban đầu).
3. Lô không mục nào thành công thì route trả 400, không phải 200 "0 mẫu".
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.modules.identity._web_compat import get_current_user
import app.modules.dataset.catalog_sync as cs
import app.routers.classes as classes_router
import app.routers.dataset as dataset_router

client = TestClient(app)
ADMIN = {"id": "u-admin", "username": "qtv", "is_admin": True}


@pytest.fixture(autouse=True)
def _as_admin():
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    yield
    app.dependency_overrides.pop(get_current_user, None)


def test_bulk_passes_request_tenant_to_each_call(monkeypatch):
    seen = []

    def fake(uid, *, tenant_id):
        seen.append((uid, tenant_id))
        if uid == "hong":
            raise RuntimeError("no ho")
        return {"restored": uid}

    from app.modules.saas.tenant_context import tenant_scope

    with tenant_scope("truong-b"):
        result = cs._bulk(fake, ["a", "hong", "b"])

    assert seen == [("a", "truong-b"), ("hong", "truong-b"), ("b", "truong-b")]
    assert result["ok"] == ["a", "b"] and result["ok_count"] == 2
    assert result["failed"] == [{"id": "hong", "error": "no ho"}]


def test_bulk_refuses_without_tenant_scope():
    from app.modules.saas.tenant_context import TenantScopeError

    with pytest.raises(TenantScopeError):
        cs._bulk(lambda uid, *, tenant_id: None, ["a"])


def test_restore_samples_route_returns_400_when_every_item_failed(monkeypatch):
    monkeypatch.setattr(dataset_router, "bulk_restore_samples",
                        lambda uids: {"ok": [], "failed": [{"id": u, "error": "khong thay"} for u in uids],
                                      "ok_count": 0, "failed_count": len(uids)})
    r = client.post("/dataset/samples/trash/restore", json={"sample_uids": ["x1", "x2"]})
    assert r.status_code == 400
    assert "x1" in r.json()["detail"] and "khong thay" in r.json()["detail"]


def test_restore_samples_route_partial_success_is_200_with_failed_list(monkeypatch):
    monkeypatch.setattr(dataset_router, "bulk_restore_samples",
                        lambda uids: {"ok": ["x1"], "failed": [{"id": "x2", "error": "khong thay"}],
                                      "ok_count": 1, "failed_count": 1})
    r = client.post("/dataset/samples/trash/restore", json={"sample_uids": ["x1", "x2"]})
    assert r.status_code == 200
    body = r.json()
    assert body["success"] is True and body["ok_count"] == 1 and body["failed"][0]["id"] == "x2"


def test_purge_classes_route_returns_400_when_every_item_failed(monkeypatch):
    monkeypatch.setattr(classes_router, "bulk_purge_classes",
                        lambda uids: {"ok": [], "failed": [{"id": u, "error": "TypeError cu"} for u in uids],
                                      "ok_count": 0, "failed_count": len(uids)})
    r = client.post("/classes/trash/purge", json={"class_uids": ["c1"]})
    assert r.status_code == 400
    assert "c1" in r.json()["detail"]


def test_restore_classes_route_returns_400_when_every_item_failed(monkeypatch):
    monkeypatch.setattr(classes_router, "bulk_restore_classes",
                        lambda uids: {"ok": [], "failed": [{"id": u, "error": "TypeError cu"} for u in uids],
                                      "ok_count": 0, "failed_count": len(uids)})
    r = client.post("/classes/trash/restore", json={"class_uids": ["c1"]})
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Xoá vĩnh viễn một lớp: thứ tự kiểm-rồi-mới-gỡ, và phiên thu đi cùng lớp
# ---------------------------------------------------------------------------
#
# Chạy `sync_purge_class` thật với các seam I/O thay bằng hàm giả — thứ đang
# kiểm là THỨ TỰ và TẬP các thao tác, không phải Drive hay đĩa.

@pytest.fixture
def purge_seams(monkeypatch, tmp_path):
    calls: list = []

    class Meta:
        label_original = "lop-thu"
        language = "vn"
        dialect = "can-tho"
        tenant_id = "default"  # như ClassMetadata thật; dọn Drive cần tenant cho raw_videos/

        def hierarchy_path(self):
            return tmp_path / "features" / "lop-thu"

        def folder_name(self):
            return "class_lop-thu_abc"

    monkeypatch.setattr(cs, "_load_all_labels_unscoped", lambda: [])
    monkeypatch.setattr(cs, "load_labels", lambda scope: [])
    monkeypatch.setattr(cs, "db_get_deleted_class", lambda uid: {"class_uid": uid})
    monkeypatch.setattr(cs, "_build_class_meta_from_row", lambda row: Meta())
    monkeypatch.setattr(cs, "_remove_tree", lambda p: calls.append(("rm", str(p.name))))
    for name in ("db_delete_samples_by_class", "db_delete_raw_uploads_by_class",
                 "db_delete_capture_sessions_by_class", "db_delete_class"):
        monkeypatch.setattr(cs, name, (lambda n: (lambda uid: calls.append((n, uid))))(name))
    monkeypatch.setattr(cs, "_invalidate_tts_cache", lambda label: None)
    monkeypatch.setattr(cs, "_dispatch_gdrive_folder_delete", lambda paths, tenant_id=None: None)
    monkeypatch.setattr(cs, "_sync_drive_and_sheets_versioned_tables", lambda *a, **k: None)
    monkeypatch.setattr(cs, "ensure_tables", lambda: None)
    return calls


def test_purge_deletes_capture_sessions_before_the_class(purge_seams, monkeypatch):
    monkeypatch.setattr(cs, "db_count_training_jobs_using_class", lambda uid: 0)
    out = cs.sync_purge_class("abc", tenant_id="default")
    assert out["purged"] is True
    order = [c[0] for c in purge_seams]
    # samples trước phiên thu (samples trỏ tới capture_sessions), phiên thu trước lớp.
    assert order.index("db_delete_samples_by_class") < order.index("db_delete_capture_sessions_by_class")
    assert order.index("db_delete_capture_sessions_by_class") < order.index("db_delete_class")


def test_purge_refuses_class_used_by_training_jobs_before_touching_files(purge_seams, monkeypatch):
    monkeypatch.setattr(cs, "db_count_training_jobs_using_class", lambda uid: 2)
    with pytest.raises(cs.CatalogSyncError) as exc:
        cs.sync_purge_class("abc", tenant_id="default")
    assert exc.value.status_code == 409
    assert "2 lượt huấn luyện" in str(exc.value)
    # Không một tệp hay dòng nào bị gỡ: lớp vẫn nguyên trong thùng rác.
    assert purge_seams == []

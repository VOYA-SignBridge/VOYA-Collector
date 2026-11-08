"""`GET /samples/{id}/data` phải qua CÙNG cổng kiểm duyệt với `GET /samples`.

Chia sẻ một phiên thu ra tenant là ĐĂNG KÝ dùng chung, không phải công bố:
chưa được admin duyệt thì chỉ chủ dùng được. Danh sách đã ẩn mẫu chưa duyệt của
người khác, nhưng trước 16/10/2026 đường tải theo id thì không.

Không cần CSDL: mọi nguồn dữ liệu của endpoint được thay bằng bản giả, để bài
này chỉ đo đúng một thứ — thứ tự và kết quả của các cổng.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.routers import dataset

TENANT = "truong-thu-nghiem"
OWNER, OTHER = "chu-mau", "nguoi-khac"


@pytest.fixture
def mau(tmp_path, monkeypatch):
    tep = tmp_path / "mau.npz"
    tep.write_bytes(b"npz")
    state = {"review_status": "pending", "moderator": False}

    def rows(_tenant):
        return [{"sample_uid": "s1", "auth_user_id": OWNER, "file_path": str(tep),
                 "review_status": state["review_status"]}]

    monkeypatch.setattr(dataset, "list_samples_v2", rows)
    monkeypatch.setattr(dataset, "require_tenant", lambda: TENANT)
    # Phiên đã chia sẻ ra tenant: cổng phạm vi cho qua, chỉ còn cổng kiểm duyệt.
    monkeypatch.setattr("app.storage.metadata_db.get_readable_sample_uids", lambda uids, _u, _t, **_k: set(uids))
    calls = []

    def can_moderate(user, tenant_id=None):
        calls.append(tenant_id)
        return state["moderator"]

    monkeypatch.setattr("app.modules.admin.moderation_admin.can_moderate", can_moderate)
    return state, calls


def test_mau_CHUA_DUYET_cua_nguoi_khac_tra_404(mau):
    with pytest.raises(HTTPException) as exc:
        dataset.get_sample_data("s1", current_user={"id": OTHER})
    assert exc.value.status_code == 404


def test_chu_mau_tai_duoc_ngay_ca_khi_chua_duyet(mau):
    assert dataset.get_sample_data("s1", current_user={"id": OWNER}).status_code == 200


def test_nguoi_duyet_cua_CHINH_tenant_tai_duoc_de_duyet(mau):
    state, calls = mau
    state["moderator"] = True
    assert dataset.get_sample_data("s1", current_user={"id": OTHER}).status_code == 200
    assert calls == [TENANT]  # Hỏi quyền duyệt Ở tenant này, không phải "ở đâu đó".


def test_da_duyet_thi_thanh_vien_tai_duoc(mau):
    state, _ = mau
    state["review_status"] = "approved"
    assert dataset.get_sample_data("s1", current_user={"id": OTHER}).status_code == 200


@pytest.mark.parametrize("status", ["rejected", "", None])
def test_bi_tu_choi_hoac_khong_ro_trang_thai_van_bi_chan(mau, status):
    state, _ = mau
    state["review_status"] = status
    with pytest.raises(HTTPException) as exc:
        dataset.get_sample_data("s1", current_user={"id": OTHER})
    assert exc.value.status_code == 404

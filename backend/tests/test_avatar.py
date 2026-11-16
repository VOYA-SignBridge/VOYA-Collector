"""Ảnh đại diện chọn từ bộ mẫu, và tên đăng nhập KHÔNG sửa được.

`PATCH /auth/me` từng là đường đổi tên đăng nhập. Tên đăng nhập là danh tính (được
chép vào mẫu, video và tệp nguồn của dữ liệu đã đóng góp), nên người dùng không
còn đường nào đổi nó; endpoint này chỉ còn chọn ảnh đại diện.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from app.modules.identity import _web_compat as auth
from app.routers import auth as auth_router


@pytest.fixture
def account():
    from conftest import purge_registered_account

    name = f"av{uuid.uuid4().hex[:8]}"
    user = auth.create_user(username=name, email=f"{name}@example.test",
                            password="correct horse battery")
    yield {"id": str(user["id"]), "username": name}
    purge_registered_account(name)


def _avatar(account) -> str | None:
    return auth._fetch_user_by_id(account["id"])["avatar_key"]


def _patch(account, key):
    user = auth._fetch_user_by_id(account["id"])
    return auth_router.update_me(auth_router.UpdateProfileRequest(avatar_key=key), user)


class TestChonAnhDaiDien:
    def test_chua_chon_thi_la_none(self, account):
        assert _avatar(account) is None

    def test_chon_roi_doc_lai_o_ho_so(self, account):
        assert _patch(account, "bluehand") == {"avatar_key": "bluehand"}
        assert _avatar(account) == "bluehand"
        # Cùng hồ sơ mà `/me` và đăng nhập trả ra.
        assert auth_router._public_user(auth._fetch_user_by_id(account["id"]))["avatar_key"] == "bluehand"

    def test_bo_chon_thi_ve_none(self, account):
        _patch(account, "bluehand")
        _patch(account, None)
        assert _avatar(account) is None

    @pytest.mark.parametrize("bad", ["", "Hoa", "a b", "../x", "x" * 33, "<script>"])
    def test_khoa_sai_dang_bi_tu_choi_va_khong_duoc_luu(self, account, bad):
        with pytest.raises(HTTPException) as exc:
            _patch(account, bad)
        assert exc.value.status_code == 422
        assert _avatar(account) is None


class TestTenDangNhapKhongSuaDuoc:
    def test_yeu_cau_khong_con_truong_username(self):
        model = auth_router.UpdateProfileRequest
        fields = getattr(model, "model_fields", None) or model.__fields__  # Pydantic v2 | v1
        assert "username" not in fields

    def test_gui_kem_username_cung_khong_doi_ten(self, account):
        """Trường lạ bị bỏ qua chứ không được âm thầm áp dụng."""
        payload = auth_router.UpdateProfileRequest(avatar_key="bluehand", username="nguoi-khac")
        user = auth._fetch_user_by_id(account["id"])
        auth_router.update_me(payload, user)
        assert auth._fetch_user_by_id(account["id"])["username"] == account["username"]

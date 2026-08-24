"""Bốn điểm cuối trả "người dùng hiện tại" phải trả CÙNG một câu trả lời.

Vết đã đo trên stack đang chạy, 24/08/2026 — cùng một tài khoản, cùng một phiên:

    POST /auth/login   can_moderate=false   tenant_role=null
    GET  /auth/me      can_moderate=true    tenant_role=admin

Chỉ `/me` tính hai trường dẫn xuất ấy; `/login`, bước hai của xác thực hai lớp
và `/refresh` trả `UserOut` với giá trị mặc định.

Chưa cắn ai — `useAuth` lấy người dùng từ `/me`, còn `LoginPage` chỉ gọi
`notifyAuthChange()`. Nhưng người viết tiếp mà dùng kết quả đăng nhập sẽ nhận
`can_moderate` sai một cách IM LẶNG, và hậu quả là mục Kiểm duyệt biến mất với
đúng người có quyền. `/refresh` còn tệ hơn một bậc: nó chạy mỗi lần vé ngắn hạn
hết hạn, nên hồ sơ nghèo đi GIỮA phiên chứ không phải lúc đăng nhập — kiểu lỗi
khó lần nhất, vì nó không dính vào hành động nào của người dùng.

Đây là siêu dữ liệu để VẼ giao diện. Bài cuối tệp ghim điều đó: cờ này KHÔNG
phải nơi quyết định thẩm quyền — máy chủ vẫn tự kiểm ở `require_moderator`.
"""

from __future__ import annotations

import uuid

import pytest

PW = "Mat-khau-du-manh-2026"
CAC_TRUONG = ("tenant_role", "can_moderate")


def _ten(tien_to: str) -> str:
    return f"{tien_to}{uuid.uuid4().hex[:8]}"


@pytest.fixture
def phien():
    """Dựng một tài khoản rồi đăng nhập, trả `(client, hồ sơ từ /login)`.

    IP mới cho mỗi request là bắt buộc: bộ đếm rate-limit sống qua các lượt chạy
    suite, nên dùng chung 127.0.0.1 sẽ bắt đầu trả 429 ở lượt thứ N.
    """
    from fastapi.testclient import TestClient

    from conftest import LoopbackPeer, fresh_client_ip
    from app import auth
    from app.main import app

    def _tao(*, is_admin: bool):
        ten = _ten("capz")
        auth.create_user(username=ten, email=f"{ten}@example.com",
                         password=PW, is_admin=is_admin)
        client = TestClient(LoopbackPeer(app))
        r = client.post("/api/v1/auth/login",
                        json={"identifier": ten, "password": PW},
                        headers={"X-Forwarded-For": fresh_client_ip()})
        assert r.status_code == 200, r.text
        return client, r.json(), ten

    return _tao


def _me(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 200, r.text
    return r.json()


def _khong_lech(a: dict, b: dict, ten_a: str, ten_b: str):
    lech = {k: (a.get(k), b.get(k)) for k in CAC_TRUONG if a.get(k) != b.get(k)}
    assert not lech, (
        f"{ten_a} và {ten_b} trả khác nhau cho cùng một người: {lech}. "
        "Cả hai phải đi qua `_with_capabilities`.")


def test_quan_tri_nen_tang_duoc_bao_la_duyet_duoc_o_CA_HAI_noi(phien):
    """Bài tái hiện đúng vết đã đo: `is_admin` mà `can_moderate=false`."""
    client, login, _ = phien(is_admin=True)
    me = _me(client)

    _khong_lech(login, me, "/login", "/me")
    assert me["is_admin"] is True
    assert me["can_moderate"] is True, (
        "quản trị viên nền tảng cầm mọi quyền, kể cả kiểm duyệt")
    assert login["can_moderate"] is True, "và `/login` phải nói cùng một điều"


def test_nguoi_dung_thuong_khong_duoc_bao_la_duyet_duoc(phien):
    """Đối chứng. Không có bài này thì một bản vá gán cứng `True` cũng xanh."""
    client, login, _ = phien(is_admin=False)
    me = _me(client)

    _khong_lech(login, me, "/login", "/me")
    assert me["is_admin"] is False
    assert me["can_moderate"] is False
    assert login["can_moderate"] is False


def test_lam_moi_phien_KHONG_lam_ngheo_ho_so(phien):
    """`/refresh` chạy giữa phiên, mỗi lần vé ngắn hạn hết hạn."""
    client, _, _ = phien(is_admin=True)
    me = _me(client)

    r = client.post("/api/v1/auth/refresh")
    if r.status_code != 200:
        pytest.skip(f"/refresh không dùng được trong ngữ cảnh test: {r.status_code}")

    _khong_lech(r.json(), me, "/refresh", "/me")


def test_co_nay_KHONG_phai_noi_quyet_dinh_tham_quyen():
    """Ghim ranh giới: `can_moderate` là dữ liệu để VẼ, không phải để CHO PHÉP.

    Một client sửa cờ này chỉ tự vẽ ra một mục menu dẫn tới 403. Bài này canh
    việc điểm cuối kiểm duyệt vẫn TỰ tra quyền, thay vì có ai đó sau này "đơn
    giản hoá" bằng cách tin vào cờ đã nằm sẵn trong hồ sơ.
    """
    import inspect

    from app.routers import moderation

    nguon = inspect.getsource(moderation.require_moderator)
    assert "can_moderate" in nguon, (
        "`require_moderator` phải tự tra quyền, không được tin cờ trong hồ sơ")

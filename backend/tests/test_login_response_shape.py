"""Hình dạng phản hồi của `/auth/login` — kiểm ở tầng ENDPOINT, không phải hàm.

`test_session_lifecycle.py::TestKhongRoBamMatKhau` đã kiểm `_public_user` lọc
đúng. Nhưng hàm đó chỉ có tác dụng nếu endpoint THẬT SỰ gọi nó, và chính chỗ nối
ấy mới là chỗ đã hỏng: bỏ `response_model=UserOut` để trả được hai hình dạng đã
vô tình gỡ luôn bộ lọc duy nhất ngăn `password_hash` đi ra.

Vì thế bộ này gửi một yêu cầu HTTP thật và đọc thân phản hồi — thứ mà một test
gọi thẳng hàm không bao giờ nhìn thấy.
"""

from __future__ import annotations

import uuid

import pytest

#: Cột KHÔNG được xuất hiện trong bất kỳ phản hồi nào. Danh sách chứ không phải
#: một tên: `sessions_invalid_before` không bí mật bằng băm mật khẩu, nhưng nó là
#: chi tiết nội bộ của cơ chế thu hồi phiên và không việc gì phải ra ngoài.
CAM = ("password_hash", "sessions_invalid_before")


@pytest.fixture
def client():
    """`TestClient` giữ cookie giữa các lượt gọi, và mỗi lượt mang một IP mới.

    IP mới cho từng yêu cầu là bắt buộc: giới hạn tốc độ đăng nhập đếm theo IP,
    và nếu mọi test dùng chung một địa chỉ thì test thứ N sẽ bị khoá vì test thứ
    N-1 — một kiểu đỏ giả phụ thuộc THỨ TỰ chạy.
    """
    from fastapi.testclient import TestClient

    from app.main import app
    from conftest import LoopbackPeer, fresh_client_ip

    inner = TestClient(LoopbackPeer(app))

    class _IpMoiMoiLuot:
        def _goi(self, ham, url, **kwargs):
            headers = {**kwargs.pop("headers", {}),
                       "X-Forwarded-For": fresh_client_ip()}
            return ham(url, headers=headers, **kwargs)

        def post(self, url, **kwargs):
            return self._goi(inner.post, url, **kwargs)

        def get(self, url, **kwargs):
            return self._goi(inner.get, url, **kwargs)

    return _IpMoiMoiLuot()


@pytest.fixture
def tai_khoan():
    from app.auth import create_user
    from conftest import purge_registered_account

    ten = f"lg{uuid.uuid4().hex[:8]}"
    create_user(username=ten, email=f"{ten}@example.test",
                password="correct horse battery")
    yield {"username": ten, "email": f"{ten}@example.test",
           "password": "correct horse battery"}
    purge_registered_account(ten)


def test_dang_nhap_thanh_cong_KHONG_tra_bam_mat_khau(client, tai_khoan):
    res = client.post("/api/v1/auth/login", json={
        "identifier": tai_khoan["email"], "password": tai_khoan["password"],
    })
    assert res.status_code == 200, res.text

    than = res.json()
    for cot in CAM:
        assert cot not in than, f"`{cot}` rò ra trong phản hồi đăng nhập"
    # Và vẫn trả đủ thứ giao diện cần — nếu không thì bộ lọc quá tay.
    assert than["username"] == tai_khoan["username"]
    assert than["email"] == tai_khoan["email"]
    assert than["id"]


def test_auth_me_cung_khong_tra_bam_mat_khau(client, tai_khoan):
    """`/auth/me` CÓ `response_model`, nên nó vốn đã an toàn. Kiểm vì hai đường
    này trả cùng một kiểu dữ liệu, và một ngày nào đó ai đó sẽ đồng bộ chúng
    theo hướng sai."""
    client.post("/api/v1/auth/login", json={
        "identifier": tai_khoan["email"], "password": tai_khoan["password"],
    })
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 200, res.text
    for cot in CAM:
        assert cot not in res.json()


#: Đường xác thực CỐ Ý không khai `response_model`, kèm lý do.
#:
#: Không khai `response_model` là trạng thái RỦI RO, không phải trạng thái mặc
#: định: nó gỡ bộ lọc duy nhất chặn cột nội bộ đi ra. Danh sách này buộc mỗi
#: ngoại lệ phải được viết ra, đúng cách `test_tenant_isolation` canh
#: `system_scope`.
KHONG_CO_RESPONSE_MODEL = {
    # Hai hình dạng trả về: hồ sơ người dùng, hoặc vé bước hai. Đường thành công
    # đi qua `_public_user`.
    "/auth/login": "hai hình dạng — dùng _public_user",
    "/auth/login/2fa": "hai hình dạng — dùng _public_user",
    # Trả về số đếm và trạng thái, không chạm hồ sơ người dùng.
    "/auth/my-notice": "không trả hồ sơ",
    "/auth/my-notice/ack": "không trả hồ sơ",
    "/auth/me (PATCH)": "trả kết quả đổi tên, không phải hồ sơ đầy đủ",
}


def test_moi_duong_KHONG_khai_response_model_deu_phai_co_ly_do():
    """Cổng canh chung, và nó canh *đường mới chưa ai viết test*.

    Đây mới là thứ đáng ghim: một endpoint tương lai bỏ `response_model` cho
    tiện sẽ đỏ ở đây, chứ không âm thầm rò một cột nào đó ra ngoài.
    """
    from app.routers.auth import router

    thieu = []
    for route in router.routes:
        if getattr(route, "response_model", None) is not None:
            continue
        # `route.path` ĐÃ mang tiền tố `/auth` của router; ghép thêm một lần
        # nữa cho ra `/auth/auth/login` và test tự báo oan chính nó.
        khoa = route.path
        if "PATCH" in getattr(route, "methods", set()) and route.path == "/auth/me":
            khoa = "/auth/me (PATCH)"
        if khoa not in KHONG_CO_RESPONSE_MODEL:
            thieu.append(f"{sorted(route.methods)} {khoa}")

    assert not thieu, (
        f"đường xác thực không khai `response_model` mà chưa có lý do: {thieu}. "
        f"Khai `response_model`, hoặc thêm vào KHONG_CO_RESPONSE_MODEL kèm lý do "
        f"và bảo đảm nó KHÔNG trả thẳng dict hồ sơ người dùng."
    )

"""Bộ test không bao giờ được gửi một lá thư thật.

Sự cố 25/08/2026
-----------------
`scripts/run_tests.sh` truyền nguyên `.env` sản xuất vào container test, nên
container nhận đúng thông tin đăng nhập Gmail thật. Mọi bài chạm đường mời
thành viên hoặc đường gửi mã xác minh đều gửi thư THẬT tới địa chỉ bịa.

Không lượt chạy nào đỏ vì chuyện đó, và lý do là điều đáng nhớ nhất ở đây:
**Gmail nhận thư ở tầng SMTP** — nó chưa biết địa chỉ đích ở tên miền khác có
tồn tại hay không — nên `email_service._send` không thấy ngoại lệ nào và lượt
chạy vẫn xanh. Thư không gửi được quay về SAU ĐÓ, bất đồng bộ, dưới dạng bounce
vào hộp thư NGƯỜI GỬI. Đo được: hơn ba nghìn thư trước khi ai đó nhìn vào hộp
thư ấy.

Bài học chung: "không có ngoại lệ nào" KHÔNG đồng nghĩa "đã gửi tới nơi". Một
giao thức nhận-rồi-chuyển-tiếp không thể báo lỗi đồng bộ cho một địa chỉ nó
chưa hỏi tới.

Tệp này canh lớp chặn ấy. Nó cố ý dùng ĐÚNG đường mã mà sản xuất dùng
(`email_service.send_*`), chứ không kiểm một biến cấu hình: kiểm cấu hình chỉ
chứng minh cấu hình đúng, không chứng minh không có gói tin nào ra ngoài.
"""

from __future__ import annotations

import pytest

from app import email_service as es


def test_lop_chan_thay_hai_lop_smtp(_ensure_no_real_smtp=None):
    """Cả `SMTP` lẫn `SMTP_SSL` phải bị thay — `_send` chọn nhánh theo
    `smtp_use_tls`, nên chặn một nhánh là để hở nhánh kia."""
    import smtplib

    assert smtplib.SMTP.__name__ == "_SMTPGia", "SMTP chua bi chan"
    assert smtplib.SMTP_SSL.__name__ == "_SMTPGia", "SMTP_SSL chua bi chan"


@pytest.mark.parametrize("goi", [
    lambda: es.send_verification_code_email("khong-ai@example.invalid", "424242",
                                            purpose="verify_email"),
    lambda: es.send_invitation_email("khong-ai@example.invalid", tenant_name="T",
                                     role="editor", accept_url="https://x/y",
                                     expires_hours=48),
    lambda: es.send_password_reset_email("khong-ai@example.invalid", "ai do",
                                         "https://x/y"),
])
def test_moi_duong_gui_deu_bi_chan(goi, monkeypatch):
    """Gọi thật các hàm gửi. Không lá nào được rời máy.

    `smtp_host` được đặt tới một giá trị TRUTHY để `_send` đi đúng nhánh gửi
    thật — nếu để rỗng thì bài này chỉ chứng minh nhánh "chưa cấu hình" hoạt
    động, mà đó không phải nhánh gây ra sự cố.
    """
    from conftest import THU_DA_CHAN

    monkeypatch.setattr(es.settings, "smtp_host", "smtp.test.invalid")
    truoc = len(THU_DA_CHAN)
    goi()
    assert len(THU_DA_CHAN) == truoc + 1, (
        "duong gui nay khong di qua lop chan — hoac no mo socket rieng, hoac "
        "no da bi bo qua"
    )
    assert THU_DA_CHAN[-1]["to"] == "khong-ai@example.invalid"


def test_cau_hinh_smtp_cua_lan_chay_khong_tro_vao_may_chu_that():
    """Lớp chặn thứ nhất. `.invalid` là TLD dành riêng (RFC 2606) nên không bao
    giờ phân giải được.

    Bỏ qua khi chạy ngoài `scripts/run_tests.sh` — lớp thứ hai (conftest) mới là
    lớp bắt buộc, và nó đã được ba bài trên chứng minh.
    """
    host = (es.settings.smtp_host or "").lower()
    if not host or not host.endswith(".invalid"):
        pytest.skip("khong chay qua scripts/run_tests.sh — lop hai da phu")
    assert "gmail" not in host


def test_email_service_khong_duoc_bind_thang_lop_SMTP():
    """Lớp chặn thay THUỘC TÍNH của module `smtplib`, nên nó chỉ có tác dụng khi
    `email_service` tra thuộc tính ấy LÚC GỌI.

    Đổi `import smtplib` thành `from smtplib import SMTP` sẽ giữ lại lớp gốc ở
    thời điểm import — trước khi fixture kịp chạy — và mọi lá thư lại đi ra
    thật, im lặng y như trước 25/08/2026. Không phép kiểm nào khác bắt được:
    suite vẫn xanh, chỉ có hộp thư là biết.

    Đây là lý do bài này kiểm NGUỒN chứ không kiểm hành vi — hành vi lúc đó vẫn
    "đúng" theo mọi nghĩa quan sát được từ trong tiến trình.
    """
    import inspect

    from app import email_service

    nguon = inspect.getsource(email_service)
    assert "from smtplib import" not in nguon, (
        "email_service dang bind thang lop SMTP — lop chan trong conftest se bi "
        "lach qua. Dung `import smtplib` roi goi `smtplib.SMTP(...)`."
    )

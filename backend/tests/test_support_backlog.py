"""Tồn đọng kênh hỗ trợ: phép đếm, ngưỡng, và thư gửi cho người trực.

Điều đáng kiểm nhất ở đây không phải "thư có gửi không" mà là **phép đếm có
đếm đúng thứ cần đếm không**. Một cảnh báo tồn đọng đếm sai theo hướng thiếu
thì im lặng đúng lúc cần kêu, và không có gì trên màn hình phân biệt được nó
với một kênh hỗ trợ đang chạy tốt.

Ba cái bẫy được ghim lại thành test riêng:

* lời nhắn của trợ lý không được tính là "đã trả lời";
* phiếu đã đóng không còn là phiếu đang chờ;
* thư phải mang CON SỐ, không chỉ mang lời cảnh báo.
"""

from __future__ import annotations

import uuid

import pytest

from app import support, support_backlog
from app.storage.metadata_db import _execute, _fetch_all
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope, tenant_scope


def _make_account(prefix: str) -> dict:
    from app.auth import create_user

    name = f"{prefix}{uuid.uuid4().hex[:8]}"
    user = create_user(username=name, email=f"{name}@example.test",
                       password="correct horse battery")
    return {"id": str(user["id"]), "username": name}


def _purge(account: dict) -> None:
    from conftest import purge_registered_account

    with system_scope("test cleanup: ton dong ho tro"):
        _execute("DELETE FROM support_messages WHERE ticket_id IN "
                 "(SELECT ticket_id FROM support_tickets WHERE user_id = %s)",
                 (account["id"],))
        _execute("DELETE FROM support_tickets WHERE user_id = %s", (account["id"],))
    purge_registered_account(account["username"])


@pytest.fixture
def account():
    acc = _make_account("blg")
    yield acc
    _purge(acc)


@pytest.fixture
def scope():
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


def _age_last_message(ticket_id: str, hours: float) -> None:
    """Đẩy lời nhắn cuối lùi về quá khứ.

    Không có cách nào khác để kiểm ngưỡng 5 giờ trong một bộ test chạy vài
    giây. Chỉ dịch `created_at` chứ không đụng nội dung — thứ đang được kiểm là
    phép trừ thời gian, không phải phép ghi.

    Phải nhắm đúng lời nhắn CUỐI CÙNG CỦA NGƯỜI DÙNG, không phải lời nhắn cuối
    cùng nói chung: sau `create_ticket` thì người nói sau cùng là trợ lý, và
    lùi giờ của trợ lý không đổi được điều gì — phép đo chỉ nhìn lời của con
    người. Bản đầu của hàm này nhắm sai và test đỏ với `oldest_hours = 0.0`.
    """
    with system_scope("test: lui thoi gian loi nhan"):
        _execute(
            "UPDATE support_messages SET created_at = NOW() - (%s || ' hours')::interval "
            "WHERE message_id = ("
            "  SELECT message_id FROM support_messages "
            "   WHERE ticket_id = %s AND author_kind = 'user' "
            "   ORDER BY created_at DESC LIMIT 1)",
            (str(hours), str(ticket_id)))


def _stat_now():
    """Số liệu tồn đọng của tổ chức mặc định, đo lại ngay bây giờ.

    Đo theo TENANT chứ không theo phiếu, vì đó là đơn vị mà cảnh báo gửi đi:
    một thư cho một tổ chức, không phải một thư cho một phiếu. Các test dưới
    đây vì thế so sánh TRƯỚC/SAU thay vì so với một hằng số — bộ test dùng
    chung tổ chức mặc định nên con số tuyệt đối phụ thuộc thứ tự chạy.
    """
    with system_scope("test: doc so lieu ton dong"):
        for row in support_backlog.measure():
            if row["tenant_id"] == str(DEFAULT_TENANT_ID):
                return row
    return None


def _messages(ticket_id: str):
    with system_scope("test: doc loi nhan"):
        return _fetch_all(
            "SELECT author_kind FROM support_messages WHERE ticket_id = %s "
            "ORDER BY created_at", (str(ticket_id),))


# ===========================================================================
# Phép đếm
# ===========================================================================
class TestPhepDem:
    def test_tro_ly_tra_loi_KHONG_lam_phieu_het_cho(self, account, scope):
        """Cái bẫy chính.

        Trợ lý trả lời NGAY sau mỗi lời nhắn của người dùng. Nếu phép đếm coi
        lời của nó là "đã có người trả lời" thì không phiếu nào đang chờ bao
        giờ — cảnh báo im lặng vĩnh viễn và trông y hệt một kênh hỗ trợ rảnh.
        """
        t = support.create_ticket(
            account["id"], "Mẫu tôi tải lên không thấy đâu",
            "Tôi tải lên xong mà không tìm ra mẫu.", "data", account["username"])

        kinds = [m["author_kind"] for m in _messages(t["ticket_id"])]
        assert "bot" in kinds, \
            "phải có lời của trợ lý thì test này mới kiểm được điều nó định kiểm"

        stat = _stat_now()
        assert stat is not None and stat["waiting"] >= 1

    def test_nguoi_truc_tra_loi_thi_phieu_do_het_cho(self, account, scope):
        t = support.create_ticket(
            account["id"], "Huấn luyện báo lỗi giữa chừng",
            "Chạy tới epoch 3 thì dừng.", "bug", account["username"])
        truc = _make_account("trc")
        try:
            truoc = _stat_now()["waiting"]
            support.reply(t["ticket_id"], truc["id"], "Tôi đang xem giúp bạn.",
                          author_label=truc["username"], is_staff=True)
            sau = _stat_now()
            assert (sau is None and truoc >= 1) or sau["waiting"] == truoc - 1
        finally:
            _purge(truc)

    def test_phieu_da_dong_khong_con_dang_cho(self, account, scope):
        t = support.create_ticket(
            account["id"], "Tôi muốn đổi tên đăng nhập",
            "Tên hiện tại bị sai chính tả.", "account", account["username"])
        truoc = _stat_now()["waiting"]

        support.set_status(t["ticket_id"], "closed", account["id"])

        sau = _stat_now()
        assert (sau is None and truoc >= 1) or sau["waiting"] == truoc - 1

    def test_dem_loi_nhan_chua_tra_chu_khong_phai_so_phieu(self, account, scope):
        """Một người nhắn năm câu trong một phiếu là năm câu đang treo.

        Hai con số này KHÁC nhau và ngưỡng dùng cả hai: 10 lời nhắn chưa trả
        có thể chỉ nằm trong đúng một phiếu.
        """
        t = support.create_ticket(
            account["id"], "Tôi cần gặp người hỗ trợ",
            "Việc này gấp, mong được giúp.", "other", account["username"])
        for i in range(4):
            support.reply(t["ticket_id"], account["id"],
                          f"Nhắc lại lần {i + 1}, tôi vẫn đang chờ.",
                          author_label=account["username"], is_staff=False)

        nguoi_dung_noi = [m for m in _messages(t["ticket_id"]) if m["author_kind"] == "user"]
        assert len(nguoi_dung_noi) == 5, "1 câu mở phiếu + 4 câu nhắc"

        stat = _stat_now()
        assert stat["unanswered_messages"] >= 5


# ===========================================================================
# Ngưỡng
# ===========================================================================
class TestNguong:
    def test_phieu_vua_mo_khong_phai_ton_dong(self, account, scope):
        support.create_ticket(
            account["id"], "Một câu hỏi nhỏ về hệ thống",
            "Tôi muốn hỏi về cách dùng.", "other", account["username"])
        stat = {"oldest_hours": 0.01, "unanswered_messages": 1}
        assert not support_backlog.breaches(stat), \
            "một phiếu vừa mở vài giây không phải là tồn đọng"

    def test_qua_5_gio_thi_vuot_nguong(self, account, scope):
        t = support.create_ticket(
            account["id"], "Phiếu này sẽ bị bỏ quên rất lâu",
            "Không ai trả lời tôi cả.", "other", account["username"])

        _age_last_message(t["ticket_id"], support_backlog.THRESHOLD_HOURS + 1)

        stat = _stat_now()
        assert stat["oldest_hours"] >= support_backlog.THRESHOLD_HOURS
        assert support_backlog.breaches(stat)

    def test_qua_10_loi_nhan_thi_vuot_nguong_du_moi_gui(self, account, scope):
        """Ngưỡng thứ hai bắt kiểu hỏng khác: nhiều câu dồn trong thời gian ngắn.

        Chỉ có ngưỡng giờ thì một đợt mười người cùng hỏi trong nửa tiếng vẫn
        lọt qua, vì chưa câu nào chờ đủ lâu.
        """
        t = support.create_ticket(
            account["id"], "Phiếu có rất nhiều lời nhắn liên tiếp",
            "Câu hỏi đầu tiên của tôi.", "other", account["username"])
        for i in range(support_backlog.THRESHOLD_MESSAGES):
            support.reply(t["ticket_id"], account["id"],
                          f"Câu hỏi tiếp theo số {i}.",
                          author_label=account["username"], is_staff=False)

        stat = _stat_now()
        assert stat["unanswered_messages"] >= support_backlog.THRESHOLD_MESSAGES
        assert support_backlog.breaches(stat)

    def test_hai_nguong_doc_lap_nhau(self):
        """Hoặc-là, không phải và-là. Một phiếu bị bỏ quên cả ngày vẫn phải kêu
        dù nó là phiếu duy nhất."""
        assert support_backlog.breaches(
            {"oldest_hours": 99.0, "unanswered_messages": 1})
        assert support_backlog.breaches(
            {"oldest_hours": 0.1, "unanswered_messages": 50})
        assert not support_backlog.breaches(
            {"oldest_hours": 0.1, "unanswered_messages": 1})


# ===========================================================================
# Thư
# ===========================================================================
class TestThu:
    def test_thu_ton_dong_mang_con_so_chu_khong_chi_mang_loi_canh_bao(self):
        """Thư phải trả lời được "có nên bỏ dở việc đang làm không".

        Câu "kênh hỗ trợ đang có tồn đọng" mà không kèm số thì người đọc vẫn
        phải mở hệ thống ra mới biết — tức là thư chưa làm xong việc của nó.
        """
        from app import email_service

        gui = {}

        def bat(to_email, subject, body, *, loggable):
            gui.update(to=to_email, subject=subject, body=body, loggable=loggable)

        goc = email_service._send
        email_service._send = bat
        try:
            email_service.send_support_backlog_email(
                "truc@example.com", waiting=7, oldest_hours=9.5,
                unanswered_messages=12, threshold_hours=5, threshold_messages=10,
                link="https://voya.example/admin/support")
        finally:
            email_service._send = goc

        assert "7" in gui["subject"], "số phiếu chờ phải ở NGAY dòng tiêu đề"
        assert "9.5" in gui["body"]
        assert "12" in gui["body"]
        assert "https://voya.example/admin/support" in gui["body"]

    def test_thu_ton_dong_noi_ro_nguong_nao_bi_vuot(self):
        """Hai ngưỡng nghĩa là hai câu chuyện khác nhau — "một phiếu bị bỏ
        quên" và "đang có một đợt hỏi dồn". Người đọc phải biết là cái nào."""
        from app import email_service

        gui = {}
        goc = email_service._send
        email_service._send = lambda to, s, b, *, loggable: gui.update(body=b)
        try:
            email_service.send_support_backlog_email(
                "truc@example.com", waiting=1, oldest_hours=9.0,
                unanswered_messages=2, threshold_hours=5, threshold_messages=10,
                link="https://voya.example/admin/support")
        finally:
            email_service._send = goc

        assert "9.0 giờ" in gui["body"]
        assert "2 lời nhắn chưa được trả lời" not in gui["body"], \
            "chỉ nêu ngưỡng ĐÃ vượt, nêu cả cái chưa vượt là làm loãng lý do"

    def test_thu_phieu_moi_KHONG_chep_noi_dung_nguoi_dung_viet(self):
        """Nội dung trao đổi là dữ liệu của tenant.

        Thư đi qua SMTP của bên thứ ba và `loggable=True` cho phép nó rơi vào
        nhật ký khi chưa cấu hình SMTP. Tiêu đề và tên người gửi là mức tối
        thiểu để người trực quyết định có mở hay không; phần người dùng gõ ra
        thì phải đọc trong hệ thống, nơi có kiểm soát truy cập.
        """
        from app import email_service

        gui = {}
        goc = email_service._send
        email_service._send = lambda to, s, b, *, loggable: gui.update(subject=s, body=b)
        try:
            email_service.send_support_ticket_email(
                "truc@example.com", ticket_id="abc-123",
                subject="Không tải được mẫu lên",
                category="data", requester="nguoidung1",
                link="https://voya.example/admin/support/abc-123")
        finally:
            email_service._send = goc

        assert "Không tải được mẫu lên" in gui["subject"], \
            "tiêu đề phiếu phải ở dòng tiêu đề thư để lọc được hộp thư"
        assert "nguoidung1" in gui["body"]
        assert "abc-123" in gui["body"]


# ===========================================================================
# Ai nhận thư
# ===========================================================================
class TestDiaChiNhanThu:
    def test_bo_qua_dia_chi_chua_xac_minh(self, scope):
        """Một địa chỉ chưa ai chứng minh là có thật vẫn có thể là của người khác.

        Thư này mang tiêu đề phiếu và tên người gửi — đủ để lộ ai đang dùng hệ
        thống và họ đang gặp chuyện gì.
        """
        acc = _make_account("mail")
        try:
            with system_scope("test: dat trang thai xac minh"):
                _execute("UPDATE users SET email_verified_at = NULL WHERE id = %s",
                         (acc["id"],))
                assert support._staff_emails([acc["id"]]) == []

                _execute("UPDATE users SET email_verified_at = NOW() WHERE id = %s",
                         (acc["id"],))
                assert len(support._staff_emails([acc["id"]])) == 1
        finally:
            _purge(acc)

    def test_danh_sach_rong_khong_lam_no(self):
        assert support._staff_emails([]) == []

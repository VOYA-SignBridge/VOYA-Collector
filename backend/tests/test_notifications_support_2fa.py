"""Ba tính năng v6: thông báo, kênh hỗ trợ, xác thực hai bước.

Bộ này tập trung vào những chỗ mà một bản cài đặt *trông như chạy được* vẫn sai:
ranh giới quyền (ai đọc được của ai), chống phát lại, và hướng hỏng khi thiếu
ngữ cảnh. Phép tính TOTP đã được kiểm riêng ở `test_totp.py` bằng vector RFC.
"""

from __future__ import annotations

import uuid

import pytest

from app import notifications, support, totp, two_factor
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

    with system_scope("test cleanup: go du lieu v6"):
        _execute("DELETE FROM notifications WHERE user_id = %s", (account["id"],))
        _execute("DELETE FROM support_messages WHERE author_id = %s", (account["id"],))
        _execute("DELETE FROM support_tickets WHERE user_id = %s", (account["id"],))
        _execute("DELETE FROM user_recovery_codes WHERE user_id = %s", (account["id"],))
        _execute("DELETE FROM user_totp WHERE user_id = %s", (account["id"],))
    purge_registered_account(account["username"])


@pytest.fixture
def account():
    acc = _make_account("nb")
    yield acc
    _purge(acc)


@pytest.fixture
def other():
    acc = _make_account("nc")
    yield acc
    _purge(acc)


@pytest.fixture
def scope():
    """Phạm vi tenant mặc định — thông báo và phiếu hỗ trợ đều chịu RLS."""
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


# ===========================================================================
# Thông báo
# ===========================================================================
class TestThongBao:
    def test_ghi_va_doc_lai_duoc(self, account, scope):
        nid = notifications.notify(
            account["id"], "training", "Huấn luyện xong", body="job-1",
            link="/training/1", severity="success")
        assert nid

        items = notifications.list_for_user(account["id"])
        assert len(items) == 1
        assert items[0]["title"] == "Huấn luyện xong"
        assert items[0]["read_at"] is None
        assert notifications.unread_count(account["id"]) == 1

    def test_loai_khong_hop_le_bi_tu_choi_chu_khong_ghi_bua(self, account, scope):
        assert notifications.notify(account["id"], "khong-co-loai-nay", "x") is None
        assert notifications.list_for_user(account["id"]) == []

    def test_muc_do_la_bi_ha_ve_info_chu_khong_no_rang_buoc(self, account, scope):
        """CHECK trong lược đồ chỉ nhận 4 giá trị. Nếu để giá trị lạ đi thẳng
        xuống, câu INSERT ném và một thao tác đã thành công bị báo lỗi."""
        notifications.notify(account["id"], "system", "x", severity="tận thế")
        assert notifications.list_for_user(account["id"])[0]["severity"] == "info"

    def test_khong_co_pham_vi_tenant_thi_KHONG_ghi(self, account):
        """Fail-closed, cùng nguyên tắc với `audit.record()`: một dòng không biết
        mình thuộc tenant nào là dòng mà RLS sẽ giấu khỏi chính người cần đọc."""
        from app.tenant_context import no_scope

        with no_scope():
            assert notifications.notify(account["id"], "system", "mo coi") is None

    def test_khong_bao_gio_nem_khi_ghi_hong(self, account, scope, monkeypatch):
        """Thông báo là việc PHỤ của một thao tác đã thành công. Một phiên huấn
        luyện chạy xong không được phép báo lỗi vì cái chuông ghi hụt."""
        def _boom(*a, **k):
            raise RuntimeError("CSDL nga")

        monkeypatch.setattr(notifications, "_fetch_all", _boom)
        assert notifications.notify(account["id"], "system", "x") is None

    def test_danh_dau_da_doc(self, account, scope):
        nid = notifications.notify(account["id"], "system", "a")
        assert notifications.mark_read(account["id"], [nid]) == 1
        assert notifications.unread_count(account["id"]) == 0
        # Lần thứ hai không đếm lại: điều kiện `read_at IS NULL` nằm trong UPDATE.
        assert notifications.mark_read(account["id"], [nid]) == 0

    def test_KHONG_danh_dau_ho_nguoi_khac(self, account, other, scope):
        """`user_id` trong WHERE là ranh giới quyền, không phải chỗ dư thừa.

        Thiếu nó, ai đoán được một UUID sẽ làm một thông báo bảo mật biến mất
        khỏi tầm mắt nạn nhân.
        """
        nid = notifications.notify(other["id"], "security", "Đăng nhập lạ")
        assert notifications.mark_read(account["id"], [nid]) == 0
        assert notifications.unread_count(other["id"]) == 1

    def test_doc_tat_ca(self, account, scope):
        for i in range(3):
            notifications.notify(account["id"], "system", f"t{i}")
        assert notifications.mark_all_read(account["id"]) == 3
        assert notifications.unread_count(account["id"]) == 0

    def test_loc_chua_doc(self, account, scope):
        a = notifications.notify(account["id"], "system", "da doc")
        notifications.notify(account["id"], "system", "chua doc")
        notifications.mark_read(account["id"], [a])
        chua = notifications.list_for_user(account["id"], unread_only=True)
        assert [n["title"] for n in chua] == ["chua doc"]

    def test_don_rac_KHONG_dung_toi_thong_bao_chua_doc(self, account, scope):
        """Một thông báo chưa đọc, dù cũ, vẫn là việc chưa ai xem. Xoá nó là
        quyết định thay người dùng rằng việc đó không còn quan trọng."""
        cu_chua_doc = notifications.notify(account["id"], "system", "cu chua doc")
        cu_da_doc = notifications.notify(account["id"], "system", "cu da doc")
        notifications.mark_read(account["id"], [cu_da_doc])
        with system_scope("test setup: day thoi gian lui"):
            _execute("UPDATE notifications SET created_at = NOW() - interval '200 days', "
                     "read_at = CASE WHEN read_at IS NULL THEN NULL "
                     "ELSE NOW() - interval '200 days' END WHERE user_id = %s",
                     (account["id"],))

        notifications.purge_old(days=90)
        con_lai = {n["notification_id"] for n in notifications.list_for_user(account["id"])}
        assert str(cu_chua_doc) in {str(x) for x in con_lai}
        assert str(cu_da_doc) not in {str(x) for x in con_lai}


# ===========================================================================
# Kênh hỗ trợ
# ===========================================================================
class TestHoTro:
    def test_mo_phieu_kem_loi_nhan_dau(self, account, scope):
        t = support.create_ticket(
            account["id"], "Không tải được mẫu", "Bấm tải thì báo lỗi 500.",
            category="bug", author_label=account["username"])
        assert t["status"] == "open"

        # Từ v3.16 phiếu mới có BA lời nhắn: lời của người dùng, câu chào của
        # trợ lý, và câu trả lời tự động. Bài test cũ ghim `len == 1`; con số
        # đó không còn đúng, nhưng ba tính chất nó thật sự bảo vệ thì vẫn phải
        # đúng — nên chúng được viết ra tường minh ở đây thay vì một phép đếm.
        assert t["messages"][0]["author_kind"] == "user"
        assert t["messages"][0]["is_staff"] is False
        assert [m["author_kind"] for m in t["messages"]] == ["user", "bot", "bot"]

        # Trợ lý KHÔNG được mang danh người trực. Đây là tính chất quan trọng
        # nhất của cả tính năng: một câu máy sinh mang nhãn "người trực" làm
        # người dùng tin rằng đã có người thật đọc phiếu của họ.
        assert all(m["is_staff"] is False for m in t["messages"])

        # Và phiếu vẫn phải nằm trong hàng đợi. Nếu câu của trợ lý đẩy trạng
        # thái sang `pending`, phiếu rơi khỏi bộ lọc mặc định của người trực và
        # không ai nhìn thấy nó nữa.
        assert t["status"] == "open"

    @pytest.mark.parametrize("subject,body", [
        ("abc", "noi dung du dai de qua nguong"),
        ("tieu de du dai", "ngan"),
    ])
    def test_tu_choi_phieu_qua_so_sai(self, account, scope, subject, body):
        with pytest.raises(support.SupportError):
            support.create_ticket(account["id"], subject, body)

    def test_khong_doc_duoc_phieu_cua_nguoi_khac(self, account, other, scope):
        t = support.create_ticket(other["id"], "Phiếu riêng tư",
                                  "Nội dung không ai khác được xem.")
        with pytest.raises(support.SupportError):
            support.get_ticket(t["ticket_id"], account["id"])

    def test_nguoi_truc_doc_duoc_moi_phieu_trong_tenant(self, account, other, scope):
        t = support.create_ticket(other["id"], "Phiếu cần trực xem",
                                  "Nội dung mô tả sự cố.")
        assert support.get_ticket(t["ticket_id"], account["id"], as_staff=True)

    def test_tra_loi_cua_truc_dua_phieu_sang_cho_nguoi_dung(self, account, scope):
        t = support.create_ticket(account["id"], "Câu hỏi về gói",
                                  "Gói của tôi hết hạn khi nào?")
        sau = support.reply(t["ticket_id"], account["id"], "Ngày 30 tháng này.",
                            author_label="truc", is_staff=True)
        assert sau["status"] == "pending"

    def test_tra_loi_cua_nguoi_dung_mo_lai_phieu(self, account, scope):
        """Trạng thái đi theo AI vừa nói, không theo một nút bấm mà ai cũng quên."""
        t = support.create_ticket(account["id"], "Vẫn còn lỗi",
                                  "Mô tả ban đầu của sự cố.")
        support.set_status(t["ticket_id"], "resolved", account["id"], is_staff=True)
        sau = support.reply(t["ticket_id"], account["id"], "Vẫn chưa được ạ.",
                            author_label=account["username"])
        assert sau["status"] == "open"
        assert sau["resolved_at"] is None

    def test_phieu_da_dong_thi_khong_gui_them_duoc(self, account, scope):
        t = support.create_ticket(account["id"], "Đã xong rồi",
                                  "Mô tả ban đầu của sự cố.")
        support.set_status(t["ticket_id"], "closed", account["id"])
        with pytest.raises(support.SupportError):
            support.reply(t["ticket_id"], account["id"], "thêm nữa")

    def test_nguoi_dung_chi_duoc_DONG_phieu_cua_minh(self, account, scope):
        t = support.create_ticket(account["id"], "Phiếu của tôi",
                                  "Mô tả ban đầu của sự cố.")
        with pytest.raises(support.SupportError):
            support.set_status(t["ticket_id"], "resolved", account["id"])
        assert support.set_status(t["ticket_id"], "closed",
                                  account["id"])["status"] == "closed"


class TestPhieuDenTayNguoiTruc:
    """Chiều người dùng → người trực, chiều mà bản đầu KHÔNG hề có.

    Bản đầu chỉ báo khi người trực trả lời. Người dùng mở phiếu thì việc duy
    nhất xảy ra là một hàng mới trong bảng: không thư, không chuông, không con
    số nào tăng ở đâu. Phiếu chỉ được đọc nếu tình cờ có ai mở đúng trang hàng
    đợi. Đo được trên bản chạy thật: người dùng nhắn, quản trị viên không biết.
    """

    @pytest.fixture
    def admin(self):
        """Một quản trị viên THẬT trong cùng tenant với người dùng thử."""
        acc = _make_account("na")
        with system_scope("test setup: cap quyen quan tri"):
            _execute("UPDATE users SET is_admin = TRUE, tenant_id = %s WHERE id = %s",
                     (DEFAULT_TENANT_ID, acc["id"]))
        yield acc
        _purge(acc)

    def _hop_thu(self, user_id: str):
        return notifications.list_for_user(user_id, limit=20)

    def test_phieu_moi_bao_cho_quan_tri_vien(self, account, admin, scope):
        support.create_ticket(account["id"], "Thanh toán bị lỗi",
                              "Bấm thanh toán thì trắng trang.",
                              category="billing", author_label=account["username"])
        hop = self._hop_thu(admin["id"])
        assert [n for n in hop if n["kind"] == "support"], \
            "quan tri vien khong nhan duoc gi khi co phieu moi"

    def test_nguoi_dung_tra_loi_cung_bao_cho_quan_tri_vien(self, account, admin, scope):
        """Trả lời cũng phải báo. Thiếu chiều này thì một phiếu đang chờ người
        dùng bổ sung sẽ nằm im mãi sau khi họ đã bổ sung xong."""
        t = support.create_ticket(account["id"], "Vẫn còn lỗi",
                                  "Mô tả ban đầu của sự cố.")
        support.reply(t["ticket_id"], admin["id"], "Bạn thử lại giúp nhé.",
                      author_label="truc", is_staff=True)
        truoc = len([n for n in self._hop_thu(admin["id"]) if n["kind"] == "support"])

        support.reply(t["ticket_id"], account["id"], "Thử rồi vẫn vậy ạ.",
                      author_label=account["username"])
        sau = len([n for n in self._hop_thu(admin["id"]) if n["kind"] == "support"])
        assert sau == truoc + 1

    def test_lien_ket_tro_toi_console_quan_tri_chu_khong_phai_trang_nguoi_dung(
        self, account, admin, scope
    ):
        """`/support/{id}` là trang của NGƯỜI DÙNG và chỉ mở phiếu của chính
        họ. Gửi quản trị viên tới đó là gửi họ tới một trang 404."""
        support.create_ticket(account["id"], "Sai đường dẫn",
                              "Mô tả ban đầu của sự cố.")
        moi = [n for n in self._hop_thu(admin["id"]) if n["kind"] == "support"][0]
        assert moi["link"].startswith("/admin/support/")

    def test_tra_loi_cua_truc_KHONG_tu_bao_cho_chinh_minh(self, account, admin, scope):
        """Thông báo đi theo chiều NGƯỢC với người vừa gửi. Báo cả hai chiều mỗi
        lần là cách nhanh nhất để mọi người tắt chuông."""
        t = support.create_ticket(account["id"], "Kiểm tra chiều thông báo",
                                  "Mô tả ban đầu của sự cố.")
        truoc = len([n for n in self._hop_thu(admin["id"]) if n["kind"] == "support"])
        support.reply(t["ticket_id"], admin["id"], "Đã tiếp nhận.",
                      author_label="truc", is_staff=True)
        sau = len([n for n in self._hop_thu(admin["id"]) if n["kind"] == "support"])
        assert sau == truoc

        # …và người dùng thì có.
        assert [n for n in self._hop_thu(account["id"]) if n["kind"] == "support"]

    def test_khong_co_quan_tri_vien_thi_GHI_LOI_chu_khong_im_lang(
        self, account, scope, caplog
    ):
        """Danh sách người nhận rỗng có hai nghĩa rất khác nhau — "tổ chức không
        có quản trị viên" và "truy vấn chạy ngoài phạm vi nên RLS trả 0 dòng" —
        và cả hai đều dẫn tới một phiếu không ai nhìn thấy. Im lặng ở đây là
        cách một lỗi RLS đội lốt một cấu hình bình thường."""
        import logging

        with caplog.at_level(logging.ERROR, logger="app.support"):
            support._alert_staff("00000000-0000-0000-0000-000000000000",
                                 str(uuid.uuid4()), "chu de", "tieu de", "ai do")
        assert any("khong tim thay quan tri vien" in r.message for r in caplog.records)

    def test_ten_tac_gia_la_bang_chung_lich_su_khong_doi_theo_doi_ten(self):
        """Cùng nguyên tắc với `audit_log.actor_label`. Nếu nhãn chạy theo tên
        hiện tại, đọc lại một phiếu cũ sẽ thấy những cái tên chưa từng tồn tại
        vào lúc đó.

        Kiểm bằng CẤU TRÚC, không bằng cách gọi `rename_user` thật: hàm đó ghi
        lại `dataset/samples.csv` — tệp SẢN XUẤT, không phải bản sao — nên gọi nó
        trong một test là sửa dữ liệu thật của người dùng. (Bản đầu của test này
        có gọi, và nó treo bộ test 8 phút vì phải viết lại 3.860 dòng.)

        Cách này còn chứng minh mạnh hơn: nó ghim rằng `support_messages` KHÔNG
        có tên trong danh sách bảng của `account_rename`, tức là không có đường
        nào để lượt đổi tên chạm tới nó.
        """
        from pathlib import Path

        nguon = (Path(__file__).resolve().parents[1] / "app" / "account_rename.py"
                 ).read_text(encoding="utf-8")
        assert "support_messages" not in nguon, (
            "đổi tên tài khoản không được đụng tới lời nhắn hỗ trợ — "
            "author_label là bằng chứng lịch sử")
        assert "audit_log" in nguon, (
            "test này chỉ có nghĩa nếu nó đang đọc đúng tệp; `audit_log` phải "
            "xuất hiện ở đó dưới dạng ngoại lệ được nêu tên")

    def test_tra_loi_cua_truc_sinh_thong_bao(self, account, scope):
        t = support.create_ticket(account["id"], "Cần phản hồi",
                                  "Mô tả ban đầu của sự cố.")
        support.reply(t["ticket_id"], account["id"], "Đã xem nhé.",
                      author_label="truc", is_staff=True)
        kinds = [n["kind"] for n in notifications.list_for_user(account["id"])]
        assert "support" in kinds


# ===========================================================================
# Xác thực hai bước
# ===========================================================================
class TestHaiBuoc:
    def test_dang_ky_roi_xac_nhan_moi_bat(self, account):
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        assert two_factor.is_enabled(account["id"]) is False, \
            "đăng ký dở KHÔNG được coi là đã bật"

        codes = two_factor.confirm_enrollment(
            account["id"], totp.totp(out["secret"]))
        assert two_factor.is_enabled(account["id"]) is True
        assert len(codes) == two_factor.RECOVERY_CODE_COUNT

    def test_ma_sai_thi_khong_bat(self, account):
        two_factor.begin_enrollment(account["id"], "a@b.vn")
        with pytest.raises(two_factor.TwoFactorError):
            two_factor.confirm_enrollment(account["id"], "000000")
        assert two_factor.is_enabled(account["id"]) is False

    def test_dang_ky_lai_khi_dang_do_thi_THAY_bi_mat(self, account):
        """Người dùng quét hỏng rồi bấm lại là chuyện thường. Giữ bí mật cũ làm
        mã trên điện thoại không bao giờ khớp."""
        a = two_factor.begin_enrollment(account["id"], "a@b.vn")
        b = two_factor.begin_enrollment(account["id"], "a@b.vn")
        assert a["secret"] != b["secret"]
        assert two_factor.confirm_enrollment(account["id"], totp.totp(b["secret"]))

    def test_da_bat_roi_thi_khong_dang_ky_de_len_duoc(self, account):
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        with pytest.raises(two_factor.TwoFactorError):
            two_factor.begin_enrollment(account["id"], "a@b.vn")

    def test_ma_dung_de_BAT_2FA_khong_dung_lai_duoc(self, account):
        """Chính lượt xác nhận cũng tiêu bước thời gian của nó.

        Nếu không, mã người dùng vừa gõ để bật 2FA còn dùng được thêm 30 giây
        nữa — và đó là mã vừa hiện trên màn hình cho cả phòng nhìn thấy.
        """
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        ma = totp.totp(out["secret"])
        two_factor.confirm_enrollment(account["id"], ma)
        assert two_factor.verify_code(account["id"], ma) is False

    def test_CHONG_PHAT_LAI_trong_cung_buoc_thoi_gian(self, account):
        """Mã TOTP sống 30 giây. Không ghi lại bước đã dùng thì người nhìn trộm
        màn hình gõ lại đúng mã đó vẫn vào được — chính kịch bản 2FA sinh ra để
        chặn.

        Lùi `last_used_step` một nhịp để mô phỏng "lần đăng nhập sau", thay vì
        `sleep(30)`: cái đang được kiểm là phép so sánh bước, và chờ thật chỉ
        làm bộ test chậm thêm nửa phút mà không kiểm thêm gì.
        """
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        with system_scope("test setup: lui moc da tieu mot nhip"):
            _execute("UPDATE user_totp SET last_used_step = last_used_step - 1 "
                     "WHERE user_id = %s", (account["id"],))

        ma = totp.totp(out["secret"])
        assert two_factor.verify_code(account["id"], ma) is True
        assert two_factor.verify_code(account["id"], ma) is False, "mã dùng lại được"

    def test_chua_bat_thi_khong_kiem_ma(self, account):
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        assert two_factor.verify_code(account["id"], totp.totp(out["secret"])) is False

    def test_bi_mat_luu_trong_CSDL_da_ma_hoa(self, account):
        """Bản dump CSDL bị rò không được phép đủ để sinh mã của người khác."""
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        with system_scope("test read: bi mat da ma hoa"):
            rows = _fetch_all("SELECT secret_enc FROM user_totp WHERE user_id = %s",
                              (account["id"],))
        assert out["secret"] not in rows[0]["secret_enc"]

    def test_ma_khoi_phuc_dung_duoc_MOT_lan(self, account):
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        codes = two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))

        assert two_factor.consume_recovery_code(account["id"], codes[0]) is True
        assert two_factor.consume_recovery_code(account["id"], codes[0]) is False
        assert two_factor.count_unused_recovery_codes(account["id"]) == len(codes) - 1

    def test_ma_khoi_phuc_cua_nguoi_khac_khong_dung_duoc(self, account, other):
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        codes = two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        assert two_factor.consume_recovery_code(other["id"], codes[0]) is False

    def test_ma_khoi_phuc_bo_qua_hoa_va_dau_cach(self, account):
        """Người ta chép mã từ một tờ giấy in ra; viết hoa và dấu cách là chuyện
        bình thường, và từ chối vì thế là từ chối oan đúng lúc người dùng đang
        không có đường vào nào khác."""
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        codes = two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        assert two_factor.consume_recovery_code(
            account["id"], f"  {codes[0].upper()}  ") is True

    def test_cap_lai_ma_khoi_phuc_giet_bo_cu(self, account):
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        cu = two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        moi = two_factor.regenerate_recovery_codes(account["id"])

        assert set(cu).isdisjoint(moi)
        assert two_factor.consume_recovery_code(account["id"], cu[0]) is False
        assert two_factor.consume_recovery_code(account["id"], moi[0]) is True

    def test_tat_2FA_xoa_sach_ma_khoi_phuc(self, account):
        """Mã khôi phục còn sót sau khi tắt là một đường vào không ai còn nhớ là
        mình đã mở."""
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        codes = two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        two_factor.disable(account["id"])

        assert two_factor.is_enabled(account["id"]) is False
        assert two_factor.count_unused_recovery_codes(account["id"]) == 0
        assert two_factor.consume_recovery_code(account["id"], codes[0]) is False

    def test_trang_thai_bao_dung_so_ma_con_lai(self, account):
        out = two_factor.begin_enrollment(account["id"], "a@b.vn")
        codes = two_factor.confirm_enrollment(account["id"], totp.totp(out["secret"]))
        two_factor.consume_recovery_code(account["id"], codes[0])

        st = two_factor.status(account["id"])
        assert st["enabled"] is True and st["pending"] is False
        assert st["recovery_codes_left"] == len(codes) - 1


class TestVeHaiBuoc:
    """Vé tạm giữa hai bước đăng nhập."""

    def test_ve_hop_le_tra_ve_dung_nguoi(self):
        from app.auth import create_2fa_challenge, verify_2fa_challenge

        assert verify_2fa_challenge(create_2fa_challenge("u-123")) == "u-123"

    def test_ve_gia_bi_tu_choi(self):
        from app.auth import verify_2fa_challenge

        assert verify_2fa_challenge("khong-phai-jwt") is None
        assert verify_2fa_challenge("") is None

    def test_access_token_KHONG_dung_thay_ve_duoc(self):
        """Thiếu bước kiểm `typ`, một access token bình thường sẽ qua được cửa
        này — tức bước hai tự vô hiệu hoá chính nó."""
        from app.auth import create_access_token, verify_2fa_challenge

        assert verify_2fa_challenge(create_access_token({"sub": "u-123"})) is None

    def test_ve_KHONG_dung_thay_access_token_duoc(self):
        """Chiều ngược lại cũng phải đóng, và ban đầu nó KHÔNG đóng.

        Mọi token đều ký bằng cùng một khoá, nên chữ ký hợp lệ chỉ chứng minh
        "hệ thống này phát ra nó", không chứng minh nó được phát ra để làm gì.
        `_decode_token` lúc đầu chỉ kiểm `sub`, nên vé hai bước đi thẳng qua cửa
        xác thực — người vừa nhập đúng mật khẩu vào được hệ thống mà chưa qua
        bước hai, tức là 2FA tự vô hiệu hoá chính nó.
        """
        from fastapi import HTTPException

        from app.auth import _decode_token, create_2fa_challenge

        with pytest.raises(HTTPException) as e:
            _decode_token(create_2fa_challenge("u-123"))
        assert e.value.status_code == 401

    def test_token_cu_khong_co_typ_van_di_qua(self):
        """Đường chuyển tiếp: token cấp trước khi có claim `typ` không được phép
        401 hàng loạt lúc triển khai. Nó tự đóng sau một vòng đời access token."""
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        from app.auth import _decode_token
        from app.config import settings

        cu = jose_jwt.encode(
            {"sub": "u-1", "exp": datetime.now(timezone.utc) + timedelta(minutes=30)},
            settings.secret_key, algorithm=settings.algorithm)
        assert _decode_token(cu)["sub"] == "u-1"

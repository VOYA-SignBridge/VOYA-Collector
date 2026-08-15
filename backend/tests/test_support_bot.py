"""Trợ lý tự động trong kênh hỗ trợ.

Bộ này canh những tính chất mà một bản cài đặt *trông như chạy được* vẫn phá:

* trợ lý không được mang danh người trực;
* câu của trợ lý không được đẩy phiếu ra khỏi hàng đợi;
* trợ lý phải im khi đã có người thật vào;
* hàng đợi phải nói tên NGƯỜI DÙNG, không phải tên trợ lý.

Ba cái sau đều là biến thể của cùng một lớp lỗi đã phải đi vá một lần: người
dùng nhắn mà quản trị viên không nhìn thấy.
"""

from __future__ import annotations

import uuid

import pytest

from app import support, support_bot
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

    with system_scope("test cleanup: tro ly ho tro"):
        _execute("DELETE FROM support_messages WHERE ticket_id IN "
                 "(SELECT ticket_id FROM support_tickets WHERE user_id = %s)",
                 (account["id"],))
        _execute("DELETE FROM support_tickets WHERE user_id = %s", (account["id"],))
    purge_registered_account(account["username"])


@pytest.fixture
def account():
    acc = _make_account("bot")
    yield acc
    _purge(acc)


@pytest.fixture
def staff():
    acc = _make_account("trc")
    yield acc
    _purge(acc)


@pytest.fixture
def scope():
    with tenant_scope(DEFAULT_TENANT_ID):
        yield


# ===========================================================================
# Khớp luật — thuần hàm, không chạm cơ sở dữ liệu
# ===========================================================================
class TestKhopLuat:
    @pytest.mark.parametrize("cau", [
        "Tôi quên mật khẩu",
        "toi quen mat khau",
        "QUÊN MẬT KHẨU rồi làm sao",
        "Quên Mật Khẩu",
    ])
    def test_bo_dau_va_chu_hoa_khong_lam_truot(self, cau):
        """Người ta gõ có dấu, không dấu và VIẾT HOA như nhau.

        Khớp trên chuỗi thô sẽ trượt hầu hết, và cái trượt đó IM LẶNG — trợ lý
        chỉ đơn giản là không trả lời được, không ai biết vì sao.
        """
        rule = support_bot.match(cau)
        assert rule is not None and rule.topic == "password"

    def test_xin_gap_nguoi_that_thang_moi_luat_khac(self):
        """`handoff` đứng đầu bảng luật là chủ ý.

        Khi người ta đã nói "cho tôi gặp người thật" thì mọi luật khác đều sai,
        kể cả khi câu đó có nhắc tới mật khẩu.
        """
        assert support_bot.wants_human("mật khẩu gì cũng được, tôi cần gặp người hỗ trợ")

    def test_khong_khop_thi_NOI_THANG_la_khong_biet(self):
        answer, chips, topic = support_bot.answer_for(
            "con mèo của tôi ngồi lên bàn phím")
        assert topic == "unknown"
        assert answer == support_bot.FALLBACK
        # Không đoán, nhưng cũng không bỏ rơi: luôn còn lối gọi người thật.
        assert support_bot.ESCAPE_CHIP in chips

    def test_luon_tra_ve_mot_cau(self):
        """Im lặng là hướng hỏng tệ nhất trong kênh hỗ trợ: người dùng không
        phân biệt được "hệ thống chưa đọc" với "hệ thống bỏ qua tôi"."""
        for cau in ("", "   ", "?", "asdfghjkl"):
            answer, _chips, _topic = support_bot.answer_for(cau)
            assert answer.strip()

    def test_moi_chip_mo_dau_deu_khop_mot_luat(self):
        """Một chip không khớp luật nào là một cái bẫy: người dùng bấm vào rồi
        nhận đúng câu "tôi chưa hiểu"."""
        starters = support_bot.starters()
        # Không có chốt này thì `starters()` trả rỗng là test xanh mà chưa bấm
        # thử chip nào — đúng cái bẫy mà docstring vừa mô tả.
        assert starters, "starters() không trả chip nào"
        for chip in starters:
            assert support_bot.match(chip) is not None, chip

    def test_moi_chip_goi_y_deu_khop_mot_luat(self):
        assert support_bot.RULES, "không có luật nào để đối chiếu"
        da_kiem = 0
        for rule in support_bot.RULES:
            for chip in rule.suggestions:
                assert support_bot.match(chip) is not None, chip
                da_kiem += 1
        # Vòng lặp LỒNG: `RULES` không rỗng vẫn chưa đủ, vì mọi luật đều có thể
        # có `suggestions` rỗng và thân trong không chạy lần nào.
        assert da_kiem, "không luật nào có chip gợi ý để kiểm"


# ===========================================================================
# Trợ lý trong luồng phiếu thật
# ===========================================================================
class TestTroLyTrongPhieu:
    def test_phieu_moi_co_chao_va_tra_loi_tu_dong(self, account, scope):
        t = support.create_ticket(
            account["id"], "Tôi quên mật khẩu", "Đăng nhập mãi không được.",
            category="account", author_label=account["username"])
        kinds = [m["author_kind"] for m in t["messages"]]
        assert kinds == ["user", "bot", "bot"]
        assert t["messages"][1]["body"] == support_bot.GREETING
        # Câu thứ ba phải là câu ĐÚNG CHỦ ĐỀ, không phải câu chung chung.
        assert "Quên mật khẩu?" in t["messages"][2]["body"]

    def test_tro_ly_KHONG_mang_danh_nguoi_truc(self, account, scope):
        t = support.create_ticket(account["id"], "Tôi quên mật khẩu",
                                  "Không vào được tài khoản.")
        bot_msgs = [m for m in t["messages"] if m["author_kind"] == "bot"]
        assert bot_msgs
        for m in bot_msgs:
            assert m["is_staff"] is False
            assert m["author_label"] == support_bot.BOT_LABEL

    def test_tro_ly_KHONG_day_phieu_ra_khoi_hang_doi(self, account, scope):
        """Nếu câu của trợ lý đổi trạng thái sang `pending`, phiếu rơi khỏi bộ
        lọc mặc định của người trực — và biến mất khỏi màn hình của người duy
        nhất có thể xử lý nó. Đúng lớp lỗi đã phải đi vá một lần."""
        t = support.create_ticket(account["id"], "Tôi quên mật khẩu",
                                  "Không vào được tài khoản.")
        assert t["status"] == "open"

        t2 = support.reply(t["ticket_id"], account["id"], "Vẫn chưa nhận được mã.")
        assert t2["status"] == "open"

        hang_doi = support.list_tickets(status="open")
        assert t["ticket_id"] in {str(x["ticket_id"]) for x in hang_doi}

    def test_tro_ly_im_khi_da_co_nguoi_truc(self, account, staff, scope):
        """Sau khi một người thật đã trả lời, chen câu máy vào giữa cuộc trao
        đổi là phá cuộc trao đổi đó — và tệ hơn, câu máy có thể mâu thuẫn với
        điều người trực vừa nói mà người dùng không biết tin ai."""
        t = support.create_ticket(account["id"], "Tôi quên mật khẩu",
                                  "Không vào được tài khoản.")
        support.reply(t["ticket_id"], staff["id"], "Mình đang kiểm tra giúp bạn.",
                      author_label=staff["username"], is_staff=True)

        truoc = len(support.get_ticket(t["ticket_id"], account["id"])["messages"])
        sau = support.reply(t["ticket_id"], account["id"], "Tôi quên mật khẩu nữa.")
        # Chỉ THÊM một lời của người dùng, không có câu máy nào nữa.
        assert len(sau["messages"]) == truoc + 1
        assert sau["messages"][-1]["author_kind"] == "user"

    def test_chip_goi_y_tat_khi_nguoi_truc_vao(self, account, staff, scope):
        t = support.create_ticket(account["id"], "Tôi quên mật khẩu",
                                  "Không vào được tài khoản.")
        assert t["bot_suggestions"], "phải có chip khi trợ lý còn đang trực"

        support.reply(t["ticket_id"], staff["id"], "Mình xử lý ngay.",
                      author_label=staff["username"], is_staff=True)
        sau = support.get_ticket(t["ticket_id"], account["id"])
        assert sau["bot_suggestions"] == []

    def test_hang_doi_noi_ten_NGUOI_DUNG_khong_phai_tro_ly(self, account, scope):
        """Không lọc `author_kind` thì mọi phiếu trong hàng đợi đều mang tên
        người gửi là "Trợ lý tự động" — người trực mất luôn cột quan trọng
        nhất của hàng đợi: ai đang hỏi."""
        support.create_ticket(account["id"], "Tôi quên mật khẩu",
                              "Không vào được tài khoản.",
                              author_label=account["username"])
        row = next(x for x in support.list_tickets(user_id=account["id"]))
        assert row["requester"] == account["username"]
        assert row["requester"] != support_bot.BOT_LABEL

    def test_dem_loi_nhan_KHONG_tinh_tro_ly(self, account, scope):
        """Con số này nói với người trực "cuộc trao đổi dài bao nhiêu". Cộng cả
        câu máy vào làm một phiếu chưa ai đụng trông như đã trao đổi ba lượt."""
        support.create_ticket(account["id"], "Tôi quên mật khẩu",
                              "Không vào được tài khoản.")
        row = next(x for x in support.list_tickets(user_id=account["id"]))
        assert row["message_count"] == 1

    def test_doan_xem_truoc_lay_loi_cua_nguoi_khong_phai_may(self, account, scope):
        support.create_ticket(account["id"], "Tôi quên mật khẩu",
                              "Câu này phải hiện trong hàng đợi.")
        row = next(x for x in support.list_tickets(user_id=account["id"]))
        assert row["last_snippet"].startswith("Câu này phải hiện")
        assert row["last_kind"] == "user"

    def test_rang_buoc_CSDL_chan_tro_ly_deo_mac_nguoi_truc(self, account, scope):
        """`ck_support_author_kind_matches` là hàng rào cuối.

        Ứng dụng đã cẩn thận, nhưng một lượt ghi tay hoặc một đường mã mới có
        thể tạo ra hàng `author_kind='bot'` kèm `is_staff=TRUE` — đúng lời nói
        dối mà cả cột này sinh ra để ngăn.
        """
        import psycopg2

        t = support.create_ticket(account["id"], "Tôi quên mật khẩu",
                                  "Không vào được tài khoản.")
        with system_scope("test: thu pha rang buoc"):
            with pytest.raises(psycopg2.errors.CheckViolation):
                _execute(
                    "INSERT INTO support_messages "
                    "(tenant_id, ticket_id, author_label, is_staff, body, author_kind) "
                    "VALUES (%s, %s, %s, TRUE, %s, 'bot')",
                    (DEFAULT_TENANT_ID, t["ticket_id"], "giả danh", "xin chào"))

    def test_loi_nhan_cu_van_doc_duoc_sau_khi_them_cot(self, account, scope):
        """Backfill suy `author_kind` từ `is_staff` — không bịa dữ liệu, vì với
        hàng cũ `is_staff` đúng là toàn bộ thông tin đã có."""
        t = support.create_ticket(account["id"], "Tôi quên mật khẩu",
                                  "Không vào được tài khoản.")
        rows = _fetch_all(
            "SELECT author_kind, is_staff FROM support_messages "
            "WHERE ticket_id = %s", (t["ticket_id"],))
        assert rows
        for r in rows:
            assert r["author_kind"] in ("user", "staff", "bot")
            assert (r["author_kind"] == "staff") is bool(r["is_staff"])

"""Vòng đời đăng ký: kỳ hạn, nhắc, ân hạn, khoá mềm.

Bản kiểm 09/08 đo được **0 trên 9 bước** của vòng đời này. Bộ test dưới đây
canh 7 bước đã hiện thực; hai bước còn lại (thanh toán, hoá đơn) không có mã
để canh và cũng không được giả vờ là có.

Cái khó của phần này là **thời gian**, nên mọi test đều truyền `now` tường
minh thay vì chờ đồng hồ. Một test vòng đời dựa vào thời gian thật thì hoặc
chạy 30 ngày, hoặc xanh vì lý do sai.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app import plans, subscription_lifecycle as sub
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _schema():
    db.ensure_tables()


@pytest.fixture
def tenant():
    """Một tenant dùng-một-lần, kèm đăng ký mở trên gói `school` (monthly)."""
    tid = f"sub{uuid.uuid4().hex[:8]}"
    with system_scope("test: dựng tenant thử vòng đời"):
        db._execute(
            "INSERT INTO tenants (tenant_id, display_name) VALUES (%s, %s)",
            (tid, f"Thử vòng đời {tid}"))
        db._execute(
            "INSERT INTO tenant_subscriptions "
            "(subscription_id, tenant_id, plan_code, status) VALUES (%s, %s, %s, 'active')",
            (str(uuid.uuid4()), tid, "plus"))
    yield tid
    # Dọn từng câu riêng — một câu hỏng không được chặn câu sau.
    with system_scope("test cleanup: gỡ tenant thử"):
        for sql in ("DELETE FROM tenant_subscriptions WHERE tenant_id = %s",
                    "DELETE FROM tenant_members WHERE tenant_id = %s",
                    "DELETE FROM tenants WHERE tenant_id = %s"):
            try:
                db._execute(sql, (tid,))
            except Exception:
                pass


def _sub_of(tenant_id):
    return sub.open_subscription(tenant_id)


def _set(tenant_id, **cols):
    """Ép thẳng vài cột để dựng một mốc thời gian, không phải chờ nó tới."""
    sets = ", ".join(f"{k} = %s" for k in cols)
    with system_scope("test: dựng mốc thời gian"):
        db._execute(f"UPDATE tenant_subscriptions SET {sets} WHERE tenant_id = %s",
                    (*cols.values(), tenant_id))


class TestKyHan:
    def test_dang_ky_moi_duoc_dat_ky_han(self, tenant):
        """Trước v3.14 một đăng ký mở là mở vô thời hạn."""
        assert _sub_of(tenant)["current_period_end"] is None
        sub.start_period(tenant)
        row = _sub_of(tenant)
        assert row["current_period_end"] is not None
        assert row["current_period_start"] is not None

    def test_ky_dau_dai_bang_dung_mot_ky_tinh_cuoc(self, tenant):
        """Gói `plus` có `billing_period = monthly` và `trial_days = 0`.

        Kỳ đầu phải là đúng 30 ngày. Bản trước khẳng định 14, vì gói `school`
        khi đó có `trial_days = 14` và kỳ đầu được rút ngắn về đúng thời gian
        dùng thử. v6 bỏ hẳn khái niệm dùng thử (`trial_days = 0` ở cả bốn gói),
        nên phép cộng dồn không còn đường sai nào để chặn — điều duy nhất còn
        phải giữ là kỳ đầu không dài hơn một kỳ tính cước, tức không phải 44.
        """
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        sub.start_period(tenant, now=at)
        row = _sub_of(tenant)
        assert (row["current_period_end"] - at).days == 30
        # Không còn mốc dùng thử để ghi: một ngày ở đây nghĩa là hệ thống vẫn
        # tin có bản dùng thử, và sẽ có nơi nào đó đi đòi nó hết hạn.
        assert row["trial_ends_at"] is None

    def test_goi_khong_ky_han_thi_de_trong_chu_khong_dat_nam_2999(self, tenant):
        """`none` nghĩa là KHÔNG ÁP DỤNG. Một ngày rất xa trông như dữ liệu hỏng."""
        _set(tenant, plan_code="enterprise")
        sub.start_period(tenant)
        assert _sub_of(tenant)["current_period_end"] is None

    def test_goi_lai_khi_ky_con_han_khong_doi_moc(self, tenant):
        """`sweep()` chạy mỗi giờ và gọi hàm này. Không idempotent thì mỗi giờ
        người dùng lại được tặng thêm một kỳ."""
        at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        sub.start_period(tenant, now=at)
        first_end = _sub_of(tenant)["current_period_end"]
        sub.start_period(tenant, now=at + timedelta(days=1))
        assert _sub_of(tenant)["current_period_end"] == first_end


class TestKyKhongTroi:
    def test_gia_han_neo_vao_moc_cu_chu_khong_vao_bay_gio(self, tenant):
        """Lượt quét chạy mỗi giờ nên gia hạn luôn muộn hơn mốc hết hạn.

        Neo vào "bây giờ" thì mỗi kỳ trôi thêm chừng ấy, và sau một năm gói
        tháng lệch khoảng nửa ngày so với ngày người ta đã trả tiền cho.
        """
        end = datetime.now(timezone.utc) - timedelta(hours=5)
        _set(tenant, current_period_start=end - timedelta(days=30),
             current_period_end=end, auto_renew=True)

        sub.sweep()
        row = _sub_of(tenant)
        assert row["current_period_start"] == end          # đúng mốc cũ
        assert row["current_period_end"] == end + timedelta(days=30)

    def test_bo_lo_nhieu_ky_thi_nhay_toi_ky_hien_tai(self, tenant):
        """Worker nghỉ dài. Mở một kỳ đã hết hạn từ trước nghĩa là lượt quét sau
        lại thấy nó hết hạn — tổ chức đi qua chuỗi "gia hạn → hết hạn" hàng loạt.
        """
        long_past = datetime.now(timezone.utc) - timedelta(days=200)
        _set(tenant, current_period_start=long_past - timedelta(days=30),
             current_period_end=long_past, auto_renew=True)

        sub.sweep()
        row = _sub_of(tenant)
        assert row["current_period_end"] > datetime.now(timezone.utc)
        # Và chỉ nhảy vừa đủ: kỳ mới không dài hơn một kỳ chuẩn.
        assert (row["current_period_end"] - row["current_period_start"]).days == 30


#: Một quản trị viên giả cho các test nhắc hạn.
#
#: Vá `_tenant_admins`, KHÔNG phải `_tenant_admin_emails`. Từ khi có thêm kênh
#: thông báo trong ứng dụng, `_send_reminder` cần cả `id` lẫn `email` nên nó hỏi
#: `_tenant_admins`; `_tenant_admin_emails` giờ chỉ là một lớp mỏng bọc ngoài và
#: đường gửi thư không còn đi qua nó. Vá seam cũ thì bản vá trượt trong im lặng:
#: truy vấn thật chạy, tenant tạm không có quản trị viên nào, không thư nào được
#: gửi, và test đỏ ở `assert [] == [7]` — một thông báo trông như lỗi mốc nhắc
#: chứ không như một bản vá đặt sai chỗ.
_ADMIN_GIA = {"id": "00000000-0000-0000-0000-000000000001", "email": "a@b.test"}


class TestNhacTruocHan:
    def test_nhac_dung_moc_va_khong_gui_lai(self, tenant, monkeypatch):
        """Tác vụ quét chạy MỖI GIỜ. Không có cột chống trùng thì một người
        nhận 24 lá thư "còn 7 ngày" trong một ngày."""
        sent = []
        monkeypatch.setattr(
            "app.email_service.send_subscription_reminder_email",
            lambda to, **kw: sent.append((to, kw["days_left"])))
        monkeypatch.setattr(sub, "_tenant_admins", lambda _t: [_ADMIN_GIA])

        end = datetime.now(timezone.utc) + timedelta(days=6, hours=1)
        _set(tenant, current_period_start=end - timedelta(days=30),
             current_period_end=end)

        sub.sweep()
        assert [d for _a, d in sent] == [7]

        sub.sweep()          # ngay sau đó — không được gửi thêm
        assert [d for _a, d in sent] == [7]

    def test_moc_gan_hon_thi_gui_tiep(self, tenant, monkeypatch):
        sent = []
        monkeypatch.setattr(
            "app.email_service.send_subscription_reminder_email",
            lambda to, **kw: sent.append(kw["days_left"]))
        monkeypatch.setattr(sub, "_tenant_admins", lambda _t: [_ADMIN_GIA])

        _set(tenant, current_period_end=datetime.now(timezone.utc) + timedelta(days=6, hours=1))
        sub.sweep()
        _set(tenant, current_period_end=datetime.now(timezone.utc) + timedelta(hours=20))
        sub.sweep()
        assert sent == [7, 1]

    def test_smtp_hong_khong_lam_hong_luot_quet(self, tenant, monkeypatch):
        """Một sự cố thư không được biến thành một sự cố vòng đời: tenant xếp
        sau trong danh sách vẫn phải được xét."""
        def _explode(*_a, **_k):
            raise RuntimeError("SMTP chết")

        monkeypatch.setattr("app.email_service.send_subscription_reminder_email", _explode)
        monkeypatch.setattr(sub, "_tenant_admins", lambda _t: [_ADMIN_GIA])
        _set(tenant, current_period_end=datetime.now(timezone.utc) + timedelta(days=6, hours=1))

        out = sub.sweep()
        assert out["loi"] == 0
        # Mốc vẫn được ghi: nếu không, hộp thư hỏng làm quét thử lại mỗi giờ.
        assert _sub_of(tenant)["last_reminder_days"] == 7


class TestToiHan:
    def test_tu_gia_han_mo_ky_moi(self, tenant):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        _set(tenant, current_period_start=past - timedelta(days=30),
             current_period_end=past, auto_renew=True)

        out = sub.sweep()
        assert out["gia_han"] == 1
        assert _sub_of(tenant)["current_period_end"] > datetime.now(timezone.utc)

    def test_khong_tu_gia_han_thi_vao_an_han_va_VAN_GHI_DUOC(self, tenant):
        """`past_due` nằm trong `WRITABLE_BILLING_STATUSES`, và đó là chủ ý:
        khoá một trường vì hoá đơn trễ hai ngày là cách nhanh nhất để mất họ."""
        past = datetime.now(timezone.utc) - timedelta(days=1)
        _set(tenant, current_period_end=past, auto_renew=False)

        out = sub.sweep()
        assert out["vao_an_han"] == 1
        assert plans.billing_status_of(tenant) == "past_due"
        plans.assert_writable(tenant)          # không được ném

    def test_het_an_han_thi_khoa_mem(self, tenant):
        long_past = datetime.now(timezone.utc) - timedelta(days=90)
        _set(tenant, current_period_end=long_past, auto_renew=False,
             grace_until=long_past + timedelta(days=7))

        out = sub.sweep()
        assert out["khoa_mem"] == 1
        assert plans.billing_status_of(tenant) == "suspended"
        with pytest.raises(plans.TenantSuspended):
            plans.assert_writable(tenant)

    def test_khoa_mem_khong_xoa_gi(self, tenant):
        """Hết hạn là sự kiện thương mại, không phải phán quyết về dữ liệu."""
        long_past = datetime.now(timezone.utc) - timedelta(days=90)
        _set(tenant, current_period_end=long_past, auto_renew=False,
             grace_until=long_past + timedelta(days=7))
        sub.sweep()

        with system_scope("test read"):
            assert db._fetch_all(
                "SELECT 1 FROM tenant_subscriptions WHERE tenant_id = %s", (tenant,))
            assert db._fetch_all("SELECT 1 FROM tenants WHERE tenant_id = %s", (tenant,))

    def test_khoa_mem_khong_lap_lai(self, tenant):
        long_past = datetime.now(timezone.utc) - timedelta(days=90)
        _set(tenant, current_period_end=long_past, auto_renew=False,
             grace_until=long_past + timedelta(days=7))
        sub.sweep()
        assert sub.sweep()["khoa_mem"] == 0


class TestTuHuy:
    def test_tat_tu_gia_han_khong_dong_ngay(self, tenant):
        """Đóng ngay khi người ta bấm huỷ là lấy đi phần họ đã trả tiền."""
        sub.start_period(tenant)
        end_before = _sub_of(tenant)["current_period_end"]

        sub.set_auto_renew(tenant, False)
        row = _sub_of(tenant)
        assert row["auto_renew"] is False
        assert row["current_period_end"] == end_before
        assert row["ended_at"] is None
        plans.assert_writable(tenant)          # vẫn ghi được tới hết kỳ

    def test_tenant_khong_co_dang_ky_thi_bao_ro(self, tenant):
        with system_scope("test"):
            db._execute("DELETE FROM tenant_subscriptions WHERE tenant_id = %s", (tenant,))
        with pytest.raises(sub.SubscriptionError) as exc:
            sub.set_auto_renew(tenant, False)
        assert exc.value.code == "no_subscription"


class TestMoTaChoGiaoDien:
    def test_goi_vinh_vien_tra_None_chu_khong_phai_0(self, tenant):
        """"Còn 0 ngày" trên một gói vĩnh viễn là câu sai đủ để người dùng gọi điện."""
        _set(tenant, plan_code="enterprise")
        sub.start_period(tenant)
        assert sub.describe(tenant)["days_left"] is None

    def test_co_san_co_chi_doc_de_giao_dien_khoi_tu_suy(self, tenant):
        assert sub.describe(tenant)["read_only"] is False
        long_past = datetime.now(timezone.utc) - timedelta(days=90)
        _set(tenant, current_period_end=long_past, auto_renew=False,
             grace_until=long_past + timedelta(days=7))
        sub.sweep()
        assert sub.describe(tenant)["read_only"] is True


class TestQuetChiuDuocLoi:
    def test_mot_tenant_hong_khong_chan_tenant_khac(self, tenant, monkeypatch):
        """Bài học từ teardown: một câu ném ngoại lệ giữa chừng thì mọi thứ xếp
        sau nó không bao giờ chạy tới."""
        real = sub.start_period
        seen = []

        def _explode_for_one(tid, **kw):
            seen.append(tid)
            if tid == tenant:
                raise RuntimeError("hỏng có chủ ý")
            return real(tid, **kw)

        monkeypatch.setattr(sub, "start_period", _explode_for_one)
        out = sub.sweep()
        assert out["loi"] >= 1
        assert out["xet"] >= 1

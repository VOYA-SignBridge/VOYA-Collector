"""Gói và hạn mức: cái gì chặn, cái gì không, và vì sao.

Bộ test này canh những khẳng định mà một lỗi trong đó sẽ không lộ ra bằng lỗi
runtime — nó lộ ra bằng việc một khách hàng dùng gấp mười lần gói họ trả tiền,
hoặc bằng việc một khách hàng đã trả tiền bị chặn oan.
"""

from __future__ import annotations

import uuid

import pytest

from app import plans
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def throwaway_tenant():
    """Tenant sạch, tự dọn. Không sao chép danh mục cho nhanh."""
    from app import tenant_admin
    from conftest import purge_tenant

    tenant_id = f"qt{uuid.uuid4().hex[:10]}"
    tenant_admin.create_tenant(
        tenant_id, display_name="Quota Test", clone_catalog=False, plan_code="free"
    )
    plans._clear_caches()
    yield tenant_id
    purge_tenant(tenant_id)
    plans._clear_caches()


def _set_plan(tenant_id: str, plan_code: str) -> None:
    with system_scope("test: point a tenant at a plan"):
        db._execute(
            "UPDATE tenants SET plan_code = %s WHERE tenant_id = %s",
            (plan_code, tenant_id),
        )
    plans._clear_caches()


class TestNullMeansUnlimited:
    def test_the_internal_plan_has_no_ceiling_at_all(self):
        """Tenant gốc giữ dữ liệu thật và không bao giờ được một hạn mức
        thương mại chặn giữa chừng."""
        plan = plans.get_plan("enterprise")
        assert plan is not None
        for column in ("max_samples", "max_seats", "max_classes", "max_storage_mb"):
            assert plan[column] is None, f"{column} phải là NULL (không giới hạn)"

    def test_a_null_limit_never_raises(self, throwaway_tenant):
        _set_plan(throwaway_tenant, "enterprise")
        # Không ném là toàn bộ nội dung khẳng định ở đây.
        # `api_keys` chứ không `samples`: từ v8 số mẫu KHÔNG còn là hạn mức
        # thương mại. Bài này kiểm quy ước NULL = không giới hạn, nên nó cần
        # một chỉ số còn sống làm phương tiện, không cần chỉ số nào cụ thể.
        plans.check_quota(throwaway_tenant, "api_keys", adding=10_000_000)


class TestQuotaArithmetic:
    def test_a_batch_that_would_cross_the_line_is_refused_as_a_batch(
        self, throwaway_tenant
    ):
        """`used + adding > limit`, không phải `used >= limit`.

        Đây là chỗ dễ viết sai nhất và cái sai không lộ ra: kiểm từng-cái-một
        cho một tenant ở mức 499/500 sẽ cho lọt trọn một lô 5 mẫu, vì mỗi mẫu
        đơn lẻ đều "chưa chạm trần" tại thời điểm được hỏi.
        """
        _set_plan(throwaway_tenant, "free")  # max_api_keys = 1
        # 0 khoá thật, nên xin thêm 2 phải bị từ chối còn 1 thì không.
        plans.check_quota(throwaway_tenant, "api_keys", adding=1)
        with pytest.raises(plans.QuotaExceeded):
            plans.check_quota(throwaway_tenant, "api_keys", adding=2)

    def test_the_refusal_carries_the_numbers_not_just_a_sentence(
        self, throwaway_tenant
    ):
        """Giao diện cần con số để vẽ "đã dùng X/Y", và nó không được phép
        moi con số đó ra từ chuỗi tiếng Việt — chuỗi sẽ đổi."""
        _set_plan(throwaway_tenant, "free")
        with pytest.raises(plans.QuotaExceeded) as caught:
            plans.check_quota(throwaway_tenant, "api_keys", adding=99_999)
        assert caught.value.metric == "api_keys"
        assert caught.value.limit == 1
        assert caught.value.current == 0
        # 402, không phải 403: yêu cầu hợp lệ, gói không đủ — có đường đi tiếp.
        assert caught.value.status_code == 402

    def test_an_unknown_metric_is_a_programming_error_not_a_silent_pass(
        self, throwaway_tenant
    ):
        """Gõ sai tên chỉ số phải NỔ. Trả về "không vi phạm" cho một chỉ số
        không tồn tại nghĩa là mọi cổng gọi sai tên đều mở toang mà xanh."""
        with pytest.raises(KeyError):
            plans.check_quota(throwaway_tenant, "sampels")


class TestSuspensionClosesWrites:
    def test_a_suspended_tenant_cannot_write(self, throwaway_tenant):
        from app import tenant_admin

        tenant_admin.set_billing_status(throwaway_tenant, "suspended", reason="thử")
        with pytest.raises(plans.TenantSuspended):
            plans.assert_writable(throwaway_tenant)

    def test_past_due_still_writes(self, throwaway_tenant):
        """Có chủ ý, và trái với phản xạ thông thường.

        Khoá dữ liệu của một trường vì hoá đơn trễ vài ngày là cách nhanh nhất
        để mất họ, và số tiền không vì thế mà đòi được nhanh hơn. Treo là quyết
        định của người vận hành, không phải hệ quả tự động của một ngày trôi
        qua.
        """
        from app import tenant_admin

        tenant_admin.set_billing_status(throwaway_tenant, "past_due")
        plans.assert_writable(throwaway_tenant)  # không ném

    def test_the_bootstrap_tenant_cannot_be_suspended(self):
        """Treo nó là tự khoá mình ra khỏi chính API vừa dùng để treo."""
        from app import tenant_admin
        from app.tenancy import DEFAULT_TENANT_ID

        with pytest.raises(tenant_admin.TenantError) as caught:
            tenant_admin.set_billing_status(DEFAULT_TENANT_ID, "suspended")
        assert caught.value.status_code == 409


class TestSeats:
    def test_so_thanh_vien_KHONG_con_bi_goi_chan(self, throwaway_tenant):
        """ĐẢO CHIỀU ở v8 (25/08/2026). Bài này trước đây khẳng định người thứ
        tư bị từ chối với 402.

        Membership thuộc mặt phẳng PHÂN QUYỀN — nó tồn tại vì lý do bảo mật,
        không vì lý do thương mại. Bán theo đầu người còn tạo một khuyến khích
        ngược ở đúng chỗ không nên có: một tổ chức chạm trần sẽ dùng chung tài
        khoản để tiết kiệm ghế, và dùng chung tài khoản phá mọi vết kiểm toán
        mà hệ thống này dựng lên.

        `max_seats` vẫn còn trong bảng `plans` (gói Free = 3) — cột chưa bị bỏ
        vì lý do tương thích. Bài này canh việc con số ấy KHÔNG được cưỡng chế
        trở lại một cách âm thầm.
        """
        from app import auth, tenant_admin

        _set_plan(throwaway_tenant, "free")  # max_seats = 3, nhưng không ai đọc
        created = []
        try:
            for _ in range(3):
                name = f"seat{uuid.uuid4().hex[:9]}"
                user = auth.create_user(
                    username=name, email=f"{name}@example.com", password="@Minh123456"
                )
                created.append(user["id"])
                tenant_admin.add_member(throwaway_tenant, user["id"])

            name = f"seat{uuid.uuid4().hex[:9]}"
            extra = auth.create_user(
                username=name, email=f"{name}@example.com", password="@Minh123456"
            )
            created.append(extra["id"])
            # Người thứ TƯ, vượt `max_seats = 3` của gói Free. Phải vào được.
            tenant_admin.add_member(throwaway_tenant, extra["id"])
            assert "seats" not in plans.USAGE_METRICS, (
                "`seats` quay lại làm hạn mức gói — xem docstring bài này")
        finally:
            with system_scope("test cleanup: remove seat-test accounts"):
                for user_id in created:
                    for table in ("tenant_members", "refresh_tokens", "user_consents"):
                        try:
                            db._execute(
                                f"DELETE FROM {table} WHERE user_id = %s", (user_id,)
                            )
                        except Exception:
                            pass
                    try:
                        db._execute("DELETE FROM users WHERE id = %s", (user_id,))
                    except Exception:
                        pass

    def test_changing_an_existing_members_role_does_not_need_a_free_seat(
        self, throwaway_tenant
    ):
        """Nếu tính đổi vai trò là tiêu ghế, một tổ chức đầy ghế sẽ không sửa
        nổi vai trò của chính thành viên mình — bế tắc không lối ra ngoài việc
        nâng gói."""
        from app import auth, tenant_admin

        _set_plan(throwaway_tenant, "free")
        name = f"seat{uuid.uuid4().hex[:9]}"
        user = auth.create_user(
            username=name, email=f"{name}@example.com", password="@Minh123456"
        )
        try:
            tenant_admin.add_member(throwaway_tenant, user["id"])
            _set_plan(throwaway_tenant, "free")
            with system_scope("test: shrink the plan to exactly the seats in use"):
                db._execute(
                    "UPDATE plans SET max_seats = 1 WHERE plan_code = 'free'"
                )
            plans._clear_caches()
            # Đã là thành viên → không tiêu thêm ghế → phải qua.
            tenant_admin.add_member(throwaway_tenant, user["id"], "admin")
        finally:
            with system_scope("test cleanup: restore the trial plan and the account"):
                db._execute("UPDATE plans SET max_seats = 3 WHERE plan_code = 'free'")
                for table in ("tenant_members", "refresh_tokens", "user_consents"):
                    try:
                        db._execute(f"DELETE FROM {table} WHERE user_id = %s", (user["id"],))
                    except Exception:
                        pass
                db._execute("DELETE FROM users WHERE id = %s", (user["id"],))
            plans._clear_caches()


class TestPlanChangesAreRecorded:
    def test_exactly_one_open_subscription_survives_a_plan_change(
        self, throwaway_tenant
    ):
        """Chỉ mục duy nhất một phần là thứ ép điều này; test canh rằng thứ tự
        đóng-trước-mở-sau trong `_open_subscription` không bị đảo."""
        from app import tenant_admin

        tenant_admin.change_plan(throwaway_tenant, "plus", note="nâng gói")
        tenant_admin.change_plan(throwaway_tenant, "free", note="hạ lại")

        with system_scope("test: read the subscription history"):
            rows = db._fetch_all(
                "SELECT plan_code, ended_at FROM tenant_subscriptions "
                "WHERE tenant_id = %s ORDER BY started_at",
                (throwaway_tenant,),
            )
        open_rows = [r for r in rows if r["ended_at"] is None]
        assert len(open_rows) == 1
        assert open_rows[0]["plan_code"] == "free"
        # Lịch sử phải còn nguyên: một tranh chấp hoá đơn hỏi "ngày đó họ ở gói
        # nào", và câu đó chỉ trả lời được nếu các dòng cũ vẫn ở đấy.
        assert len(rows) == 3, [dict(r) for r in rows]

    def test_downgrading_below_current_usage_is_allowed_and_then_blocks_writes(
        self, throwaway_tenant
    ):
        """Hạ gói một tổ chức đang dùng vượt mức mới là hợp lệ (khách ngừng
        trả tiền). Kết quả đúng là họ GIỮ dữ liệu và không thêm được nữa — chứ
        không phải hệ thống từ chối thao tác hạ gói."""
        from app import tenant_admin

        with system_scope("test: pretend the plan is already exceeded"):
            db._execute("UPDATE plans SET max_api_keys = 0 WHERE plan_code = 'free'")
        plans._clear_caches()
        try:
            tenant_admin.change_plan(throwaway_tenant, "free")  # không ném
            with pytest.raises(plans.QuotaExceeded):
                plans.check_quota(throwaway_tenant, "api_keys", adding=1)
        finally:
            with system_scope("test cleanup: restore the trial plan"):
                db._execute(
                    "UPDATE plans SET max_api_keys = 1 WHERE plan_code = 'free'"
                )
            plans._clear_caches()


class TestLookupFailsClosed:
    def test_an_unknown_tenant_gets_the_tightest_plan_not_the_loosest(self):
        """Một lỗi tra cứu phải nghiêng về TỪ CHỐI.

        Nghiêng về cho phép nghĩa là mọi sự cố cơ sở dữ liệu đều mở toang hạn
        mức của cả nền tảng — và không có gì trong nhật ký nói rằng điều đó vừa
        xảy ra.
        """
        plan = plans.plan_for_tenant("khong-ton-tai-dau")
        assert plan["plan_code"] == "free"
        assert plan["max_samples"] == 500


class TestHopDongCuongChe:
    """API phải TỰ KHAI trần nào là cam kết, không để phía gọi suy từ con số.

    Tới v8, bảng `plans` mang bốn cột chưa cổng nào đọc — `max_workspaces`,
    `max_projects`, `included_training_credits`, `audit_retention_days`. Chúng
    có giá trị thật và đi thẳng ra API, nên giao diện và bảng giá trình bày
    chúng y hệt những trần đang chạy. Người mua không có cách nào phân biệt một
    cam kết với một chỗ giữ sẵn.
    """

    def test_bon_tran_hoan_lai_phai_bi_danh_dau_chua_cuong_che(self):
        for cot in ("max_workspaces", "max_projects",
                    "included_training_credits", "audit_retention_days"):
            assert plans.limit_is_enforced(cot) is False, (
                f"{cot} chưa có cổng nào đọc; khai là đã cưỡng chế biến một chỗ "
                f"giữ sẵn thành một lời hứa"
            )

    def test_dung_luong_la_tran_du_lieu_dang_cuong_che(self):
        assert plans.limit_is_enforced("max_storage_mb") is True

    def test_cot_chua_khai_mac_dinh_la_CHUA_cuong_che(self):
        """Hụt về phía khiêm tốn. Quên khai thì bị hiện là "chưa cưỡng chế", chứ
        không phải được quảng cáo như một cam kết."""
        assert plans.limit_is_enforced("max_thu_gi_do_moi_toanh") is False

    def test_moi_cot_sua_duoc_deu_phai_co_mat_trong_hop_dong(self):
        """Chốt chặn cho lần thêm hạn mức tiếp theo.

        Một cột sửa được nhưng không khai sẽ mặc định là "chưa cưỡng chế" — an
        toàn, nhưng im lặng. Bài này biến sự im lặng ấy thành một lượt chạy đỏ,
        để người thêm cột phải quyết định thay vì bỏ lửng.
        """
        khong_phai_han_muc = {
            "display_name", "description", "price_cents",
            "is_self_serve", "is_listed", "trial_days",
        }
        thieu = [
            c for c in plans.EDITABLE_PLAN_FIELDS
            if c not in khong_phai_han_muc and c not in plans.PLAN_LIMIT_ENFORCEMENT
        ]
        assert not thieu, (
            f"hạn mức chưa khai trong PLAN_LIMIT_ENFORCEMENT: {thieu}. "
            f"Khai True nếu có cổng thật đọc nó, False nếu chưa."
        )

    def test_anh_chup_muc_dung_mang_ca_co_cuong_che_lan_dung_luong_that(self, throwaway_tenant):
        anh = plans.usage_snapshot(throwaway_tenant)
        assert "storage" in anh, "dung lượng là trần dữ liệu DUY NHẤT từ v8"
        assert anh["storage"]["unit"] == "bytes"
        assert anh["storage"]["enforced"] is True
        for ten, khoi in anh.items():
            if ten.startswith("_"):
                continue
            assert "enforced" in khoi, f"chỉ số {ten} phải nói rõ có cưỡng chế không"
        assert anh["_plan"]["enforcement"]["max_workspaces"] is False

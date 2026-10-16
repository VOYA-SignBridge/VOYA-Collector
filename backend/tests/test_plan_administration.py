"""Sửa bảng giá lúc chạy.

Tồn tại vì migration v4.1 seed `plans` bằng `ON CONFLICT DO NOTHING` — cố ý,
để một lần khởi động lại không ghi đè mọi chỉnh tay của người vận hành. Nhưng
nếu không có đường sửa nào thì "chỉnh tay" chỉ có nghĩa là gõ SQL vào cơ sở dữ
liệu sản xuất; chú thích trong migration hoá ra hứa một API không tồn tại, và
đó chính là khoảng trống bộ test này lấp.
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
def scratch_plan():
    """Một gói dùng một lần, để test không đụng vào bốn gói thật.

    Sửa `trial` rồi khôi phục cũng chạy được, nhưng một test đỏ giữa chừng sẽ
    để lại bảng giá sản xuất ở trạng thái sai — và bảng giá là thứ quyết định
    ai bị chặn ở đâu.
    """
    import uuid

    code = f"test_{uuid.uuid4().hex[:8]}"
    with system_scope("test: create a throwaway plan"):
        db._execute(
            "INSERT INTO plans(plan_code, display_name, max_samples, price_cents) "
            "VALUES(%s, %s, %s, %s)",
            (code, "Gói thử", 100, 0),
        )
    plans._clear_caches()
    yield code
    with system_scope("test cleanup: remove the throwaway plan"):
        db._execute("DELETE FROM plans WHERE plan_code = %s", (code,))
    plans._clear_caches()


class TestUpdatePlan:
    def test_editableField_isPersisted(self, scratch_plan):
        plans.update_plan(scratch_plan, {"max_samples": 999})

        assert plans.get_plan(scratch_plan)["max_samples"] == 999

    def test_updatedPlan_isVisibleImmediatelyDespiteTheCache(self, scratch_plan):
        """`get_plan` đệm 30 giây. Không xoá đệm sau khi ghi thì người vận hành
        vừa sửa hạn mức sẽ tải lại trang và thấy số cũ — rồi sửa lần nữa."""
        plans.get_plan(scratch_plan)  # nạp vào đệm
        plans.update_plan(scratch_plan, {"max_samples": 42})

        assert plans.get_plan(scratch_plan)["max_samples"] == 42

    def test_nullOnAnUnlimitableLimit_meansUnlimited(self, scratch_plan):
        plans.update_plan(scratch_plan, {"max_samples": None})

        assert plans.get_plan(scratch_plan)["max_samples"] is None

    def test_nullOnAFieldThatIsNotACeiling_isRefused(self, scratch_plan):
        """NULL nghĩa là "không giới hạn", và chỉ TRẦN mới mang được nghĩa đó.

        Bản trước dùng `max_api_keys` làm ví dụ, vì khi ấy nó là trần duy nhất
        không được phép vô hạn. v6 gỡ ràng buộc đó — gói Enterprise là "custom",
        nên MỌI trần đều nhận NULL — và cùng lượt đó ví dụ cũ hết hiệu lực.

        Luật thì không đổi, chỉ đổi chỗ áp dụng: `display_name` không phải một
        trần, nên NULL ở đó không có nghĩa gì cả. Cột NOT NULL sẽ chặn ở tầng
        cơ sở dữ liệu, nhưng thông điệp Postgres không nói được cho người vận
        hành phải làm gì.
        """
        with pytest.raises(plans.PlanError) as caught:
            plans.update_plan(scratch_plan, {"display_name": None})

        assert caught.value.status_code == 422

    def test_unknownField_isRefusedRatherThanIgnored(self, scratch_plan):
        """Bỏ qua âm thầm là cách một lỗi gõ sai trở thành "đã lưu rồi mà không
        đổi gì"."""
        with pytest.raises(plans.PlanError) as caught:
            plans.update_plan(scratch_plan, {"max_sample": 10})

        assert caught.value.status_code == 422

    def test_planCode_cannotBeRenamed(self, scratch_plan):
        """`plan_code` là khoá chính và có khoá ngoại từ `tenants` lẫn
        `tenant_subscriptions` trỏ tới. Đổi nó là đổi định danh của một gói
        đang được dùng."""
        with pytest.raises(plans.PlanError):
            plans.update_plan(scratch_plan, {"plan_code": "ten-khac"})

    def test_negativeLimit_isRefusedByTheDatabaseConstraint(self, scratch_plan):
        """`ck_plans_limits_non_negative` là chỗ chặn thật. Test này chứng minh
        ràng buộc đó CÓ chạy qua đường API, chứ không phải chỉ tồn tại trong
        lược đồ."""
        with pytest.raises(plans.PlanError) as caught:
            plans.update_plan(scratch_plan, {"max_samples": -5})

        assert caught.value.status_code == 422

    def test_unknownPlan_is404(self):
        with pytest.raises(plans.PlanError) as caught:
            plans.update_plan("khong-co-goi-nay", {"max_samples": 1})

        assert caught.value.status_code == 404


class TestQuotaFollowsTheEditedPlan:
    def test_loweringALimit_immediatelyBlocksTheNextWrite(self, scratch_plan):
        """Điểm của cả tính năng: sửa bảng giá phải đổi hành vi chặn NGAY, chứ
        không chờ triển khai lại. Không có khẳng định này thì "sửa được" chỉ
        nghĩa là một hàng trong bảng đã đổi."""
        from app import tenant_admin
        from conftest import purge_tenant
        import uuid

        tenant_id = f"pe{uuid.uuid4().hex[:10]}"
        tenant_admin.create_tenant(
            tenant_id, clone_catalog=False, plan_code=scratch_plan
        )
        try:
            # `api_keys` chứ không `classes`: từ v8 số lớp KHÔNG còn là hạn
            # mức thương mại. Bài này kiểm việc SỬA BẢNG GIÁ đổi hành vi chặn
            # ngay lập tức, nên nó cần một chỉ số còn sống làm phương tiện.
            plans.update_plan(scratch_plan, {"max_api_keys": 0})
            with pytest.raises(plans.QuotaExceeded):
                plans.check_quota(tenant_id, "api_keys", adding=1)

            plans.update_plan(scratch_plan, {"max_api_keys": None})
            plans.check_quota(tenant_id, "api_keys", adding=1)  # không ném
        finally:
            purge_tenant(tenant_id)
            plans._clear_caches()


class TestDoiGoiLaMotGiaoDich:
    """`change_plan` phải hoặc ghi cả hai vế, hoặc không ghi vế nào.

    Vì sao phải có bài này (v8, 25/08/2026)
    ---------------------------------------
    Bản trước gọi hai `_execute` liên tiếp, và `_cursor()` dùng `with conn:` nên
    MỖI lượt gọi là một giao dịch riêng. Đường đi hạnh phúc vẫn xanh: cả hai câu
    chạy, cả hai commit, mọi phép kiểm đều đúng.

    Cái sai chỉ hiện ra khi câu thứ hai hỏng — và khi đó nó để lại:

        tenants.plan_code       = gói MỚI, đã có hiệu lực cưỡng chế
        tenant_subscriptions    = KHÔNG có dòng nào cho gói mới

    Tức là một tổ chức bị tính theo một gói mà lịch sử không hề ghi nhận. Không
    phép kiểm nào bắt được, vì cái sai là một dòng THIẾU chứ không phải một dòng
    sai. Nên bài test phải BƠM lỗi vào giữa hai vế; test đường hạnh phúc không
    chứng minh được tính nguyên tử.
    """

    def test_ve_hai_hong_thi_ve_mot_cung_khong_con(self, monkeypatch):
        from app import tenant_admin
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope
        from conftest import purge_tenant

        tid = f"atm{uuid.uuid4().hex[:9]}"
        tenant_admin.create_tenant(tid, clone_catalog=False, plan_code="free")
        try:
            def _no_giua_chung(*a, **kw):
                raise RuntimeError("chet may giua hai ve")

            monkeypatch.setattr(tenant_admin, "_open_subscription", _no_giua_chung)
            with pytest.raises(RuntimeError):
                tenant_admin.change_plan(tid, "pro")

            with system_scope("test: doc lai goi sau khi bom loi"):
                rows = _fetch_all(
                    "SELECT plan_code FROM tenants WHERE tenant_id = %s", (tid,))
            assert rows[0]["plan_code"] == "free", (
                "vế một phải bị cuộn lại cùng vế hai — nếu không, tổ chức bị tính "
                "theo một gói mà lịch sử không ghi nhận"
            )
        finally:
            purge_tenant(tid)

    def test_dong_truoc_mo_sau_cung_la_mot_giao_dich(self, monkeypatch):
        """Hai câu BÊN TRONG `_open_subscription` cũng phải cùng sống cùng chết.

        Đóng được dòng cũ rồi mở dòng mới hỏng sẽ để lại một tenant KHÔNG có
        đăng ký nào đang mở — đúng trạng thái mà chỉ mục duy nhất một phần
        `uq_tenant_subscriptions_open` sinh ra để canh, và nó là trạng thái
        THIẾU nên chỉ mục ấy im lặng.
        """
        from app import tenant_admin
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope
        from conftest import purge_tenant

        tid = f"atm{uuid.uuid4().hex[:9]}"
        tenant_admin.create_tenant(tid, clone_catalog=False, plan_code="free")
        try:
            with system_scope("test: dem dong dang mo truoc khi bom loi"):
                truoc = _fetch_all(
                    "SELECT subscription_id FROM tenant_subscriptions "
                    " WHERE tenant_id = %s AND ended_at IS NULL", (tid,))

            that = tenant_admin._open_subscription

            def _hong_o_cau_hai(tenant_id, plan_code, **kw):
                cur = kw.get("cur")
                cur.execute(
                    "UPDATE tenant_subscriptions SET ended_at = NOW(), "
                    "status = 'superseded' "
                    " WHERE tenant_id = %s AND ended_at IS NULL", (tenant_id,))
                raise RuntimeError("chet may sau khi dong, truoc khi mo")

            monkeypatch.setattr(tenant_admin, "_open_subscription", _hong_o_cau_hai)
            with pytest.raises(RuntimeError):
                tenant_admin.change_plan(tid, "pro")
            monkeypatch.setattr(tenant_admin, "_open_subscription", that)

            with system_scope("test: dem lai dong dang mo"):
                sau = _fetch_all(
                    "SELECT subscription_id FROM tenant_subscriptions "
                    " WHERE tenant_id = %s AND ended_at IS NULL", (tid,))
            assert len(sau) == len(truoc), (
                "câu đóng phải bị cuộn lại cùng câu mở — nếu không, tenant không "
                "còn đăng ký nào đang mở và chỉ mục duy nhất không kêu"
            )
        finally:
            purge_tenant(tid)

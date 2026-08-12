"""Sửa bảng giá lúc chạy.

Tồn tại vì migration v4.1 seed `plans` bằng `ON CONFLICT DO NOTHING` — cố ý,
để một lần khởi động lại không ghi đè mọi chỉnh tay của người vận hành. Nhưng
nếu không có đường sửa nào thì "chỉnh tay" chỉ có nghĩa là gõ SQL vào cơ sở dữ
liệu sản xuất; chú thích trong migration hoá ra hứa một API không tồn tại, và
đó chính là khoảng trống bộ test này lấp.
"""

from __future__ import annotations

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

    def test_nullOnAFieldThatCannotBeUnlimited_isRefused(self, scratch_plan):
        """`max_api_keys` NULL sẽ có nghĩa "vô hạn khoá", thứ bảng giá không
        định nghĩa. Cột NOT NULL sẽ chặn ở tầng cơ sở dữ liệu, nhưng thông điệp
        Postgres không nói được cho người vận hành phải làm gì."""
        with pytest.raises(plans.PlanError) as caught:
            plans.update_plan(scratch_plan, {"max_api_keys": None})

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
            plans.update_plan(scratch_plan, {"max_classes": 0})
            with pytest.raises(plans.QuotaExceeded):
                plans.check_quota(tenant_id, "classes", adding=1)

            plans.update_plan(scratch_plan, {"max_classes": None})
            plans.check_quota(tenant_id, "classes", adding=1)  # không ném
        finally:
            purge_tenant(tenant_id)
            plans._clear_caches()

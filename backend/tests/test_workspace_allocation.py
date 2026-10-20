"""Cây phạm vi Workspace/Project và phép cấp phát hạn mức xuống cấp project.

Vì sao tệp này canh chủ yếu những thứ phải TỪ CHỐI
---------------------------------------------------
Cấp phát là một con số **trang trí** nếu tổng của nó vượt được trần gói: ba
project mỗi cái "được" 1.000 mẫu trong khi gói cho 500 thì bảng vẫn hiển thị
đẹp, và cái sai chỉ lộ ra khi ai đó chạm trần thật — lúc đó người dùng đã tin
vào con số suốt nhiều tuần. Nên phần lớn phép kiểm ở đây hỏi *"nó có chặn
không"*, chứ không phải *"nó có ghi được không"*.

Ba bất biến được canh
---------------------
1. **Trần gói cưỡng chế trên TỔNG**, không phải trên từng dòng.
2. **`NULL` là "không giới hạn", không phải "bằng không"** — đọc nhầm chiều này
   sẽ chặn toàn bộ hoạt động của một project thay vì mở nó ra.
3. **Project của tenant khác không cấp phát được**, kể cả khi biết đúng UUID.
"""

from __future__ import annotations

import uuid

import pytest

from app import workspace_admin as wa
from app.storage import metadata_db as db
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def tenant_plus():
    """Tenant gói `plus` — cần một gói CÓ trần để phép kiểm vượt trần có nghĩa."""
    from app import plans, tenant_admin
    from conftest import purge_tenant

    tenant_id = f"ws{uuid.uuid4().hex[:10]}"
    tenant_admin.create_tenant(
        tenant_id, display_name="Tổ Chức Thử", clone_catalog=False, plan_code="plus"
    )
    plans._clear_caches()
    yield tenant_id
    try:
        purge_tenant(tenant_id)
    except Exception:
        pass
    plans._clear_caches()


def _ws_with_projects(tenant_id: str, n: int = 2):
    ws = wa.create_workspace(tenant_id, name="Khoa CNTT")
    wid = str(ws["workspace_id"])
    projects = [
        str(wa.create_project(tenant_id, wid, name=f"Lớp K{47 + i}")["project_id"])
        for i in range(n)
    ]
    return wid, projects


def _ceiling(tenant_id: str, metric: str = "samples") -> int:
    value = wa._tenant_ceiling(tenant_id)[metric]
    if value is None:
        pytest.skip("gói thử nghiệm không đặt trần cho chỉ tiêu này")
    return int(value)


class TestCeilingIsEnforcedOnTheSum:
    def test_single_allocation_within_ceiling_is_accepted(self, tenant_plus):
        wid, (p1, _) = _ws_with_projects(tenant_plus)
        cap = _ceiling(tenant_plus)

        wa.set_allocation(
            tenant_plus, workspace_id=wid, project_id=p1,
            metric="samples", allocated=cap // 2, actor_user_id=None,
        )
        table = wa.list_allocations(tenant_plus, wid)
        assert table["allocated_total"]["samples"] == cap // 2
        assert table["remaining"]["samples"] == cap - cap // 2

    def test_second_allocation_that_overflows_the_sum_is_refused(self, tenant_plus):
        """Đây là phép kiểm mà cả tính năng đứng hoặc đổ theo.

        Từng dòng đều dưới trần, nhưng TỔNG thì không. Một cài đặt chỉ so từng
        dòng với trần sẽ nhận cả hai và vẫn "chạy đúng" ở mọi phép kiểm khác.
        """
        wid, (p1, p2) = _ws_with_projects(tenant_plus)
        cap = _ceiling(tenant_plus)

        wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p1,
                          metric="samples", allocated=cap, actor_user_id=None)

        with pytest.raises(wa.WorkspaceError) as exc:
            wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p2,
                              metric="samples", allocated=1, actor_user_id=None)
        assert exc.value.status_code == 409

    def test_reducing_a_project_frees_room_for_another(self, tenant_plus):
        """Sửa một dòng phải tính lại tổng, không cộng dồn.

        Nếu phép kiểm cộng cả dòng đang sửa vào "đã cấp", thì hạ 1.000 xuống 100
        vẫn báo vượt trần — và không ai chia lại được hạn mức đã trót cấp.
        """
        wid, (p1, p2) = _ws_with_projects(tenant_plus)
        cap = _ceiling(tenant_plus)

        wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p1,
                          metric="samples", allocated=cap, actor_user_id=None)
        wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p1,
                          metric="samples", allocated=cap // 4, actor_user_id=None)
        wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p2,
                          metric="samples", allocated=cap // 4, actor_user_id=None)

        assert wa.list_allocations(tenant_plus, wid)["allocated_total"]["samples"] == \
            2 * (cap // 4)


class TestNullMeansUnlimited:
    def test_null_allocation_is_stored_and_not_counted_as_zero(self, tenant_plus):
        wid, (p1, _) = _ws_with_projects(tenant_plus)

        wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p1,
                          metric="samples", allocated=None, actor_user_id=None)
        table = wa.list_allocations(tenant_plus, wid)
        cell = table["projects"][0]["allocations"]["samples"] \
            if table["projects"][0]["project_id"] == p1 \
            else table["projects"][1]["allocations"]["samples"]

        assert cell["allocated"] is None
        # KHÔNG được cộng 0 vào tổng: "không giới hạn" không phải "không dùng gì".
        assert table["allocated_total"]["samples"] == 0

    def test_negative_allocation_is_refused(self, tenant_plus):
        wid, (p1, _) = _ws_with_projects(tenant_plus)
        with pytest.raises(wa.WorkspaceError) as exc:
            wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p1,
                              metric="samples", allocated=-1, actor_user_id=None)
        assert exc.value.status_code == 422


class TestScopeConfinement:
    def test_unknown_metric_is_refused(self, tenant_plus):
        """Tên gõ sai phải bật ra, không được tạo một dòng không ai đọc."""
        wid, (p1, _) = _ws_with_projects(tenant_plus)
        with pytest.raises(wa.WorkspaceError) as exc:
            wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p1,
                              metric="max_samples", allocated=10, actor_user_id=None)
        assert exc.value.status_code == 422

    def test_project_of_another_workspace_is_refused(self, tenant_plus):
        """Biết đúng UUID không đủ — project phải nằm trong workspace được nêu."""
        wid_a, (p_a, _) = _ws_with_projects(tenant_plus)
        ws_b = wa.create_workspace(tenant_plus, name="Khoa Ngoại Ngữ")

        with pytest.raises(wa.WorkspaceError) as exc:
            wa.set_allocation(tenant_plus, workspace_id=str(ws_b["workspace_id"]),
                              project_id=p_a, metric="samples", allocated=1,
                              actor_user_id=None)
        assert exc.value.status_code == 404

    def test_allocation_rows_do_not_leak_across_tenants(self, tenant_plus):
        """RLS phải giữ bảng cấp phát trong đúng tenant của nó.

        Đọc dưới `system_scope` để đếm được TỔNG số dòng, rồi đọc lại qua đường
        ứng dụng: nếu hai con số bằng nhau trong khi tồn tại tenant khác có
        cấp phát, thì policy đang không lọc gì cả.
        """
        wid, (p1, _) = _ws_with_projects(tenant_plus)
        wa.set_allocation(tenant_plus, workspace_id=wid, project_id=p1,
                          metric="samples", allocated=1, actor_user_id=None)

        with system_scope("test: đếm toàn bộ bảng cấp phát"):
            everything = db._fetch_all(
                "SELECT tenant_id FROM project_allocations", ()
            )
        mine = [r for r in everything if r["tenant_id"] == tenant_plus]
        assert len(mine) == 1

        scoped = db._fetch_all(
            "SELECT tenant_id FROM project_allocations WHERE tenant_id = %s",
            (tenant_plus,),
        )
        assert len(scoped) == 1

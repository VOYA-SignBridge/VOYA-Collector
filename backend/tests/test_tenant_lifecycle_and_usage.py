"""Xuất dữ liệu, xoá vĩnh viễn, và đo mức dùng.

Xoá vĩnh viễn là thao tác KHÔNG hoàn tác được duy nhất trong hệ thống, nên
phần lớn tệp này canh những thứ phải TỪ CHỐI chứ không phải những thứ phải
chạy. Một cái phanh hỏng chỉ lộ ra đúng một lần, vào đúng lúc không cứu được.
"""

from __future__ import annotations

import json
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone

import pytest

from app import tenant_lifecycle, usage
from app.storage import metadata_db as db
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def doomed_tenant():
    """Tenant dùng một lần cho các test vòng đời.

    `clone_catalog=False`: bản sao danh mục tạo hàng trăm dòng và không test
    nào ở đây cần chúng; bỏ qua làm mỗi test nhanh hơn hẳn.
    """
    from app import plans, tenant_admin
    from conftest import purge_tenant

    tenant_id = f"lc{uuid.uuid4().hex[:10]}"
    tenant_admin.create_tenant(
        tenant_id, display_name="Sắp Đóng Cửa", clone_catalog=False, plan_code="plus"
    )
    plans._clear_caches()
    yield tenant_id
    # Tenant có thể đã bị chính test xoá hẳn; dọn phải chịu được điều đó.
    try:
        purge_tenant(tenant_id)
    except Exception:
        pass
    plans._clear_caches()


def _soft_delete(tenant_id: str, *, days_ago: int = 0) -> None:
    """Xoá mềm, và lùi mốc thời gian về quá khứ nếu cần vượt ân hạn."""
    with system_scope("test: soft-delete a tenant at a chosen moment"):
        db._execute(
            "UPDATE tenants SET deleted_at = NOW() - %s * INTERVAL '1 day', "
            "is_active = FALSE WHERE tenant_id = %s",
            (days_ago, tenant_id),
        )


# --------------------------------------------------------------------------- export


class TestExport:
    def test_the_bundle_carries_the_data_and_not_the_credentials(self, doomed_tenant):
        """Khoá API và bí mật webhook KHÔNG được nằm trong tệp zip.

        Chúng là thông tin xác thực, không phải dữ liệu của khách hàng; một
        gói gửi qua email không phải chỗ để chúng đi ra ngoài.
        """
        from app import api_keys, webhooks

        api_keys.create_key(doomed_tenant, name="ci")
        webhooks.create_endpoint(doomed_tenant, url="https://hooks.example.com/x")

        job = tenant_lifecycle.request_export(doomed_tenant, scope="metadata")
        result = tenant_lifecycle.run_export(job["export_id"])
        assert result["status"] == "ready"

        path = tenant_lifecycle.export_file(doomed_tenant, job["export_id"])
        with zipfile.ZipFile(path) as bundle:
            names = set(bundle.namelist())
            tenant_json = json.loads(bundle.read("data/tenant.json"))
            readme = bundle.read("README.txt").decode("utf-8")

        assert "data/tenant.json" in names
        assert "data/samples.json" in names
        assert not any("api_keys" in n for n in names), names
        assert not any("webhook_endpoints" in n for n in names), names
        assert tenant_json[0]["tenant_id"] == doomed_tenant
        # README phải NÓI RÕ cái gì bị cố ý bỏ ra, nếu không người nhận sẽ
        # tưởng bản xuất không đầy đủ và mở phiếu hỏi.
        assert "khoá API" in readme.lower() or "khoá api" in readme.lower()

        path.unlink(missing_ok=True)

    def test_one_tenant_cannot_download_anothers_export(self, doomed_tenant):
        from app import plans, tenant_admin
        from conftest import purge_tenant

        stranger = f"lc{uuid.uuid4().hex[:10]}"
        tenant_admin.create_tenant(stranger, clone_catalog=False, plan_code="free")
        plans._clear_caches()
        try:
            job = tenant_lifecycle.request_export(doomed_tenant)
            tenant_lifecycle.run_export(job["export_id"])
            with pytest.raises(tenant_lifecycle.LifecycleError) as caught:
                tenant_lifecycle.export_file(stranger, job["export_id"])
            assert caught.value.status_code == 404
        finally:
            purge_tenant(stranger)
            plans._clear_caches()

    def test_an_expired_export_refuses_to_download(self, doomed_tenant):
        job = tenant_lifecycle.request_export(doomed_tenant)
        tenant_lifecycle.run_export(job["export_id"])
        with system_scope("test: age the export past its TTL"):
            db._execute(
                "UPDATE tenant_exports SET expires_at = NOW() - INTERVAL '1 day' "
                "WHERE export_id = %s",
                (job["export_id"],),
            )
        with pytest.raises(tenant_lifecycle.LifecycleError) as caught:
            tenant_lifecycle.export_file(doomed_tenant, job["export_id"])
        assert caught.value.status_code == 410

    def test_cleanup_removes_the_file_from_disk(self, doomed_tenant):
        """Bản xuất là bản sao ĐẦY ĐỦ dữ liệu của một tổ chức. Đánh dấu hết hạn
        trong bảng mà để tệp nằm lại là chưa dọn gì cả."""
        job = tenant_lifecycle.request_export(doomed_tenant)
        tenant_lifecycle.run_export(job["export_id"])
        path = tenant_lifecycle.export_file(doomed_tenant, job["export_id"])
        assert path.exists()

        with system_scope("test: age the export past its TTL"):
            db._execute(
                "UPDATE tenant_exports SET expires_at = NOW() - INTERVAL '1 day' "
                "WHERE export_id = %s",
                (job["export_id"],),
            )
        tenant_lifecycle.cleanup_expired_exports()
        assert not path.exists()


# --------------------------------------------------------------------------- purge


class TestPurgeBrakes:
    def test_the_bootstrap_tenant_can_never_be_purged(self):
        with pytest.raises(tenant_lifecycle.LifecycleError) as caught:
            tenant_lifecycle.purge_tenant(
                DEFAULT_TENANT_ID, confirm_tenant_id=DEFAULT_TENANT_ID,
                skip_export_check=True,
            )
        assert caught.value.status_code == 409

    def test_a_mismatched_confirmation_refuses(self, doomed_tenant):
        """Không phải nghi thức: một lời gọi API bị lặp, một nút bấm nhầm, một
        script chạy sai biến đều vượt qua được một cờ boolean."""
        _soft_delete(doomed_tenant, days_ago=999)
        with pytest.raises(tenant_lifecycle.LifecycleError) as caught:
            tenant_lifecycle.purge_tenant(
                doomed_tenant, confirm_tenant_id="go-dai-cho-xong",
                skip_export_check=True,
            )
        assert caught.value.status_code == 400

    def test_a_live_tenant_cannot_be_purged(self, doomed_tenant):
        with pytest.raises(tenant_lifecycle.LifecycleError) as caught:
            tenant_lifecycle.purge_tenant(
                doomed_tenant, confirm_tenant_id=doomed_tenant, skip_export_check=True
            )
        assert "chưa bị xoá mềm" in str(caught.value)

    def test_the_grace_period_is_enforced(self, doomed_tenant):
        _soft_delete(doomed_tenant, days_ago=0)
        with pytest.raises(tenant_lifecycle.LifecycleError) as caught:
            tenant_lifecycle.purge_tenant(
                doomed_tenant, confirm_tenant_id=doomed_tenant, skip_export_check=True
            )
        assert "ân hạn" in str(caught.value)

    def test_purge_is_refused_without_an_export(self, doomed_tenant):
        """Kịch bản hỏng hay gặp nhất không phải kẻ xấu — mà là một người vận
        hành xoá đúng tenant mình định xoá rồi phát hiện chưa ai lấy dữ liệu
        ra."""
        _soft_delete(doomed_tenant, days_ago=999)
        with pytest.raises(tenant_lifecycle.LifecycleError) as caught:
            tenant_lifecycle.purge_tenant(
                doomed_tenant, confirm_tenant_id=doomed_tenant
            )
        assert caught.value.status_code == 409
        assert "bản xuất" in str(caught.value)

    def test_the_preview_reports_real_numbers_and_changes_nothing(self, doomed_tenant):
        """"Bạn có chắc không?" mà không kèm con số là câu hỏi người ta bấm qua
        theo phản xạ."""
        preview = tenant_lifecycle.purge_preview(doomed_tenant)
        assert preview["can_purge"] is False
        assert preview["blockers"]
        assert "row_counts" in preview

        with system_scope("test: the tenant is still there after a preview"):
            rows = db._fetch_all(
                "SELECT tenant_id FROM tenants WHERE tenant_id = %s", (doomed_tenant,)
            )
        assert rows, "preview đã xoá mất tenant"


class TestPurgeExecution:
    def test_a_full_purge_leaves_a_ledger_row_and_no_tenant(self, doomed_tenant):
        from app import api_keys, webhooks

        api_keys.create_key(doomed_tenant, name="sẽ biến mất")
        webhooks.create_endpoint(doomed_tenant, url="https://hooks.example.com/gone")
        job = tenant_lifecycle.request_export(doomed_tenant)
        tenant_lifecycle.run_export(job["export_id"])
        _soft_delete(doomed_tenant, days_ago=999)

        result = tenant_lifecycle.purge_tenant(
            doomed_tenant, confirm_tenant_id=doomed_tenant, reason="test đóng cửa"
        )

        with system_scope("test: nothing of the tenant survives"):
            assert db._fetch_all(
                "SELECT 1 FROM tenants WHERE tenant_id = %s", (doomed_tenant,)
            ) == []
            for table in ("api_keys", "webhook_endpoints", "tenant_subscriptions"):
                assert db._fetch_all(
                    f"SELECT 1 FROM {table} WHERE tenant_id = %s", (doomed_tenant,)
                ) == [], f"{table} còn sót dòng"
            ledger = db._fetch_all(
                "SELECT tenant_id, reason FROM tenant_purges WHERE purge_id = %s",
                (result["purge_id"],),
            )

        # Sổ phải SỐNG SÓT qua chính việc nó ghi lại. Đó là lý do bảng này cố ý
        # không có khoá ngoại tới `tenants`.
        assert ledger and ledger[0]["tenant_id"] == doomed_tenant
        assert ledger[0]["reason"] == "test đóng cửa"

        with system_scope("test cleanup: remove the ledger row"):
            db._execute(
                "DELETE FROM tenant_purges WHERE purge_id = %s", (result["purge_id"],)
            )

    def test_a_member_of_two_tenants_survives_the_purge_of_one(self, doomed_tenant):
        """Xoá tài khoản của họ vì MỘT tổ chức đóng cửa là lấy mất quyền truy
        cập ở tổ chức kia — và để lại một bản ghi thành viên trỏ tới tài khoản
        không còn tồn tại."""
        from app import auth, plans, tenant_admin
        from conftest import purge_tenant

        survivor_tenant = f"lc{uuid.uuid4().hex[:10]}"
        tenant_admin.create_tenant(
            survivor_tenant, clone_catalog=False, plan_code="plus"
        )
        plans._clear_caches()

        name = f"both{uuid.uuid4().hex[:8]}"
        user = auth.create_user(
            username=name, email=f"{name}@example.com", password="@Minh123456"
        )
        try:
            tenant_admin.set_home_tenant(user["id"], doomed_tenant, role="admin")
            tenant_admin.add_member(survivor_tenant, user["id"])

            job = tenant_lifecycle.request_export(doomed_tenant)
            tenant_lifecycle.run_export(job["export_id"])
            _soft_delete(doomed_tenant, days_ago=999)
            tenant_lifecycle.purge_tenant(
                doomed_tenant, confirm_tenant_id=doomed_tenant
            )

            with system_scope("test: the shared account survived and moved home"):
                rows = db._fetch_all(
                    "SELECT tenant_id FROM users WHERE id = %s", (user["id"],)
                )
            assert rows, "tài khoản dùng chung bị xoá cùng tổ chức đóng cửa"
            assert rows[0]["tenant_id"] == survivor_tenant
        finally:
            with system_scope("test cleanup: remove the shared account"):
                for table in ("tenant_members", "refresh_tokens", "user_consents"):
                    try:
                        db._execute(
                            f"DELETE FROM {table} WHERE user_id = %s", (user["id"],)
                        )
                    except Exception:
                        pass
                try:
                    db._execute("DELETE FROM users WHERE id = %s", (user["id"],))
                except Exception:
                    pass
                db._execute("DELETE FROM tenant_purges WHERE tenant_id = %s",
                            (doomed_tenant,))
            purge_tenant(survivor_tenant)
            plans._clear_caches()

    def test_the_bootstrap_tenants_files_are_never_touched(self):
        """Tenant gốc dùng bố cục thư mục LỊCH SỬ ngay tại gốc dataset. Xoá nó
        sẽ cuốn theo dữ liệu của cả nền tảng, nên hàm xoá tệp phải từ chối
        thẳng chứ không tin vào việc người gọi đã kiểm."""
        assert tenant_lifecycle._remove_tenant_files(DEFAULT_TENANT_ID) == (0, 0)


# --------------------------------------------------------------------------- usage


class TestUsageRollup:
    def test_rollupDay_writesRowsRatherThanSilentlyWritingNothing(self):
        """Bằng chứng cái phễu THẬT SỰ chảy — và nó đã từng không chảy.

        `_upsert` ban đầu nằm NGOÀI khối `system_scope`, nên RLS từ chối sạch
        mọi lượt ghi vào `tenant_usage_daily`. Cả tính năng đo mức dùng ghi ra
        số không, mỗi ngày, mãi mãi, chỉ để lại một dòng lỗi trong nhật ký của
        một tác vụ nền mà không ai đọc.

        Test "gộp hai lần cho cùng kết quả" bên dưới KHÔNG bắt được: hai tập
        rỗng cũng bằng nhau. Đây là khẳng định phải có trước nó — số dòng ghi
        được phải khác không khi dữ liệu nguồn có tồn tại.
        """
        with system_scope("test: find a day that definitely has samples"):
            rows = db._fetch_all(
                "SELECT created_at::date AS day, count(*) AS n FROM samples "
                "WHERE created_at IS NOT NULL "
                "GROUP BY created_at::date ORDER BY n DESC LIMIT 1"
            )
        if not rows:
            pytest.skip("bản sao không có mẫu nào mang created_at")

        busiest = rows[0]["day"]
        written = usage.rollup_day(busiest, include_storage=False)
        assert written["samples_created"] > 0, (
            "gộp xong mà không ghi được hàng nào — kiểm xem lượt ghi có nằm "
            "trong system_scope không"
        )

        with system_scope("test: the rows really landed"):
            stored = db._fetch_all(
                "SELECT sum(value) AS total FROM tenant_usage_daily "
                "WHERE usage_date = %s AND metric = 'samples_created'",
                (busiest,),
            )
        assert int(stored[0]["total"] or 0) == int(rows[0]["n"])

    def test_rolling_up_twice_gives_the_same_answer(self, doomed_tenant):
        """Tác vụ nền có thể chạy hai lần sau một lần khởi động lại, và người
        vận hành phải lấp được khoảng trống bằng tay sau sự cố."""
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()
        usage.rollup_day(yesterday, include_storage=False)

        with system_scope("test: read the rollup after one run"):
            first = db._fetch_all(
                "SELECT metric, value FROM tenant_usage_daily "
                "WHERE usage_date = %s ORDER BY tenant_id, metric",
                (yesterday,),
            )
        usage.rollup_day(yesterday, include_storage=False)
        with system_scope("test: read the rollup after two runs"):
            second = db._fetch_all(
                "SELECT metric, value FROM tenant_usage_daily "
                "WHERE usage_date = %s ORDER BY tenant_id, metric",
                (yesterday,),
            )
        assert [dict(r) for r in first] == [dict(r) for r in second]

    def test_a_softdeleted_sample_still_counts_for_the_day_it_was_recorded(self):
        """Hoá đơn tháng trước KHÔNG được đổi số sau khi đã gửi đi.

        Đây là ranh giới giữa `usage` (đã TỪNG dùng, bất biến) và
        `plans.current_usage` (ĐANG dùng, phải khớp thực tế). Tính trực tiếp
        trên bảng nguồn có lọc `deleted_at` sẽ lặng lẽ viết lại lịch sử mỗi lần
        ai đó dọn dữ liệu.
        """
        sql = usage._ROLLUPS["samples_created"]
        assert "deleted_at" not in sql, (
            "chỉ số ĐÃ TỪNG thu không được lọc theo xoá mềm — xem docstring "
            "đầu app/usage.py"
        )

    def test_storage_is_taken_as_the_last_reading_not_a_sum(self, doomed_tenant):
        """Cộng ba mươi lần đo dung lượng lại với nhau cho ra một con số không
        có nghĩa gì cả."""
        today = datetime.now(timezone.utc).date()
        with system_scope("test: write two storage readings"):
            for offset, value in ((2, 100), (1, 250)):
                db._execute(
                    "INSERT INTO tenant_usage_daily(tenant_id, usage_date, metric, value) "
                    "VALUES(%s, %s, %s, %s) ON CONFLICT (tenant_id, usage_date, metric) "
                    "DO UPDATE SET value = EXCLUDED.value",
                    (doomed_tenant, today - timedelta(days=offset),
                     usage.STORAGE_METRIC, value),
                )
        totals = usage.usage_totals(doomed_tenant, days=30)
        assert totals[usage.STORAGE_METRIC] == 250, "dung lượng bị cộng dồn"

    def test_a_day_with_no_row_is_absent_rather_than_zero(self, doomed_tenant):
        """Chèn số 0 cho ngày chưa gộp khiến "chưa tính" trông y hệt "không có
        hoạt động" — hai chuyện rất khác nhau khi đọc biểu đồ."""
        series = usage.usage_series(doomed_tenant, days=30)
        for metric, points in series.items():
            dates = [p["date"] for p in points]
            assert len(dates) == len(set(dates)), metric
        assert all(isinstance(v, list) for v in series.values())

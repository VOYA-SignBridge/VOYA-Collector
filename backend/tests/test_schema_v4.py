"""Bất biến của lược đồ v4 — mặt phẳng thương mại.

Ba mục ở đây đều chốt một lỗi ĐÃ mắc trong chính đợt làm này, không phải một
mối lo giả định. Mỗi test ghi rõ lỗi nào, vì một test chốt bất biến mà không
nói tại sao sẽ bị người sau xoá đi khi nó cản đường.
"""

from __future__ import annotations

import pytest

from app.storage import metadata_db as db
from app.storage import rls


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


V4_TENANT_TABLES = (
    "api_keys", "tenant_exports", "tenant_subscriptions", "tenant_usage_daily",
    "webhook_deliveries", "webhook_endpoints",
)
V4_PLATFORM_TABLES = ("plans", "tenant_purges")


def _columns(table: str) -> dict:
    return {
        r["column_name"]: r
        for r in db._fetch_all(
            "SELECT column_name, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s",
            (table,),
        )
    }


class TestTablesExistAndAreScopedCorrectly:
    @pytest.mark.parametrize("table", V4_TENANT_TABLES + V4_PLATFORM_TABLES)
    def test_the_table_exists(self, table):
        assert _columns(table), f"bảng {table} chưa được tạo"

    @pytest.mark.parametrize("table", V4_TENANT_TABLES)
    def test_tenant_tables_have_rls_on_and_forced(self, table):
        """`FORCE` chứ không chỉ `ENABLE`. Không có FORCE, chủ sở hữu bảng bỏ
        qua chính sách — và trên nhiều bản triển khai, vai ứng dụng LÀ chủ."""
        rows = db._fetch_all(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = %s",
            (table,),
        )
        assert rows and rows[0]["relrowsecurity"] is True, f"{table}: RLS chưa bật"
        assert rows[0]["relforcerowsecurity"] is True, f"{table}: RLS chưa FORCE"
        assert table in rls.RLS_TABLES

    @pytest.mark.parametrize("table", V4_PLATFORM_TABLES)
    def test_platform_tables_are_deliberately_outside_rls(self, table):
        """`plans` là bảng giá dùng chung; `tenant_purges` ghi lại việc một
        tenant đã biến mất, nên không còn tenant nào để phạm vi hoá theo.

        Test này là bản ghi của một QUYẾT ĐỊNH. Nếu ai đó thêm RLS cho chúng,
        nó đỏ và buộc người đó đọc lý do trước khi đổi.
        """
        assert table not in rls.RLS_TABLES
        assert table not in db.TENANT_SCOPED_TABLES

    def test_every_v4_tenant_table_has_a_tenant_foreign_key(self):
        """Vòng lặp khoá ngoại tenant chạy hai lần, lần hai ở CUỐI danh sách
        migration. Bảng v4 được chèn TRƯỚC lần hai đó để được nhặt miễn phí —
        nếu ai chuyển chúng xuống sau, test này đỏ."""
        names = {f"fk_{t}_tenant" for t in V4_TENANT_TABLES}
        found = {
            r["conname"]
            for r in db._fetch_all(
                "SELECT conname FROM pg_constraint WHERE conname = ANY(%s)",
                (list(names),),
            )
        }
        assert found == names, f"thiếu khoá ngoại tenant: {sorted(names - found)}"


class TestPlanColumnCannotBeNull:
    def test_plan_code_is_not_null(self):
        """Một tenant không gói đi qua MỌI cổng hạn mức mà không bị hỏi gì."""
        assert _columns("tenants")["plan_code"]["is_nullable"] == "NO"

    def test_plan_code_also_has_a_default(self):
        """NOT NULL mà không có mặc định là một cái bẫy, và nó đã sập.

        Câu `INSERT INTO tenants(tenant_id, display_name, slug)` ở đầu danh
        sách migration không nêu `plan_code`. Lượt chạy đầu vô hại (cột chưa
        có); từ lượt thứ HAI nó vi phạm NOT NULL và bị `ensure_tables` nuốt
        thành cảnh báo. Trên máy đã có tenant gốc thì không ai thấy gì — trên
        một bản cài mà hàng đó vắng, tenant gốc lặng lẽ không bao giờ ra đời.

        Mặc định là `trial`, tức gói CHẶT NHẤT: một đường chèn quên nêu gói
        nhận hạn mức nhỏ nhất, sai theo hướng chặn chứ không phải hướng mở.
        """
        default = _columns("tenants")["plan_code"]["column_default"]
        assert default is not None, "plan_code NOT NULL nhưng không có mặc định"
        assert "free" in default, default

    def test_the_bootstrap_insert_does_not_use_on_conflict(self):
        """Nguyên nhân gốc của lỗi trên, chốt ở dạng đọc được từ mã.

        `ON CONFLICT DO NOTHING` vẫn DỰNG tuple rồi mới phát hiện trùng, nên
        NOT NULL được kiểm trước. `WHERE NOT EXISTS` không sinh hàng nào khi
        hàng đã có, nên không có tuple nào để kiểm.
        """
        bootstrap = [
            s for s in db.MIGRATION_STATEMENTS
            if isinstance(s, str)
            and s.startswith("INSERT INTO tenants(tenant_id, display_name, slug)")
        ]
        assert bootstrap, "không tìm thấy câu chèn tenant gốc"
        for statement in bootstrap:
            assert "ON CONFLICT" not in statement, statement
            assert "WHERE NOT EXISTS" in statement, statement


class TestSeededPlans:
    def test_the_four_plans_are_present(self):
        codes = {r["plan_code"] for r in db._fetch_all("SELECT plan_code FROM plans")}
        assert {"enterprise", "free", "plus", "pro"} <= codes

    def test_the_enterprise_plan_is_not_offered_for_self_serve(self):
        """Nó không có hạn mức nào. Để nó tự đăng ký được là phát gói không
        giới hạn cho bất kỳ ai điền đúng một trường trong biểu mẫu.

        v6 tách đôi hai cờ này, và chúng KHÔNG còn đi cùng nhau. `internal`
        trước kia vừa ẩn vừa cấm tự đăng ký, nên một khẳng định gộp là đủ. Sau
        khi nó thành `enterprise`, gói này phải HIỆN trên bảng giá — đó là bậc
        cao nhất, khách hàng cần thấy để liên hệ — nhưng vẫn không được tự đăng
        ký. Cờ giữ cửa là `is_self_serve`; `is_listed` chỉ là chuyện trưng bày.
        """
        row = db._fetch_all(
            "SELECT is_self_serve, is_listed FROM plans WHERE plan_code = 'enterprise'"
        )[0]
        assert row["is_self_serve"] is False
        assert row["is_listed"] is True

    def test_the_default_tenant_is_on_the_unlimited_plan(self):
        """Nó giữ dữ liệu thật và không bao giờ nên bị một hạn mức thương mại
        chặn giữa chừng."""
        from app.tenancy import DEFAULT_TENANT_ID

        row = db._fetch_all(
            "SELECT plan_code FROM tenants WHERE tenant_id = %s", (DEFAULT_TENANT_ID,)
        )[0]
        assert row["plan_code"] == "enterprise"

    def test_every_live_tenant_has_exactly_one_open_subscription(self):
        """Chỉ mục duy nhất một phần ép điều này; test canh rằng backfill v4.3
        đã sinh dòng mở đầu cho MỌI tenant có sẵn, không chỉ tenant mới."""
        rows = db._fetch_all(
            "SELECT t.tenant_id, count(s.subscription_id) AS n "
            "FROM tenants t LEFT JOIN tenant_subscriptions s "
            "  ON s.tenant_id = t.tenant_id AND s.ended_at IS NULL "
            "WHERE t.deleted_at IS NULL GROUP BY t.tenant_id"
        )
        wrong = [dict(r) for r in rows if int(r["n"]) != 1]
        assert not wrong, f"tenant không có đúng một đăng ký đang mở: {wrong}"


class TestPurgeOrderIsSharedNotCopied:
    def test_conftest_imports_the_production_order(self):
        """Bản trước là một tuple chép tay trong conftest, song song với thứ tự
        mà hàm xoá thật cũng cần. Hai bản sao của một thứ tự phụ thuộc trôi ra
        khỏi nhau ở lần thêm bảng tiếp theo — và cái lệch lộ ra lúc xoá tenant
        thật trên sản xuất, không phải ở đây."""
        from conftest import _TENANT_PURGE_ORDER

        from app.tenant_lifecycle import PURGE_ORDER

        assert _TENANT_PURGE_ORDER is PURGE_ORDER

    def test_children_come_before_parents(self):
        """Thứ tự LÀ một phần của tính đúng, không phải sở thích."""
        from app.tenant_lifecycle import PURGE_ORDER

        position = {table: i for i, table in enumerate(PURGE_ORDER)}
        rows = db._fetch_all(
            "SELECT c.relname AS child, f.relname AS parent FROM pg_constraint k "
            "JOIN pg_class c ON c.oid = k.conrelid "
            "JOIN pg_class f ON f.oid = k.confrelid "
            "WHERE k.contype = 'f'"
        )
        violations = [
            (r["child"], r["parent"])
            for r in rows
            if r["child"] in position and r["parent"] in position
            and r["child"] != r["parent"]
            and position[r["child"]] > position[r["parent"]]
        ]
        assert not violations, (
            f"cha bị xoá trước con, câu DELETE sẽ bị khoá ngoại từ chối: {violations}"
        )

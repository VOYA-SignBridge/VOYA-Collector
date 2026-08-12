"""Cưỡng chế RLS ở đường GHI, và chốt chặn đích của migration.

Vì sao tách khỏi `test_authorization.py`
-----------------------------------------
`TestTheCompatibilityViewDoesNotBypassRls` trong tệp đó đọc SIÊU DỮ LIỆU: view
có `security_invoker` không, bảng nền có `FORCE ROW LEVEL SECURITY` không. Cả
hai là điều kiện CẦN, và cả hai vẫn xanh trên một hệ mà vị từ policy viết sai.

Tệp này thử GHI thật rồi khẳng định cơ sở dữ liệu TỪ CHỐI. Đó là khác biệt giữa
"cơ chế đã được lắp" và "cơ chế chặn được".

Hai phép thử hỏng đã dạy ra hình dạng của tệp này
--------------------------------------------------
Ngày 12/08/2026, khi dò cổng RLS bằng tay, hai lần đo liên tiếp đều "đạt" mà
không chứng minh được gì:

  1. ``INSERT INTO tenant_members (...) SELECT ... FROM users ...`` trả
     ``INSERT 0 0``, trông như một lần chặn thành công. Thật ra câu SELECT
     nguồn đã bị RLS lọc sạch trước khi có dòng nào để chèn — không có gì bị từ
     chối, chỉ là không có gì để chèn.

  2. Sửa thành VALUES cố định thì vướng bẫy khác: MỌI user trong hệ đều đã là
     thành viên của tenant đích, nên lệnh chèn va vào CHỈ MỤC DUY NHẤT chứ
     không phải policy. Vẫn ra lỗi, vẫn trông như đã chặn.

Nên fixture ở đây dựng dữ liệu MỚI HOÀN TOÀN: hai tenant và một user chưa thuộc
tenant nào. Chỉ khi đó, một lệnh ghi bị từ chối mới chứng minh được rằng chính
RLS từ chối nó — và chỉ khi đó `pytest.raises(InsufficientPrivilege)` mới có
nghĩa, vì `InsufficientPrivilege` là mã lỗi RIÊNG của vi phạm row-level
security, khác với `UniqueViolation`.

Liên quan: ``app/storage/rls.py``, ``app/storage/authz_schema.py``,
``docs/AUTHORIZATION.md``.
"""

from __future__ import annotations

import logging

import pytest


# ---------------------------------------------------------------------------
# Dữ liệu thử: hai tenant, và một người thử thuộc tenant thứ nhất
# ---------------------------------------------------------------------------

#: Tên CỐ ĐỊNH, có chữ `test`, đọc được, ngắn — không phải hex ngẫu nhiên.
#:
#: Bản đầu dùng `uuid4().hex[:8]`. Nó chạy được, nhưng sai ở chỗ quan trọng:
#: khi một hàng sót lại trong cơ sở dữ liệu dùng chung — và điều đó ĐÃ xảy ra
#: trong lượt điều tra này — thì `pytest-rlsw-a-3f9c1e02` không nói cho ai biết
#: nó từ đâu ra. Một cái tên như `test-rls-home` thì tự khai: đây là rác của bộ
#: test, và của phần kiểm RLS.
#:
#: Cái giá của tên cố định là hai lượt chạy song song sẽ đụng nhau. Bộ này chạy
#: tuần tự (không có pytest-xdist), và fixture tự dọn ở ĐẦU nên một lượt chạy
#: trước bị ngắt cũng không chặn lượt sau.
#: Ba tenant, không phải hai. `OWNER` là nơi người thử THUỘC VỀ; `HOME` và
#: `OTHER` là hai tenant nó CHƯA thuộc, để mọi bài kiểm ở dưới tự do ghi
#: membership vào cả hai mà không va chỉ mục duy nhất.
OWNER_TENANT = "test-rls-owner"
HOME_TENANT = "test-rls-home"
OTHER_TENANT = "test-rls-other"
PROBE_USERNAME = "test-rls-probe"
PROBE_EMAIL = "test-rls-probe@test.invalid"

_ALL_TENANTS = [OWNER_TENANT, HOME_TENANT, OTHER_TENANT]


def _purge(cur) -> None:
    """Xoá sạch dấu vết của fixture này. Chạy cả trước lẫn sau."""
    cur.execute("DELETE FROM memberships WHERE tenant_id = ANY(%s)", (_ALL_TENANTS,))
    cur.execute("DELETE FROM users WHERE username = %s", (PROBE_USERNAME,))
    cur.execute("DELETE FROM tenants WHERE tenant_id = ANY(%s)", (_ALL_TENANTS,))


@pytest.fixture
def rls_write_fixture():
    """Hai tenant, và một người thử thuộc tenant thứ nhất chứ không thuộc tenant thứ hai.

    Người dùng mới được nhân bản từ một hàng `users` có sẵn qua
    `jsonb_populate_record` chứ không liệt kê cột bằng tay: bảng `users` có
    hàng chục cột NOT NULL, và một danh sách viết tay sẽ hỏng ở lần ai đó thêm
    cột bắt buộc tiếp theo — hỏng theo kiểu làm ĐỎ một test an ninh vì lý do
    không liên quan gì tới an ninh.

    Dọn dẹp ở `finally`, kể cả khi test ném. Bài học đã trả giá trong repo này:
    một lượt chạy suite từng để lại 37 tệp trong kho pháp lý thật.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    with system_scope("test: dung du lieu cho cong RLS ghi"), _cursor() as cur:
        # Dọn TRƯỚC, không chỉ sau. Tên cố định nên một lượt chạy trước bị ngắt
        # giữa chừng sẽ để lại đúng ba hàng này; xoá chúng ở đầu khiến fixture
        # tự lành thay vì đỏ vì lỗi trùng khoá của một lượt chạy đã chết.
        _purge(cur)

        for tenant in _ALL_TENANTS:
            cur.execute(
                "INSERT INTO tenants (tenant_id, display_name, slug, plan_code) "
                "VALUES (%s, %s, %s, 'internal')", (tenant, tenant, tenant))
        cur.execute(
            "INSERT INTO users SELECT (jsonb_populate_record(NULL::users, "
            "  to_jsonb(u) || jsonb_build_object('id', gen_random_uuid()::text, "
            "    'username', %s, 'email', %s, 'tenant_id', %s))).* "
            "FROM users u LIMIT 1 RETURNING id",
            (PROBE_USERNAME, PROBE_EMAIL, OWNER_TENANT))
        user_id = cur.fetchone()[0]

        # Người thử PHẢI là thành viên của tenant nhà nó — và đó là lý do có
        # `OWNER_TENANT` chứ không phải chỉ hai tenant.
        #
        # Không phải để các bài kiểm dưới đây chạy được; chúng chạy được kể cả
        # khi không có dòng này. Mà vì `test_every_live_user_is_a_member_of_
        # their_tenant` canh một bất biến TOÀN CỤC: mọi tài khoản còn sống đều
        # thuộc tenant của nó. Luồng đăng ký giữ đúng bất biến đó — có lời mời
        # thì `consume_invitation` gắn vào, không có thì `create_self_serve_
        # tenant` dựng tổ chức riêng, và nếu cả hai hỏng thì tài khoản bị VÔ
        # HIỆU HOÁ. Một tài khoản sống không thuộc tenant nào là trạng thái sản
        # xuất không tạo ra được.
        #
        # Bản đầu của fixture này tạo người thử mà KHÔNG cho membership, nên
        # trong lúc nó sống, bất biến toàn cục bị vi phạm — và bài kiểm kia đỏ
        # hay xanh tuỳ thứ tự chạy. Đó là hồi quy do chính tệp này gây ra, không
        # phải bất biến đã lỗi thời.
        cur.execute(_INSERT_MEMBERSHIP, (user_id, OWNER_TENANT))

    try:
        yield {"home": HOME_TENANT, "other": OTHER_TENANT, "user": str(user_id)}
    finally:
        with system_scope("test: don du lieu cong RLS ghi"), _cursor() as cur:
            _purge(cur)


_INSERT_MEMBERSHIP = (
    "INSERT INTO memberships (user_id, scope_level, tenant_id, legacy_role, status, joined_at) "
    "VALUES (%s, 'TENANT', %s, 'editor', 'ACTIVE', NOW())"
)


@pytest.mark.integration
class TestRlsBlocksCrossTenantWrites:
    """Cơ sở dữ liệu phải TỪ CHỐI, không phải chỉ "không ghi được gì"."""

    def test_writing_into_the_current_tenant_succeeds(self, rls_write_fixture):
        """Vế ALLOW. Không có nó, một policy `USING (false)` cũng xanh hết."""
        from app.storage.metadata_db import _cursor
        from app.tenant_context import tenant_scope

        f = rls_write_fixture
        with tenant_scope(f["home"]), _cursor() as cur:
            cur.execute(_INSERT_MEMBERSHIP, (f["user"], f["home"]))
            cur.execute("SELECT count(*) FROM memberships WHERE user_id = %s", (f["user"],))
            assert cur.fetchone()[0] == 1

    def test_writing_into_another_tenant_is_refused(self, rls_write_fixture):
        from psycopg2 import errors

        from app.storage.metadata_db import _cursor
        from app.tenant_context import tenant_scope

        f = rls_write_fixture
        with pytest.raises(errors.InsufficientPrivilege):
            with tenant_scope(f["home"]), _cursor() as cur:
                cur.execute(_INSERT_MEMBERSHIP, (f["user"], f["other"]))

    def test_writing_without_any_tenant_scope_is_refused(self, rls_write_fixture):
        """Fail-CLOSED khi không có phạm vi.

        Đây là vế mà ghi chép dự án gọi là "RLS fail-OPEN ở mặt phẳng danh
        tính": một truy vấn chạy TRƯỚC khi biết tenant nào khớp 0 dòng và bị
        đọc thành "không có gì". Ở đường GHI, hành vi đúng là NÉM LỖI, và đó
        là thứ test này ghim lại.
        """
        from psycopg2 import errors

        from app.storage.metadata_db import _cursor
        from app.tenant_context import no_scope

        f = rls_write_fixture
        with pytest.raises(errors.InsufficientPrivilege):
            with no_scope(), _cursor() as cur:
                cur.execute(_INSERT_MEMBERSHIP, (f["user"], f["home"]))

    def test_update_cannot_drag_a_row_into_another_tenant(self, rls_write_fixture):
        """`USING` và `WITH CHECK` là hai vị từ khác nhau, và cần cả hai.

        Chỉ có `USING`, một dòng đọc được sẽ SỬA được sang tenant khác — tức là
        chuyển dữ liệu qua ranh giới bằng UPDATE thay vì INSERT. Không test nào
        khác trong repo bắt được hình dạng đó.
        """
        from psycopg2 import errors

        from app.storage.metadata_db import _cursor
        from app.tenant_context import tenant_scope

        f = rls_write_fixture
        with tenant_scope(f["home"]), _cursor() as cur:
            cur.execute(_INSERT_MEMBERSHIP, (f["user"], f["home"]))

        with pytest.raises(errors.InsufficientPrivilege):
            with tenant_scope(f["home"]), _cursor() as cur:
                cur.execute("UPDATE memberships SET tenant_id = %s WHERE user_id = %s",
                            (f["other"], f["user"]))

    def test_the_compatibility_view_is_not_a_way_around(self, rls_write_fixture):
        """View kế thừa policy của bảng nền — đo bằng một lệnh ghi, không bằng cờ.

        `tenant_members` không nằm trong `RLS_TABLES` được nữa (không gắn policy
        lên view được), nên thứ duy nhất giữ nó an toàn là `security_invoker`
        trỏ ngược về `memberships`. Mất thuộc tính đó là fail-OPEN toàn bộ mặt
        phẳng danh tính, và đây là phép đo trực tiếp của điều đó.
        """
        from psycopg2 import errors

        from app.storage.metadata_db import _cursor
        from app.tenant_context import tenant_scope

        f = rls_write_fixture
        with pytest.raises(errors.InsufficientPrivilege):
            with tenant_scope(f["home"]), _cursor() as cur:
                cur.execute("INSERT INTO tenant_members (tenant_id, user_id, role) "
                            "VALUES (%s, %s, 'admin')", (f["other"], f["user"]))

    def test_system_scope_may_write_across_tenants(self, rls_write_fixture):
        """Phạm vi hệ thống là lối đi HỢP LỆ, và nó phải còn hoạt động.

        Không có test này, siết policy quá tay sẽ làm hỏng đăng ký tài khoản và
        backfill mà không test nào đỏ — cả hai đều ghi ngoài mọi tenant. Một
        cổng an ninh chỉ kiểm vế DENY sẽ khuyến khích đúng loại "sửa" đó.
        """
        from app.storage.metadata_db import _cursor
        from app.tenant_context import system_scope

        f = rls_write_fixture
        with system_scope("test: ghi lien tenant hop le"), _cursor() as cur:
            cur.execute(_INSERT_MEMBERSHIP, (f["user"], f["other"]))
            # Hỏi ĐÍCH DANH dòng vừa ghi, không phải `fetchone()` trên toàn bộ
            # membership của người thử: nó còn một membership ở tenant nhà, nên
            # "dòng đầu tiên" không xác định và một assert như thế sẽ đỏ hoặc
            # xanh tuỳ thứ tự Postgres trả về.
            cur.execute(
                "SELECT count(*) FROM memberships WHERE user_id = %s AND tenant_id = %s",
                (f["user"], f["other"]))
            assert cur.fetchone()[0] == 1

    def test_a_misspelt_system_scope_sentinel_fails_closed(self, rls_write_fixture):
        """`app.system_scope` chỉ nhận đúng chuỗi `'on'`.

        Phát hiện tình cờ khi dò cổng: một phép thử đặt `'1'` và bị TỪ CHỐI.
        Hành vi đó đúng và đáng ghim lại — nếu vị từ từng được nới thành "khác
        rỗng thì coi như hệ thống", mọi giá trị rác sẽ mở toang cách ly tenant,
        và không gì khác trong bộ test bắt được.
        """
        from psycopg2 import errors

        from app.storage.metadata_db import _cursor

        f = rls_write_fixture
        with pytest.raises(errors.InsufficientPrivilege):
            with _cursor() as cur:
                cur.execute("SELECT set_config('app.tenant_id', '', false), "
                            "       set_config('app.system_scope', '1', false)")
                cur.execute(_INSERT_MEMBERSHIP, (f["user"], f["home"]))


# ---------------------------------------------------------------------------
# Chốt chặn đích migration
# ---------------------------------------------------------------------------

class TestMigrationTargetGuard:
    """Chặn lớp lỗi đã gây ra sự cố sản xuất ngày 12/08/2026.

    Một lệnh kiểm chứng chạy `ensure_tables()` trên container dùng-một-lần với
    `-e POSTGRES_DB=authz_v5`, tin rằng mình đang dựng lược đồ lên một BẢN SAO.
    Ứng dụng không dựng DSN từ `POSTGRES_DB` — nó đọc `MIGRATION_DATABASE_URL`
    — nên biến đó bị bỏ qua trong im lặng và migration chạy thẳng lên `signdb`
    của sản xuất.

    Không mất dữ liệu, nhưng sản xuất rơi vào trạng thái lược-đồ-mới/mã-cũ mà
    không ai chọn. Điều biến một lỗi gõ thành sự cố là ở chỗ KHÔNG BƯỚC NÀO nói
    ra nó đang sắp ghi vào đâu.
    """

    class _Cursor:
        """Cursor giả trả về đúng bộ giá trị mà chốt chặn hỏi."""

        def __init__(self, database: str) -> None:
            self._database = database
            self.executed: list[str] = []

        def execute(self, sql, params=None):
            self.executed.append(sql)

        def fetchone(self):
            return (self._database, "admin", "10.0.0.1", 5432)

    def test_it_refuses_when_the_database_is_not_the_expected_one(self, monkeypatch):
        from app.storage.metadata_db import (
            EXPECTED_DATABASE_ENV,
            WrongMigrationTarget,
            _assert_expected_database,
        )

        monkeypatch.setenv(EXPECTED_DATABASE_ENV, "authz_v5")
        with pytest.raises(WrongMigrationTarget) as excinfo:
            _assert_expected_database(self._Cursor("signdb"))

        # Thông điệp phải nêu CẢ HAI tên. Một lỗi chỉ nói "sai cơ sở dữ liệu"
        # bắt người đọc tự đi tìm nó đang ở đâu, đúng lúc họ đang hoảng.
        assert "authz_v5" in str(excinfo.value)
        assert "signdb" in str(excinfo.value)

    def test_it_allows_the_expected_database(self, monkeypatch):
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV, _assert_expected_database

        monkeypatch.setenv(EXPECTED_DATABASE_ENV, "authz_v5")
        _assert_expected_database(self._Cursor("authz_v5"))  # không được ném

    def test_it_stays_out_of_the_way_when_unset(self, monkeypatch):
        """`ensure_tables()` chạy hợp lệ ở MỖI lần khởi động backend.

        Một chốt chặn luôn-bật sẽ chặn cả đường đi đúng, nên nó phải im lặng khi
        không ai yêu cầu — và đó chính là lý do nó KHÔNG đủ một mình, và vì sao
        dòng banner phải chạy vô điều kiện.
        """
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV, _assert_expected_database

        monkeypatch.delenv(EXPECTED_DATABASE_ENV, raising=False)
        _assert_expected_database(self._Cursor("signdb"))  # không được ném

    def test_it_always_announces_the_target(self, monkeypatch, caplog):
        """Lớp phòng thủ thứ hai, và là lớp đã THIẾU khi sự cố xảy ra.

        Chốt chặn chỉ giúp người ĐÃ NGỜ. Dòng banner giúp người chưa ngờ gì —
        nó biến đích thành thứ đọc được ở dòng log đầu tiên, thay vì phải suy ra
        sau khi bảng đã bị bỏ.
        """
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV, _assert_expected_database

        monkeypatch.delenv(EXPECTED_DATABASE_ENV, raising=False)
        with caplog.at_level(logging.WARNING):
            _assert_expected_database(self._Cursor("signdb"))

        banner = [r.getMessage() for r in caplog.records if "MIGRATION-TARGET" in r.getMessage()]
        assert banner, "khong co dong banner nao noi ra dich cua migration"
        assert "signdb" in banner[0]

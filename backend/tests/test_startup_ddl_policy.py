"""Allowlist DDL khởi động: mọi câu phải CHỨNG MINH được là an toàn.

Tệp anh em của `test_schema_version_gate.py`. Cái lưới ở đó hỏi "câu này có
giống thứ ta biết là nguy hiểm không" và quét năm từ khoá. Tệp này hỏi ngược
lại — "câu này có thuộc tập được phép không" — và đó là khác biệt đã đo được:

    lưới từ khoá   bỏ sót 32 câu, gồm 5 câu đổi tên role, 1 câu đổi kiểu cột
                   sang uuid, 2 câu RENAME COLUMN, 1 câu SET NOT NULL
    allowlist      cả 32 câu rơi xuống mặt phẳng migration

Nhóm quan trọng nhất là `TestUnknownStatementsFailClosed`. Hai nhóm kia canh
những hình dạng đã biết; nhóm đó canh những hình dạng chưa ai nghĩ tới, và nó
là thứ còn giá trị sau khi mọi người quên tệp này tồn tại.
"""

from __future__ import annotations

import pytest

from app.storage.startup_ddl_policy import (
    STARTUP_EXCEPTIONS,
    UNFILTERABLE_GROUPS,
    classify_corpus,
    migration_only_statements,
    startup_corpus,
)


def _verdicts():
    return classify_corpus()


def _filterable_verdicts():
    return [v for v in _verdicts() if v.group not in UNFILTERABLE_GROUPS]


class TestEveryStartupStatementIsClassified:
    """Lớp C: không có câu nào "chưa biết là gì" mà vẫn được chạy."""

    def test_no_statement_on_the_startup_path_is_unclassified(self):
        """Cái test sẽ đỏ khi ai đó thêm một câu DDL bộ phân loại chưa hiểu.

        Câu đó KHÔNG lên đường khởi động — `migration_only_statements()` đã
        đẩy nó sang mặt phẳng migration, nên hệ vẫn đúng. Nhưng nó cũng đã
        lặng lẽ đổi payload migration, tức là đổi checksum, tức là cần một
        phiên bản mới. Test này bắt người thêm phải nói ra điều đó.
        """
        unknown = [v for v in _verdicts() if not v.is_startup_safe]
        classified_as_migration = migration_only_statements()
        surprises = [v for v in unknown
                     if v.statement not in classified_as_migration]

        assert not surprises, (
            "Có câu KHÔNG chứng minh được là an toàn lúc khởi động mà bộ lọc "
            "cũng không đẩy được sang migration:\n\n"
            + "\n\n".join(v.describe() for v in surprises))

    def test_the_unfilterable_lists_are_all_startup_safe(self):
        """Ba danh sách chạy KHÔNG qua bộ lọc, nên chúng chỉ kiểm được.

        `SCHEMA_VERSION_DDL` phải chạy trước mọi thứ (cổng phiên bản đọc nó),
        `TENANT_FK_LOOP_SQL` là lần phát thứ ba của vòng khoá ngoại, `rls_ddl`
        cài chính sách cách ly tenant. Một câu không an toàn lọt vào ba danh
        sách này thì không cơ chế nào chặn được — chỉ còn test này.
        """
        offenders = [v for v in _verdicts()
                     if v.group in UNFILTERABLE_GROUPS and not v.is_startup_safe]

        assert not offenders, (
            "Câu không an toàn nằm trong danh sách KHÔNG lọc được. Nó sẽ chạy ở "
            "mỗi lần khởi động dù bộ phân loại nói gì:\n\n"
            + "\n\n".join(v.describe() for v in offenders))

    def test_most_statements_still_pass_as_startup_safe(self):
        """Sàn, không phải trần.

        Test trên cũng xanh nếu bộ phân loại thoái hoá thành "mọi thứ đều là
        migration". Lúc đó khởi động không cài nổi lược đồ và không ai biết vì
        sao. Con số neo lại: 503/564 câu, đếm ngày 13/08/2026.
        """
        verdicts = _verdicts()
        safe = [v for v in verdicts if v.is_startup_safe]

        assert len(safe) >= len(verdicts) * 0.8, (
            f"chi con {len(safe)}/{len(verdicts)} cau duoc coi la an toan luc "
            f"khoi dong — truoc day la 503. Bo phan loai co the da hong.")


class TestDangerousShapesNeverReachStartup:
    """Lớp B: sáu hình dạng cái lưới từ khoá cũ không bắt được."""

    @pytest.mark.parametrize("label, statement", [
        ("data_backfill",
         "UPDATE users SET display_name = username WHERE display_name IS NULL"),
        ("column_type_change",
         "ALTER TABLE signers ALTER COLUMN external_user_id TYPE uuid "
         "USING external_user_id::uuid"),
        ("column_rename",
         "ALTER TABLE roles RENAME COLUMN name TO role_code"),
        ("tighten_to_not_null",
         "ALTER TABLE tenants ALTER COLUMN plan_code SET NOT NULL"),
        # Chiều NGƯỢC lại, chuyển sang đây ngày 24/08/2026. Trước đó nó nằm ở
        # danh sách "additive được phép", dưới nhãn `relax_default`.
        #
        # Nới ràng buộc không phải phép cộng. `SET NOT NULL` bị chặn vì nó có
        # thể NGÃ trên dữ liệu xấu — tức nó ồn ào, và ồn ào thì thấy được.
        # `DROP NOT NULL` thì không bao giờ ngã: nó lặng lẽ gỡ một phép kiểm ở
        # mọi lần khởi động, không lần triển khai nào ghi lại, và không ai biết
        # phiên bản nào đã làm điều đó. Bất đối xứng theo đúng hướng sai.
        ("relax_to_nullable",
         "ALTER TABLE probe ALTER COLUMN note DROP NOT NULL"),
        # `DROP DEFAULT` đổi ngữ nghĩa của MỌI câu INSERT sau nó. Đây chính là
        # hình dạng đứng sau v7: một `DEFAULT 1` lặng lẽ dựng con trỏ registry
        # trỏ vào phiên bản chưa tồn tại, suốt nhiều tháng không ai thấy.
        ("drop_column_default",
         "ALTER TABLE probe ALTER COLUMN note DROP DEFAULT"),
        ("table_to_view_swap",
         "DROP VIEW IF EXISTS tenant_members"),
        ("privilege_change",
         "GRANT SELECT ON ALL TABLES IN SCHEMA public TO voya_app"),
    ])
    def test_a_dangerous_statement_is_refused(self, label, statement):
        corpus = {"probe": (statement,)}
        verdict = classify_corpus(corpus)[0]

        assert not verdict.is_startup_safe, (
            f"`{label}` duoc coi la an toan luc khoi dong: {verdict.detail}")
        assert migration_only_statements(corpus) == frozenset({statement})

    @pytest.mark.parametrize("label, statement", [
        ("create_table", "CREATE TABLE IF NOT EXISTS probe (id INT)"),
        ("create_index", "CREATE INDEX IF NOT EXISTS ix_probe ON probe (id)"),
        ("add_column", "ALTER TABLE probe ADD COLUMN IF NOT EXISTS note TEXT"),
        ("enable_rls", "ALTER TABLE probe ENABLE ROW LEVEL SECURITY"),
        ("replace_view", "CREATE OR REPLACE VIEW probe_view AS SELECT 1"),
    ])
    def test_an_additive_statement_is_allowed(self, label, statement):
        verdict = classify_corpus({"probe": (statement,)})[0]

        assert verdict.is_startup_safe, f"`{label}` bi tu choi: {verdict.detail}"

    def test_a_do_block_hiding_a_data_write_is_refused(self):
        """Hình dạng ngoài của một khối `DO $$` không nói được gì.

        Đây chính là chỗ 32 câu lọt qua: bốn khối trong tập thật trông hệt như
        mẫu "thêm ràng buộc nếu chưa có", và bên trong là một câu đổi kiểu cột,
        hai câu đổi tên cột, một câu `SET NOT NULL`.
        """
        innocent_looking = (
            "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_constraint "
            "WHERE conname = 'ck_probe') THEN "
            "UPDATE probe SET note = 'da sua'; END IF; END $$")
        verdict = classify_corpus({"probe": (innocent_looking,)})[0]

        assert not verdict.is_startup_safe
        assert "UPDATE" in verdict.detail

    def test_a_foreign_key_action_is_not_mistaken_for_a_data_write(self):
        """`ON UPDATE CASCADE` không phải một câu UPDATE.

        Bắt nhầm ở đây tốn ba mươi báo động giả trên tập thật — và một cổng kêu
        oan là một cổng sắp bị gỡ.
        """
        statement = (
            "ALTER TABLE samples ADD CONSTRAINT fk_samples_class "
            "FOREIGN KEY (tenant_id, class_uid) REFERENCES classes(tenant_id, "
            "class_uid) ON UPDATE CASCADE ON DELETE RESTRICT")
        verdict = classify_corpus({"probe": (statement,)})[0]

        assert verdict.is_startup_safe, verdict.detail


class TestDropIsSafeOnlyWhenSomethingRecreatesIt:
    """`DROP POLICY` / `DROP TRIGGER` / `DROP CONSTRAINT` được miễn trừ theo
    mẫu "bỏ rồi dựng lại". Miễn trừ đó chỉ đúng khi câu dựng lại CÓ THẬT."""

    def test_a_constraint_drop_followed_by_an_add_is_allowed(self):
        corpus = {"probe": (
            "ALTER TABLE probe DROP CONSTRAINT IF EXISTS ck_probe_status",
            "ALTER TABLE probe ADD CONSTRAINT ck_probe_status "
            "CHECK (status IN ('a', 'b'))",
        )}
        drop_verdict = classify_corpus(corpus)[0]

        assert drop_verdict.is_startup_safe, drop_verdict.detail

    def test_a_constraint_drop_with_nothing_recreating_it_is_refused(self):
        """Chuyện này có thật trong tập đang chạy.

        `ALTER TABLE roles DROP CONSTRAINT IF EXISTS roles_name_key` bỏ một
        ràng buộc UNIQUE và không câu nào dựng lại. Cái lưới cũ cố ý bỏ qua mọi
        `DROP CONSTRAINT` vì coi chúng là nửa đầu của mẫu bỏ-rồi-dựng — nên câu
        này chạy ở mỗi lần khởi động suốt từ đó.
        """
        corpus = {"probe": (
            "ALTER TABLE probe DROP CONSTRAINT IF EXISTS uq_probe_name",
        )}
        verdict = classify_corpus(corpus)[0]

        assert not verdict.is_startup_safe
        assert "dựng lại" in verdict.detail

    def test_a_policy_drop_with_nothing_recreating_it_is_refused(self):
        """Bỏ một chính sách RLS mà không cài lại là gỡ hàng rào cách ly
        tenant — thứ nguy hiểm nhất trong tệp này, và trông vô hại nhất."""
        corpus = {"probe": ("DROP POLICY IF EXISTS p_probe_tenant ON probe",)}
        verdict = classify_corpus(corpus)[0]

        assert not verdict.is_startup_safe

    def test_a_do_block_dropping_without_readding_is_refused(self):
        corpus = {"probe": (
            "DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_constraint "
            "WHERE conname = 'fk_probe') THEN "
            "ALTER TABLE probe DROP CONSTRAINT fk_probe; END IF; END $$",
        )}
        verdict = classify_corpus(corpus)[0]

        assert not verdict.is_startup_safe
        assert "fk_probe" in verdict.detail

    def test_a_do_block_dropping_and_readding_the_same_name_is_allowed(self):
        """Khối `DO $$` là MỘT giao dịch, nên bỏ-rồi-dựng trong đó không để lại
        khe hở nào: hoặc cả hai câu ăn, hoặc không câu nào."""
        corpus = {"probe": (
            "DO $$ BEGIN ALTER TABLE probe DROP CONSTRAINT IF EXISTS ck_probe; "
            "ALTER TABLE probe ADD CONSTRAINT ck_probe CHECK (n > 0); END $$",
        )}
        verdict = classify_corpus(corpus)[0]

        assert verdict.is_startup_safe, verdict.detail


class TestUnknownStatementsFailClosed:
    """Lớp C. Cái mua được nhiều nhất, vì nó canh thứ chưa ai nghĩ tới."""

    def test_an_unrecognised_statement_is_not_startup_safe(self):
        corpus = {"probe": ("CLUSTER probe USING ix_probe",)}
        verdict = classify_corpus(corpus)[0]

        assert not verdict.is_startup_safe
        assert "không khớp hình dạng nào" in verdict.detail

    def test_an_unrecognised_statement_lands_on_the_migration_plane(self):
        statement = "REINDEX TABLE probe"

        assert migration_only_statements({"probe": (statement,)}) == \
            frozenset({statement})

    def test_a_safe_shape_carrying_a_hidden_write_is_refused(self):
        """Khớp hình dạng KHÔNG đủ — động từ đột biến vẫn bị soi.

        `CREATE TABLE ... AS SELECT` mở đầu đúng như một `CREATE TABLE IF NOT
        EXISTS` bình thường; phần đọc dữ liệu nằm ở cuối câu.
        """
        statement = ("CREATE TABLE IF NOT EXISTS probe_copy AS "
                     "SELECT * FROM probe; INSERT INTO probe_copy SELECT 1")
        verdict = classify_corpus({"probe": (statement,)})[0]

        assert not verdict.is_startup_safe


class TestStartupAndMigrationPlanesAreDisjoint:
    """Một câu thuộc đúng MỘT mặt phẳng. Không có vùng xám."""

    def test_no_statement_is_both_startup_safe_and_migration_only(self):
        from app.storage.metadata_db import one_way_statements

        one_way = one_way_statements()
        both = [v.statement for v in _filterable_verdicts()
                if v.is_startup_safe and v.statement in migration_only_statements()]

        assert not both
        # Và chiều ngược lại: không câu nào rơi khỏi cả hai mặt phẳng.
        homeless = [v for v in _filterable_verdicts()
                    if not v.is_startup_safe and v.statement not in one_way]
        assert not homeless, "\n\n".join(v.describe() for v in homeless)

    def test_the_hand_registered_statements_stay_on_the_migration_plane(self):
        """Danh sách tay là lớp đỡ, không phải phần thừa.

        Đo ngày 13/08/2026: bộ phân loại coi HAI trong số các câu đã đăng ký
        tay là an toàn (`ADD CONSTRAINT` trong khối DO, và một `DROP DEFAULT`).
        Người đăng ký chúng biết thứ bộ phân loại không biết: cả hai là mảnh
        của cùng một lượt gỡ `legacy_role`, và tách lẻ ra thì vô nghĩa.
        """
        from app.storage.authz_schema import AUTHZ_ONE_WAY_DDL
        from app.storage.metadata_db import one_way_statements

        one_way = one_way_statements()
        escaped = [s for s in AUTHZ_ONE_WAY_DDL if s not in one_way]

        assert not escaped, (
            "câu đã đăng ký tay lại lên được đường khởi động:\n  "
            + "\n  ".join(" ".join(s.split())[:120] for s in escaped))

    def test_every_packaged_payload_statement_is_also_classified_one_way(self):
        """Chiều đúng của quan hệ giữa lịch sử và phân loại.

        Bản đầu của test này đòi ngược lại — payload phải PHỦ mọi câu một
        chiều — và đó chính là mô hình đã gây ra lỗi 13/08: nó buộc lịch sử
        của một phiên bản đã apply phải lớn lên theo mỗi lần bộ phân loại giỏi
        thêm. Phân loại tiến hoá, lịch sử thì không.

        Chiều còn lại vẫn phải đúng, và nó là chiều có ý nghĩa: một câu nằm
        trong payload của v5 mà bộ phân loại lại coi là an toàn lúc khởi động
        thì nó vừa "chỉ chạy khi có người ra lệnh" vừa "chạy mỗi lần khởi
        động" — mâu thuẫn, và vế thứ hai là vế thắng.

        Chênh lệch giữa hai tập KHÔNG phải lỗi: đó là tồn đọng phân loại — 43
        câu vừa phát hiện, chờ được xếp vào payload của một phiên bản tương
        lai. Xem `docs/10-issues/INCIDENT_2026-08-12_schema_code_skew.md`.
        """
        from app.storage.metadata_db import one_way_statements
        from app.storage.migration_history import MIGRATION_HISTORY, labelled_payload

        one_way = one_way_statements()
        escaped = [
            f"v{version}:{label}"
            for version in sorted(MIGRATION_HISTORY)
            for label, statement in labelled_payload(version)
            if statement not in one_way
        ]

        assert not escaped, (
            "câu thuộc payload của một phiên bản đã đóng gói lại lên được "
            "đường khởi động:\n  " + "\n  ".join(escaped))


class TestStartupExceptionsAreJustified:
    """Mỗi ngoại lệ phải nói ra lý do, và lý do phải còn đúng."""

    def test_every_exception_matches_a_statement_that_still_exists(self):
        """Ngoại lệ chết là ngoại lệ nguy hiểm: nó nới lỏng một cửa không còn
        ai đi qua, và lần sau có người viết một câu khớp dấu vân tay đó thì
        cửa mở sẵn."""
        from app.storage.schema_version import canonical_sql

        everything = [canonical_sql(s)
                      for stmts in startup_corpus().values() for s in stmts]
        dead = [exc.label for exc in STARTUP_EXCEPTIONS
                if not any(exc.fingerprint in c for c in everything)]

        assert not dead, f"ngoai le khong con khop cau nao: {dead}"

    def test_every_exception_states_a_reason(self):
        thin = [exc.label for exc in STARTUP_EXCEPTIONS if len(exc.reason) < 40]

        assert not thin, (
            f"ngoai le chi co ly do lay le: {thin}. Mot dong 'vi xua nay van "
            f"chay' khong phai ly do.")

    def test_every_exception_names_a_guard_that_is_present(self):
        """Chốt chặn được khai phải có thật TRONG câu đang chạy, không phải
        trong bản chép tay ở registry."""
        from app.storage.schema_version import canonical_sql

        everything = [canonical_sql(s)
                      for stmts in startup_corpus().values() for s in stmts]
        unguarded = []
        for exc in STARTUP_EXCEPTIONS:
            for c in everything:
                if exc.fingerprint in c and exc.guard.upper() not in c.upper():
                    unguarded.append(exc.label)

        assert not unguarded, (
            f"ngoai le khai chot chan ma cau lenh khong con co: {unguarded}")

    def test_every_exception_is_recognised_by_the_classifier(self):
        labels = {f"exception:{exc.label}" for exc in STARTUP_EXCEPTIONS}
        seen = {v.shape for v in _verdicts() if (v.shape or "").startswith("exception:")}

        assert labels == seen, f"khai {labels}, dung {seen}"


# ---------------------------------------------------------------------------
# Ba mặt phẳng (13/08/2026)
# ---------------------------------------------------------------------------

class TestEveryStatementLandsOnExactlyOnePlane:
    """Mỗi câu có đúng một kết luận, và "chưa kết luận" phải đỏ."""

    def test_no_statement_is_left_unknown(self):
        """`unknown` nghĩa là chưa ai từng nhìn câu này.

        Nó KHÔNG chạy lúc khởi động (mặc định fail-closed), nên hệ vẫn đúng.
        Nhưng im lặng cho qua chính là mô hình cũ — "không thấy nguy hiểm thì
        cho chạy" — chỉ đổi chiều. Người thêm câu phải nói ra nó là gì.
        """
        from app.storage.startup_ddl_policy import UNKNOWN, statements_by_plane

        unknown = statements_by_plane()[UNKNOWN]

        assert not unknown, (
            f"{len(unknown)} câu chưa được phân loại:\n\n"
            + "\n\n".join(v.describe() for v in unknown))

    def test_the_planes_add_up_to_the_whole_corpus(self):
        from app.storage.startup_ddl_policy import statements_by_plane

        planes = statements_by_plane()
        assert sum(len(v) for v in planes.values()) == len(_verdicts())

    def test_a_known_danger_is_not_reported_as_unknown(self):
        """Hai kết cục khác nhau và phải nói ra điều khác nhau.

        `migration-only` = biết là gì, chỉ chưa ai quyết nó thuộc phiên bản
        nào. `unknown` = chưa ai từng nhìn. Gộp hai cái làm một thì tồn đọng
        "cần quyết phiên bản" lẫn vào tồn đọng "cần đọc lần đầu".
        """
        from app.storage.startup_ddl_policy import MIGRATION_ONLY, UNKNOWN

        known = classify_corpus(
            {"probe": ("UPDATE users SET is_active = FALSE WHERE id IS NULL",)})[0]
        never_seen = classify_corpus({"probe": ("CLUSTER probe USING ix_probe",)})[0]

        assert known.plane == MIGRATION_ONLY
        assert never_seen.plane == UNKNOWN


class TestOnlyStartupSafeStatementsRunAtStartup:
    """Meta-test: đối chiếu KẾT LUẬN với thứ THỰC SỰ chạy.

    Mọi test khác trong tệp này kiểm bộ phân loại. Test này kiểm rằng bộ phân
    loại có thật sự điều khiển được đường khởi động — không có nó, cả tệp có
    thể xanh trong khi `ensure_tables()` vẫn chạy đúng những câu bị cấm.
    """

    def _executed_at_startup(self):
        from app.storage.metadata_db import startup_safe

        executed = []
        for group, statements in startup_corpus().items():
            if group in UNFILTERABLE_GROUPS:
                executed.extend((group, s) for s in statements)
            else:
                executed.extend((group, s) for s in startup_safe(list(statements)))
        return executed

    def test_everything_that_runs_at_startup_is_classified_startup_safe(self):
        from app.storage.startup_ddl_policy import STARTUP_SAFE

        by_statement = {v.statement: v for v in _verdicts()}
        offenders = [
            by_statement[s] for group, s in self._executed_at_startup()
            if by_statement[s].plane != STARTUP_SAFE
        ]

        assert not offenders, (
            "Câu KHÔNG thuộc mặt phẳng startup-safe mà vẫn chạy khi backend "
            "lên:\n\n" + "\n\n".join(v.describe() for v in offenders))

    @pytest.mark.parametrize("plane", ["historical-only", "migration-only"])
    def test_a_barred_plane_never_reaches_the_startup_path(self, plane):
        from app.storage.startup_ddl_policy import statements_by_plane

        executed = {s for _, s in self._executed_at_startup()}
        leaked = [v for v in statements_by_plane()[plane] if v.statement in executed]

        assert not leaked, (
            f"{len(leaked)} câu `{plane}` vẫn chạy lúc khởi động:\n\n"
            + "\n\n".join(v.describe() for v in leaked))

    def test_the_startup_path_is_not_empty(self):
        """Đối chứng dương: ba test trên cũng xanh nếu khởi động không chạy gì.

        Con số neo lại: 503 câu, đếm ngày 13/08/2026.
        """
        assert len(self._executed_at_startup()) >= 400


class TestHistoricalRegistryIsHonest:
    """Khai một câu là "lịch sử" là khẳng định mạnh nhất trong tệp này."""

    def test_every_historical_group_matches_a_real_statement(self):
        """Nhóm chết là nhóm nguy hiểm: nó mở sẵn một cửa không ai còn đi qua.

        Đã bắt được một lần thật — mẫu của `migrate_system_roles_to_assignments`
        chỉ khớp tên bảng nên nuốt luôn câu BỎ bảng đó, và
        `drop_legacy_membership_tables` thành nhóm không khớp gì.
        """
        from app.storage.startup_ddl_policy import (
            HISTORICAL_MIGRATIONS, HISTORICAL_ONLY, statements_by_plane)

        used = {v.shape for v in statements_by_plane()[HISTORICAL_ONLY]}
        dead = [e.label for e in HISTORICAL_MIGRATIONS
                if f"historical:{e.label}" not in used]

        assert not dead, f"nhom lich su khong khop cau nao: {dead}"

    def test_every_historical_group_states_a_reason(self):
        from app.storage.startup_ddl_policy import HISTORICAL_MIGRATIONS

        thin = [e.label for e in HISTORICAL_MIGRATIONS if len(e.reason) < 60]
        assert not thin, f"nhom lich su chi co ly do lay le: {thin}"

    def test_no_historical_group_captures_a_statement_that_is_safe_anyway(self):
        """Mẫu quá rộng thì gỡ một câu vô hại khỏi đường khởi động, và một máy
        cài mới sẽ thiếu nó mà không ai biết vì sao.

        Câu hỏi đúng là "gỡ nhãn lịch sử ra thì câu này có thành startup-safe
        không", chứ không phải "nó có chứa động từ đột biến không". Bản đầu
        hỏi vế sau và báo oan ba câu `DROP CONSTRAINT` không có câu dựng lại:
        `DROP CONSTRAINT` cố ý KHÔNG nằm trong `_MUTATING_VERBS` vì nó do lớp
        kiểm cặp xử lý — nên nó nguy hiểm mà không có động từ nào.
        """
        import app.storage.startup_ddl_policy as policy

        before = {v.statement for v in policy.statements_by_plane()[
            policy.HISTORICAL_ONLY]}

        registry = policy.HISTORICAL_MIGRATIONS
        policy.HISTORICAL_MIGRATIONS = ()
        policy._classify_cached.cache_clear()
        try:
            safe_anyway = [
                v for v in policy.classify_corpus()
                if v.statement in before and v.is_startup_safe
            ]
        finally:
            policy.HISTORICAL_MIGRATIONS = registry
            policy._classify_cached.cache_clear()

        assert not safe_anyway, (
            "câu vốn đã an toàn lúc khởi động mà bị một nhóm lịch sử bắt "
            "nhầm:\n\n" + "\n\n".join(v.describe() for v in safe_anyway))

"""Cổng phiên bản lược đồ, và lời hứa "khởi động không phá gì".

Sự cố 12/08/2026 có hai nửa, và bản vá đầu chỉ chữa nửa thứ nhất:

    nửa 1  lệnh chạy nhầm cơ sở dữ liệu   -> `_assert_expected_database`
    nửa 2  KHỞI ĐỘNG tự ý đổi lược đồ,     -> tệp này
           rồi mã cũ chạy trên lược đồ mới

Tệp này canh nửa thứ hai bằng ba nhóm:

  * `TestStartupPathIsNonDestructive` — cái lưới. Nó không kiểm một câu cụ thể
    nào; nó quét TOÀN BỘ danh sách chạy lúc khởi động và bắt bất cứ câu phá huỷ
    nào lọt vào sau này. Đây là test duy nhất trong tệp còn giá trị sau khi mọi
    người đã quên chuyện gì xảy ra ngày 12/08.
  * `TestCompatibilityWindow` — cổng hai chiều, kể cả chiều ít ai nghĩ tới.
  * `TestMigrateCommand` — ba lần từ chối của lệnh migration.
"""

from __future__ import annotations

import re

import pytest

from app.storage.schema_version import (
    APP_SCHEMA_VERSION,
    MIN_SUPPORTED_SCHEMA_VERSION,
    SchemaNotMigrated,
    SchemaTooNew,
    SchemaTooOld,
    compatibility_error,
    read_schema_version,
)


# Chỉ những câu KHÔNG có đường về. `DROP POLICY` / `DROP TRIGGER` /
# `DROP CONSTRAINT` cố ý KHÔNG có mặt: chúng là nửa đầu của mẫu
# "drop rồi tạo lại" — cài đặt lại thứ vừa bỏ trong cùng lượt chạy, nên chúng
# bổ khuyết chứ không phá.
_IRREVERSIBLE = re.compile(
    r"DROP\s+TABLE|DROP\s+COLUMN|DROP\s+INDEX|TRUNCATE|DELETE\s+FROM",
    re.IGNORECASE,
)


def _startup_lists() -> dict[str, list[str]]:
    from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS
    from app.storage.metadata_db import (
        DDL_STATEMENTS, INDEX_STATEMENTS, MIGRATION_STATEMENTS, startup_safe,
    )

    return {
        "DDL_STATEMENTS": startup_safe(DDL_STATEMENTS),
        "MIGRATION_STATEMENTS": startup_safe(MIGRATION_STATEMENTS),
        "INDEX_STATEMENTS": startup_safe(INDEX_STATEMENTS),
        "AUTHZ_DDL_STATEMENTS": startup_safe(AUTHZ_DDL_STATEMENTS),
    }


class TestStartupPathIsNonDestructive:
    """`ensure_tables()` chỉ được THÊM. Cái lưới, không phải danh sách kiểm."""

    def test_no_irreversible_statement_survives_the_filter(self):
        offenders: list[str] = []
        for name, statements in _startup_lists().items():
            for stmt in statements:
                if _IRREVERSIBLE.search(stmt):
                    offenders.append(f"{name}: {' '.join(stmt.split())[:120]}")

        assert not offenders, (
            "Có câu phá huỷ nằm trên đường KHỞI ĐỘNG. Mỗi lần backend lên là "
            "một lần nó chạy — kể cả khi người vận hành chỉ định restart một "
            "service. Thêm câu đó vào `one_way_statements()` để chỉ "
            "`python -m app.cli.migrate` chạy được nó:\n  "
            + "\n  ".join(offenders)
        )

    def test_the_one_way_set_is_not_empty(self):
        """Bộ lọc phải THỰC SỰ lọc thứ gì đó.

        Test trên chỉ nói "đường khởi động sạch". Nó cũng xanh khi ai đó xoá
        luôn mấy câu phá huỷ khỏi mã — lúc đó lượt migration im lặng không làm
        gì, và một máy cài mới nhận về một lược đồ dở dang.

        Con số là thứ neo lại: 11 câu, đếm ngày 12/08/2026.
        """
        from app.storage.metadata_db import one_way_statements

        one_way = one_way_statements()
        assert len(one_way) >= 8, (
            f"chi con {len(one_way)} cau mot chieu — truoc day la 11. "
            f"Neu that su bo bot, sua con so nay va noi ro vi sao."
        )

    def test_filtering_preserves_relative_order(self):
        """Thứ tự là tài sản: bốn ràng buộc thứ tự trong `AUTHZ_DDL_STATEMENTS`
        mỗi cái đổi lấy một lần hỏng thật. Lọc phần tử không được xáo phần còn
        lại."""
        from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS
        from app.storage.metadata_db import one_way_statements, startup_safe

        one_way = one_way_statements()
        expected = [s for s in AUTHZ_DDL_STATEMENTS if s not in one_way]
        assert startup_safe(AUTHZ_DDL_STATEMENTS) == expected

    def test_migration_path_still_runs_everything(self):
        """Lệnh migration KHÔNG được đánh rơi câu nào — nó là đường duy nhất
        đưa một máy cài mới tới lược đồ hiện hành."""
        from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS
        from app.storage.metadata_db import one_way_statements, startup_safe

        one_way = one_way_statements()
        dropped = [s for s in AUTHZ_DDL_STATEMENTS if s in one_way]
        assert dropped, "khong con cau nao bi loc — bo loc da thanh do trang tri"
        assert len(startup_safe(AUTHZ_DDL_STATEMENTS)) + len(dropped) == \
            len(AUTHZ_DDL_STATEMENTS)

    def test_the_compatibility_view_stays_on_the_startup_path(self):
        """`CREATE OR REPLACE VIEW tenant_members` KHÔNG phá gì, và định nghĩa
        của nó đi theo MÃ chứ không theo dữ liệu. Một ảnh mới phải mang được
        định nghĩa view của chính nó lên mà không cần nghi thức migration."""
        from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS
        from app.storage.metadata_db import startup_safe

        on_startup = " ".join(startup_safe(AUTHZ_DDL_STATEMENTS))
        assert "CREATE OR REPLACE VIEW tenant_members" in on_startup
        assert "security_invoker" in on_startup


class TestCompatibilityWindow:
    """Fail-closed CẢ HAI chiều."""

    def test_matching_version_is_accepted(self):
        assert compatibility_error(APP_SCHEMA_VERSION) is None

    def test_unstamped_database_is_refused(self):
        error = compatibility_error(None)
        assert isinstance(error, SchemaNotMigrated)
        # Thông điệp phải NÓI RA lệnh cần chạy. Một cổng chặn mà không chỉ
        # đường thì lượt triển khai kế tiếp sẽ được "sửa" bằng cách gỡ cổng.
        assert "app.cli.migrate" in str(error)
        assert "--adopt" in str(error)

    def test_older_schema_is_refused(self):
        error = compatibility_error(MIN_SUPPORTED_SCHEMA_VERSION - 1)
        assert isinstance(error, SchemaTooOld)
        assert "app.cli.migrate" in str(error)

    def test_newer_schema_is_refused(self):
        """Chiều đã gây ra sự cố: ảnh CŨ trên lược đồ MỚI.

        Nó không "thiếu tính năng" — nó đọc và ghi theo một hình dạng đã đổi,
        và phần lớn đường đi vẫn trả 200. Chỉ chặn "DB quá cũ" là bỏ sót đúng
        cái đã xảy ra.
        """
        error = compatibility_error(APP_SCHEMA_VERSION + 1)
        assert isinstance(error, SchemaTooNew)
        # KHÔNG được gợi ý chạy migration: migration chỉ đi tới.
        assert "khoi phuc" in str(error).lower() or "sao luu" in str(error).lower()

    def test_the_window_is_a_real_interval(self):
        assert MIN_SUPPORTED_SCHEMA_VERSION <= APP_SCHEMA_VERSION

    @pytest.mark.parametrize("version", [
        MIN_SUPPORTED_SCHEMA_VERSION,
        APP_SCHEMA_VERSION,
    ])
    def test_both_ends_of_the_window_are_inclusive(self, version):
        assert compatibility_error(version) is None


class TestStampedDatabase:
    """Vòng đọc/ghi thật trên Postgres."""

    def test_the_test_database_is_stamped_and_compatible(self):
        from app.storage.metadata_db import _migration_cursor

        with _migration_cursor() as cur:
            version = read_schema_version(cur)

        assert version is not None, (
            "co so du lieu test chua duoc dong dau — conftest.pytest_sessionstart "
            "phai chay migrate_database() truoc moi fixture"
        )
        assert compatibility_error(version) is None

    def test_the_registry_keeps_history_not_just_a_current_value(self):
        """`MAX(version)` chứ không phải một dòng bị ghi đè: câu hỏi của lượt
        điều tra là "ai đưa nó tới đây, lúc nào", không phải "bây giờ ở đâu"."""
        from app.storage.metadata_db import _migration_cursor
        from app.storage.schema_version import SCHEMA_VERSION_TABLE

        with _migration_cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = %s", (SCHEMA_VERSION_TABLE,)
            )
            columns = {r[0] for r in cur.fetchall()}

        assert {"version", "applied_at", "applied_by"} <= columns
        assert "applied_on" in columns, "thieu cot noi ra MAY nao chay lenh"


class TestMigrateCommand:
    """Ba lần từ chối, mỗi lần chặn một cách hỏng khác nhau."""

    def test_it_refuses_without_an_explicit_target(self, monkeypatch, capsys):
        """Cái đã thiếu hôm 12/08: người gõ lệnh phải nói ra họ nhắm vào đâu."""
        from app.cli import migrate
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV

        monkeypatch.delenv(EXPECTED_DATABASE_ENV, raising=False)
        code = migrate.main(["--to", str(APP_SCHEMA_VERSION)])

        assert code == 2
        assert EXPECTED_DATABASE_ENV in capsys.readouterr().out

    def test_dry_run_also_needs_the_target(self, monkeypatch, capsys):
        """Một bản xem trước của NHẦM cơ sở dữ liệu là thứ trấn an sai."""
        from app.cli import migrate
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV

        monkeypatch.delenv(EXPECTED_DATABASE_ENV, raising=False)
        code = migrate.main(["--to", str(APP_SCHEMA_VERSION), "--dry-run"])

        assert code == 2
        assert EXPECTED_DATABASE_ENV in capsys.readouterr().out

    def test_status_does_not_need_the_target(self, monkeypatch):
        """`--status` chỉ đọc. Bắt khai đích ở đây chỉ dạy người ta đặt biến
        môi trường theo phản xạ — đúng thói quen làm chốt chặn mất tác dụng."""
        from app.cli import migrate
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV

        monkeypatch.delenv(EXPECTED_DATABASE_ENV, raising=False)
        assert migrate.main(["--status"]) == 0

    def test_it_refuses_a_target_this_image_cannot_write(self, monkeypatch, capsys):
        from app.cli import migrate
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV

        monkeypatch.setenv(EXPECTED_DATABASE_ENV, _current_database())
        code = migrate.main(["--to", str(APP_SCHEMA_VERSION + 1)])

        assert code == 2
        assert "TU CHOI" in capsys.readouterr().out

    def test_it_refuses_to_migrate_backwards(self, monkeypatch, capsys):
        """Không có migration lùi. Đường quay lui duy nhất là khôi phục."""
        from app.cli import migrate
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV

        monkeypatch.setenv(EXPECTED_DATABASE_ENV, _current_database())
        # Giả vờ cơ sở dữ liệu đã đi xa hơn ảnh này.
        monkeypatch.setattr(
            migrate, "_current_version",
            lambda: (APP_SCHEMA_VERSION + 3, "signdb-gia-dinh"),
        )
        code = migrate.main(["--to", str(APP_SCHEMA_VERSION)])

        assert code == 2
        out = capsys.readouterr().out
        assert "khoi phuc" in out.lower() or "sao luu" in out.lower()

    def test_adopt_refuses_an_incomplete_schema(self, monkeypatch, capsys):
        """Đóng dấu một lược đồ dở dang biến cổng thành đồ trang trí."""
        from app.cli import migrate
        from app.storage.metadata_db import EXPECTED_DATABASE_ENV

        monkeypatch.setenv(EXPECTED_DATABASE_ENV, _current_database())
        monkeypatch.setattr(migrate, "_current_version",
                            lambda: (None, "signdb-gia-dinh"))
        monkeypatch.setattr(migrate, "_schema_looks_complete",
                            lambda: ["table memberships", "view tenant_members"])

        assert migrate.cmd_adopt() == 2
        assert "TU CHOI" in capsys.readouterr().out

    def test_adopt_is_a_noop_on_an_already_stamped_database(self, monkeypatch, capsys):
        from app.cli import migrate

        monkeypatch.setattr(migrate, "_current_version",
                            lambda: (APP_SCHEMA_VERSION, "signdb-gia-dinh"))
        assert migrate.cmd_adopt() == 0
        assert "khong can adopt" in capsys.readouterr().out


def _current_database() -> str:
    from app.storage.metadata_db import _migration_cursor

    with _migration_cursor() as cur:
        cur.execute("SELECT current_database()")
        return cur.fetchone()[0]

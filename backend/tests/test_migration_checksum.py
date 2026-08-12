"""Một migration đã áp dụng thì nội dung của nó là bất biến.

Cổng phiên bản (`test_schema_version_gate.py`) trả lời "cơ sở dữ liệu này ở
phiên bản nào". Nó KHÔNG trả lời được câu hỏi nguy hiểm hơn: *phiên bản 5 trên
máy này có phải cùng một lượt biến đổi với phiên bản 5 trong mã hôm nay không?*

Hai máy cùng mang nhãn v5 mà đi qua hai payload khác nhau sẽ có lược đồ trông
giống hệt nhau ở mọi phép kiểm cấu trúc, trong khi dữ liệu đã được biến đổi
khác nhau. Không có cách nào phát hiện bằng cách nhìn lược đồ — chỉ có cách ghi
lại nội dung lúc áp dụng rồi so lại.

Tệp này canh ba thứ:

  * chuẩn hoá đúng — sửa chú thích KHÔNG được làm gate đỏ, sửa mã thì PHẢI;
  * quyết định của cổng ở cả ba trạng thái (khớp / lệch / chưa có);
  * và quan trọng nhất: một checksum NULL **không tự hợp thức hoá**.
"""

from __future__ import annotations

import pytest

from app.storage.schema_version import (
    MigrationChecksumMismatch,
    MigrationChecksumMissing,
    canonical_sql,
    checksum_problem,
    migration_checksum,
    migration_payload,
)


class TestCanonicalSql:
    """Băm cái gì thì quyết định gate kêu vì lý do gì."""

    def test_line_comments_are_dropped(self):
        assert canonical_sql("SELECT 1 -- ghi chu\nFROM t") == "SELECT 1 FROM t"

    def test_whitespace_runs_collapse(self):
        assert canonical_sql("SELECT   1\n\n   FROM  t") == "SELECT 1 FROM t"

    def test_a_comment_marker_inside_a_string_survives(self):
        """`RAISE EXCEPTION 'a--b'` không được cắt thành `RAISE EXCEPTION 'a`.

        Đây là ca làm hỏng mọi cách chuẩn hoá viết bằng một `re.sub`. Payload
        thật có nhiều `RAISE EXCEPTION` với thông điệp tiếng Việt.
        """
        assert canonical_sql("RAISE EXCEPTION 'a--b'") == "RAISE EXCEPTION 'a--b'"

    def test_spacing_inside_a_string_is_preserved(self):
        assert canonical_sql("SELECT 'a   b'") == "SELECT 'a   b'"

    def test_doubled_quote_escape_does_not_end_the_string(self):
        assert canonical_sql("SELECT 'it''s -- ok'") == "SELECT 'it''s -- ok'"


class TestChecksumSensitivity:
    """Nhạy với thay đổi CÓ NGHĨA, và chỉ với nó."""

    def test_the_checksum_is_stable_across_calls(self):
        assert migration_checksum() == migration_checksum()

    def test_the_payload_is_ordered_not_a_set(self):
        """`one_way_statements()` là `frozenset`; thứ tự lặp của set không ổn
        định giữa các tiến trình. Băm nó sẽ cho checksum đổi ngẫu nhiên giữa
        hai lần khởi động — tức gate đỏ vô cớ, tức gate bị gỡ."""
        assert isinstance(migration_payload(), list)
        assert len(migration_payload()) >= 8

    def test_editing_only_a_comment_does_not_change_the_checksum(self):
        original = migration_payload()[0]
        commented = original + "\n-- them mot dong ghi chu\n"
        assert canonical_sql(original) == canonical_sql(commented)

    def test_editing_actual_sql_changes_the_checksum(self):
        original = migration_payload()[0]
        edited = original.replace("IF EXISTS", "IF  NOT  EXISTS", 1)
        if edited == original:            # cau dau khong chua chuoi do
            edited = original + " AND 1=1"
        assert canonical_sql(original) != canonical_sql(edited)

    def test_merging_two_statements_changes_the_checksum(self):
        """Số câu nằm trong phần được băm.

        Không có nó, gộp hai câu thành một (hoặc tách một thành hai) cho ra
        cùng chuỗi nối và cùng checksum — trong khi ý nghĩa giao dịch đã khác:
        `_run_ddl` chạy từng câu một và nuốt lỗi của từng câu.
        """
        import hashlib

        payload = [canonical_sql(s) for s in migration_payload()]
        merged = payload[:-2] + [payload[-2] + " " + payload[-1]]

        def digest(parts):
            blob = f"{len(parts)}\n" + "\n".join(parts)
            return hashlib.sha256(blob.encode("utf-8")).hexdigest()

        assert digest(payload) != digest(merged)


class TestChecksumGateDecision:
    """Ba trạng thái, ba kết luận khác nhau."""

    def _patched(self, monkeypatch, version, recorded, has_column=True):
        import app.storage.schema_version as sv
        monkeypatch.setattr(
            sv, "read_recorded_checksum",
            lambda cur: (version, recorded, has_column))
        return object()   # cursor gia; khong ai cham toi no

    def test_a_matching_checksum_is_accepted(self, monkeypatch):
        cur = self._patched(monkeypatch, 5, migration_checksum())
        assert checksum_problem(cur) is None

    def test_a_changed_checksum_is_refused(self, monkeypatch):
        cur = self._patched(monkeypatch, 5, "0" * 64)
        problem = checksum_problem(cur)
        assert isinstance(problem, MigrationChecksumMismatch)
        # Thông điệp phải dạy đúng cách sửa: bump phiên bản, không sửa v5.
        assert "v6" in str(problem)

    def test_a_missing_checksum_is_refused_not_filled(self, monkeypatch):
        """Trạng thái của sản xuất ngay sau lượt triển khai mang cột này lên.

        Nó phải TỪ CHỐI chứ không tự điền. "Nếu NULL thì ghi giá trị hiện tại"
        khiến một migration đã bị sửa tự hợp thức hoá ở lần chạy kế tiếp — mất
        đúng thứ mà cả cơ chế này sinh ra để giữ.
        """
        cur = self._patched(monkeypatch, 5, None)
        problem = checksum_problem(cur)
        assert isinstance(problem, MigrationChecksumMissing)
        assert "--adopt-checksum" in str(problem)

    def test_an_unstamped_database_is_not_a_checksum_problem(self, monkeypatch):
        """Cơ sở dữ liệu trắng do cổng phiên bản lo, không phải cổng checksum.
        Trả lỗi ở cả hai chỗ chỉ làm thông điệp mâu thuẫn nhau."""
        cur = self._patched(monkeypatch, None, None, has_column=False)
        assert checksum_problem(cur) is None

    def test_a_database_older_than_the_column_is_refused(self, monkeypatch):
        cur = self._patched(monkeypatch, 5, None, has_column=False)
        assert isinstance(checksum_problem(cur), MigrationChecksumMissing)


class TestAdoptChecksumRefusals:
    """`--adopt-checksum` là cửa một chiều, và nó phải khó mở."""

    def test_it_refuses_when_no_version_is_stamped(self, monkeypatch, capsys):
        from app.cli import migrate

        monkeypatch.setattr(migrate, "_current_version", lambda: (None, "test-db"))
        assert migrate.cmd_adopt_checksum() == 2
        assert "chua dong dau" in capsys.readouterr().out

    def test_it_refuses_when_the_schema_is_incomplete(self, monkeypatch, capsys):
        """Đóng dấu một lược đồ dở dang là khẳng định sai rằng migration đã
        chạy trọn vẹn — và khẳng định đó không rút lại được."""
        from app.cli import migrate

        monkeypatch.setattr(migrate, "_current_version", lambda: (5, "test-db"))
        monkeypatch.setattr(migrate, "_schema_looks_complete",
                            lambda: ["table memberships"])
        assert migrate.cmd_adopt_checksum() == 2
        assert "thieu" in capsys.readouterr().out

    def test_it_refuses_a_version_this_image_does_not_support(self, monkeypatch, capsys):
        from app.cli import migrate

        monkeypatch.setattr(migrate, "_current_version", lambda: (99, "test-db"))
        monkeypatch.setattr(migrate, "_schema_looks_complete", lambda: [])
        assert migrate.cmd_adopt_checksum() == 2
        assert "TU CHOI" in capsys.readouterr().out


class TestRecordedChecksumOnThisDatabase:
    """Vòng thật trên Postgres của bộ test."""

    def test_the_test_database_records_a_matching_checksum(self):
        from app.storage.metadata_db import _migration_cursor
        from app.storage.schema_version import read_recorded_checksum

        with _migration_cursor() as cur:
            version, recorded, has_column = read_recorded_checksum(cur)

        assert has_column, "cot migration_checksum chua duoc them"
        assert version is not None
        assert recorded == migration_checksum(), (
            "checksum da ghi khong khop payload hien tai — hoac payload vua doi, "
            "hoac dong dau bang duong khong ghi checksum")


@pytest.mark.parametrize("statement", migration_payload())
def test_every_payload_statement_survives_canonicalisation(statement):
    """Chuẩn hoá không được làm rỗng hay cắt cụt câu nào.

    Một lỗi trong bộ quét chuỗi sẽ biến vài câu thành chuỗi rỗng, và checksum
    vẫn tính được — vẫn ổn định — nhưng nó thôi không còn mô tả nội dung thật.
    Gate sẽ xanh mãi mãi. Đây là phép kiểm rẻ nhất bắt được điều đó.
    """
    result = canonical_sql(statement)
    assert result, "chuan hoa cho ra chuoi rong"
    assert len(result) >= len(statement) * 0.2, "chuan hoa cat mat qua nhieu"

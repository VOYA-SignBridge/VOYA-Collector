"""A1 — `tenant_id` in the source of truth.

What this suite is defending
----------------------------
Before A1, `tenant_id` existed on 12 Postgres tables but on neither CSV. The
CSVs are the source of truth and `init_db()` rebuilds Postgres from them when
the schema check fails, so a rebuild would have returned every row as the
bootstrap tenant — silently reassigning another tenant's entire corpus, with no
error and no evidence left behind because the CSV never held the tenant.

Fixing that introduces a second, subtler way to lose the same data: if the
CSV→DB upsert treats "this row says nothing about its tenant" as "this row
belongs to the bootstrap tenant", then every startup sync from a mirror written
by an older machine rewrites tenant B's rows to 'default'. The distinction
between *absent* and *default* is therefore the load-bearing part of A1.

How these tests try not to lie
------------------------------
Three rules, because a green suite that cannot fail is worse than no suite:

1. **No assertion on source text where behaviour can be observed.** An earlier
   draft of this file asserted `"tenant_id" in inspect.getsource(...)` to check
   a SELECT list. It passed unconditionally — the word also appeared in the
   comment above the query. Every such check is now a real call with a real
   result.
2. **Every input-handling test walks a type zoo**, not one happy string. The
   values that actually reach these functions come from CSV cells, JSON bodies
   and psycopg2 rows, and each of those can produce a different Python type for
   what a developer pictures as "the tenant".
3. **The motivating bug has an end-to-end test with a negative control**
   (`TestRebuildFromCsv`): the same rebuild is run with and without the column,
   and the without-case is asserted to LOSE the tenant. If A1 were reverted, the
   positive test would fail; if the test itself stopped exercising anything, the
   negative control would fail too.
"""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from app.tenancy import (
    DEFAULT_TENANT_ID,
    TENANT_COLUMN,
    is_valid_tenant_id,
    normalize_tenant_id,
    optional_tenant_id,
    tenant_id_of,
)


# ---------------------------------------------------------------------------
# Shared type zoo
#
# Not decoration: these are the shapes that genuinely arrive. csv gives str,
# psycopg2 gives str or None, a JSON body gives int/float/bool/list/dict, and a
# file read in binary mode gives bytes. Each used to be a different way to end
# up with a tenant partition nobody intended.
# ---------------------------------------------------------------------------

NON_STRING_VALUES = [
    pytest.param(123, id="int"),
    pytest.param(12.5, id="float"),
    pytest.param(True, id="bool"),
    pytest.param(b"default", id="bytes"),
    pytest.param(["default"], id="list"),
    pytest.param({"tenant_id": "default"}, id="dict"),
    pytest.param(("default",), id="tuple"),
    pytest.param(object(), id="object"),
]

MALFORMED_STRINGS = [
    pytest.param("Default", id="uppercase"),
    pytest.param("TRUONG-B", id="all-caps"),
    pytest.param("-leading-hyphen", id="leading-hyphen"),
    pytest.param("_leading-underscore", id="leading-underscore"),
    pytest.param("has space", id="inner-space"),
    pytest.param("truong\tb", id="tab"),
    pytest.param("truong\nb", id="inner-newline"),
    pytest.param("has/slash", id="slash"),
    pytest.param("has\\backslash", id="backslash"),
    pytest.param("has.dot", id="dot"),
    pytest.param("..", id="parent-dir"),
    pytest.param("../etc/passwd", id="path-traversal"),
    pytest.param("truong-b'; DROP TABLE samples--", id="sql-ish"),
    pytest.param("tenant;drop", id="semicolon"),
    pytest.param("trường-b", id="unicode-diacritics"),
    pytest.param("租户", id="unicode-cjk"),
    pytest.param("tenant%s", id="percent-format"),
    pytest.param("x" * 64, id="too-long-64"),
]

WELL_FORMED_STRINGS = [
    pytest.param("default", id="bootstrap"),
    pytest.param("a", id="single-char"),
    pytest.param("9", id="single-digit"),
    pytest.param("truong-b", id="hyphenated"),
    pytest.param("ctu_2026", id="underscored"),
    pytest.param("a1b2c3", id="alphanumeric"),
    pytest.param("x" * 63, id="max-length-63"),
]

BLANKS = [
    pytest.param(None, id="none"),
    pytest.param("", id="empty"),
    pytest.param("   ", id="spaces"),
    pytest.param("\t", id="tab-only"),
    pytest.param("\n", id="newline-only"),
    pytest.param(" \t\n ", id="mixed-whitespace"),
]


# ---------------------------------------------------------------------------
# 1. Tenancy primitives
# ---------------------------------------------------------------------------

class TestValidation:
    def test_the_constant_passes_its_own_validator(self):
        # It is interpolated into DDL as DEFAULT '<id>'; the import guard in
        # app/tenancy.py should have raised before any SQL was built otherwise.
        assert is_valid_tenant_id(DEFAULT_TENANT_ID)

    @pytest.mark.parametrize("value", WELL_FORMED_STRINGS)
    def test_accepts_well_formed(self, value):
        assert is_valid_tenant_id(value)

    @pytest.mark.parametrize("value", MALFORMED_STRINGS)
    def test_rejects_malformed(self, value):
        assert not is_valid_tenant_id(value)

    @pytest.mark.parametrize("value", BLANKS)
    def test_rejects_blank(self, value):
        assert not is_valid_tenant_id(value)

    @pytest.mark.parametrize("value", NON_STRING_VALUES)
    def test_rejects_non_strings(self, value):
        assert not is_valid_tenant_id(value)

    @pytest.mark.parametrize(
        "value",
        [
            pytest.param("truong-b\n", id="trailing-lf"),
            pytest.param("truong-b\r\n", id="trailing-crlf"),
            pytest.param("truong-b\r", id="trailing-cr"),
            pytest.param("truong-b\t", id="trailing-tab"),
            pytest.param("truong-b ", id="trailing-space"),
            pytest.param(" truong-b", id="leading-space"),
        ],
    )
    def test_rejects_unstripped_surrounding_whitespace(self, value):
        r"""Regression: the anchors used to be ^ and $.

        In Python `$` ALSO matches immediately before a trailing newline, so
        "truong-b\n" validated as a well-formed id. Written into a CSV it breaks
        the row; used as a directory name (A4) it creates a path with a newline;
        and it compares unequal to "truong-b", so it is a separate partition
        that looks identical in every log line. `\Z` is what makes it false.

        This function does NOT strip — callers that should tolerate stray
        whitespace go through normalize_tenant_id, which strips first.
        """
        assert not is_valid_tenant_id(value)


class TestNormalize:
    """`normalize_tenant_id` — the CSV WRITE path: a new row must get an owner."""

    @pytest.mark.parametrize("value", BLANKS)
    def test_blank_becomes_the_bootstrap_tenant(self, value):
        assert normalize_tenant_id(value) == DEFAULT_TENANT_ID

    @pytest.mark.parametrize("value", WELL_FORMED_STRINGS)
    def test_well_formed_passes_through(self, value):
        assert normalize_tenant_id(value) == value

    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param("  truong-b  ", id="spaces"),
            pytest.param("\ttruong-b\n", id="tab-and-lf"),
            pytest.param("truong-b\r\n", id="crlf"),
            pytest.param("truong-b\n", id="lf"),
        ],
    )
    def test_surrounding_whitespace_is_stripped(self, raw):
        """Stripping happens HERE, not in the validator.

        A CSV cell edited by hand in a spreadsheet routinely gains a space, and
        a file written with CRLF hands back a trailing \\r. Both mean the same
        tenant, so normalize repairs them — while is_valid_tenant_id keeps
        rejecting the raw form, which is what stops the unstripped value from
        becoming its own partition.
        """
        assert normalize_tenant_id(raw) == "truong-b"

    @pytest.mark.parametrize("value", MALFORMED_STRINGS)
    def test_malformed_raises_rather_than_being_repaired(self, value):
        # Coercing a typo would let it quietly become a new partition.
        with pytest.raises(ValueError):
            normalize_tenant_id(value)

    @pytest.mark.parametrize("value", NON_STRING_VALUES)
    def test_non_strings_raise_type_error(self, value):
        # str(123) is "123", which matches the alphabet — so without an explicit
        # type check an integer would silently become tenant "123".
        with pytest.raises(TypeError):
            normalize_tenant_id(value)

    def test_fallback_is_overridable(self):
        assert normalize_tenant_id(None, fallback="truong-b") == "truong-b"


class TestOptional:
    """`optional_tenant_id` — the DB UPSERT path: absent must stay absent."""

    @pytest.mark.parametrize("value", BLANKS)
    def test_blank_returns_none_not_the_default(self, value):
        """THE regression guard for A1.

        If this ever returns DEFAULT_TENANT_ID, every startup sync from a CSV
        written before the tenant column existed rewrites other tenants' rows to
        the bootstrap tenant — no error at any layer.
        """
        assert optional_tenant_id(value) is None

    @pytest.mark.parametrize("value", WELL_FORMED_STRINGS)
    def test_well_formed_passes_through(self, value):
        assert optional_tenant_id(value) == value

    @pytest.mark.parametrize("value", MALFORMED_STRINGS)
    def test_malformed_raises(self, value):
        with pytest.raises(ValueError):
            optional_tenant_id(value)

    @pytest.mark.parametrize("value", NON_STRING_VALUES)
    def test_non_strings_raise_type_error(self, value):
        with pytest.raises(TypeError):
            optional_tenant_id(value)


class TestRowAccessor:
    @pytest.mark.parametrize("value", WELL_FORMED_STRINGS)
    def test_reads_the_agreed_key(self, value):
        assert tenant_id_of({TENANT_COLUMN: value}) == value

    @pytest.mark.parametrize("row", [{}, {TENANT_COLUMN: None}, {TENANT_COLUMN: ""}])
    def test_missing_or_blank_falls_back(self, row):
        assert tenant_id_of(row) == DEFAULT_TENANT_ID

    def test_other_keys_are_ignored(self):
        # Guards against an accessor that scans values instead of the one key.
        assert tenant_id_of({"user_id": "truong-b"}) == DEFAULT_TENANT_ID


# ---------------------------------------------------------------------------
# 2. Both CSV schemas carry the column, and adding it shifted nothing
# ---------------------------------------------------------------------------

def test_sample_fields_never_shift_existing_columns():
    """Bất biến thật là *cột cũ không xê dịch*, không phải *tenant_id đứng cuối*.

    Bài này trước đây khẳng định `SAMPLE_FIELDS[-1] == TENANT_COLUMN`, đúng vào
    lúc `tenant_id` là cột mới nhất. Ngày 21/08/2026 thêm `review_status`
    (trạng thái kiểm duyệt cộng đồng) và nó phải nằm SAU `tenant_id` — đúng theo
    chính lý do nêu ở đây: bản nhân bản Google Sheets phát header nguyên văn
    thành dòng 1, nên một cột chèn vào bất kỳ đâu ngoài vị trí cuối sẽ đẩy mọi
    cột Sheets hiện có sang phải một ô.

    Đây là lần thứ HAI cùng một bài kiểm phải đổi hình vì cùng một lý do —
    `test_label_fields_never_shift_existing_columns` đã đi qua đúng chuyện này
    ngày 14/08 khi thêm cột `region`. Ghim theo VỊ TRÍ, không theo "đứng cuối".
    """
    from app.dataset_samples import SAMPLE_FIELDS

    assert SAMPLE_FIELDS.count(TENANT_COLUMN) == 1
    # 32 là vị trí của tenant_id từ khi nó được thêm; thay đổi số này nghĩa là
    # một cột đã bị chèn vào TRƯỚC nó, và bảng tính Sheets đang chạy đã lệch.
    assert SAMPLE_FIELDS.index(TENANT_COLUMN) == 32
    # Cột mới nhất đứng cuối.
    assert SAMPLE_FIELDS[-1] == "review_status"


def test_label_fields_never_shift_existing_columns():
    """Bất biến thật là *cột cũ không xê dịch*, không phải *tenant_id đứng cuối*.

    Bài này trước đây khẳng định `LABEL_FIELDS[-1] == TENANT_COLUMN`, đúng vào
    lúc `tenant_id` là cột mới nhất. Ngày 14/08/2026 thêm cột `region` (tách
    vùng miền khỏi `dialect`) và nó phải nằm SAU `tenant_id` — đúng theo chính
    lý do nêu ở bài kiểm phía trên: cột mới chèn vào bất kỳ đâu ngoài vị trí
    cuối sẽ đẩy mọi cột Sheets hiện có sang phải một ô.

    Nên ghim thứ hai thứ: `tenant_id` vẫn ở đúng chỉ số cũ (không bị đẩy), và
    cột mới nhất đứng cuối.
    """
    from app.dataset_manager import LABEL_FIELDS

    assert LABEL_FIELDS.count(TENANT_COLUMN) == 1
    # 19 là vị trí của tenant_id từ khi nó được thêm; thay đổi số này nghĩa là
    # một cột đã bị chèn vào giữa và bản chiếu Sheets đã lệch.
    assert LABEL_FIELDS.index(TENANT_COLUMN) == 19
    assert LABEL_FIELDS[-1] == "region"


def test_raw_upload_fields_end_with_tenant_id():
    from app.raw_uploads import RAW_UPLOAD_FIELDS

    assert RAW_UPLOAD_FIELDS[-1] == TENANT_COLUMN
    assert RAW_UPLOAD_FIELDS.count(TENANT_COLUMN) == 1


@pytest.mark.parametrize(
    "module,attr,table",
    [
        ("app.dataset_samples", "SAMPLE_FIELDS", "samples"),
        ("app.dataset_manager", "LABEL_FIELDS", "classes"),
        ("app.raw_uploads", "RAW_UPLOAD_FIELDS", "raw_uploads"),
    ],
)
def test_sot_manifest_promises_every_csv_column(module, attr, table):
    """The manifest is what a reader machine verifies its schema against.

    A column the writer emits but the manifest does not promise is how a reader
    passes verification and then fails mid-import.
    """
    import importlib

    from app.sot.catalog_schema import REQUIRED_COLUMNS

    fields = getattr(importlib.import_module(module), attr)
    assert TENANT_COLUMN in fields
    assert TENANT_COLUMN in REQUIRED_COLUMNS[table]


# ---------------------------------------------------------------------------
# 3. The samples.csv migration: backfills a VALUE and corrupts nothing
# ---------------------------------------------------------------------------

@pytest.fixture
def csv_module(tmp_path, monkeypatch):
    import app.dataset_samples as ds

    path = tmp_path / "samples.csv"
    monkeypatch.setattr(ds, "SAMPLES_CSV", path)
    monkeypatch.setattr(ds, "SAMPLES_DIR", tmp_path)
    monkeypatch.setattr(ds, "DATASET_ROOT", tmp_path)
    return ds, path


def _write(path: Path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def _read(path: Path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


class TestSamplesMigration:
    def test_backfills_existing_rows_with_the_value(self, csv_module):
        ds, path = csv_module
        _write(path, [["sample_uid", "slug"], ["a", "x"], ["b", "y"]])

        assert ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID) is True

        assert _read(path) == [
            ["sample_uid", "slug", TENANT_COLUMN],
            ["a", "x", DEFAULT_TENANT_ID],
            ["b", "y", DEFAULT_TENANT_ID],
        ]

    def test_default_fill_stays_blank_for_other_columns(self, csv_module):
        """auth_user_id must keep its old behaviour.

        The owner of a historical row is genuinely unknown, and writing a guess
        would manufacture attribution. Only tenant_id has a provable backfill.
        """
        ds, path = csv_module
        _write(path, [["sample_uid"], ["a"]])

        assert ds.ensure_samples_column("auth_user_id") is True
        assert _read(path)[1] == ["a", ""]

    def test_is_idempotent(self, csv_module):
        ds, path = csv_module
        _write(path, [["sample_uid"], ["a"]])

        assert ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID) is True
        assert ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID) is False
        assert _read(path)[1] == ["a", DEFAULT_TENANT_ID]

    def test_second_call_does_not_overwrite_a_real_tenant(self, csv_module):
        """Idempotency must be a no-op, not a re-fill.

        Re-running the migration on a file that already holds tenant B rows must
        not reset them — the boot path calls it on every start.
        """
        ds, path = csv_module
        _write(path, [["sample_uid", TENANT_COLUMN], ["a", "truong-b"]])

        assert ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID) is False
        assert _read(path)[1] == ["a", "truong-b"]

    def test_short_row_is_padded_with_blanks_not_the_fill(self, csv_module):
        """Padding and the new cell are different things.

        If they shared a value, a row missing two trailing cells would end up
        with 'default' sitting in, say, quality_status.
        """
        ds, path = csv_module
        _write(path, [["sample_uid", "slug", "quality_status"], ["a"]])

        ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID)

        assert _read(path)[1] == ["a", "", "", DEFAULT_TENANT_ID]

    def test_over_long_row_is_refused_rather_than_misaligned(self, csv_module):
        """A row with MORE cells than the header cannot be migrated safely.

        Appending the tenant after the surplus cells would put it under no
        column at all and shift the reader's view of that row. Raising is the
        safe outcome: db.py wraps this call in try/except, so boot continues
        with the migration skipped and the catalog untouched, instead of
        rewriting the source of truth into a misaligned state.
        """
        ds, path = csv_module
        _write(path, [["sample_uid", "slug"], ["a", "x", "surplus"]])

        with pytest.raises(ValueError):
            ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID)

    def test_original_file_survives_a_refused_migration(self, csv_module):
        ds, path = csv_module
        before = [["sample_uid", "slug"], ["a", "x", "surplus"]]
        _write(path, before)

        with pytest.raises(ValueError):
            ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID)

        assert _read(path) == before
        assert not (path.parent / (path.name + ".tmp")).exists()

    @pytest.mark.parametrize(
        "label",
        [
            pytest.param("Xin chào, bạn", id="comma"),
            pytest.param('He said "hi"', id="double-quote"),
            pytest.param("line1\nline2", id="embedded-newline"),
            pytest.param("Tiếng Việt có dấu ăằẵ", id="unicode"),
            pytest.param("  padded  ", id="surrounding-spaces"),
            pytest.param("semi;colon\ttab", id="semicolon-tab"),
            pytest.param("", id="empty-cell"),
        ],
    )
    def test_migration_preserves_cell_contents_exactly(self, csv_module, label):
        """The migration rewrites the whole file; nothing may be re-encoded.

        These are real label values — sign-language labels are Vietnamese prose
        and go through Google Sheets, which is exactly where commas, quotes and
        newlines come from.
        """
        ds, path = csv_module
        _write(path, [["sample_uid", "label_original"], ["a", label]])

        ds.ensure_samples_column(TENANT_COLUMN, fill=DEFAULT_TENANT_ID)

        with open(path, newline="", encoding="utf-8") as f:
            row = next(csv.DictReader(f))
        assert row["label_original"] == label
        assert row[TENANT_COLUMN] == DEFAULT_TENANT_ID


# ---------------------------------------------------------------------------
# 4. Writers stamp a tenant instead of leaving the cell empty
# ---------------------------------------------------------------------------

@pytest.fixture
def no_mirror(monkeypatch):
    """append_*_row pushes to Drive/Sheets; not in a unit test."""
    import app.storage.catalog_mirror as mirror

    monkeypatch.setattr(
        mirror, "mirror_samples_to_gdrive_and_sheets", lambda *a, **k: None
    )
    monkeypatch.setattr(mirror, "mirror_csv_to_gdrive", lambda *a, **k: None)


class TestWritersStampTenant:
    def test_sample_row_gets_the_bootstrap_tenant(self, csv_module, no_mirror):
        """csv.DictWriter uses restval="", so an omitted key writes an EMPTY
        cell. Without the stamp a freshly captured sample lands in the source of
        truth owned by nobody, and nothing raises."""
        ds, path = csv_module
        ds.append_sample_row({"sample_uid": "a", "slug": "x"})

        with open(path, newline="", encoding="utf-8") as f:
            assert next(csv.DictReader(f))[TENANT_COLUMN] == DEFAULT_TENANT_ID

    def test_sample_row_keeps_an_explicit_tenant(self, csv_module, no_mirror):
        ds, path = csv_module
        ds.append_sample_row({"sample_uid": "a", TENANT_COLUMN: "truong-b"})

        with open(path, newline="", encoding="utf-8") as f:
            assert next(csv.DictReader(f))[TENANT_COLUMN] == "truong-b"

    def test_sample_row_refuses_a_malformed_tenant(self, csv_module, no_mirror):
        ds, _ = csv_module
        with pytest.raises(ValueError):
            ds.append_sample_row({"sample_uid": "a", TENANT_COLUMN: "Truong B"})

    def test_caller_dict_is_not_mutated(self, csv_module, no_mirror):
        ds, _ = csv_module
        caller_dict = {"sample_uid": "a"}
        ds.append_sample_row(caller_dict)
        assert TENANT_COLUMN not in caller_dict

    def test_label_row_gets_the_bootstrap_tenant(self, tmp_path, monkeypatch):
        import app.dataset_manager as dm

        path = tmp_path / "labels.csv"
        monkeypatch.setattr(dm, "MASTER_LABELS", path)
        monkeypatch.setattr(dm, "regenerate_label_indexes", lambda *a, **k: None)
        _write(path, [list(dm.LABEL_FIELDS)])

        dm.append_label_row({"class_uid": "c1", "slug": "xin-chao"})

        with open(path, newline="", encoding="utf-8") as f:
            assert next(csv.DictReader(f))[TENANT_COLUMN] == DEFAULT_TENANT_ID

    def test_class_metadata_defaults_and_honours_the_tenant(self):
        from app.dataset_manager import ClassMetadata

        common = dict(
            slug="xin-chao", label_original="Xin chào", language="vn",
            dialect="bac", is_common_global=False, is_common_language=False,
        )
        assert ClassMetadata(class_uid="c1", **common).to_label_row()[
            TENANT_COLUMN
        ] == DEFAULT_TENANT_ID
        assert ClassMetadata(
            class_uid="c2", tenant_id="truong-b", **common
        ).to_label_row()[TENANT_COLUMN] == "truong-b"


class TestRawUploadsMigration:
    @pytest.fixture
    def raw_module(self, tmp_path, monkeypatch):
        import app.raw_uploads as ru

        path = tmp_path / "uploads.csv"
        monkeypatch.setattr(ru, "RAW_UPLOADS_CSV", path)
        monkeypatch.setattr(ru, "RAW_UPLOADS_DIR", tmp_path)
        return ru, path

    def test_header_upgrade_backfills_and_preserves_rows(self, raw_module):
        """append_raw_upload_row writes with the full fieldnames but only emits
        a header for an EMPTY file — so a 15-column file gaining a 16-column row
        would put every value one place left of its name."""
        ru, path = raw_module
        old_header = [c for c in ru.RAW_UPLOAD_FIELDS if c != TENANT_COLUMN]
        _write(path, [old_header, ["u1"] + [""] * (len(old_header) - 1)])

        assert ru._upgrade_raw_uploads_header() is True

        rows = _read(path)
        assert rows[0] == list(ru.RAW_UPLOAD_FIELDS)
        assert rows[1][0] == "u1"
        assert rows[1][-1] == DEFAULT_TENANT_ID

    def test_header_upgrade_is_idempotent(self, raw_module):
        ru, path = raw_module
        _write(path, [list(ru.RAW_UPLOAD_FIELDS)])
        assert ru._upgrade_raw_uploads_header() is False

    def test_append_stamps_the_tenant(self, raw_module, no_mirror):
        ru, path = raw_module
        ru.append_raw_upload_row({"upload_uid": "u1"})

        with open(path, newline="", encoding="utf-8") as f:
            assert next(csv.DictReader(f))[TENANT_COLUMN] == DEFAULT_TENANT_ID


# ---------------------------------------------------------------------------
# 5. DB→CSV projections never emit an unassigned row
# ---------------------------------------------------------------------------

class TestProjections:
    def test_sample_projection_forces_a_tenant(self):
        from app.dataset_samples import _db_row_to_csv_row

        assert _db_row_to_csv_row({"sample_uid": "a"})[TENANT_COLUMN] == DEFAULT_TENANT_ID
        assert _db_row_to_csv_row(
            {"sample_uid": "a", TENANT_COLUMN: "truong-b"}
        )[TENANT_COLUMN] == "truong-b"

    def test_class_projection_forces_a_tenant(self):
        from app.catalog_sync import _db_class_row_to_label_row

        assert _db_class_row_to_label_row({"class_uid": "c"})[
            TENANT_COLUMN
        ] == DEFAULT_TENANT_ID


# ---------------------------------------------------------------------------
# 6. Payload builders: absent stays absent, all the way to the placeholder
# ---------------------------------------------------------------------------

UPSERT_FNS = [
    pytest.param("insert_sample", "sample_uid", id="samples"),
    pytest.param("upsert_class", "class_uid", id="classes"),
    pytest.param("insert_raw_upload", "upload_uid", id="raw_uploads"),
]


class TestPayloads:
    @pytest.mark.parametrize("fn_name,uid_key", UPSERT_FNS)
    @pytest.mark.parametrize("row_extra", [{}, {TENANT_COLUMN: None}, {TENANT_COLUMN: ""}])
    def test_silence_reaches_sql_as_none(self, fn_name, uid_key, row_extra, monkeypatch):
        from app.storage import metadata_db as mdb

        captured = {}
        monkeypatch.setattr(mdb, "_execute", lambda sql, params: captured.update(params))
        getattr(mdb, fn_name)({uid_key: "x", **row_extra})

        assert captured[TENANT_COLUMN] is None

    @pytest.mark.parametrize("fn_name,uid_key", UPSERT_FNS)
    def test_explicit_tenant_reaches_sql(self, fn_name, uid_key, monkeypatch):
        from app.storage import metadata_db as mdb

        captured = {}
        monkeypatch.setattr(mdb, "_execute", lambda sql, params: captured.update(params))
        getattr(mdb, fn_name)({uid_key: "x", TENANT_COLUMN: "truong-b"})

        assert captured[TENANT_COLUMN] == "truong-b"

    @pytest.mark.parametrize("fn_name,uid_key", UPSERT_FNS)
    def test_malformed_tenant_never_reaches_sql(self, fn_name, uid_key, monkeypatch):
        from app.storage import metadata_db as mdb

        called = []
        monkeypatch.setattr(mdb, "_execute", lambda sql, params: called.append(params))
        with pytest.raises(ValueError):
            getattr(mdb, fn_name)({uid_key: "x", TENANT_COLUMN: "Truong B"})
        assert called == []


def test_ddl_never_spells_the_tenant_inline():
    """Every tenant default in the schema comes from the one constant.

    The point is auditability: "do all writers agree on the bootstrap tenant?"
    should be a fact about one symbol, not a grep across string literals.
    """
    from app.storage.metadata_db import DDL_STATEMENTS, MIGRATION_STATEMENTS

    tenant_defaults = [
        line.strip()
        for stmt in (*DDL_STATEMENTS, *MIGRATION_STATEMENTS)
        for line in stmt.splitlines()
        if "tenant_id" in line and "DEFAULT '" in line
    ]
    assert tenant_defaults, "expected the schema to declare tenant defaults"
    for line in tenant_defaults:
        assert f"DEFAULT '{DEFAULT_TENANT_ID}'" in line, (
            f"tenant default not sourced from the constant: {line}"
        )


# ---------------------------------------------------------------------------
# 7. Real Postgres — the behaviour, not the SQL text
# ---------------------------------------------------------------------------

TENANT_B = "a1-test-tenant"
CLASS_UID = "a1-test-class"
# Lớp thứ hai, thuộc tenant khởi tạo.
#
# Cần từ schema v3: `samples` nay mang khoá ngoại GHÉP (tenant_id, class_uid)
# thay cho khoá một cột, nên một mẫu ở tenant A không còn trỏ được sang lớp của
# tenant B. Ba test dưới đây chuyển mẫu về tenant khởi tạo, và khi đó lớp đích
# phải tồn tại ở ĐÓ.
#
# Không thể dùng lại `CLASS_UID` cho cả hai tenant như fixture đang làm với
# `dialects`: khoá chính của `dialects` là (tenant_id, dialect_id) nên cùng một
# id sống được ở hai tenant, còn khoá chính của `classes` là `class_uid` một
# cột. Hệ quả đáng ghi lại: với lược đồ hiện tại, chuyển một mẫu sang tenant
# khác BẮT BUỘC phải trỏ nó sang một lớp khác — không có cách nào khác.
CLASS_UID_DEFAULT = "a1-test-class-default"
SAMPLE_UID = "a1de57ab09"   # samples_uid_is_hex10 CHECK: uuid4().hex[:10] shape
DIALECT = "a1tst"


@pytest.fixture
def tenant_b():
    """A second tenant owning one class and one sample.

    Isolation cannot be demonstrated with a single tenant, and neither can the
    overwrite bug: with only 'default' present, every wrong answer happens to
    look like the right one.
    """
    from app.storage.metadata_db import _execute, _fetch_all, ensure_tables

    ensure_tables()

    def cleanup():
        _execute("DELETE FROM samples WHERE sample_uid = %s", (SAMPLE_UID,))
        _execute("DELETE FROM classes WHERE class_uid IN (%s, %s)",
                 (CLASS_UID, CLASS_UID_DEFAULT))
        _execute(
            "DELETE FROM dialects WHERE dialect_id = %s AND tenant_id IN (%s, %s)",
            (DIALECT, TENANT_B, DEFAULT_TENANT_ID),
        )
        _execute("DELETE FROM tenants WHERE tenant_id = %s", (TENANT_B,))

    cleanup()
    _execute(
        "INSERT INTO tenants(tenant_id, display_name, slug) VALUES(%s, %s, %s)",
        (TENANT_B, "A1 test tenant", TENANT_B),
    )
    # classes.dialect and samples.dialect carry a composite FK
    # (tenant_id, dialect) -> dialects. The synthetic dialect is registered for
    # BOTH tenants because one test moves a row to the bootstrap tenant, and the
    # FK correctly refuses that while the destination has no such dialect — a
    # genuine integrity property the fixture has to satisfy rather than dodge.
    for owner in (TENANT_B, DEFAULT_TENANT_ID):
        _execute(
            """
            INSERT INTO dialects(tenant_id, dialect_id, display_name, language, status)
            VALUES(%s, %s, 'A1 test dialect', 'vn', 'approved')
            ON CONFLICT (tenant_id, dialect_id) DO NOTHING
            """,
            (owner, DIALECT),
        )
    _execute(
        """
        INSERT INTO classes(class_uid, class_idx, slug, label_original,
                            language, dialect, folder_name, tenant_id)
        VALUES(%s, 99123, 'a1-test-slug', 'A1 Test', 'vn', %s, 'a1_test_folder', %s)
        """,
        (CLASS_UID, DIALECT, TENANT_B),
    )
    # Bản sao ở tenant khởi tạo, cùng lý do fixture đăng ký phương ngữ cho cả
    # hai tenant: khoá ngoại ghép từ chối đúng, và fixture phải thoả nó chứ
    # không né. `class_idx` khác đi vì `uq_classes_tenant_class_idx` là duy
    # nhất theo từng tenant, không phải toàn cục.
    _execute(
        """
        INSERT INTO classes(class_uid, class_idx, slug, label_original,
                            language, dialect, folder_name, tenant_id)
        VALUES(%s, 99124, 'a1-test-slug-default', 'A1 Test', 'vn', %s,
               'a1_test_folder_default', %s)
        """,
        (CLASS_UID_DEFAULT, DIALECT, DEFAULT_TENANT_ID),
    )
    _execute(
        """
        INSERT INTO samples(sample_uid, class_uid, slug, label_original, language,
                            dialect, source_type, session_id, file_path,
                            created_at, tenant_id)
        VALUES(%s, %s, 'a1-test-slug', 'A1 Test', 'vn', %s, 'web', 'a1-sess',
               '/mock/a1.npz', NOW(), %s)
        """,
        (SAMPLE_UID, CLASS_UID, DIALECT, TENANT_B),
    )

    yield _fetch_all

    cleanup()


def _tenant_of(fetch_all, table, key_col, key):
    rows = fetch_all(
        f"SELECT tenant_id FROM {table} WHERE {key_col} = %s", (key,)  # noqa: S608
    )
    assert rows, f"{table} row vanished — the fixture, not the assertion, is broken"
    return rows[0]["tenant_id"]


def _csv_shaped_sample(**overrides):
    """A row shaped like samples.csv hands one to the sync: all strings."""
    row = {
        "sample_uid": SAMPLE_UID,
        "class_uid": CLASS_UID,
        "slug": "a1-test-slug",
        "label_original": "A1 Test",
        "language": "vn",
        "dialect": DIALECT,
        "source_type": "web",
        "session_id": "a1-sess",
        "file_path": "/mock/a1.npz",
        "created_at": "",
        "seq_len": "",          # empty numerics are how the CSV mirror spells NULL
        "completeness": "",
    }
    row.update(overrides)
    return row


class TestAgainstPostgres:
    def test_fixture_really_created_a_second_tenant(self, tenant_b):
        # If this fails, every other test in the class is vacuous.
        assert _tenant_of(tenant_b, "samples", "sample_uid", SAMPLE_UID) == TENANT_B
        assert _tenant_of(tenant_b, "classes", "class_uid", CLASS_UID) == TENANT_B

    def test_tenantless_mirror_row_does_not_steal_the_sample(self, tenant_b):
        """THE integration guard.

        Simulates the startup sync reading a samples.csv written by a machine
        that predates the tenant column. Before the fix this rewrote the row to
        'default' and tenant B's sample was gone from tenant B, silently.
        """
        from app.storage.metadata_db import upsert_sample

        upsert_sample(_csv_shaped_sample())
        assert _tenant_of(tenant_b, "samples", "sample_uid", SAMPLE_UID) == TENANT_B

    def test_tenantless_mirror_row_does_not_steal_the_class(self, tenant_b):
        from app.storage.metadata_db import upsert_class

        upsert_class({
            "class_uid": CLASS_UID, "class_idx": 99123, "slug": "a1-test-slug",
            "label_original": "A1 Test", "language": "vn", "dialect": DIALECT,
            "folder_name": "a1_test_folder",
        })
        assert _tenant_of(tenant_b, "classes", "class_uid", CLASS_UID) == TENANT_B

    def test_a_blank_tenant_cell_is_also_treated_as_silence(self, tenant_b):
        # A migrated CSV whose cell was never filled reads back as "", not None.
        from app.storage.metadata_db import upsert_sample

        upsert_sample(_csv_shaped_sample(**{TENANT_COLUMN: ""}))
        assert _tenant_of(tenant_b, "samples", "sample_uid", SAMPLE_UID) == TENANT_B

    def test_an_explicit_tenant_still_wins(self, tenant_b):
        """Absent is preserved; stated is honoured. Otherwise a genuine
        reassignment could never be written at all.

        `class_uid` chuyển theo, và đó không phải chi tiết vặt của test: từ
        schema v3, khoá ngoại ghép (tenant_id, class_uid) khiến một mẫu không
        thể ở tenant này mà mang lớp của tenant kia. Chuyển tenant mà không
        chuyển lớp sẽ tạo ra một dòng vô nghĩa — thuộc `default` nhưng nhãn
        lấy từ danh mục của `a1-test-tenant`.
        """
        from app.storage.metadata_db import upsert_sample

        upsert_sample(_csv_shaped_sample(
            class_uid=CLASS_UID_DEFAULT, **{TENANT_COLUMN: DEFAULT_TENANT_ID}))
        assert _tenant_of(tenant_b, "samples", "sample_uid", SAMPLE_UID) == DEFAULT_TENANT_ID

    def test_a_moved_sample_cannot_keep_the_old_tenants_class(self, tenant_b):
        """Mặt còn lại của test trên, viết ra để sự thay đổi không lặng lẽ.

        Trước schema v3 câu này CHẠY ĐƯỢC: khoá ngoại một cột chỉ hỏi
        "class_uid có tồn tại không", không hỏi "có thuộc tenant này không".
        """
        import psycopg2
        from app.storage.metadata_db import upsert_sample

        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            upsert_sample(_csv_shaped_sample(**{TENANT_COLUMN: DEFAULT_TENANT_ID}))

    def test_a_brand_new_row_lands_on_the_bootstrap_tenant(self, tenant_b):
        """INSERT (not conflict) with no tenant: NOT NULL forbids passing the
        NULL through, so the VALUES clause substitutes."""
        from app.storage.metadata_db import _execute, upsert_sample

        new_uid = "a1de57ab10"
        try:
            upsert_sample(_csv_shaped_sample(sample_uid=new_uid,
                                             class_uid=CLASS_UID_DEFAULT,
                                             file_path="/mock/a1-new.npz"))
            assert _tenant_of(tenant_b, "samples", "sample_uid", new_uid) == DEFAULT_TENANT_ID
        finally:
            _execute("DELETE FROM samples WHERE sample_uid = %s", (new_uid,))

    def test_reconcile_query_returns_the_tenant(self, tenant_b):
        """Behaviour, not source text.

        An earlier version of this test asserted the word "tenant_id" appeared
        in the function's source — which the comment above the query satisfied
        on its own, so it passed with the column removed from the SELECT.
        """
        from app.storage.metadata_db import list_active_samples

        rows = {r["sample_uid"]: r for r in list_active_samples()}
        assert SAMPLE_UID in rows, "fixture sample missing from the reconcile query"
        assert rows[SAMPLE_UID][TENANT_COLUMN] == TENANT_B

    def test_projection_of_a_real_db_row_keeps_the_tenant(self, tenant_b):
        """Ties the reconcile query to the CSV projection end to end."""
        from app.dataset_samples import _db_row_to_csv_row
        from app.storage.metadata_db import list_active_samples

        row = next(r for r in list_active_samples() if r["sample_uid"] == SAMPLE_UID)
        assert _db_row_to_csv_row(row)[TENANT_COLUMN] == TENANT_B


class TestRebuildFromCsv:
    """The motivating scenario, with a negative control.

    init_db() drops every table and re-seeds from the CSVs when the schema check
    fails. These two tests run that path with and without the column, and assert
    that the presence of the column is what decides whether tenant B survives.
    """

    @pytest.fixture
    def rebuilt(self, tenant_b, monkeypatch):
        from app.storage.metadata_db import _execute

        def run(sample_row):
            # Wipe only the SAMPLE; the class stays so the FK is satisfiable.
            _execute("DELETE FROM samples WHERE sample_uid = %s", (SAMPLE_UID,))
            import app.dataset_manager as dm
            import app.dataset_samples as ds
            import app.raw_uploads as ru
            from app.db import sync_missing_data_on_startup

            # Vá các hàm ĐỌC TOÀN KHO, không phải bản có phạm vi.
            #
            # `sync_missing_data_on_startup` chạy trước khi có bất kỳ phạm vi
            # tenant nào, nên nó gọi `_load_all_*_unscoped()`. Vá nhầm sang tên
            # có phạm vi thì bản vá trượt trong im lặng: hàm thật đọc CSV thật,
            # `sample_row` dựng ở đây không có trong đó, và test đỏ ở
            # `_tenant_of` với thông báo "samples row vanished — the fixture,
            # not the assertion, is broken". Thông báo ấy nói đúng.
            monkeypatch.setattr(ds, "_load_all_samples_unscoped", lambda: [sample_row])
            monkeypatch.setattr(dm, "_load_all_labels_unscoped", lambda: [])
            monkeypatch.setattr(ru, "list_raw_uploads", lambda: [])

            assert sync_missing_data_on_startup(full=False) is True
            return _tenant_of(tenant_b, "samples", "sample_uid", SAMPLE_UID)

        return run

    def test_a_csv_carrying_the_tenant_restores_it(self, rebuilt):
        assert rebuilt(_csv_shaped_sample(**{TENANT_COLUMN: TENANT_B})) == TENANT_B

    def test_a_csv_without_the_column_loses_it(self, rebuilt):
        """NEGATIVE CONTROL — asserts the damage the column prevents.

        This is the pre-A1 world: the rebuild silently returns tenant B's sample
        as the bootstrap tenant. It is asserted rather than avoided so that the
        positive test above cannot pass for an unrelated reason, and so the cost
        of dropping the column from samples.csv stays written down and testable.

        Lớp phải là lớp của tenant khởi tạo: hàng rơi về `default`, và từ schema
        v3 khoá ngoại ghép không cho nó giữ lớp của tenant B. Điều này KHÔNG làm
        nhẹ đi thiệt hại mà test đang chứng minh — mẫu vẫn bị mất khỏi tenant B
        đúng như trước; chỉ là bây giờ dòng kết quả ít nhất còn mạch lạc.
        """
        assert rebuilt(_csv_shaped_sample(class_uid=CLASS_UID_DEFAULT)) == DEFAULT_TENANT_ID

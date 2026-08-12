"""Evidence tests for the deploy-hardening fixes (review rounds 1–3).

Run so you SEE the observed behavior, not just "pass":

    ../.venv/Scripts/python.exe -m pytest tests/test_deploy_fixes.py -v -s

Every test prints an `[evidence] ...` line with the ACTUAL value it asserted on,
so a green run also shows you *what* was true.

Covers:
  1. _split_sql_statements  — schema splitter survives ';' inside $$ / '...'
  2. sync_from_sot          — one bad row is skipped, sync still succeeds
  3. _host_port             — 'host:port' in SMTP_HOST is parsed correctly
"""

from __future__ import annotations

import pytest

from app.sot import keys
from app.sot.publisher import publish_version
from app.sot.reader_sync import CatalogSink, _split_sql_statements, sync_from_sot
from app.sot.store import LocalSotStore


# ===========================================================================
# 1. SQL statement splitter (fixes the naive ';' split that would drop a
#    future trigger/function body and silently leave a table uncreated)
# ===========================================================================

def test_split_simple_statements():
    out = _split_sql_statements("CREATE TABLE a(x int);\nCREATE INDEX i ON a(x);\n")
    print(f"\n[evidence] simple split -> {out}")
    assert out == ["CREATE TABLE a(x int)", "CREATE INDEX i ON a(x)"]


def test_split_keeps_dollar_quoted_function_body_intact():
    # A PL/pgSQL body has ';' INSIDE $$...$$ — the whole thing is ONE statement.
    sql = (
        "CREATE FUNCTION f() RETURNS trigger AS $$ BEGIN a := 1; RETURN a; END; $$ "
        "LANGUAGE plpgsql;\n"
        "CREATE TABLE b(y int)"
    )
    out = _split_sql_statements(sql)
    print(f"\n[evidence] dollar-quote split -> count={len(out)} "
          f"(naive split would give {sql.count(';') + 1})")
    print(f"[evidence]   stmt[0] (function, keeps inner ';') = {out[0]!r}")
    print(f"[evidence]   stmt[1] = {out[1]!r}")
    assert len(out) == 2                     # NOT 4 (what naive split(';') gives)
    assert "RETURN a" in out[0] and out[0].count(";") >= 2  # inner ';' preserved
    assert out[1] == "CREATE TABLE b(y int)"


def test_split_ignores_semicolon_inside_string_literal():
    out = _split_sql_statements("INSERT INTO t VALUES ('a;b'); SELECT 1")
    print(f"\n[evidence] quoted ';' split -> {out}")
    assert out == ["INSERT INTO t VALUES ('a;b')", "SELECT 1"]


def test_split_ignores_semicolon_inside_a_line_comment():
    """A semicolon in prose is not a statement boundary.

    Comments were passed straight through, so an English sentence in a schema
    comment — the place a trade-off is most likely to be explained, and where a
    semicolon is most likely to appear — split the statement in two. The export
    still looked fine; the deploy applied half a CREATE TABLE.
    """
    sql = (
        "CREATE TABLE t (\n"
        "    a int,  -- one thing; and another\n"
        "    b int\n"
        ");\n"
        "CREATE INDEX i ON t(a)"
    )
    out = _split_sql_statements(sql)
    print(f"\n[evidence] commented ';' split -> {len(out)} statements")
    assert len(out) == 2
    assert "CREATE TABLE" in out[0] and "b int" in out[0]
    assert out[1].strip() == "CREATE INDEX i ON t(a)"


def test_split_ignores_semicolon_inside_a_block_comment():
    out = _split_sql_statements("CREATE TABLE t (a int /* x; y */); SELECT 1")
    assert len(out) == 2
    assert out[1].strip() == "SELECT 1"


def test_split_does_not_treat_a_quoted_dash_dash_as_a_comment():
    """`--` inside a string literal is data. Treating it as a comment would
    swallow the rest of the line, including the closing quote."""
    out = _split_sql_statements("INSERT INTO t VALUES ('a--b'); SELECT 1")
    assert out == ["INSERT INTO t VALUES ('a--b')", "SELECT 1"]


def test_real_catalog_schema_splits_into_every_statement():
    # The real thing the server applies at deploy: prove it round-trips to the
    # exact number of statements, and that the core tables are among them.
    from app.sot import catalog_schema
    from app.storage.metadata_db import (
        DDL_STATEMENTS,
        INDEX_STATEMENTS,
        MIGRATION_STATEMENTS,
    )

    sql = catalog_schema.export_schema_sql()
    out = _split_sql_statements(sql)
    expected = len(DDL_STATEMENTS) + len(MIGRATION_STATEMENTS) + len(INDEX_STATEMENTS)

    print(f"\n[evidence] real schema.sql -> {len(out)} statements (expected {expected}):")
    for s in out:
        print("   -", s.split("(")[0].strip()[:52])
    assert len(out) == expected
    assert any("CREATE TABLE" in s and "classes" in s for s in out)
    assert all(s.strip() for s in out)  # no empty fragments


# ===========================================================================
# 2. Reader resilience — a single bad row must NOT abort the whole sync
#    (deploy priority: "dữ liệu máy này ổn rồi, ưu tiên chạy thành công")
# ===========================================================================

def _publish_sot(tmp_path, csvs):
    """Publish one valid, signed SOT version to a local store."""
    authz = tmp_path / "authorized_keys.json"
    authz.write_text("[]", encoding="utf-8")
    key_path = tmp_path / "m.key"
    pk = keys.generate_private_key()
    keys.save_private_key(pk, key_path)
    keys.add_authorized_key("desk", keys.public_key_b64(pk), authz)

    store = LocalSotStore(tmp_path / "SOT")
    publish_version(
        store,
        csv_sources=csvs,
        schema_sql="CREATE TABLE IF NOT EXISTS classes ();",
        schema_version=8,
        required_columns={"classes": ["class_uid"], "samples": ["sample_uid"]},
        machine_name="desk",
        private_key_path=key_path,
        authorized_keys_path=authz,
    )
    return store, keys.load_authorized_keys(authz)


def test_bad_row_is_skipped_and_sync_still_succeeds(tmp_path):
    csvs = {
        "labels.csv": b"class_uid,slug\nc1,hello\n",
        "samples.csv": b"sample_uid,class_uid\ns1,c1\ns2,c1\ns3,c1\n",
        "raw_uploads.csv": b"upload_uid,class_uid\nu1,c1\n",
    }
    store, authorized = _publish_sot(tmp_path, csvs)

    applied = {"classes": [], "samples": [], "raw_uploads": []}

    def upsert_sample(row):
        if row["sample_uid"] == "s2":
            raise ValueError("simulated DB constraint failure on s2")
        applied["samples"].append(row["sample_uid"])

    sink = CatalogSink(
        apply_schema=lambda sql: None,
        column_exists=lambda t, c: True,
        count_rows=lambda t: len(applied[t]),
        upsert_class=lambda r: applied["classes"].append(r["class_uid"]),
        upsert_sample=upsert_sample,
        upsert_raw_upload=lambda r: applied["raw_uploads"].append(r["upload_uid"]),
    )

    result = sync_from_sot(store, sink, authorized_keys=authorized)

    print(f"\n[evidence] status={result.status!r} "
          f"(a bad row did NOT block the deploy)")
    print(f"[evidence] samples upserted={result.rows_upserted['samples']} "
          f"failed={result.rows_failed} good_ids={applied['samples']}")

    assert result.status == "applied"                 # sync SUCCEEDED
    assert applied["samples"] == ["s1", "s3"]          # s2 skipped, others kept
    assert result.rows_upserted["samples"] == 2
    assert result.rows_failed["samples"] == 1


def test_all_rows_ok_reports_zero_failures(tmp_path):
    csvs = {
        "labels.csv": b"class_uid,slug\nc1,hi\n",
        "samples.csv": b"sample_uid,class_uid\ns1,c1\n",
        "raw_uploads.csv": b"upload_uid,class_uid\n",
    }
    store, authorized = _publish_sot(tmp_path, csvs)
    seen = {"classes": [], "samples": [], "raw_uploads": []}
    sink = CatalogSink(
        apply_schema=lambda sql: None,
        column_exists=lambda t, c: True,
        count_rows=lambda t: len(seen[t]),
        upsert_class=lambda r: seen["classes"].append(r["class_uid"]),
        upsert_sample=lambda r: seen["samples"].append(r["sample_uid"]),
        upsert_raw_upload=lambda r: seen["raw_uploads"].append(r["upload_uid"]),
    )
    result = sync_from_sot(store, sink, authorized_keys=authorized)
    print(f"\n[evidence] clean run rows_failed={result.rows_failed} (should be empty)")
    assert result.rows_failed == {}


# ===========================================================================
# 3. SMTP host:port parsing (fixes the broken email connection when
#    SMTP_HOST='smtp.gmail.com:587' is fed whole to smtplib)
# ===========================================================================

@pytest.mark.parametrize(
    "smtp_host,smtp_port,expected",
    [
        ("smtp.gmail.com:587", 25, ("smtp.gmail.com", 587)),   # port in host wins
        ("smtp.gmail.com", 587, ("smtp.gmail.com", 587)),       # host only, keep port
        ("smtp.gmail.com:notaport", 587, ("smtp.gmail.com:notaport", 587)),  # bad port -> no split
        ("2001:db8::1", 587, ("2001:db8::1", 587)),             # IPv6 (many ':') -> no split
    ],
)
def test_host_port_parsing(monkeypatch, smtp_host, smtp_port, expected):
    import app.email_service as es

    monkeypatch.setattr(es.settings, "smtp_host", smtp_host)
    monkeypatch.setattr(es.settings, "smtp_port", smtp_port)
    got = es._host_port()
    print(f"\n[evidence] SMTP_HOST={smtp_host!r} SMTP_PORT={smtp_port} -> {got}")
    assert got == expected

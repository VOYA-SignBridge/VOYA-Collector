"""Pin REQUIRED_COLUMNS to the columns the reader upserts actually write.

REQUIRED_COLUMNS is the manifest's promise to a reader: "apply this schema, then
confirm these columns exist before importing a single row". Its own docstring
calls it "columns each reader upsert writes" — but nothing enforced that, and it
had drifted: classes.hands_required and the five sample quality metrics
(left/right/both hand ratios, jitter, quality_flags) were being written by the
upserts while absent from the coverage list.

The consequence of that drift is the exact failure the check exists to prevent —
verification passes on a reader missing those columns, and the import then blows
up (or silently drops data) halfway through. These tests fail the moment the two
lists diverge again, in either direction.
"""

import re
from pathlib import Path

import pytest

from app.sot.catalog_schema import REQUIRED_COLUMNS

_METADATA_DB = Path(__file__).resolve().parents[1] / "app" / "storage" / "metadata_db.py"

# table name -> the tuple in metadata_db.py naming the columns its upsert writes
_KEY_TUPLES = {
    "classes": "_CLASS_DB_KEYS",
    "samples": "_SAMPLE_DB_KEYS",
    "raw_uploads": "_RAW_UPLOAD_DB_KEYS",
}


def _written_columns(tuple_name: str) -> list[str]:
    """Read a _*_DB_KEYS tuple out of metadata_db.py as source text.

    Parsed rather than imported so the test needs no DB connection and stays
    usable on a bare checkout.
    """
    source = _METADATA_DB.read_text(encoding="utf-8")
    match = re.search(rf"^{tuple_name}\s*=\s*\((.*?)\)", source, re.S | re.M)
    assert match, f"{tuple_name} not found in metadata_db.py"
    raw = match.group(1).replace("\n", " ")
    return [c.strip().strip("\"'") for c in raw.split(",") if c.strip().strip("\"'")]


@pytest.mark.parametrize("table,tuple_name", sorted(_KEY_TUPLES.items()))
def test_required_columns_cover_every_written_column(table, tuple_name):
    """Every column an upsert writes must be one the manifest guarantees."""
    written = _written_columns(tuple_name)
    declared = set(REQUIRED_COLUMNS[table])
    missing = [c for c in written if c not in declared]
    assert not missing, (
        f"{table}: {tuple_name} writes {missing}, but REQUIRED_COLUMNS does not "
        f"list them — a reader missing these columns would pass verification and "
        f"then fail during import. Add them to REQUIRED_COLUMNS."
    )


@pytest.mark.parametrize("table", sorted(_KEY_TUPLES))
def test_required_columns_have_no_phantom_entries(table):
    """Guard the other direction: nothing declared that the schema cannot supply.

    deleted_at is the deliberate exception — the upserts never write it (soft
    deletes are preserved, not overwritten by a sync) but the reader's schema
    must still have it for the soft-delete logic to work at all.
    """
    from app.storage.metadata_db import DDL_STATEMENTS, MIGRATION_STATEMENTS

    ddl = " ".join(DDL_STATEMENTS) + " " + " ".join(MIGRATION_STATEMENTS)
    unknown = [c for c in REQUIRED_COLUMNS[table] if c not in ddl]
    assert not unknown, (
        f"{table}: REQUIRED_COLUMNS names {unknown}, which no CREATE TABLE or "
        f"migration in metadata_db.py creates. A reader could never satisfy it."
    )

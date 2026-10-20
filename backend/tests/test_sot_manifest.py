"""SOT manifest, checksums, and version naming (Ver{N}_DDMMYYYY)."""

from __future__ import annotations

from datetime import date

import pytest

from app.sot import manifest as m


# ---------------------------------------------------------------------------
# Checksums + canonical serialization
# ---------------------------------------------------------------------------

def test_sha256_bytes_known_value():
    assert m.sha256_bytes(b"") == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_sha256_file(tmp_path):
    p = tmp_path / "f.bin"
    p.write_bytes(b"hello")
    assert m.sha256_file(p) == m.sha256_bytes(b"hello")


def test_canonical_bytes_is_order_independent():
    a = {"b": 1, "a": 2, "c": {"y": 1, "x": 2}}
    b = {"c": {"x": 2, "y": 1}, "a": 2, "b": 1}
    assert m.canonical_bytes(a) == m.canonical_bytes(b)


def test_canonical_bytes_changes_with_content():
    assert m.canonical_bytes({"a": 1}) != m.canonical_bytes({"a": 2})


def test_canonical_bytes_utf8():
    out = m.canonical_bytes({"label": "Miến Điện"})
    assert "Miến Điện" in out.decode("utf-8")


# ---------------------------------------------------------------------------
# Manifest build + validate
# ---------------------------------------------------------------------------

def test_build_manifest_shape():
    man = m.build_manifest(
        version_name="Ver1_18072026",
        machine_name="desktop-A",
        schema_version=8,
        file_hashes={"labels.csv": "abc"},
        row_counts={"labels.csv": 46},
        required_columns={"classes": ["class_uid", "slug"]},
        created_at="2026-07-18T00:00:00Z",
    )
    assert man["version"] == "Ver1_18072026"
    assert man["schema_version"] == 8
    assert man["files"]["labels.csv"] == "abc"
    assert man["row_counts"]["labels.csv"] == 46
    # required_columns sorted for determinism
    assert man["required_columns"]["classes"] == ["class_uid", "slug"]


def test_validate_manifest_ok():
    man = m.build_manifest(
        version_name="Ver2_01082026", machine_name="x", schema_version=8,
        file_hashes={}, row_counts={}, required_columns={},
    )
    m.validate_manifest_shape(man)  # no raise


@pytest.mark.parametrize("missing", ["version", "files", "row_counts", "schema_version", "required_columns"])
def test_validate_manifest_rejects_missing_key(missing):
    man = m.build_manifest(
        version_name="Ver1_18072026", machine_name="x", schema_version=8,
        file_hashes={}, row_counts={}, required_columns={},
    )
    del man[missing]
    with pytest.raises(ValueError):
        m.validate_manifest_shape(man)


def test_validate_manifest_rejects_bad_version():
    man = m.build_manifest(
        version_name="not-a-version", machine_name="x", schema_version=8,
        file_hashes={}, row_counts={}, required_columns={},
    )
    with pytest.raises(ValueError):
        m.validate_manifest_shape(man)


# ---------------------------------------------------------------------------
# Version naming
# ---------------------------------------------------------------------------

def test_parse_version_name_valid():
    assert m.parse_version_name("Ver1_18072026") == (1, date(2026, 7, 18))
    assert m.parse_version_name("Ver42_01012027") == (42, date(2027, 1, 1))


@pytest.mark.parametrize("bad", [
    "Ver_18072026", "Version1_18072026", "Ver1-18072026", "Ver1_1872026",
    "ver1_18072026", "Ver1_99992026", "", "Ver1_32012026",  # invalid day
])
def test_parse_version_name_invalid(bad):
    assert m.parse_version_name(bad) is None


def test_next_version_empty_starts_at_1():
    assert m.next_version_name([], today=date(2026, 7, 18)) == "Ver1_18072026"


def test_next_version_increments_from_highest():
    existing = ["Ver1_10012026", "Ver3_15062026", "Ver2_20032026"]
    assert m.next_version_name(existing, today=date(2026, 7, 18)) == "Ver4_18072026"


def test_next_version_ignores_junk_folders():
    existing = ["Ver2_01012026", "junk", "backup", "Ver1_02012026"]
    assert m.next_version_name(existing, today=date(2026, 8, 1)) == "Ver3_01082026"


def test_date_formatted_ddmmyyyy():
    # 5 August 2026 -> 05082026 (zero padded)
    assert m.next_version_name([], today=date(2026, 8, 5)) == "Ver1_05082026"


def test_latest_version_picks_highest_number():
    assert m.latest_version(["Ver1_01012026", "Ver5_02012026", "Ver3_03012026"]) == "Ver5_02012026"
    assert m.latest_version([]) is None
    assert m.latest_version(["junk"]) is None

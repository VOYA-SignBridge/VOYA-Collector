"""Community / Tenant / Artifact — the three planes and the rules between them.

The architecture in one line: Community is a template that is cloned ONCE into a
tenant's own registry; artifacts pin an immutable version; nothing ever falls
back from a tenant to the community catalogue at runtime.

What is pinned here is mostly what must NOT happen. Every rule below exists
because its absence produced a real defect:

  - a hardcoded profile list drifted from the seeded one and silently dropped
    every `legacy_unassigned` class out of splits;
  - `registry_version` was a counter that got overwritten and `export_snapshot`
    wrote one file, so "this dataset pins v2" could not be honoured — v2's
    contents were gone the moment v3 was written;
  - init_db re-clones on every boot, so a naive bump climbed the version forever
    while nothing changed.

No database: SQL is asserted directly and the CSV/JSON work is real file I/O.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app.storage.metadata_db as mdb  # noqa: E402
import app.vocabulary_registry as vr  # noqa: E402
from app.cli.export_registry_snapshot import build_bootstrap_snapshot  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------
# 1. No hardcoded profile list anywhere
# --------------------------------------------------------------------------

def test_profiles_come_from_a_tracked_seed_file():
    seed = REPO / "config" / "profiles.seed.csv"
    assert seed.is_file(), "profile list must live in config, not in code"
    text = seed.read_text(encoding="utf-8")
    assert "legacy_unassigned" in text, (
        "the profile whose absence silently dropped 7 classes must be in the seed"
    )


def test_no_fallback_tuple_survives_in_the_shared_module():
    src = (REPO / "processed" / "shared" / "vocabulary.py").read_text(encoding="utf-8")
    assert "_FALLBACK_PROFILES" not in src.replace("# ", ""), (
        "a hardcoded list here is what drifted from the database"
    )
    assert "RegistrySnapshotMissing" in src


def test_registry_module_does_not_hardcode_profiles():
    src = Path(vr.__file__).read_text(encoding="utf-8")
    # The seeding loop used to carry the six ids inline, next to a comment
    # explaining why deriving them from data would be circular.
    for pid in ("north", "central", "south", "hoa_de"):
        assert f'("{pid}", "' not in src, f"profile '{pid}' is hardcoded again"


def test_bootstrap_snapshot_keeps_seed_display_order():
    """Geographic order, not alphabetical. Ordering by id put `central` before
    `north`; `alphabet` stayed first only by coincidence of spelling."""
    snap = build_bootstrap_snapshot()
    ids = [p["profile_id"] for p in snap["profiles"]]
    assert ids[:5] == ["alphabet", "north", "central", "south", "hoa_de"]
    assert "legacy_unassigned" in ids


def test_bootstrap_snapshot_labels_its_own_origin():
    """An artifact built from the template must be able to say so."""
    snap = build_bootstrap_snapshot()
    assert snap["source"] == "community_seed"
    assert snap["tenant_id"] is None
    assert snap["registry_version"] == 0
    assert len(snap["content_hash"]) == 64


def test_bootstrap_needs_no_database():
    import inspect

    src = inspect.getsource(build_bootstrap_snapshot)
    assert "metadata_db" not in src and "psycopg2" not in src


def test_bootstrap_hash_matches_the_backend_recipe():
    """Two implementations of the hash (stdlib in the CLI, backend in the
    registry) must agree, or a bootstrap snapshot could never be verified."""
    snap = build_bootstrap_snapshot()
    stored = snap["content_hash"]
    assert vr.content_hash(snap) == stored


def test_hash_ignores_snapshot_metadata_only():
    base = {"source": "tenant", "dialects": [{"dialect_id": "bac"}], "profiles": []}
    h = vr.content_hash(base)
    assert vr.content_hash({**base, "registry_version": 9, "generated": "x"}) == h
    assert vr.content_hash({**base, "dialects": [{"dialect_id": "nam"}]}) != h


# --------------------------------------------------------------------------
# 2. Immutable versions
# --------------------------------------------------------------------------

def test_registry_versions_table_is_append_only_by_shape():
    ddl = " ".join(mdb.MIGRATION_STATEMENTS)
    assert "CREATE TABLE IF NOT EXISTS registry_versions" in ddl
    assert "PRIMARY KEY (tenant_id, version)" in ddl
    assert "content_hash TEXT NOT NULL" in ddl
    assert "snapshot     JSONB NOT NULL" in ddl


def test_version_rows_are_never_updated():
    src = Path(vr.__file__).read_text(encoding="utf-8")
    assert "UPDATE registry_versions" not in src, "a published version must never change"
    assert "DELETE FROM registry_versions" not in src


def test_per_version_snapshot_path_is_distinct():
    a = vr.version_snapshot_path("default", 2)
    b = vr.version_snapshot_path("default", 3)
    assert a != b and a.parent == b.parent
    assert a != vr.SNAPSHOT_PATH, "the pointer file is overwritten; frozen ones are not"


def test_export_never_rewrites_a_frozen_version(tmp_path, monkeypatch):
    monkeypatch.setattr(vr, "SNAPSHOT_PATH", tmp_path / "vocabulary_registry.json")
    payload = {"source": "tenant", "tenant_id": "t1", "registry_version": 7,
               "content_hash": "abc", "dialects": [], "profiles": [], "aliases": {}}
    vr.export_snapshot("t1", payload=payload)
    frozen = vr.version_snapshot_path("t1", 7)
    assert frozen.is_file()

    # Re-exporting the SAME content is a no-op, not an error: init_db runs on
    # every boot and must stay idempotent.
    vr.export_snapshot("t1", payload=dict(payload))
    assert json.loads(frozen.read_text(encoding="utf-8"))["dialects"] == []

    # DIFFERENT content under the same version number means two states were
    # published as one — fatal, never an overwrite.
    with pytest.raises(vr.RegistryPinError):
        vr.export_snapshot("t1", payload={**payload, "dialects": [{"dialect_id": "tampered"}]})
    assert json.loads(frozen.read_text(encoding="utf-8"))["dialects"] == [], (
        "v7 must keep saying what v7 said"
    )


def test_frozen_write_is_atomic(tmp_path, monkeypatch):
    """No half-written snapshot: a truncated file still parses as JSON often
    enough that it would not be caught by chance."""
    import inspect

    src = inspect.getsource(vr._freeze_version_file)
    assert "os.fsync" in src
    assert "os.link" in src, "the name must be claimed by the filesystem, not by a prior exists() check"


def test_version_creation_is_serialised():
    """The dedup check and the insert must share one transaction, or two
    backends booting together publish two versions from one state."""
    import inspect

    src = inspect.getsource(vr._bump)
    assert "pg_advisory_xact_lock" in src
    assert "_fetch_all" not in src, "reading latest outside the cursor reopens the race"
    assert inspect.getsource(vr.publish_catalog_version).count("pg_advisory_xact_lock") == 1


def test_explicit_path_does_not_freeze_a_version(tmp_path, monkeypatch):
    """Exporting to a chosen path is a copy, not a publish."""
    monkeypatch.setattr(vr, "SNAPSHOT_PATH", tmp_path / "vocabulary_registry.json")
    out = tmp_path / "copy.json"
    payload = {"source": "tenant", "tenant_id": "t2", "registry_version": 3,
               "content_hash": "x", "dialects": [], "profiles": [], "aliases": {}}
    vr.export_snapshot("t2", path=out, payload=payload)
    assert out.is_file()
    assert not vr.version_snapshot_path("t2", 3).exists()


# --------------------------------------------------------------------------
# 3. Pin verification refuses, never degrades
# --------------------------------------------------------------------------

def test_missing_pinned_version_raises(monkeypatch):
    monkeypatch.setattr(vr, "get_registry_version", lambda t, v: None)
    with pytest.raises(vr.RegistryPinError) as e:
        vr.verify_pinned_snapshot("default", 2, "abc")
    assert "không tồn tại" in str(e.value)


def test_hash_mismatch_raises(monkeypatch):
    monkeypatch.setattr(vr, "get_registry_version",
                        lambda t, v: {"version": v, "content_hash": "REAL"})
    with pytest.raises(vr.RegistryPinError):
        vr.verify_pinned_snapshot("default", 2, "CLAIMED")


def test_matching_pin_passes(monkeypatch):
    monkeypatch.setattr(vr, "get_registry_version",
                        lambda t, v: {"version": v, "content_hash": "SAME"})
    vr.verify_pinned_snapshot("default", 2, "SAME")


# --------------------------------------------------------------------------
# 4. No runtime path from tenant back to community
# --------------------------------------------------------------------------

def test_catalog_tables_are_separate_from_tenant_tables():
    """Separate tables, not a reserved tenant_id: 'a tenant may never read the
    template' is then enforced by which table a query names, rather than by
    remembering a WHERE clause."""
    ddl = " ".join(mdb.MIGRATION_STATEMENTS)
    for t in ("community_dialects", "community_profiles", "community_versions"):
        assert f"CREATE TABLE IF NOT EXISTS {t}" in ddl


# Every function allowed to NAME a community table in SQL. The list is the
# point: a new one may only be added deliberately, and adding it is the moment
# to ask whether a tenant can reach it. Everything here is either the clone path
# or the system-admin plane (see routers/vocabulary.py `catalog_router`).
#
# Calling one of these is not itself a violation — seed_from_csv does, and must,
# because bootstrapping a tenant IS the clone path. What is forbidden is a new
# query against the tables.
CATALOG_TABLES = ("community_dialects", "community_profiles", "community_versions")
CATALOG_PLANE_FUNCTIONS = {
    "clone_catalog_to_tenant", "system_catalog_snapshot", "seed_system_catalog",
    "publish_catalog_version", "list_catalog_versions", "get_catalog_version",
    "_update_catalog_row", "update_catalog_dialect", "update_catalog_profile",
}


def test_only_declared_functions_touch_the_system_catalog():
    """The tenant plane must have no path into the template, at all.

    Enumerating every function that queries a community table beats counting a
    fixed list: a helper added later that quietly reads `community_dialects`
    from a tenant-facing lookup fails here instead of shipping.
    """
    import re

    src = Path(vr.__file__).read_text(encoding="utf-8")
    bounds = [(m.group(1), m.start()) for m in re.finditer(r"^def (\w+)", src, re.M)]
    offenders = set()
    for i, (name, start) in enumerate(bounds):
        end = bounds[i + 1][1] if i + 1 < len(bounds) else len(src)
        body = src[start:end]
        if any(t in body for t in CATALOG_TABLES) and name not in CATALOG_PLANE_FUNCTIONS:
            offenders.add(name)
    assert not offenders, (
        f"these functions query the system-catalog tables without being declared: {sorted(offenders)}"
    )
    for fn in ("clone_catalog_to_tenant", "system_catalog_snapshot", "seed_system_catalog",
               "publish_catalog_version"):
        assert f"def {fn}" in src

    # No read path from a tenant-facing lookup into the community tables.
    for fn_name in ("list_dialects", "list_profiles", "known_dialect_ids", "resolve_dialect"):
        start = src.index(f"def {fn_name}")
        body = src[start:start + 1200]
        assert "community_" not in body, f"{fn_name} must never touch the system-catalog tables"


def test_clone_records_its_origin_version():
    import inspect

    src = inspect.getsource(vr.clone_catalog_to_tenant)
    assert "cloned_from_community_version" in src


# --------------------------------------------------------------------------
# 5. Tenant-scoped permission
# --------------------------------------------------------------------------

@pytest.fixture
def roles(monkeypatch):
    # `u-norole` là thành viên CÓ THẬT của t1 với `role IS NULL` — trạng thái
    # thay thế vai `viewer` đã nghỉ. Nó phải đi qua nhánh "có dòng, role NULL"
    # chứ không phải nhánh "không có dòng", vì hai nhánh đó từng cho ra hai kết
    # quả khác nhau: cái sau trả `None`, cái trước trả chuỗi `"None"`.
    table = {("t1", "u-editor"): "editor", ("t1", "u-admin"): "admin",
             ("t1", "u-norole"): None, ("t2", "u-editor"): "editor"}

    def _fetch(sql, params=()):
        key = (params[0], params[1])
        return [{"role": table[key]}] if key in table else []

    monkeypatch.setattr(mdb, "_fetch_all", _fetch)
    return table


@pytest.mark.parametrize("user,expected", [
    ("u-admin", True), ("u-editor", True), ("u-norole", False),
    ("u-nobody", False), (None, False),
])
def test_only_tenant_admin_or_editor_may_edit(roles, user, expected):
    assert vr.can_edit_registry("t1", user) is expected


def test_a_member_without_a_role_reads_as_no_role_not_as_the_string_None(roles):
    """`tenant_role` phải trả `None`, không phải `"None"`.

    Bản trước viết `str(rows[0]["role"])` vô điều kiện. Từ ngày cột `role` nhận
    NULL, câu đó biến một thành viên không vai thành chuỗi `"None"` — một vai
    không tồn tại, đi thẳng vào `LEGACY_TENANT_ROLE_MAP.get(...)`, và đẻ ra một
    dòng log mức ERROR ở MỖI request của người đó. Quyền vẫn đúng, tiếng ồn thì
    không.
    """
    assert vr.tenant_role("t1", "u-norole") is None


def test_editor_of_one_tenant_has_no_power_in_another(roles):
    """The entire point of the tenant plane."""
    assert vr.can_edit_registry("t2", "u-editor") is True
    assert vr.can_edit_registry("t1", "u-norole") is False
    assert vr.can_edit_registry("t3", "u-editor") is False


def test_system_admin_is_a_separate_authority(roles):
    assert vr.can_edit_registry("t3", "u-nobody", is_system_admin=True) is True


def test_system_catalog_guard_refuses_tenant_users():
    """The catalogue is system-managed configuration; a tenant user has no
    business reading or writing the template every other tenant is born from."""
    with pytest.raises(PermissionError) as e:
        vr.assert_system_admin(False)
    assert "System Catalog" in str(e.value)
    vr.assert_system_admin(True)


def test_membership_role_is_constrained_in_sql():
    ddl = " ".join(mdb.MIGRATION_STATEMENTS)
    assert "CREATE TABLE IF NOT EXISTS tenant_members" in ddl
    # NULL nằm trong tập hợp lệ, `viewer` thì không.
    #
    # Kiểm CẢ HAI vế. Chỉ kiểm vế đầu thì một ràng buộc còn sót `viewer` vẫn
    # xanh; chỉ kiểm vế sau thì một ràng buộc `NOT NULL` cũng xanh — và cái đó
    # nghĩa là không có chỗ cho "không vai", tức là đúng thứ lượt này dựng ra.
    assert "role IS NULL OR role IN ('admin', 'editor')" in ddl
    assert "role IN ('admin', 'editor', 'viewer')" not in ddl

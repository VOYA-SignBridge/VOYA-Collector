"""A4 — the second isolation plane: bytes on disk, not just rows in Postgres.

The claim is narrower than A3's and is stated precisely: **new** data written by
a tenant lands in that tenant's own subtree. Existing files do not move. 8.784
`.npz` files already sit under `dataset/features/<lang>/<dialect>/`, relocating
them is not an atomic operation, and a half-finished move leaves the dataset
unreadable — for no gain, since what is being demonstrated is that new writes are
partitioned.

The layout is therefore split by TENANT rather than by time: the bootstrap tenant
keeps the historical tree, everyone else gets `_tenants/<id>/`. Each tenant then
has exactly one layout, so no read path needs a new-then-legacy fallback — which
is what keeps the twenty callers of `hierarchy_path()` untouched.
"""

from __future__ import annotations

import pytest

from app import dataset_manager
from app.dataset_manager import (
    ClassMetadata,
    ambient_tenant,
    ambient_tenant_features_root,
    tenant_features_root,
)
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import no_scope, system_scope, tenant_scope


def features_root():
    """Read the root from the module, never from a binding taken at import.

    `test_optimizations` reassigns `dataset_manager.FEATURES_ROOT` to a temp
    directory. A `from ... import FEATURES_ROOT` here would capture the value as
    it was when this file was imported, so these assertions would compare the
    production function's answer (which reads the module attribute) against a
    stale constant — and fail depending on test ORDER, which is the worst way
    for a test to fail.
    """
    return dataset_manager.FEATURES_ROOT


def _meta(tenant: str, **kw) -> ClassMetadata:
    base = dict(
        class_uid="uid-1234abcd",
        slug="cam-on",
        label_original="Cảm ơn",
        language="vn",
        dialect="bac",
        is_common_global=False,
        is_common_language=False,
        tenant_id=tenant,
    )
    base.update(kw)
    return ClassMetadata(**base)


class TestLayout:
    def test_bootstrap_tenant_keeps_the_historical_path(self):
        """The property that makes A4 cheap: not one existing file moves."""
        assert tenant_features_root(DEFAULT_TENANT_ID) == features_root()

    def test_other_tenants_are_partitioned(self):
        assert tenant_features_root("truong-b") == features_root() / "_tenants" / "truong-b"

    def test_partitions_do_not_overlap(self):
        a = _meta("truong-a").hierarchy_path()
        b = _meta("truong-b").hierarchy_path()
        assert a != b
        assert not str(a).startswith(str(b))
        assert not str(b).startswith(str(a))

    def test_same_slug_in_two_tenants_is_two_directories(self):
        """The normal case, not an edge case: two deployments collecting
        Vietnamese sign language both have a folder for 'cam-on'."""
        assert _meta("truong-a").hierarchy_path() != _meta("truong-b").hierarchy_path()

    @pytest.mark.parametrize("kind,expected_tail", [
        ({"is_common_global": True}, ("global_common",)),
        ({"is_common_language": True}, ("vn", "common")),
        ({}, ("vn", "bac")),
    ])
    def test_every_branch_of_the_hierarchy_is_partitioned(self, kind, expected_tail):
        """Three branches — global-common, language-common, dialect-specific.
        A partition that covered only the third would leak the other two."""
        path = _meta("truong-b", **kind).hierarchy_path()
        parts = path.parts
        assert "_tenants" in parts and "truong-b" in parts
        tenant_at = parts.index("truong-b")
        assert parts[tenant_at + 1: tenant_at + 1 + len(expected_tail)] == expected_tail

    def test_tenant_id_cannot_escape_the_root(self):
        """`../` in a tenant id would write outside the dataset entirely. The
        restricted alphabet in `app.tenancy` is what prevents it, so this pins
        that the storage layer actually relies on the validator rather than
        constructing the path first and checking later."""
        for bad in ("../etc", "a/b", "..", "a\\b"):
            with pytest.raises(ValueError):
                tenant_features_root(bad)

    def test_underscore_prefix_cannot_collide_with_a_language(self):
        """Language codes are lowercase letters; `_tenants` cannot be one, so a
        language directory can never be mistaken for the partition namespace."""
        assert tenant_features_root("truong-b").parts[-2] == "_tenants"
        assert not _meta(DEFAULT_TENANT_ID).hierarchy_path().parts.__contains__("_tenants")


class TestAmbientTenant:
    def test_uses_the_scoped_tenant(self):
        with tenant_scope("truong-b"):
            assert ambient_tenant() == "truong-b"
            assert ambient_tenant_features_root() == features_root() / "_tenants" / "truong-b"

    def test_system_scope_writes_as_the_bootstrap_tenant(self):
        """Platform work — the CSV import, a CLI — creates rows that provably
        predate multi-tenancy. Same answer `app.tenancy` gives for an absent
        value everywhere else."""
        with system_scope("test"):
            assert ambient_tenant() == DEFAULT_TENANT_ID

    def test_unscoped_writes_as_the_bootstrap_tenant(self):
        with no_scope():
            assert ambient_tenant() == DEFAULT_TENANT_ID


class TestOwnerSurvivesEveryRoundTrip:
    """A class read back from a row must remember who owns it.

    This is where A4 actually breaks in practice. `hierarchy_path()` is derived
    from `ClassMetadata.tenant_id`, and the field has a default — so every
    builder that forgets it produces a class that silently claims to belong to
    the bootstrap tenant. Reading tenant B's class then writes tenant B's samples
    into tenant A's directory: the exact leak the partition exists to prevent,
    with no error anywhere.

    Six builders across five modules construct ClassMetadata from a row. All six
    were missing the field; these tests are what stops a seventh from being
    added the same way.
    """

    ROW = {
        "class_uid": "uid-1",
        "class_idx": "7",
        "slug": "cam-on",
        "label_original": "Cảm ơn",
        "language": "vn",
        "dialect": "bac",
        "is_common_global": "0",
        "is_common_language": "0",
        "folder_name": "class_cam-on_uid-1",
        "tenant_id": "truong-b",
    }

    def test_labels_csv_row(self):
        from app.dataset_manager import _build_meta_from_row

        assert _build_meta_from_row(dict(self.ROW)).tenant_id == "truong-b"

    def test_catalog_sync_row(self):
        from app.catalog_sync import _build_class_meta_from_row

        assert _build_class_meta_from_row(dict(self.ROW)).tenant_id == "truong-b"

    def test_blank_tenant_means_the_bootstrap_tenant(self):
        """Rows written before the column existed. Consistent with every other
        absent-value decision in `app.tenancy`."""
        from app.dataset_manager import _build_meta_from_row

        row = dict(self.ROW, tenant_id="")
        assert _build_meta_from_row(row).tenant_id == DEFAULT_TENANT_ID

    def test_path_follows_the_owner_not_the_caller(self):
        """The decisive property: a platform job acting for nobody must still
        write tenant B's class into tenant B's tree."""
        from app.dataset_manager import _build_meta_from_row

        meta = _build_meta_from_row(dict(self.ROW))
        with system_scope("test"):
            assert "_tenants" in meta.hierarchy_path().parts
            assert "truong-b" in meta.hierarchy_path().parts


class TestAuditToleratesThePartition:
    def test_scan_does_not_report_the_partition_dir_as_a_language(self, tmp_path):
        from app.feature_structure_audit import scan

        (tmp_path / "_tenants" / "truong-b" / "vn" / "bac" / "class_x").mkdir(parents=True)
        (tmp_path / "vn" / "bac" / "class_y").mkdir(parents=True)
        result = scan(str(tmp_path))
        assert result["legacy_roots"] == []
        # `class_y` sits at the correct depth for the legacy layout, and nothing
        # under `_tenants` may be reported as misplaced.
        assert all("_tenants" not in p for p in result["misplaced_subdirs"])

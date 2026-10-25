"""Safety regression tests for the local Community export importer."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "dataset" / "import_community_export.py"
SPEC = importlib.util.spec_from_file_location("import_community_export", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
IMPORTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = IMPORTER
SPEC.loader.exec_module(IMPORTER)


class CommunityImporterSafetyTests(unittest.TestCase):
    def test_storage_keys_map_drive_aliases_to_local_layout(self):
        cases = [
            ("Samples/vn/class-a/sample.npz", "features", "features/vn/class-a/sample.npz"),
            ("dataset/features/vn/class-a/sample.npz", "features", "features/vn/class-a/sample.npz"),
            ("Videos/vn/clip.mp4", "raw_videos", "raw_videos/vn/clip.mp4"),
        ]
        for source, tree, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(IMPORTER._normalise_storage_key(source, tree), expected)

    def test_storage_keys_reject_paths_outside_dataset(self):
        for unsafe in ("../outside.npz", "Samples/../../outside.npz", r"C:\outside.npz"):
            with self.subTest(unsafe=unsafe), self.assertRaises(IMPORTER.ImportRefused):
                IMPORTER._normalise_storage_key(unsafe, "features")

    def test_atomic_copy_is_idempotent_and_refuses_different_destination(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as directory:
            root = Path(directory)
            source = root / "source.npz"
            destination = root / "dataset" / "features" / "sample.npz"
            source.write_bytes(b"same-content")
            item = IMPORTER.CopyItem(source, destination, "features/sample.npz")

            self.assertEqual(IMPORTER._copy_atomic(item), "copied")
            self.assertEqual(IMPORTER._copy_atomic(item), "unchanged")

            destination.write_bytes(b"different-content")
            with self.assertRaisesRegex(IMPORTER.ImportRefused, "refusing to overwrite"):
                IMPORTER._copy_atomic(item)

    def test_populated_catalogue_cannot_be_replaced_with_different_rows(self):
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as directory:
            catalogue = Path(directory) / "labels.csv"
            catalogue.write_text("class_uid,tenant_id\nold,default\n", encoding="utf-8")

            with self.assertRaisesRegex(IMPORTER.ImportRefused, "populated catalogue"):
                IMPORTER._catalog_is_empty_or_equal(
                    catalogue,
                    ("class_uid", "tenant_id"),
                    ({"class_uid": "new", "tenant_id": "default"},),
                )


if __name__ == "__main__":
    unittest.main()

"""Create an immutable, versioned dataset manifest.

Usage:
    python scripts/create_dataset_manifest.py --version isds2026_v1
    python scripts/create_dataset_manifest.py --version test_v1 \
        --features-root dataset/features --labels-csv dataset/labels.csv \
        --signers-csv dataset/signers.csv --out-dir dataset/manifests

Outputs (in --out-dir):
    dataset_manifest_<version>.csv    one row per .npz sample
    labels_<version>.csv              frozen copy of the label table
    signers_<version>.csv             frozen copy of the signer registry
    dataset_stats_<version>.json      counts by scope/profile/signer/class
    dataset_manifest_<version>.sha256 checksum of the manifest file itself

Rules:
  - a released manifest is IMMUTABLE: this script refuses to overwrite an
    existing version unless --force is passed (use a NEW version instead);
  - file checksums are sha256 of the npz bytes;
  - raw_landmarks_available is read from the npz keys (never guessed);
  - signer_id is resolved from the legacy name mapping when the sidecar/meta
    has no signer_id yet; unresolvable rows keep signer_id="" and are counted.

Requires numpy (to inspect npz keys); otherwise stdlib only.
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.vocabulary import (  # noqa: E402
    label_key_v2,
    semantic_label_from_slug,
    validate_label_v2,
)

MANIFEST_FIELDS = [
    "sample_id", "file_path", "file_checksum",
    "label_key", "semantic_label", "vocabulary_scope", "recognition_profile",
    "vocabulary_group", "collection_campaign", "motion_type",
    "signer_id", "session_id", "source_type",
    "raw_landmarks_available", "normalization_version", "quality_status",
    # physical-location columns kept so the existing dataset_loader keeps working
    "class_uid", "slug", "label_original", "language", "dialect", "folder_name", "file",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_sidecar(npz_path: Path) -> dict:
    sidecar = npz_path.with_suffix(".json")
    if sidecar.exists():
        try:
            return json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _npz_flags(npz_path: Path) -> dict:
    try:
        with np.load(npz_path, allow_pickle=True) as z:
            keys = set(z.keys())
        return {"readable": True, "raw": "landmarks_raw" in keys}
    except Exception:
        return {"readable": False, "raw": False}


def build_legacy_user_index(sources) -> dict:
    """sample_id -> legacy user_id name, from frozen split CSVs / samples.csv.

    Many pre-sidecar npz files have no per-sample JSON; the frozen legacy split
    CSVs are the only surviving record of who signed them. This is recorded
    provenance (not inference) — rows absent everywhere stay unresolved.
    """
    index: dict = {}
    for src in sources:
        src = Path(src)
        if not src.exists():
            continue
        for r in _read_csv(src):
            sid = (r.get("sample_id") or r.get("sample_uid") or "").strip()
            name = (r.get("user_id") or "").strip()
            if sid and name and sid not in index:
                index[sid] = name
    return index


def build_manifest(features_root: Path, labels_rows: list, signer_name_to_id: dict,
                   legacy_user_index: dict | None = None) -> tuple:
    label_by_folder = {}
    for r in labels_rows:
        folder = (r.get("folder_name") or "").strip()
        if folder:
            label_by_folder[folder] = r

    rows, unreadable, unlabeled = [], [], []
    for npz_path in sorted(features_root.rglob("*.npz")):
        folder = npz_path.parent.name
        label_row = label_by_folder.get(folder)
        if label_row is None:
            unlabeled.append(str(npz_path))
            continue
        flags = _npz_flags(npz_path)
        if not flags["readable"]:
            unreadable.append(str(npz_path))
            continue
        side = _load_sidecar(npz_path)

        slug = (label_row.get("slug") or "").strip()
        scope = (label_row.get("vocabulary_scope") or "").strip()
        profile = (label_row.get("recognition_profile") or "").strip()
        language = (label_row.get("language") or "vn").strip() or "vn"
        try:
            lkey = label_key_v2(language, scope, profile, slug)
        except ValueError:
            # unassigned rows keep the legacy key so they remain addressable
            dialect = (label_row.get("dialect") or "").strip()
            lkey = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"

        sample_id = npz_path.stem.replace("sample_", "")
        raw_name = str(side.get("user_id") or side.get("user") or "").strip()
        if not raw_name and legacy_user_index:
            raw_name = legacy_user_index.get(sample_id, "")
        signer_id = str(side.get("signer_id") or "").strip() or signer_name_to_id.get(raw_name, "")

        quality_flags = str(side.get("quality_flags") or "").strip()
        quality_status = str(side.get("quality_status") or "").strip() or (
            "flagged" if quality_flags else "unknown"
        )

        rel = npz_path.relative_to(REPO_ROOT) if str(npz_path).startswith(str(REPO_ROOT)) else npz_path
        rows.append({
            "sample_id": sample_id,
            "file_path": str(rel).replace("\\", "/"),
            "file_checksum": sha256_file(npz_path),
            "label_key": lkey,
            "semantic_label": (label_row.get("semantic_label") or semantic_label_from_slug(slug)),
            "vocabulary_scope": scope,
            "recognition_profile": profile,
            "vocabulary_group": (label_row.get("vocabulary_group") or "").strip(),
            "collection_campaign": str(side.get("collection_campaign") or label_row.get("collection_campaign") or "").strip(),
            "motion_type": (label_row.get("motion_type") or "").strip(),
            "signer_id": signer_id,
            "session_id": str(side.get("session_id") or "").strip(),
            "source_type": str(side.get("source_type") or "camera").strip(),
            "raw_landmarks_available": "1" if flags["raw"] else "0",
            "normalization_version": str(side.get("normalization_version") or "hands126_v1").strip(),
            "quality_status": quality_status,
            "class_uid": (label_row.get("class_uid") or "").strip(),
            "slug": slug,
            "label_original": (label_row.get("label_original") or "").strip(),
            "language": language,
            "dialect": (label_row.get("dialect") or "").strip(),
            "folder_name": folder,
            "file": npz_path.name,
        })
    return rows, unreadable, unlabeled


def compute_stats(rows: list) -> dict:
    return {
        "total_samples": len(rows),
        "by_vocabulary_scope": dict(Counter(r["vocabulary_scope"] or "<unassigned>" for r in rows)),
        "by_recognition_profile": dict(Counter(r["recognition_profile"] or "<none>" for r in rows)),
        "by_signer": dict(Counter(r["signer_id"] or "<unresolved>" for r in rows)),
        "by_label_key": dict(Counter(r["label_key"] for r in rows)),
        "raw_landmarks_available": dict(Counter(r["raw_landmarks_available"] for r in rows)),
        "by_quality_status": dict(Counter(r["quality_status"] for r in rows)),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--version", required=True)
    ap.add_argument("--features-root", type=Path, default=REPO_ROOT / "dataset" / "features")
    ap.add_argument("--labels-csv", type=Path, default=REPO_ROOT / "dataset" / "labels.csv")
    ap.add_argument("--signers-csv", type=Path, default=REPO_ROOT / "dataset" / "signers.csv")
    ap.add_argument("--signer-mapping", type=Path, default=REPO_ROOT / "config" / "legacy_signer_mapping.json")
    ap.add_argument("--legacy-user-sources", type=Path, nargs="*",
                    default=[REPO_ROOT / "processed" / "splits" / "train.csv",
                             REPO_ROOT / "processed" / "splits" / "val.csv",
                             REPO_ROOT / "processed" / "splits" / "test.csv",
                             REPO_ROOT / "dataset" / "samples.csv"],
                    help="Frozen CSVs recording sample_id->user_id for pre-sidecar samples")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "dataset" / "manifests")
    ap.add_argument("--force", action="store_true", help="Overwrite an existing version (breaks immutability — avoid)")
    args = ap.parse_args()

    out_dir = args.out_dir
    manifest_path = out_dir / f"dataset_manifest_{args.version}.csv"
    if manifest_path.exists() and not args.force:
        print(f"[ERROR] {manifest_path} already exists. Manifests are immutable — "
              f"create a NEW --version (or pass --force if you really mean to overwrite).")
        return 2

    labels_rows = _read_csv(args.labels_csv)
    signer_name_to_id = {}
    if args.signer_mapping.exists():
        signer_name_to_id = json.loads(args.signer_mapping.read_text(encoding="utf-8")).get(
            "legacy_name_to_signer_id", {})

    legacy_user_index = build_legacy_user_index(args.legacy_user_sources)
    rows, unreadable, unlabeled = build_manifest(
        args.features_root, labels_rows, signer_name_to_id, legacy_user_index)
    stats = compute_stats(rows)
    stats["generated_at"] = datetime.utcnow().isoformat() + "Z"
    stats["version"] = args.version
    stats["unreadable_files"] = unreadable
    stats["unlabeled_files_count"] = len(unlabeled)

    out_dir.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        w.writeheader()
        w.writerows(rows)

    # Frozen copies of labels + signers
    import shutil
    shutil.copy2(args.labels_csv, out_dir / f"labels_{args.version}.csv")
    if args.signers_csv.exists():
        shutil.copy2(args.signers_csv, out_dir / f"signers_{args.version}.csv")
    (out_dir / f"dataset_stats_{args.version}.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    checksum = sha256_file(manifest_path)
    (out_dir / f"dataset_manifest_{args.version}.sha256").write_text(checksum + "\n", encoding="utf-8")

    print(f"manifest -> {manifest_path}  ({len(rows)} samples, sha256={checksum[:12]}...)")
    print(f"stats: scope={stats['by_vocabulary_scope']} profiles={stats['by_recognition_profile']}")
    print(f"raw available: {stats['raw_landmarks_available']}")
    if unreadable:
        print(f"[WARN] unreadable npz: {len(unreadable)}")
    if unlabeled:
        print(f"[WARN] npz without matching label folder: {len(unlabeled)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

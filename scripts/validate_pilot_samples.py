"""Pilot collection validation — release gate for newly collected samples.

Usage:
    python scripts/validate_pilot_samples.py --campaign isds2026_v1
    python scripts/validate_pilot_samples.py --paths dataset/features/vn/... [...]

Validates every sample of a collection campaign (or an explicit path list)
BEFORE a manifest release is allowed:
  - npz contains landmarks_raw [T,126], landmarks_normalized [60,126],
    legacy 'sequence' key, and all three validity masks [60] (contract v2);
  - sidecar JSON exists with: signer_id matching an ACTIVE registry entry,
    collection_campaign matching, normalization_version, preprocess_contract_version;
  - the sample's class row has a VALID vocabulary schema v2 assignment
    (non-empty scope; common/profile rules hold);
  - masks are consistent with the normalized array (zero block <=> mask false).

Read-only. Exit 0 = pilot PASS (manifest release may proceed); 1 = FAIL.
Process: run a small pilot batch through this gate before opening the main
campaign; re-run on the full campaign before create_dataset_manifest.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.vocabulary import validate_label_v2  # noqa: E402


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate_sample(npz_path: Path, labels_by_folder: dict, active_signers: set,
                    campaign: str | None) -> list:
    errors = []
    sidecar = npz_path.with_suffix(".json")
    side = {}
    if not sidecar.exists():
        errors.append("missing sidecar JSON")
    else:
        try:
            side = json.loads(sidecar.read_text(encoding="utf-8"))
        except Exception:
            errors.append("unreadable sidecar JSON")

    try:
        with np.load(npz_path, allow_pickle=True) as z:
            keys = set(z.keys())
            required = {"sequence", "landmarks_normalized", "landmarks_raw",
                        "frame_valid_mask", "left_hand_valid_mask", "right_hand_valid_mask"}
            missing = required - keys
            if missing:
                errors.append(f"npz missing keys: {sorted(missing)}")
            else:
                norm = z["landmarks_normalized"]
                raw = z["landmarks_raw"]
                fm = z["frame_valid_mask"]
                lm = z["left_hand_valid_mask"]
                rm = z["right_hand_valid_mask"]
                if norm.shape != (60, 126):
                    errors.append(f"landmarks_normalized shape {norm.shape} != (60,126)")
                if raw.ndim != 2 or raw.shape[1] != 126 or raw.shape[0] < 1:
                    errors.append(f"landmarks_raw shape {raw.shape} invalid")
                for name, m in (("frame", fm), ("left", lm), ("right", rm)):
                    if m.shape != (60,) or m.dtype != np.bool_:
                        errors.append(f"{name}_valid_mask shape/dtype invalid: {m.shape} {m.dtype}")
                if norm.shape == (60, 126) and fm.shape == (60,):
                    computed = np.any(norm != 0.0, axis=1)
                    if not np.array_equal(computed, fm):
                        errors.append("frame_valid_mask inconsistent with normalized array")
    except Exception as exc:
        errors.append(f"npz unreadable: {exc}")

    signer = str(side.get("signer_id") or "").strip()
    if not signer:
        errors.append("sidecar missing signer_id")
    elif signer not in active_signers:
        errors.append(f"signer_id '{signer}' not an active registry entry")
    if campaign:
        c = str(side.get("collection_campaign") or "").strip()
        if c != campaign:
            errors.append(f"collection_campaign '{c}' != expected '{campaign}'")
    for field in ("normalization_version", "preprocess_contract_version"):
        if not str(side.get(field) or "").strip():
            errors.append(f"sidecar missing {field}")

    label_row = labels_by_folder.get(npz_path.parent.name)
    if label_row is None:
        errors.append(f"no label row for folder '{npz_path.parent.name}'")
    else:
        scope = (label_row.get("vocabulary_scope") or "").strip()
        if not scope:
            errors.append("class vocabulary_scope unassigned (needs review)")
        else:
            errors.extend(validate_label_v2(label_row))
        if not (label_row.get("semantic_label") or "").strip():
            errors.append("class missing semantic_label")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--campaign", type=str, default=None,
                    help="Validate all samples whose sidecar carries this collection_campaign")
    ap.add_argument("--paths", type=Path, nargs="*", default=None,
                    help="Explicit npz paths to validate (pilot batch)")
    ap.add_argument("--features-root", type=Path, default=REPO_ROOT / "dataset" / "features")
    ap.add_argument("--labels-csv", type=Path, default=REPO_ROOT / "dataset" / "labels.csv")
    ap.add_argument("--signers-csv", type=Path, default=REPO_ROOT / "dataset" / "signers.csv")
    ap.add_argument("--max-report", type=int, default=20)
    args = ap.parse_args()

    labels_by_folder = {(r.get("folder_name") or "").strip(): r
                        for r in _read_csv(args.labels_csv)}
    active_signers = {(r.get("signer_id") or "").strip()
                      for r in _read_csv(args.signers_csv)
                      if (r.get("is_active") or "1").strip() != "0"} if args.signers_csv.exists() else set()

    if args.paths:
        candidates = list(args.paths)
    elif args.campaign:
        candidates = []
        for npz in sorted(args.features_root.rglob("*.npz")):
            side = npz.with_suffix(".json")
            if side.exists():
                try:
                    if json.loads(side.read_text(encoding="utf-8")).get("collection_campaign") == args.campaign:
                        candidates.append(npz)
                except Exception:
                    continue
    else:
        print("[ERROR] provide --campaign or --paths")
        return 2

    if not candidates:
        print("[FAIL] no samples matched — a pilot batch must exist before the campaign opens.")
        return 1

    failed = 0
    for npz in candidates:
        errs = validate_sample(Path(npz), labels_by_folder, active_signers, args.campaign)
        if errs:
            failed += 1
            if failed <= args.max_report:
                print(f"[FAIL] {npz}")
                for e in errs:
                    print(f"    - {e}")

    print(f"\nPilot validation: {len(candidates) - failed}/{len(candidates)} passed")
    if failed:
        print("RESULT: FAIL — do NOT create a release manifest from this campaign yet.")
        return 1
    print("RESULT: PASS — campaign data meets contract v2; manifest release allowed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

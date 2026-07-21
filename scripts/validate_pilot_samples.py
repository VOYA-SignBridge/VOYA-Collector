"""Pilot collection validation — release gate for newly collected samples.

Usage:
    python scripts/validate_pilot_samples.py --campaign isds2026_v1
    python scripts/validate_pilot_samples.py --paths dataset/features/vn/... [...]

Validates every sample of a collection campaign (or an explicit path list)
BEFORE a manifest release is allowed:
  - npz contains landmarks_raw [T,126], landmarks_normalized [60,126],
    legacy 'sequence' key, and all three validity masks [60] (contract v2);
  - sidecar JSON exists with: signer_id matching an ACTIVE registry entry,
    session_id, collection_campaign matching, normalization_version,
    preprocess_contract_version, storage_contract_version, quality_status;
  - the sample's class row has a VALID vocabulary schema v2 assignment
    (non-empty scope; common/profile rules hold) and a recognition profile;
  - masks are consistent with the normalized array (zero block <=> mask false),
    for the frame mask AND both per-hand masks;
  - landmarks_normalized is REPRODUCIBLE from landmarks_raw by re-applying
    processed/shared/normalization — the storage-level guard against a
    normalization drift between collection and training.

Read-only. Exit 0 = pilot PASS (manifest release may proceed); 1 = FAIL.
Process: run a small pilot batch through this gate before opening the main
campaign; re-run on the full campaign before create_dataset_manifest.
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.normalization import normalize_hands_vector_126  # noqa: E402
from processed.shared.vocabulary import RECOGNITION_PROFILES, validate_label_v2  # noqa: E402

EXPECTED_STORAGE_CONTRACT = "npz_v2"
EXPECTED_NORMALIZATION = "hands126_v1"
VALID_QUALITY_STATUS = {"ok", "flagged"}
# QC metrics the collection path attaches; a pilot sample without them cannot
# support any quality-filtered training experiment later.
REQUIRED_QC_FIELDS = ("completeness", "jitter", "left_hand_ratio", "right_hand_ratio")


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
                # Per-hand masks: a hand slot is present iff its 63-dim block
                # is non-zero. Wrist-centering maps the wrist to exactly 0, so
                # this must be evaluated over the whole block, never one point.
                if norm.shape == (60, 126) and lm.shape == (60,) and rm.shape == (60,):
                    if not np.array_equal(np.any(norm[:, :63] != 0.0, axis=1), lm):
                        errors.append("left_hand_valid_mask inconsistent with normalized array")
                    if not np.array_equal(np.any(norm[:, 63:] != 0.0, axis=1), rm):
                        errors.append("right_hand_valid_mask inconsistent with normalized array")
                # Legacy alias must not drift from the canonical array.
                if "sequence" in keys and norm.shape == (60, 126):
                    if not np.array_equal(np.asarray(z["sequence"], dtype=np.float32),
                                          np.asarray(norm, dtype=np.float32)):
                        errors.append("'sequence' differs from 'landmarks_normalized'")
                # Storage-level golden check: normalized frames must be
                # reproducible from the stored raw frames via the SHARED
                # normalization module (the same file the realtime service
                # loads). Compares the overlapping, unpadded prefix only.
                if (norm.shape == (60, 126) and raw.ndim == 2 and raw.shape[1] == 126):
                    n_cmp = min(int(raw.shape[0]), 60)
                    bad = 0
                    worst = 0.0
                    for t in range(n_cmp):
                        expect = normalize_hands_vector_126(
                            np.asarray(raw[t], dtype=np.float32))
                        d = float(np.abs(np.asarray(norm[t], dtype=np.float32) - expect).max())
                        if d > 1e-5:
                            bad += 1
                            worst = max(worst, d)
                    if bad:
                        errors.append(
                            f"landmarks_normalized not reproducible from landmarks_raw: "
                            f"{bad}/{n_cmp} frames differ (max |diff|={worst:.2e})")
    except Exception as exc:
        errors.append(f"npz unreadable: {exc}")

    signer = str(side.get("signer_id") or "").strip()
    if not signer:
        errors.append("sidecar missing signer_id")
    elif signer not in active_signers:
        errors.append(f"signer_id '{signer}' not an active registry entry")
    if not str(side.get("session_id") or "").strip():
        errors.append("sidecar missing session_id")
    if campaign:
        c = str(side.get("collection_campaign") or "").strip()
        if c != campaign:
            errors.append(f"collection_campaign '{c}' != expected '{campaign}'")
    for field in ("normalization_version", "preprocess_contract_version",
                  "storage_contract_version"):
        if not str(side.get(field) or "").strip():
            errors.append(f"sidecar missing {field}")
    norm_ver = str(side.get("normalization_version") or "").strip()
    if norm_ver and norm_ver != EXPECTED_NORMALIZATION:
        errors.append(f"normalization_version '{norm_ver}' != '{EXPECTED_NORMALIZATION}'")
    store_ver = str(side.get("storage_contract_version") or "").strip()
    if store_ver and store_ver != EXPECTED_STORAGE_CONTRACT:
        errors.append(f"storage_contract_version '{store_ver}' != '{EXPECTED_STORAGE_CONTRACT}'")

    # QC status must be recorded, otherwise no quality-filtered experiment can
    # ever be run over this campaign.
    qstatus = str(side.get("quality_status") or "").strip()
    if not qstatus:
        errors.append("sidecar missing quality_status")
    elif qstatus not in VALID_QUALITY_STATUS:
        errors.append(f"quality_status '{qstatus}' not in {sorted(VALID_QUALITY_STATUS)}")
    for field in REQUIRED_QC_FIELDS:
        if side.get(field) is None:
            errors.append(f"sidecar missing QC metric '{field}'")

    label_row = labels_by_folder.get(npz_path.parent.name)
    if label_row is None:
        errors.append(f"no label row for folder '{npz_path.parent.name}'")
    else:
        scope = (label_row.get("vocabulary_scope") or "").strip()
        if not scope:
            errors.append("class vocabulary_scope unassigned (needs review)")
        else:
            errors.extend(validate_label_v2(label_row))
        # A profile_specific class must name a TRAINABLE profile; common is
        # allowed to carry none.
        profile = (label_row.get("recognition_profile") or "").strip()
        if scope == "profile_specific" and profile not in RECOGNITION_PROFILES:
            errors.append(f"recognition_profile '{profile}' is not trainable")
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
    ap.add_argument("--min-signers", type=int, default=6,
                    help="warn if the campaign has fewer distinct signers than this")
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
    reasons: Counter = Counter()
    by_signer: Counter = Counter()
    by_quality: Counter = Counter()
    by_profile: Counter = Counter()
    by_session: Counter = Counter()

    for npz in candidates:
        npz = Path(npz)
        errs = validate_sample(npz, labels_by_folder, active_signers, args.campaign)
        side = {}
        sidecar = npz.with_suffix(".json")
        if sidecar.exists():
            try:
                side = json.loads(sidecar.read_text(encoding="utf-8"))
            except Exception:
                side = {}
        by_signer[str(side.get("signer_id") or "<none>")] += 1
        by_quality[str(side.get("quality_status") or "<none>")] += 1
        by_session[str(side.get("session_id") or "<none>")] += 1
        row = labels_by_folder.get(npz.parent.name) or {}
        by_profile[str(row.get("recognition_profile") or "<none>")] += 1
        if errs:
            failed += 1
            for e in errs:
                # collapse per-sample specifics into a reason bucket
                reasons[e.split(":")[0].split("(")[0].strip()] += 1
            if failed <= args.max_report:
                print(f"[FAIL] {npz}")
                for e in errs:
                    print(f"    - {e}")

    if failed > args.max_report:
        print(f"... and {failed - args.max_report} more failing sample(s) not shown")

    print("\n--- campaign composition ---")
    print(f"  samples        : {len(candidates)}")
    print(f"  signers        : {dict(by_signer.most_common())}")
    print(f"  sessions       : {len(by_session)} distinct")
    print(f"  profiles       : {dict(by_profile.most_common())}")
    print(f"  quality_status : {dict(by_quality.most_common())}")
    if reasons:
        print("\n--- failure reasons ---")
        for reason, n in reasons.most_common():
            print(f"  {n:5d}  {reason}")

    # Signer diversity is what makes signer-disjoint evaluation possible at all;
    # warn early rather than after the manifest is frozen.
    real_signers = {s for s in by_signer if s != "<none>"}
    if len(real_signers) < args.min_signers:
        print(f"\n[WARN] only {len(real_signers)} distinct signer(s); "
              f"signer-disjoint splitting needs >= {args.min_signers} "
              f"(and >= 3 per class) to produce a non-empty val/test.")

    print(f"\nPilot validation: {len(candidates) - failed}/{len(candidates)} passed")
    if failed:
        print("RESULT: FAIL — do NOT create a release manifest from this campaign yet.")
        return 1
    print("RESULT: PASS — campaign data meets contract v2; manifest release allowed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

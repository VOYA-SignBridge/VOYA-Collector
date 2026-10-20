"""Bring image-space samples into the corpus's coordinate convention.

THE PROBLEM
-----------
Two collection paths wrote into the same samples.csv without agreeing on a
coordinate space. The camera path normalizes before writing — each hand moved
onto its own wrist, x,y divided by that hand's own span. The video path never
normalized at all, so its `sequence` is raw MediaPipe image coordinates.

Measured over the corpus:

    wrist-centred   3431 files   hand span p50 = 1.205
    image-coords     440 files   hand span p50 = 0.448

A 2.7x scale difference plus a translation offset, in the same feature vector,
fed to the same network. The training loader does not normalize, so nothing
downstream reconciles them.

WHAT THIS DOES
--------------
For each affected sample:

  1. archives the file it is about to change, under dataset/_backup_renorm/;
  2. writes the ORIGINAL array into the raw archive (dataset/raw/...) as
     `landmarks_raw` — so the recording survives as a recording, and this
     migration becomes reversible from data rather than from a backup;
  3. re-runs processed/shared/normalization over it and rewrites `sequence`;
  4. restamps the metadata and the sidecar to say what the file now is.

Step 2 is what makes this safe: the array being replaced is not deleted, it is
promoted to the archive where it always belonged. `--revert` reads it back.

WHY NOT JUST DROP THEM
----------------------
They are 4 classes, and one of them — "Cảm ơn" — has 120 affected samples and
0 unaffected ones. Excluding would delete the class outright. None of the 4 is
in the alphabet research split, so neither choice touches the thesis artifacts.

Default is a dry run. Nothing is written without --apply.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path

_here = Path(__file__).resolve().parent
if str(_here) not in _sys.path:
    _sys.path.insert(0, str(_here))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import csv
import json
import shutil
import sys
from collections import Counter

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.normalization import normalize_hands_vector_126  # noqa: E402

DATASET = REPO_ROOT / "dataset"
BACKUP_ROOT = DATASET / "_backup_renorm"


def raw_archive_path(npz_path: Path) -> Path:
    """dataset/features/<...>/x.npz -> dataset/raw/<...>/x.npz

    See app.dataset_samples.raw_archive_path, which is the definition.
    """
    parts = list(npz_path.resolve().parts)
    for i in range(len(parts) - 1, -1, -1):
        if parts[i] == "features":
            parts[i] = "raw"
            return Path(*parts)
    return npz_path.parent / "raw" / npz_path.name


def is_image_space(seq: np.ndarray) -> bool:
    """True when at least one live hand's wrist is NOT at the origin.

    Exact rather than statistical: normalization pins landmark 0 at the origin
    by construction, so a single live wrist away from it rules normalization
    out. No threshold is being tuned here.
    """
    if seq.ndim != 2 or seq.shape[1] != 126:
        return False
    hands = seq.reshape(len(seq), 2, 21, 3)
    saw = False
    for h in range(2):
        block = hands[:, h]
        live = np.any(block.reshape(len(block), -1) != 0.0, axis=1)
        if not live.any():
            continue
        saw = True
        if float(np.abs(block[live][:, 0, :2]).max()) > 1e-4:
            return True
    return False if saw else False


def normalize_sequence(seq: np.ndarray) -> np.ndarray:
    out = np.empty_like(seq, dtype=np.float32)
    for t in range(len(seq)):
        out[t] = normalize_hands_vector_126(np.asarray(seq[t], dtype=np.float32))
    return out


def atomic_savez(path: Path, arrays: dict) -> None:
    import os
    import tempfile

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="npztmp_", suffix=".npz", dir=str(path.parent))
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            np.savez_compressed(f, **arrays)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except Exception:
                pass


def load_npz(path: Path):
    with np.load(path, allow_pickle=True) as z:
        arrays = {k: np.asarray(z[k]) for k in z.keys() if k != "meta"}
        meta = z["meta"].item() if "meta" in z else {}
    return arrays, meta


def affected_files() -> list:
    """Every readable sample whose stored `sequence` is in image space."""
    found = []
    for f in sorted((DATASET / "features").rglob("*.npz")):
        try:
            with np.load(f, allow_pickle=True) as z:
                if "sequence" not in z:
                    continue
                seq = np.asarray(z["sequence"], dtype=np.float32)
        except Exception:
            continue
        if is_image_space(seq):
            found.append(f)
    return found


def migrate(path: Path, apply: bool) -> str:
    arrays, meta = load_npz(path)
    seq = np.asarray(arrays["sequence"], dtype=np.float32)

    if not is_image_space(seq):
        return "skip_already_normalized"
    archived = raw_archive_path(path)
    if archived.exists():
        # Re-running must not overwrite an archived recording with a
        # normalized array — that would destroy the very thing being saved.
        return "skip_archive_exists"

    normalized = normalize_sequence(seq)
    if is_image_space(normalized):
        return "fail_still_image_space"

    if not apply:
        return "would_migrate"

    relative = path.relative_to(DATASET)
    backup = BACKUP_ROOT / relative
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, backup)
    sidecar = path.with_suffix(".json")
    if sidecar.exists():
        shutil.copy2(sidecar, (BACKUP_ROOT / relative).with_suffix(".json"))

    # The recording first, exactly as save_sequence_npz orders it: if this
    # process dies between the two writes, the take survives.
    raw_meta = dict(meta)
    raw_meta["coordinate_space"] = "mediapipe_image"
    atomic_savez(archived, {"landmarks_raw": seq.astype(np.float32), "meta": raw_meta})

    new_arrays = dict(arrays)
    new_arrays["sequence"] = normalized
    new_arrays["landmarks_normalized"] = normalized
    new_arrays.pop("landmarks_raw", None)

    new_meta = dict(meta)
    new_meta["coordinate_space"] = "wrist_centred_v1"
    new_meta["normalization_version"] = "hands126_v1"
    new_meta["raw_landmarks_available"] = True
    new_meta["storage_contract_version"] = "npz_v3_split_raw"
    new_meta["renormalized_from_image_space"] = True
    new_arrays_meta = {**new_arrays, "meta": new_meta}
    atomic_savez(path, new_arrays_meta)

    if sidecar.exists():
        try:
            side = json.loads(sidecar.read_text(encoding="utf-8"))
            side.update({
                "coordinate_space": "wrist_centred_v1",
                "normalization_version": "hands126_v1",
                "raw_landmarks_available": True,
                "storage_contract_version": "npz_v3_split_raw",
                "renormalized_from_image_space": True,
            })
            sidecar.write_text(json.dumps(side, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"  sidecar update failed for {path.name}: {exc}")

    return "migrated"


def revert(path: Path, apply: bool) -> str:
    """Put the original array back from the raw archive."""
    archived = raw_archive_path(path)
    if not archived.is_file():
        return "skip_no_archive"
    arrays, meta = load_npz(path)
    if not meta.get("renormalized_from_image_space"):
        return "skip_not_migrated"
    if not apply:
        return "would_revert"

    with np.load(archived, allow_pickle=True) as z:
        original = np.asarray(z["landmarks_raw"], dtype=np.float32)

    new_arrays = dict(arrays)
    new_arrays["sequence"] = original
    new_arrays["landmarks_normalized"] = original
    new_meta = dict(meta)
    new_meta["coordinate_space"] = "mediapipe_image"
    new_meta.pop("renormalized_from_image_space", None)
    new_meta["raw_landmarks_available"] = False
    atomic_savez(path, {**new_arrays, "meta": new_meta})
    archived.unlink()
    return "reverted"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="actually write; without it nothing is modified")
    ap.add_argument("--revert", action="store_true",
                    help="restore the original arrays from the raw archive")
    args = ap.parse_args()

    if args.revert:
        targets = [f for f in sorted((DATASET / "features").rglob("*.npz"))
                   if raw_archive_path(f).is_file()]
        print(f"candidates for revert: {len(targets)}")
        results = Counter(revert(f, args.apply) for f in targets)
    else:
        targets = affected_files()
        print(f"samples stored in image space: {len(targets)}")
        by_class = Counter(f.parent.parent.name if f.parent.name.startswith("aug_")
                           else f.parent.name for f in targets)
        for cls, n in by_class.most_common():
            print(f"  {cls}: {n}")
        results = Counter(migrate(f, args.apply) for f in targets)

    print()
    for k, v in results.most_common():
        print(f"{k}: {v}")
    if not args.apply:
        print("\nDRY RUN — nothing was written. Re-run with --apply.")
    else:
        print(f"\nbackup of every changed file: {BACKUP_ROOT}")
    return 0 if not any(k.startswith("fail") for k in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

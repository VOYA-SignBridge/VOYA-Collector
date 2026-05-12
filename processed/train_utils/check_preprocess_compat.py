from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

try:
    # Workspace layout: processed/dataset_versioning.py
    from dataset_versioning import get_splits_dir  # type: ignore
except Exception:
    try:
        # Legacy layout: train_model/dataset_versioning.py
        from train_model.dataset_versioning import get_splits_dir  # type: ignore
    except Exception:
        get_splits_dir = None  # type: ignore

try:
    # When run as module: python -m processed.train_utils.check_preprocess_compat
    from .dataset_loader import NPZSignDataset  # type: ignore
except Exception:
    # When run as script: python train_utils/check_preprocess_compat.py
    # Ensure we can import from this workspace layout: processed/train_utils/dataset_loader.py
    import sys

    processed_root = Path(__file__).resolve().parents[1]
    if str(processed_root) not in sys.path:
        sys.path.insert(0, str(processed_root))

    try:
        from train_utils.dataset_loader import NPZSignDataset  # type: ignore
    except Exception:
        # Legacy layout fallback
        repo_root = Path(__file__).resolve().parents[2]
        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from train_model.train_utils.dataset_loader import NPZSignDataset  # type: ignore


_D = 126
_HAND_D = 63


@dataclass
class RunningStats:
    min_val: float = float("inf")
    max_val: float = float("-inf")
    sum_val: float = 0.0
    count: int = 0

    def update(self, arr: np.ndarray) -> None:
        if arr.size == 0:
            return
        mn = float(np.min(arr))
        mx = float(np.max(arr))
        self.min_val = min(self.min_val, mn)
        self.max_val = max(self.max_val, mx)
        self.sum_val += float(np.sum(arr))
        self.count += int(arr.size)

    @property
    def mean(self) -> float:
        return self.sum_val / max(1, self.count)


def _split_xyz(hand: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    # hand: [T, 21*3]
    pts = hand.reshape(hand.shape[0], 21, 3)
    return pts[:, :, 0], pts[:, :, 1], pts[:, :, 2]


def _nonzero_mask(hand: np.ndarray) -> np.ndarray:
    # consider hand present if any coord non-zero at a timestep
    return np.any(np.abs(hand) > 0, axis=1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Inspect dataset (.npz) feature statistics to infer whether realtime preprocessing (raw MediaPipe left+right) "
            "matches training features. This does NOT use the webcam; it inspects split CSV referenced feature files."
        )
    )
    try:
        default_splits = get_splits_dir() if get_splits_dir else (Path(__file__).resolve().parents[1] / "processed" / "splits")
    except Exception:
        default_splits = Path(__file__).resolve().parents[1] / "processed" / "splits"

    parser.add_argument("--csv", type=Path, default=default_splits / "train.csv", help="Split CSV to sample from")
    parser.add_argument("--n", type=int, default=200, help="Number of VALID samples to scan (skips missing files)")
    parser.add_argument("--max_tries", type=int, default=2000, help="Max dataset indices to try while collecting N valid samples")
    parser.add_argument("--max_missing_examples", type=int, default=5, help="How many missing-file examples to print")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    rng = np.random.default_rng(int(args.seed))

    ds = NPZSignDataset(args.csv, to_tensor=False)
    if len(ds) == 0:
        raise SystemExit(f"Empty dataset: {args.csv}")

    target_n = min(int(args.n), len(ds))
    max_tries = min(int(args.max_tries), len(ds))
    if max_tries < target_n:
        max_tries = target_n
    idxs = rng.choice(len(ds), size=max_tries, replace=False)

    # Stats per hand per axis
    stats: Dict[str, RunningStats] = {
        "left_x": RunningStats(),
        "left_y": RunningStats(),
        "left_z": RunningStats(),
        "right_x": RunningStats(),
        "right_y": RunningStats(),
        "right_z": RunningStats(),
    }

    # Range checks for [0,1] on x/y (typical MediaPipe normalized image coords)
    outside_xy = {"left": 0, "right": 0}
    total_xy = {"left": 0, "right": 0}

    # Hand presence and rough left/right spatial sanity
    left_present = 0
    right_present = 0
    both_present = 0

    # Mean x per hand across present timesteps
    sum_mean_x_left = 0.0
    sum_mean_x_right = 0.0
    count_mean_x = 0

    missing_count = 0
    missing_examples = []
    scanned_valid = 0

    for i in idxs:
        if scanned_valid >= target_n:
            break
        try:
            x, _, meta = ds[int(i)]
        except FileNotFoundError as e:
            missing_count += 1
            if len(missing_examples) < int(args.max_missing_examples):
                missing_examples.append(str(e))
            continue
        except Exception:
            # Any decode/shape issues are treated as invalid samples for this analysis.
            continue
        x = np.asarray(x, dtype=np.float32)
        if x.shape != (60, _D):
            raise SystemExit(f"Unexpected shape {x.shape} at idx={i}; expected (60,{_D})")

        scanned_valid += 1

        left = x[:, :_HAND_D]
        right = x[:, _HAND_D:]

        left_mask = _nonzero_mask(left)
        right_mask = _nonzero_mask(right)
        left_has = bool(np.any(left_mask))
        right_has = bool(np.any(right_mask))
        left_present += int(left_has)
        right_present += int(right_has)
        both_present += int(left_has and right_has)

        lx, ly, lz = _split_xyz(left)
        rx, ry, rz = _split_xyz(right)

        # update stats only where hand is present (avoid all-zero padding dominating)
        if left_has:
            m = left_mask
            stats["left_x"].update(lx[m])
            stats["left_y"].update(ly[m])
            stats["left_z"].update(lz[m])
            # xy range check
            total_xy["left"] += int(lx[m].size + ly[m].size)
            outside_xy["left"] += int(np.sum((lx[m] < 0) | (lx[m] > 1)) + np.sum((ly[m] < 0) | (ly[m] > 1)))

        if right_has:
            m = right_mask
            stats["right_x"].update(rx[m])
            stats["right_y"].update(ry[m])
            stats["right_z"].update(rz[m])
            total_xy["right"] += int(rx[m].size + ry[m].size)
            outside_xy["right"] += int(np.sum((rx[m] < 0) | (rx[m] > 1)) + np.sum((ry[m] < 0) | (ry[m] > 1)))

        # mean x sanity check when BOTH hands present
        if left_has and right_has:
            # use only present timesteps for each hand
            lx_mean = float(np.mean(lx[left_mask]))
            rx_mean = float(np.mean(rx[right_mask]))
            sum_mean_x_left += lx_mean
            sum_mean_x_right += rx_mean
            count_mean_x += 1

    def pct(out: int, total: int) -> float:
        return 100.0 * float(out) / float(max(1, total))

    print("=== Dataset Feature Preprocess Check ===")
    print(f"CSV: {args.csv}")
    print(f"Requested valid samples: {target_n}")
    print(f"Scanned valid samples:   {scanned_valid}")
    print(f"Missing feature files:   {missing_count}")
    if missing_examples:
        print("Missing examples (first few):")
        for ex in missing_examples:
            print(f"- {ex}")
    print("")

    print("Presence (any non-zero coords across T):")
    denom = max(1, scanned_valid)
    print(f"- left present:  {left_present}/{scanned_valid} ({100.0*left_present/denom:.1f}%)")
    print(f"- right present: {right_present}/{scanned_valid} ({100.0*right_present/denom:.1f}%)")
    print(f"- both present:  {both_present}/{scanned_valid} ({100.0*both_present/denom:.1f}%)")
    print("")

    print("Value ranges (only timesteps where that hand is present):")
    for k in ("left_x", "left_y", "left_z", "right_x", "right_y", "right_z"):
        s = stats[k]
        if s.count == 0:
            print(f"- {k}: (no data)")
        else:
            print(f"- {k}: min={s.min_val:.4f} max={s.max_val:.4f} mean={s.mean:.4f}")
    print("")

    print("XY normalized-range check (expect most x/y in [0,1] if raw MediaPipe normalized image coords):")
    print(f"- left  x/y outside [0,1]:  {outside_xy['left']}/{total_xy['left']} ({pct(outside_xy['left'], total_xy['left']):.2f}%)")
    print(f"- right x/y outside [0,1]:  {outside_xy['right']}/{total_xy['right']} ({pct(outside_xy['right'], total_xy['right']):.2f}%)")
    print("")

    if count_mean_x:
        avg_lx = sum_mean_x_left / count_mean_x
        avg_rx = sum_mean_x_right / count_mean_x
        print("Left-vs-right ordering sanity (only samples where BOTH hands present):")
        print(f"- mean(x_left)  avg: {avg_lx:.4f}")
        print(f"- mean(x_right) avg: {avg_rx:.4f}")
        if avg_lx < avg_rx:
            print("- Heuristic: first 63 dims look like LEFT hand (x_left < x_right).")
        elif avg_lx > avg_rx:
            print("- Heuristic: first 63 dims may be RIGHT hand (x_left > x_right) OR the camera/features are mirrored.")
        else:
            print("- Heuristic: inconclusive (means equal).")
    else:
        print("Left-vs-right ordering sanity: not enough two-hand samples to infer.")

    print("")
    print("Interpretation tips:")
    print("- If x/y are mostly within [0,1], dataset likely stores raw MediaPipe normalized coords (no extra normalization).")
    print("- If x/y often fall outside [0,1] or are centered around 0, dataset likely applies extra normalization/centering during feature export.")
    print("- If mean(x_left) > mean(x_right) consistently, left/right halves may be swapped or the extraction used a mirrored image.")


if __name__ == "__main__":
    main()

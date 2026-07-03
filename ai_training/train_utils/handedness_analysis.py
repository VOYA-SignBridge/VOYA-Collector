"""
Handedness analysis tools for identifying asymmetries in sign language recognition.

Analyzes which hand is present/dominant in each sample to track:
- Left-hand-only accuracy
- Right-hand-only accuracy
- Both-hands accuracy
- Per-class handedness distribution
"""

from __future__ import annotations

from typing import Dict, List, Tuple
import numpy as np
from collections import defaultdict, Counter


# MediaPipe hands semantic in this pipeline:
# Slot 0: LEFT (actually MediaPipe RIGHT, due to swapped semantic)
# Slot 1: RIGHT (actually MediaPipe LEFT, due to swapped semantic)
# Each hand: 21 points × 3 coords = 63 features per hand
HAND_DIM = 63
POINTS_PER_HAND = 21
COORDS_PER_POINT = 3


def detect_hand_presence(x: np.ndarray) -> Tuple[bool, bool]:
    """
    Detect which hands are present in a feature vector.

    Args:
        x: (60, 126) or (126,) feature array

    Returns:
        (left_present, right_present)

    Note:
        Due to swapped semantics:
        - left_present means slot 0 has non-zero landmarks
        - right_present means slot 1 has non-zero landmarks
    """
    x = np.asarray(x, dtype=np.float32)

    if x.ndim == 2:
        # (T, 126): check any timestep
        x = x.reshape(-1, 126)
        x = np.any(x != 0, axis=0)  # Collapse time dimension

    if x.shape[-1] != 126:
        return False, False

    # Reshape: (2, 63)
    hands = x.reshape(2, 63)

    left_present = np.any(hands[0] != 0)
    right_present = np.any(hands[1] != 0)

    return bool(left_present), bool(right_present)


def analyze_hand_dominance(x: np.ndarray) -> str:
    """
    Analyze which hand has stronger signal.

    Returns:
        'left' | 'right' | 'both' | 'unknown'
    """
    x = np.asarray(x, dtype=np.float32).reshape(-1, 126)
    hands = x.reshape(-1, 2, 63)

    left_present, right_present = detect_hand_presence(x)

    if not left_present and not right_present:
        return 'unknown'

    if left_present and not right_present:
        return 'left_only'

    if right_present and not left_present:
        return 'right_only'

    # Both present: measure signal strength
    left_mag = np.sqrt(np.sum(hands[:, 0, :]**2))
    right_mag = np.sqrt(np.sum(hands[:, 1, :]**2))

    if left_mag > right_mag * 1.2:
        return 'left_dominant'
    elif right_mag > left_mag * 1.2:
        return 'right_dominant'
    else:
        return 'balanced'


class HandednessAnalyzer:
    """Tracks handedness statistics across a dataset."""

    def __init__(self):
        self.total_samples = 0
        self.per_class_handedness: Dict[int, Counter] = defaultdict(Counter)
        self.per_class_samples: Dict[int, int] = defaultdict(int)
        self.errors = []

    def process_sample(self, x: np.ndarray, class_idx: int) -> None:
        """Record handedness info for one sample."""
        try:
            self.total_samples += 1
            self.per_class_samples[class_idx] += 1

            left_p, right_p = detect_hand_presence(x)
            handedness = analyze_hand_dominance(x)

            self.per_class_handedness[class_idx][handedness] += 1
        except Exception as e:
            self.errors.append(f"Sample {self.total_samples}: {e}")

    def get_class_handedness_distribution(self, class_idx: int) -> Dict[str, float]:
        """Get percent breakdown of handedness for a class."""
        total = self.per_class_samples.get(class_idx, 1)
        dist = {}
        for hand_type in ['left_only', 'right_only', 'left_dominant', 'right_dominant', 'balanced', 'unknown']:
            count = self.per_class_handedness[class_idx].get(hand_type, 0)
            dist[hand_type] = 100.0 * count / total if total > 0 else 0.0
        return dist

    def print_report(self, class_labels: Dict[int, str] = None) -> None:
        """Print comprehensive handedness report."""
        if class_labels is None:
            class_labels = {}

        print(f"\n{'='*80}")
        print("HANDEDNESS ANALYSIS REPORT")
        print(f"{'='*80}")
        print(f"Total samples analyzed: {self.total_samples}")
        print(f"Classes: {len(self.per_class_samples)}")

        if self.errors:
            print(f"\n⚠️  Processing errors: {len(self.errors)}")
            for err in self.errors[:3]:
                print(f"  {err}")
            if len(self.errors) > 3:
                print(f"  ... and {len(self.errors) - 3} more")

        print(f"\n{'Class':<35} {'Samples':>8} {'Type':>15} {'Distribution':<45}")
        print("-" * 80)

        for class_idx in sorted(self.per_class_samples.keys()):
            count = self.per_class_samples[class_idx]
            label = class_labels.get(class_idx, f'Class {class_idx}')
            dist = self.get_class_handedness_distribution(class_idx)

            # Find dominant handedness
            dominant = max(dist.items(), key=lambda x: x[1])
            dominant_type = dominant[0]

            dist_str = f"L:{dist['left_only']:.0f}% R:{dist['right_only']:.0f}% LD:{dist['left_dominant']:.0f}% RD:{dist['right_dominant']:.0f}%"

            print(f"{label:<35} {count:>8} {dominant_type:>15} {dist_str:<45}")

        print(f"{'='*80}\n")


def create_handedness_metadata(csv_rows: List[dict], features_loader_fn) -> List[dict]:
    """
    Enrich CSV rows with handedness metadata.

    This allows later filtering/analysis by hand presence.

    Args:
        csv_rows: List of sample dictionaries from CSV
        features_loader_fn: Function(row) -> numpy array of features

    Returns:
        Same rows, with added 'hand_presence' and 'handedness' fields
    """
    for row in csv_rows:
        try:
            x = features_loader_fn(row)
            left_p, right_p = detect_hand_presence(x)
            handedness = analyze_hand_dominance(x)

            row['left_hand_present'] = str(int(left_p))
            row['right_hand_present'] = str(int(right_p))
            row['handedness_type'] = handedness
        except Exception as e:
            row['left_hand_present'] = ''
            row['right_hand_present'] = ''
            row['handedness_type'] = 'error'

    return csv_rows

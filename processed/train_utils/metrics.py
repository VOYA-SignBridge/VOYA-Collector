from __future__ import annotations

"""Small metrics utilities for temporal classification.

These metrics are intentionally dependency-light (no sklearn) and are used by
training/evaluation scripts.

Provides:
- temporal_accuracy(preds, targets)
- sequence_consistency_score(preds)
- macro_f1(preds, targets, num_classes)
- macro_f1_from_preds(preds, targets, num_classes)  (backward-compatible alias)
- batch_scs(batch_preds)
- batch_sequence_metrics(batch_preds, batch_targets, num_classes)
"""

from typing import Dict, Iterable, List, Sequence

import numpy as np


def temporal_accuracy(preds: Sequence[int], targets: Sequence[int]) -> float:
    """Fraction of matching labels; returns 0.0 on empty or length mismatch."""
    p = np.asarray(preds)
    t = np.asarray(targets)
    if p.size == 0 or p.shape != t.shape:
        return 0.0
    return float((p == t).mean())


def sequence_consistency_score(preds: Sequence[int]) -> float:
    """SCS: proportion of consecutive positions with identical predictions.

    If length <= 1, returns 1.0 by convention (no transitions).
    """
    p = np.asarray(preds)
    if p.size <= 1:
        return 1.0
    return float((p[:-1] == p[1:]).mean())


def macro_f1(preds: Sequence[int], targets: Sequence[int], num_classes: int) -> float:
    """Unweighted mean F1 across classes; returns 0.0 on invalid input."""
    if num_classes <= 0:
        return 0.0
    p = np.asarray(preds).astype(int).ravel()
    t = np.asarray(targets).astype(int).ravel()
    if p.size == 0 or p.shape != t.shape:
        return 0.0

    f1s: List[float] = []
    for c in range(int(num_classes)):
        tp = int(((p == c) & (t == c)).sum())
        fp = int(((p == c) & (t != c)).sum())
        fn = int(((p != c) & (t == c)).sum())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        f1s.append(f1)

    return float(np.mean(f1s)) if f1s else 0.0


def macro_f1_from_preds(preds: Sequence[int], targets: Sequence[int], num_classes: int) -> float:
    """Backward-compatible alias for macro_f1."""
    return macro_f1(preds, targets, num_classes)


def batch_scs(batch_preds: Iterable[Sequence[int]]) -> float:
    """Mean SCS across a batch of sequences."""
    seqs = list(batch_preds)
    if not seqs:
        return 0.0
    return float(np.mean([sequence_consistency_score(seq) for seq in seqs]))


def batch_sequence_metrics(
    batch_preds: Sequence[Sequence[int]],
    batch_targets: Sequence[Sequence[int]],
    num_classes: int,
) -> Dict[str, float]:
    """Compute mean accuracy, mean SCS (per sequence), and macro-F1 over all windows."""
    per_acc: List[float] = []
    per_scs: List[float] = []
    all_preds: List[int] = []
    all_targets: List[int] = []

    for p_seq, t_seq in zip(batch_preds, batch_targets):
        per_acc.append(temporal_accuracy(p_seq, t_seq))
        per_scs.append(sequence_consistency_score(p_seq))
        all_preds.extend(int(x) for x in p_seq)
        all_targets.extend(int(x) for x in t_seq)

    mean_acc = float(np.mean(per_acc)) if per_acc else 0.0
    mean_scs = float(np.mean(per_scs)) if per_scs else 1.0
    macro = macro_f1(all_preds, all_targets, num_classes)
    return {"mean_accuracy": mean_acc, "mean_scs": mean_scs, "macro_f1": macro}

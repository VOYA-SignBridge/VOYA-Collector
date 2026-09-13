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

import math
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


def balanced_accuracy(preds: Sequence[int], targets: Sequence[int], num_classes: int) -> float:
    """Mean per-class recall. Unlike plain accuracy, a model that only learns
    the majority classes cannot hide behind a high score here."""
    p = np.asarray(preds).astype(int).ravel()
    t = np.asarray(targets).astype(int).ravel()
    if p.size == 0 or p.shape != t.shape:
        return 0.0
    recalls: List[float] = []
    for c in range(int(num_classes)):
        mask = t == c
        support = int(mask.sum())
        if support == 0:
            continue
        recalls.append(float((p[mask] == c).mean()))
    return float(np.mean(recalls)) if recalls else 0.0


def matthews_corrcoef(preds: Sequence[int], targets: Sequence[int], num_classes: int) -> float:
    """Multiclass Matthews correlation coefficient (Gorodkin, 2004), computed
    from the confusion matrix. Ranges [-1, 1]; 0 is chance level. Unlike
    accuracy/F1 it is symmetric in precision/recall and stays informative
    under class imbalance."""
    p = np.asarray(preds).astype(int).ravel()
    t = np.asarray(targets).astype(int).ravel()
    if p.size == 0 or p.shape != t.shape:
        return 0.0
    nc = int(num_classes)
    C = np.zeros((nc, nc), dtype=np.float64)
    for ti, pi in zip(t, p):
        if 0 <= ti < nc and 0 <= pi < nc:
            C[ti, pi] += 1
    t_sum = C.sum(axis=1)
    p_sum = C.sum(axis=0)
    n = C.sum()
    c = np.trace(C)
    cov_tp = c * n - float(np.dot(t_sum, p_sum))
    cov_tt = n ** 2 - float(np.dot(t_sum, t_sum))
    cov_pp = n ** 2 - float(np.dot(p_sum, p_sum))
    denom = math.sqrt(cov_tt * cov_pp) if cov_tt > 0 and cov_pp > 0 else 0.0
    return float(cov_tp / denom) if denom > 0 else 0.0


def top_k_accuracy(scores: "np.ndarray", targets: Sequence[int], k: int) -> float:
    """Fraction of samples whose true class is among the top-k scored
    classes. `scores` is [N, C] (logits or probabilities — ranking-only, so
    either works). Meaningful mainly when num_classes > k."""
    pr = np.asarray(scores, dtype=np.float64)
    t = np.asarray(targets).astype(int).ravel()
    if pr.ndim != 2 or pr.shape[0] == 0 or pr.shape[0] != t.shape[0]:
        return 0.0
    k = max(1, min(int(k), pr.shape[1]))
    topk = np.argpartition(-pr, kth=k - 1, axis=1)[:, :k]
    hits = np.any(topk == t[:, None], axis=1)
    return float(hits.mean())


def roc_auc_macro_ovr(scores: "np.ndarray", targets: Sequence[int], num_classes: int) -> float:
    """Macro-averaged one-vs-rest ROC-AUC via the Mann-Whitney U / rank-sum
    identity (no sklearn dependency, ties handled by average rank). Classes
    with zero positive or zero negative samples in this split have an
    undefined AUC and are skipped rather than counted as 0."""
    pr = np.asarray(scores, dtype=np.float64)
    t = np.asarray(targets).astype(int).ravel()
    if pr.ndim != 2 or pr.shape[0] == 0 or pr.shape[0] != t.shape[0]:
        return 0.0
    n = pr.shape[0]
    aucs: List[float] = []
    for c in range(int(num_classes)):
        y = (t == c)
        pos = int(y.sum())
        neg = n - pos
        if pos == 0 or neg == 0:
            continue
        col = pr[:, c]
        order = np.argsort(col, kind="mergesort")
        sorted_scores = col[order]
        ranks = np.empty(n, dtype=np.float64)
        i = 0
        while i < n:
            j = i
            while j + 1 < n and sorted_scores[j + 1] == sorted_scores[i]:
                j += 1
            avg_rank = (i + 1 + j + 1) / 2.0  # 1-indexed average rank over the tie block
            ranks[order[i:j + 1]] = avg_rank
            i = j + 1
        sum_ranks_pos = float(ranks[y].sum())
        auc = (sum_ranks_pos - pos * (pos + 1) / 2.0) / (pos * neg)
        aucs.append(float(auc))
    return float(np.mean(aucs)) if aucs else 0.0


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

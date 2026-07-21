"""Inline quality checks for live-capture (camera) sequences.

Pure numpy functions over (T, 126) hand-landmark sequences — no FastAPI/DB
imports so the video pipeline can adopt the same checks later.

Layout of the 126-dim vector (see app/processing/utils.py):
  indices   0..62  = left hand  (21 landmarks x xyz)
  indices  63..125 = right hand (21 landmarks x xyz)

Metrics must be computed BEFORE per-frame hand normalization
(normalize_hands_vector_126): at that point coordinates are still
MediaPipe image-normalized (0..1) so jitter thresholds have a physical
meaning, and a missing hand is an all-zero block.

Two-tier thresholds (configured in app/config.py, env-overridable):
  WARN   (strict)  -> sample is saved, warning codes attached for review
  REJECT (lenient) -> sample is refused (HTTP 422 upstream)
"""

import json
import os
import threading
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np

# Append-only audit log of capture ATTEMPTS (including rejected ones).
# Deliberately a plain JSONL file, not a DB table and not samples.csv: a
# rejected attempt must never become addressable as training data. The
# manifest builder scans dataset/features/**.npz and never reads this file.
_QC_AUDIT_LOCK = threading.Lock()


def quality_audit_path() -> Path:
    return Path(os.getenv("QC_AUDIT_LOG",
                          str(Path("dataset") / "quality_attempts.jsonl")))

_LEFT = slice(0, 63)
_RIGHT = slice(63, 126)
_LEFT_WRIST = slice(0, 3)
_RIGHT_WRIST = slice(63, 66)

# Warning codes (sample saved, flagged)
WARN_MISSING_REQUIRED_HAND = "MISSING_REQUIRED_HAND"
WARN_HIGH_JITTER = "HIGH_JITTER"
WARN_LOW_HAND_PRESENCE = "LOW_HAND_PRESENCE"

# Reject codes (sample refused)
REJECT_HANDS_MISSING = "QC_HANDS_MISSING"
REJECT_EXTREME_JITTER = "QC_EXTREME_JITTER"
REJECT_TOO_FEW_VALID_FRAMES = "QC_TOO_FEW_VALID_FRAMES"


def parse_hands_required(value) -> Optional[int]:
    """Parse a hands_required CSV/API value. Only 1 and 2 are meaningful;
    anything else (missing column, "", "0", junk) means unknown -> None."""
    try:
        v = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return v if v in (1, 2) else None


@dataclass(frozen=True)
class QualityMetrics:
    left_hand_ratio: float
    right_hand_ratio: float
    both_hands_ratio: float
    any_hand_ratio: float
    completeness: float
    jitter_p95: float
    activity: float
    hands_required: int  # 0 = unknown

    def as_dict(self) -> dict:
        return {k: (round(v, 5) if isinstance(v, float) else v) for k, v in asdict(self).items()}


@dataclass(frozen=True)
class QualityVerdict:
    reject_code: Optional[str] = None
    warning_codes: List[str] = field(default_factory=list)

    @property
    def flags(self) -> str:
        codes = ([self.reject_code] if self.reject_code else []) + list(self.warning_codes)
        return ",".join(codes)


def hand_presence(seq: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Per-frame boolean presence for (left, right): any nonzero value in the block."""
    left = np.any(seq[:, _LEFT] != 0.0, axis=1)
    right = np.any(seq[:, _RIGHT] != 0.0, axis=1)
    return left, right


def _wrist_displacements(wrists: np.ndarray, present: np.ndarray) -> np.ndarray:
    """Euclidean displacement between consecutive frames, only for frame pairs
    where the hand is present in both frames (zero-padded absent frames would
    otherwise create fake teleport spikes)."""
    if wrists.shape[0] < 2:
        return np.empty(0, dtype=np.float32)
    pair_ok = present[:-1] & present[1:]
    if not np.any(pair_ok):
        return np.empty(0, dtype=np.float32)
    diffs = np.diff(wrists, axis=0)
    dists = np.linalg.norm(diffs, axis=1)
    return dists[pair_ok].astype(np.float32)


def wrist_jitter_p95(seq: np.ndarray) -> float:
    """P95 of per-frame wrist displacement, pooled across both hands.

    Only counts consecutive frame pairs where that hand is present in both
    frames. Returns 0.0 when fewer than 2 valid pairs exist.
    """
    left_present, right_present = hand_presence(seq)
    disps = np.concatenate([
        _wrist_displacements(seq[:, _LEFT_WRIST], left_present),
        _wrist_displacements(seq[:, _RIGHT_WRIST], right_present),
    ])
    if disps.size < 2:
        return 0.0
    return float(np.percentile(disps, 95))


def activity_mean_abs_diff(seq: np.ndarray) -> float:
    """Mean |diff| between consecutive frames across all features.

    Same formula as pipeline._window_activity_mean_abs_diff; stored as an
    informational metric only (thresholds gate on jitter_p95).
    """
    if not isinstance(seq, np.ndarray) or seq.ndim != 2 or seq.shape[0] < 2:
        return 0.0
    diffs = np.diff(seq.astype(np.float32, copy=False), axis=0)
    return float(np.mean(np.abs(diffs)))


def compute_quality_metrics(seq: np.ndarray, hands_required: int = 0) -> QualityMetrics:
    seq = np.asarray(seq, dtype=np.float32)
    if seq.ndim != 2 or seq.shape[0] == 0:
        return QualityMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, int(hands_required or 0))

    left, right = hand_presence(seq)
    t = float(seq.shape[0])
    left_ratio = float(np.count_nonzero(left)) / t
    right_ratio = float(np.count_nonzero(right)) / t
    both_ratio = float(np.count_nonzero(left & right)) / t
    any_ratio = float(np.count_nonzero(left | right)) / t

    hands_required = int(hands_required or 0)
    if hands_required == 2:
        completeness = both_ratio
    else:
        # 1 hand required, or unknown: any detected hand counts
        completeness = any_ratio

    return QualityMetrics(
        left_hand_ratio=left_ratio,
        right_hand_ratio=right_ratio,
        both_hands_ratio=both_ratio,
        any_hand_ratio=any_ratio,
        completeness=completeness,
        jitter_p95=wrist_jitter_p95(seq),
        activity=activity_mean_abs_diff(seq),
        hands_required=hands_required,
    )


def record_quality_attempt(record: dict) -> None:
    """Append one capture-attempt audit record. Never raises.

    Stores NO landmarks and NO video — only identity, label, verdict, metrics
    and the thresholds in force. That is enough to report pass/warn/reject
    rates per campaign without the rejected data entering the dataset.
    """
    try:
        record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
        path = quality_audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, default=str)
        with _QC_AUDIT_LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
    except Exception:
        # An audit-log failure must never block or fail a capture.
        pass


def qc_threshold_snapshot(cfg) -> dict:
    """The exact thresholds this verdict was produced under.

    Stored per sample. A quality_config_version string on its own is not
    enough: every qc_* value is env-overridable, so the same version label
    could mean different thresholds on two machines or after a redeploy. The
    snapshot makes each sample self-describing and lets a later QC ablation
    group samples by the rules actually applied to them.
    """
    return {
        "quality_config_version": str(getattr(cfg, "quality_config_version", "") or ""),
        "qc_enabled": bool(getattr(cfg, "qc_enabled", True)),
        "qc_min_valid_ratio": float(getattr(cfg, "qc_min_valid_ratio", 0.7)),
        "qc_reject_hands_ratio": float(getattr(cfg, "qc_reject_hands_ratio", 0.30)),
        "qc_warn_hands_ratio": float(getattr(cfg, "qc_warn_hands_ratio", 0.80)),
        "qc_reject_jitter": float(getattr(cfg, "qc_reject_jitter", 0.35)),
        "qc_warn_jitter": float(getattr(cfg, "qc_warn_jitter", 0.12)),
    }


def evaluate_quality(metrics: QualityMetrics, cfg) -> QualityVerdict:
    """Apply two-tier thresholds. REJECT checks run first (lenient bounds:
    only truly broken samples), then WARN checks (strict bounds)."""
    min_valid = float(getattr(cfg, "qc_min_valid_ratio", 0.7))
    reject_hands = float(getattr(cfg, "qc_reject_hands_ratio", 0.30))
    warn_hands = float(getattr(cfg, "qc_warn_hands_ratio", 0.80))
    reject_jitter = float(getattr(cfg, "qc_reject_jitter", 0.35))
    warn_jitter = float(getattr(cfg, "qc_warn_jitter", 0.12))

    # --- REJECT tier ---
    if metrics.any_hand_ratio < min_valid:
        return QualityVerdict(reject_code=REJECT_TOO_FEW_VALID_FRAMES)
    if metrics.hands_required in (1, 2) and metrics.completeness < reject_hands:
        return QualityVerdict(reject_code=REJECT_HANDS_MISSING)
    if metrics.jitter_p95 > reject_jitter:
        return QualityVerdict(reject_code=REJECT_EXTREME_JITTER)

    # --- WARN tier ---
    warnings: List[str] = []
    if metrics.hands_required in (1, 2) and metrics.completeness < warn_hands:
        warnings.append(WARN_MISSING_REQUIRED_HAND)
    elif metrics.any_hand_ratio < warn_hands:
        warnings.append(WARN_LOW_HAND_PRESENCE)
    if metrics.jitter_p95 > warn_jitter:
        warnings.append(WARN_HIGH_JITTER)
    return QualityVerdict(warning_codes=warnings)

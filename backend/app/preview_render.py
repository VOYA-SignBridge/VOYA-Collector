"""Render a session's hand-keypoint sequence (.npz) into a small skeleton MP4.

Phase 2 "Tier 3" fallback: weak/hot client devices play a server pre-rendered
video instead of running the 3D/2D viewer. The video is drawn from the SAME
126-dim keypoint data the viewers use (2 hands x 21 landmarks x 3 coords), so
it never exposes the contributor's face — unlike the raw upload video.

Design constraints (see docs/PHASE2_PLAN_3D_VIEWER.md):
    - Render ONCE per session, store next to the class's .npz files so the
      catalog_sync move/delete flows carry it along with the class folder.
    - CPU-only, small footprint: 480px canvas, OpenCV drawing, then an ffmpeg
      transcode to H.264 (browsers can't play OpenCV's mp4v). If ffmpeg is
      missing (bare dev env) the mp4v file is kept as a best-effort fallback.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Optional, Tuple

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

# MediaPipe Hands topology (21 landmarks per hand).
HAND_CONNECTIONS: Tuple[Tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 4),          # thumb
    (0, 5), (5, 6), (6, 7), (7, 8),          # index
    (5, 9), (9, 10), (10, 11), (11, 12),     # middle
    (9, 13), (13, 14), (14, 15), (15, 16),   # ring
    (13, 17), (17, 18), (18, 19), (19, 20),  # pinky
    (0, 17),                                  # palm edge
)

CANVAS_SIZE = 480
_MARGIN = 48
_BG_COLOR = (30, 22, 12)        # BGR — dark navy, matches the viewer theme
_LEFT_COLOR = (53, 107, 255)    # BGR of #FF6B35 (orange) — same as capture UI
_RIGHT_COLOR = (248, 189, 56)   # BGR of #38BDF8 (sky blue)
_DEFAULT_FPS = 15.0


def safe_session_part(session_id: str) -> str:
    """Session ids come from client metadata — sanitize before touching disk."""
    cleaned = re.sub(r"[^A-Za-z0-9._-]", "_", str(session_id or "").strip())
    return cleaned[:80] or "session"


def preview_filename(session_id: str) -> str:
    return f"preview_{safe_session_part(session_id)}.mp4"


def _split_hands(sequence: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """(T, 126) -> left (T, 21, 3), right (T, 21, 3)."""
    seq = np.asarray(sequence, dtype=np.float32)
    if seq.ndim != 2 or seq.shape[1] < 126:
        raise ValueError(f"unexpected sequence shape {seq.shape}, need (T, >=126)")
    t = seq.shape[0]
    left = seq[:, :63].reshape(t, 21, 3)
    right = seq[:, 63:126].reshape(t, 21, 3)
    return left, right


def _fit_transform(left: np.ndarray, right: np.ndarray) -> Callable[[float, float], Tuple[int, int]]:
    """Map data coords to canvas pixels using the whole-sequence bounding box.

    Fitting once over the sequence (not per frame) keeps the playback steady,
    and works for both raw [0,1] MediaPipe coords and normalized features.
    Missing landmarks are stored as all-zero triples and must not skew the box.
    """
    pts = np.concatenate([left.reshape(-1, 3), right.reshape(-1, 3)], axis=0)
    mask = np.any(pts != 0.0, axis=1)
    visible = pts[mask]
    if visible.shape[0] == 0:
        x_min, x_max, y_min, y_max = 0.0, 1.0, 0.0, 1.0
    else:
        x_min = float(visible[:, 0].min())
        x_max = float(visible[:, 0].max())
        y_min = float(visible[:, 1].min())
        y_max = float(visible[:, 1].max())

    span = max(x_max - x_min, y_max - y_min, 1e-6)
    scale = (CANVAS_SIZE - 2 * _MARGIN) / span
    # Center the box on the canvas.
    x_off = (CANVAS_SIZE - (x_max - x_min) * scale) / 2.0
    y_off = (CANVAS_SIZE - (y_max - y_min) * scale) / 2.0

    def to_px(x: float, y: float) -> Tuple[int, int]:
        px = int(round((x - x_min) * scale + x_off))
        py = int(round((y - y_min) * scale + y_off))
        return px, py

    return to_px


def _draw_hand(frame: np.ndarray, hand: np.ndarray, color, to_px) -> None:
    import cv2

    # A hand that was not detected in this frame is stored as all zeros — skip
    # it entirely instead of drawing a collapsed point at the origin.
    if not np.any(hand != 0.0):
        return
    pts = [to_px(float(p[0]), float(p[1])) for p in hand]
    for a, b in HAND_CONNECTIONS:
        if np.any(hand[a] != 0.0) and np.any(hand[b] != 0.0):
            cv2.line(frame, pts[a], pts[b], color, 2, cv2.LINE_AA)
    for i, p in enumerate(pts):
        if np.any(hand[i] != 0.0):
            cv2.circle(frame, p, 4, color, -1, cv2.LINE_AA)


def _transcode_h264(src: str, dst: str) -> bool:
    """OpenCV writes mp4v which browsers refuse; re-encode to H.264 if possible."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", src,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        dst,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        return proc.returncode == 0 and os.path.getsize(dst) > 0
    except Exception as exc:
        logger.warning("[PREVIEW] ffmpeg transcode failed: %s", exc)
        return False


def render_sequence_to_mp4(sequence: np.ndarray, out_path: Path, fps: float = _DEFAULT_FPS) -> Path:
    """Draw the skeleton video for one (T, 126) sequence, atomically, to out_path."""
    import cv2

    left, right = _split_hands(sequence)
    to_px = _fit_transform(left, right)
    fps = float(fps) if fps and float(fps) > 0 else _DEFAULT_FPS

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fd, raw_tmp = tempfile.mkstemp(prefix="preview_raw_", suffix=".mp4", dir=str(out_path.parent))
    os.close(fd)
    fd, final_tmp = tempfile.mkstemp(prefix="preview_enc_", suffix=".mp4", dir=str(out_path.parent))
    os.close(fd)

    try:
        writer = cv2.VideoWriter(
            raw_tmp, cv2.VideoWriter_fourcc(*"mp4v"), fps, (CANVAS_SIZE, CANVAS_SIZE)
        )
        if not writer.isOpened():
            raise RuntimeError("OpenCV VideoWriter failed to open (mp4v)")
        try:
            for t in range(left.shape[0]):
                frame = np.full((CANVAS_SIZE, CANVAS_SIZE, 3), _BG_COLOR, dtype=np.uint8)
                _draw_hand(frame, left[t], _LEFT_COLOR, to_px)
                _draw_hand(frame, right[t], _RIGHT_COLOR, to_px)
                writer.write(frame)
        finally:
            writer.release()

        if _transcode_h264(raw_tmp, final_tmp):
            os.replace(final_tmp, out_path)
        else:
            logger.warning("[PREVIEW] serving mp4v fallback (no ffmpeg): %s", out_path)
            os.replace(raw_tmp, out_path)
        return out_path
    finally:
        for tmp in (raw_tmp, final_tmp):
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except OSError:
                    pass


# ---------------------------------------------------------------------------
# Session-level helpers (shared by the API router and the Celery task)
# ---------------------------------------------------------------------------

def find_class_meta(class_uid: str):
    from app.dataset_manager import list_classes

    for meta in list_classes():
        if meta.class_uid == class_uid:
            return meta
    return None


def _is_active_row(row: dict) -> bool:
    if (row.get("deleted_at") or "").strip():
        return False
    status = (row.get("status") or "").strip().lower()
    return status not in ("deleted", "trash", "trashed")


def list_session_rows(class_uid: str) -> dict:
    """Group this class's active sample rows by session_id.

    Rows without a session_id (old data) become single-sample pseudo-sessions
    keyed by their sample_uid, so nothing recorded is invisible in the UI.
    """
    from app.dataset_samples import list_samples

    groups: dict = {}
    for row in list_samples():
        if row.get("class_uid") != class_uid or not _is_active_row(row):
            continue
        key = (row.get("session_id") or "").strip() or f"single-{row.get('sample_uid', '')}"
        groups.setdefault(key, []).append(row)
    return groups


def pick_original_sample(rows: list) -> Optional[dict]:
    """The playable sample of a session = the non-augmented recording."""
    if not rows:
        return None

    def aug(row: dict) -> int:
        try:
            return int(row.get("augment_id") or 0)
        except (TypeError, ValueError):
            return 0

    return min(rows, key=aug)


def resolve_sample_npz(row: dict) -> Optional[Path]:
    """file_path in samples.csv is relative to DATASET_ROOT; fall back to Drive."""
    file_path = (row.get("file_path") or "").strip()
    if file_path:
        p = Path(file_path)
        if not p.is_absolute():
            p = Path(settings.dataset_root) / p
        if p.exists():
            return p

    try:
        from app.storage.gdrive_client import materialize_sample_artifacts

        cache_dir = Path(settings.dataset_root) / "cache" / "sample_downloads"
        resolved = materialize_sample_artifacts([row], cache_dir)
        if resolved:
            return Path(resolved[0])
    except Exception as exc:
        logger.warning("[PREVIEW] Drive materialize failed for %s: %s", row.get("sample_uid"), exc)
    return None


def sample_fps(row: dict) -> float:
    for key in ("fps_processed", "fps_original"):
        try:
            value = float(row.get(key) or 0)
            if value > 0:
                return value
        except (TypeError, ValueError):
            continue
    return _DEFAULT_FPS


def render_preview_for_session(class_uid: str, session_id: str) -> Path:
    """Full pipeline: locate the session's original .npz and render its preview.

    Called by the Celery task (async path) and inline when no broker is
    available (dev fallback). Idempotent — re-rendering overwrites atomically.
    """
    meta = find_class_meta(class_uid)
    if meta is None:
        raise ValueError(f"class not found: {class_uid}")

    rows = list_session_rows(class_uid).get(session_id)
    if not rows:
        raise ValueError(f"session not found: {class_uid}/{session_id}")

    row = pick_original_sample(rows)
    npz_path = resolve_sample_npz(row) if row else None
    if npz_path is None:
        raise FileNotFoundError(f"npz missing for session {class_uid}/{session_id}")

    with np.load(npz_path, allow_pickle=True) as data:
        sequence = np.asarray(data["sequence"], dtype=np.float32)

    out_path = Path(meta.hierarchy_path()) / preview_filename(session_id)
    render_sequence_to_mp4(sequence, out_path, fps=sample_fps(row))
    logger.info("[PREVIEW] rendered %s (%s frames)", out_path, sequence.shape[0])
    return out_path

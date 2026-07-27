"""Real MediaPipe feature-extraction (video -> .npz sequences).

Runs the ACTUAL pipeline (cv2 decode + MediaPipe Hands + windowing) — only the
sinks (class registration, npz/DB writes) are mocked, so nothing touches the real
dataset. Two cases:

  - a synthetic no-hand clip we generate here (ALWAYS runs): proves the machinery
    decodes + runs MediaPipe + windows without crashing, and correctly keeps 0
    samples when there are no hands.
  - a REAL hand-sign clip (opt-in): set VOYA_TEST_VIDEO=<path> to verify valid
    (seq_len, 126) sequences are extracted from genuine footage.

Requires mediapipe + opencv (present in the trainer/host venv).
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

pytest.importorskip("cv2")
pytest.importorskip("mediapipe")
import cv2  # noqa: E402

from app.processing.pipeline import process_video_job  # noqa: E402


def _fake_class():
    return SimpleNamespace(
        class_uid="SOTTEST_vidcls", slug="test-slug", label_original="test",
        language="vn", dialect="common", class_idx=1, folder_name=lambda: "class_test",
        hierarchy_path=lambda: "/tmp/class_test",  # used only in a summary log line
    )


def _make_noise_video(path, frames=40, w=320, h=240, fps=30):
    vw = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), float(fps), (w, h))
    rng = np.random.default_rng(0)
    for _ in range(frames):
        vw.write((rng.random((h, w, 3)) * 255).astype("uint8"))
    vw.release()


def _run(video_path):
    """Run extraction with all write-sinks mocked; return (result, save_mock)."""
    with patch("app.processing.pipeline.get_or_register_class", return_value=_fake_class()), \
         patch("app.processing.pipeline.count_samples_for_class", return_value=0), \
         patch("app.processing.pipeline.save_sequence_npz", return_value="/tmp/x.npz") as save:
        res = process_video_job(
            str(video_path), user="tester", label="test", session_id="s1",
            dialect="common", language="vn", user_id="uid-123",
        )
    return res, save


def test_no_hand_video_extracts_gracefully_with_zero_samples(tmp_path):
    vid = tmp_path / "noise.mp4"
    _make_noise_video(vid)
    assert vid.exists() and vid.stat().st_size > 0

    res, save = _run(vid)
    # Pipeline ran end-to-end (cv2 + MediaPipe) without crashing…
    assert isinstance(res, dict)
    # …and produced NO samples (no hands to detect) rather than garbage.
    assert res.get("kept", 0) == 0
    assert save.call_count == 0


@pytest.mark.skipif(
    not os.getenv("VOYA_TEST_VIDEO"),
    reason="set VOYA_TEST_VIDEO=<path to a real hand-sign clip> to run the real extraction",
)
def test_real_hand_video_extracts_seqlen_x_126_sequences():
    video = os.getenv("VOYA_TEST_VIDEO")
    assert os.path.exists(video), f"VOYA_TEST_VIDEO not found: {video}"

    res, save = _run(video)
    assert res.get("kept", 0) > 0, f"no samples extracted from {video}: {res}"
    assert save.call_count > 0
    # each saved sequence is (seq_len, feature_dim=126)
    seq = save.call_args_list[0].args[1]
    assert hasattr(seq, "shape") and seq.shape[1] == 126

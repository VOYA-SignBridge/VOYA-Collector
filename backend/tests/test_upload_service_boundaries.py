"""Boundary and behavior tests for upload-domain services."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import numpy as np

from app.modules.dataset import (
    camera_capture_service,
    raw_video_upload_service,
    video_processing_service,
)


def test_camera_frames_convert_mediapipe_hands_to_126_features() -> None:
    point = {"x": 1.0, "y": 2.0, "z": 3.0}
    frames = [{"landmarks": {"left_hand": [point], "right_hand": [point]}}]

    sequence = camera_capture_service.frames_to_sequence(frames, 126)

    assert sequence.shape == (1, 126)
    assert sequence.dtype == np.float32
    assert sequence[0, :3].tolist() == [1.0, 2.0, 3.0]
    assert sequence[0, 63:66].tolist() == [1.0, 2.0, 3.0]


def test_camera_capture_persists_normalized_and_raw_sequences(monkeypatch) -> None:
    class_meta = SimpleNamespace(
        class_uid="class-1",
        hands_required=1,
        recognition_profile="hoa-de",
        vocabulary_scope="profile_specific",
        vocabulary_group="daily",
        semantic_label="hello",
    )
    saved = {}
    audit = []

    monkeypatch.setattr(camera_capture_service, "get_or_register_class", lambda **_kwargs: class_meta)
    monkeypatch.setattr(camera_capture_service, "_resolve_signer", lambda _user: "signer-1")
    monkeypatch.setattr(camera_capture_service, "record_quality_attempt", audit.append)

    def save_sequence(_class_meta, sequence, **kwargs):
        saved.update({"sequence": sequence, **kwargs})
        return "/dataset/features/sample.npz"

    monkeypatch.setattr(camera_capture_service, "save_sequence_npz", save_sequence)
    frame = [0.1] * 126
    result = camera_capture_service.capture_camera_sample(
        payload={"frames": [{"landmarks": frame} for _ in range(60)]},
        current_user={"id": "user-1"},
        user="Collector",
        label="Xin chào",
        language="vn",
        dialect="hoa-de",
        session_id="session-1",
    )

    assert result["success"] is True
    assert result["paths"] == ["/dataset/features/sample.npz"]
    assert saved["sequence"].shape == (60, 126)
    assert saved["raw_sequence"].shape == (60, 126)
    assert saved["meta"]["signer_id"] == "signer-1"
    assert saved["meta"]["preprocess_contract_version"] == "v2"
    assert audit[-1]["status"] == "accepted"


def test_raw_video_upload_returns_existing_idempotent_record() -> None:
    result = asyncio.run(
        raw_video_upload_service.store_raw_video(
            file=SimpleNamespace(file=None, filename="ignored.mp4", content_type="video/mp4"),
            user="collector",
            label="hello",
            language="vn",
            dialect="common",
            session_id="new-session",
            upload_uid="abcdef12",
            current_user={"id": "user-1"},
            save_upload=lambda *_args, **_kwargs: (_ for _ in ()).throw(
                AssertionError("duplicate upload must not write")
            ),
            normalize_fields=lambda *_args: (_ for _ in ()).throw(
                AssertionError("duplicate upload must return before validation")
            ),
            find_existing=lambda _uid: {
                "session_id": "original-session",
                "storage_url": "gdrive://existing",
            },
        )
    )

    assert result["duplicate"] is True
    assert result["session_id"] == "original-session"
    assert result["storage_url"] == "gdrive://existing"


def test_video_processing_reports_invalid_missing_and_queued_items() -> None:
    rows = {
        "abcdef12": None,
        "12345678": {"upload_uid": "12345678", "local_path": "/raw/video.mp4"},
    }

    result = asyncio.run(
        video_processing_service.enqueue_uploaded_videos(
            {"upload_uids": ["bad", "abcdef12", "12345678"]},
            triggered_by="user-1",
            find_one=lambda uid: rows[uid],
            enqueue=lambda row, _user: {
                "upload_uid": row["upload_uid"],
                "job_id": "job-1",
                "status": "queued",
            },
        )
    )

    assert result == {
        "success": True,
        "queued": 1,
        "total": 3,
        "results": [
            {"upload_uid": "bad", "status": "invalid_uid"},
            {"upload_uid": "abcdef12", "status": "not_found"},
            {"upload_uid": "12345678", "job_id": "job-1", "status": "queued"},
        ],
    }

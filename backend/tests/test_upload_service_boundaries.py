"""Boundary and behavior tests for upload-domain services."""

from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from app.modules.dataset import (
    camera_capture_service,
    raw_video_upload_service,
    video_processing_service,
)
from app.routers import upload


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
        tenant_id="tenant-a",
    )
    saved = {}
    audit = []
    emitted = []
    settled = []

    monkeypatch.setattr(camera_capture_service, "get_or_register_class", lambda **_kwargs: class_meta)
    monkeypatch.setattr(camera_capture_service, "_resolve_signer", lambda _user: "signer-1")
    monkeypatch.setattr(camera_capture_service, "record_quality_attempt", audit.append)

    def save_sequence(_class_meta, sequence, **kwargs):
        saved.update({"sequence": sequence, **kwargs})
        return "/dataset/features/sample.npz"

    monkeypatch.setattr(camera_capture_service, "save_sequence_npz", save_sequence)
    reservation = object()
    monkeypatch.setattr(
        camera_capture_service, "guard_storage", lambda *_args, **_kwargs: reservation
    )
    monkeypatch.setattr(
        camera_capture_service.storage_quota,
        "settle",
        lambda *args, **kwargs: settled.append((args, kwargs)),
    )
    monkeypatch.setattr(camera_capture_service.storage_quota, "release", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        camera_capture_service,
        "emit",
        lambda *args, **kwargs: emitted.append((args, kwargs)),
    )
    point = {"x": 0.1, "y": 0.2, "z": 0.3}
    frame = {
        "left_hand": [point] * 21,
        "right_hand": [point] * 21,
        "left_hand_world": [point] * 21,
        "right_hand_world": [point] * 21,
    }
    result = camera_capture_service.capture_camera_sample(
        payload={"frames": [{"landmarks": frame} for _ in range(60)]},
        current_user={"id": "user-1"},
        user="Collector",
        label="Xin chào",
        language="vn",
        dialect="hoa-de",
        session_id="session-1",
        visibility="tenant",
    )

    assert result["success"] is True
    assert result["paths"] == ["/dataset/features/sample.npz"]
    assert saved["sequence"].shape == (60, 126)
    assert saved["raw_sequence"].shape == (60, 126)
    assert saved["world_sequence"].shape == (60, 126)
    assert saved["meta"]["signer_id"] == "signer-1"
    assert saved["meta"]["visibility"] == "tenant"
    assert saved["meta"]["preprocess_contract_version"] == "v2"
    assert audit[-1]["status"] == "accepted"
    assert settled and settled[0][1]["absorb_overflow"] is True
    assert emitted[0][0][0:2] == ("tenant-a", "sample.created")


def test_camera_router_delegates_persistence_to_service() -> None:
    source = inspect.getsource(upload.upload_camera)

    assert "camera_capture_service.capture_camera_sample" in source
    for forbidden in (
        "save_sequence_npz",
        "guard_storage",
        "storage_quota.settle",
        "record_quality_attempt",
        "emit(",
    ):
        assert forbidden not in source


def test_raw_video_upload_returns_existing_idempotent_record(monkeypatch) -> None:
    monkeypatch.setattr(
        raw_video_upload_service,
        "find_raw_upload",
        lambda _uid: {
            "session_id": "original-session",
            "storage_url": "gdrive://existing",
        },
    )
    result = asyncio.run(
        raw_video_upload_service.store_raw_video(
            file=SimpleNamespace(file=None, filename="ignored.mp4", content_type="video/mp4"),
            user="collector",
            label="hello",
            language="vn",
            dialect="common",
            class_uid=None,
            visibility="private",
            session_id="new-session",
            upload_uid="abcdef12",
            tenant_id="tenant-a",
            current_user={"id": "user-1"},
        )
    )

    assert result["duplicate"] is True
    assert result["session_id"] == "original-session"
    assert result["storage_url"] == "gdrive://existing"


def test_video_processing_reports_invalid_missing_and_queued_items() -> None:
    rows = {
        "abcdef12": None,
        "12345678": {
            "upload_uid": "12345678",
            "local_path": "/raw/video.mp4",
            "tenant_id": "tenant-a",
        },
    }

    result = asyncio.run(
        video_processing_service.enqueue_uploaded_videos(
            {"upload_uids": ["bad", "abcdef12", "12345678"]},
            triggered_by="user-1",
            tenant_id="tenant-a",
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


def test_video_processing_hides_rows_from_other_tenants() -> None:
    result = asyncio.run(
        video_processing_service.enqueue_uploaded_videos(
            {"upload_uid": "12345678"},
            triggered_by="user-1",
            tenant_id="tenant-a",
            find_one=lambda _uid: {
                "upload_uid": "12345678",
                "local_path": "/raw/video.mp4",
                "tenant_id": "tenant-b",
            },
            enqueue=lambda *_args: (_ for _ in ()).throw(
                AssertionError("cross-tenant row must not be enqueued")
            ),
        )
    )

    assert result["results"] == [
        {"upload_uid": "12345678", "status": "not_found"}
    ]


def test_video_reprocessing_preserves_original_upload_owner(monkeypatch) -> None:
    monkeypatch.setattr(
        video_processing_service,
        "raw_upload_owner",
        lambda _uid: "original-owner",
    )
    task = SimpleNamespace(id="job-1")
    with patch("app.tasks.enqueue_process_video.delay", return_value=task) as delay:
        result = video_processing_service.enqueue_video_processing(
            {
                "upload_uid": "12345678",
                "local_path": "/raw/video.mp4",
                "user_id": "display-name",
            },
            "person-clicking-reprocess",
        )

    assert result["status"] == "queued"
    assert delay.call_args.kwargs["user_id"] == "original-owner"


def test_video_process_router_delegates_to_service() -> None:
    source = inspect.getsource(upload.process_uploaded_videos)

    assert "video_processing_service.enqueue_uploaded_videos" in source
    for forbidden in (
        "find_raw_upload",
        "find_raw_uploads_by_class",
        "enqueue_process_video",
        "asyncio.to_thread",
    ):
        assert forbidden not in source

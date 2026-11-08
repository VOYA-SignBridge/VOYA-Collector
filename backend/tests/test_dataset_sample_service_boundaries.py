"""Boundary and behavior tests for dataset sample application workflows."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import pytest

from app.modules.dataset import sample_service


def test_sample_access_allows_owner_and_rejects_other_users() -> None:
    sample_service.ensure_sample_access(
        "sample-1",
        {"id": "owner-1", "is_admin": False},
        owner_lookup=lambda _sample_id: "owner-1",
    )

    with pytest.raises(sample_service.SampleAccessDeniedError):
        sample_service.ensure_sample_access(
            "sample-1",
            {"id": "other-user", "is_admin": False},
            owner_lookup=lambda _sample_id: "owner-1",
        )


def test_sample_access_admin_bypasses_owner_lookup() -> None:
    sample_service.ensure_sample_access(
        "sample-1",
        {"id": "admin-1", "is_admin": True},
        owner_lookup=lambda _sample_id: (_ for _ in ()).throw(
            AssertionError("admin access must not query ownership")
        ),
    )


def test_resolve_sample_artifact_materializes_missing_local_file(tmp_path: Path) -> None:
    materialized = tmp_path / "cache" / "sample.npz"

    result = sample_service.resolve_sample_artifact(
        "sample-1",
        sample_loader=lambda: [{"sample_uid": "sample-1", "file_path": "missing.npz"}],
        materializer=lambda rows, cache: [materialized],
        dataset_root=tmp_path,
    )

    assert result == materialized


def test_save_uploaded_npz_validates_and_delegates_to_canonical_writer() -> None:
    upload = BytesIO()
    np.savez_compressed(upload, sequence=np.ones((4, 126), dtype=np.float64))
    upload.seek(0)
    saved = {}

    def saver(class_meta, sequence, **kwargs):
        saved.update({"class_meta": class_meta, "sequence": sequence, **kwargs})
        return "/dataset/sample.npz"

    result = sample_service.save_uploaded_npz(
        class_idx=7,
        filename="sample.npz",
        file_object=upload,
        current_user={"id": "user-1", "username": "collector"},
        session_id="session-1",
        label_loader=lambda: [{
            "class_idx": "7",
            "class_uid": "class-7",
            "slug": "hello",
            "label_original": "Hello",
            "language": "en",
            "dialect": "common",
            "is_common_global": "0",
            "is_common_language": "1",
        }],
        saver=saver,
    )

    assert result == "/dataset/sample.npz"
    assert saved["sequence"].dtype == np.float32
    assert saved["meta"]["auth_user_id"] == "user-1"
    assert saved["meta"]["frames"] == 4
    assert saved["source_type"] == "video"

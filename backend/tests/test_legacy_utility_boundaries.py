"""Contracts for utilities relocated out of the application package root."""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException


def test_relocated_utility_facades_are_removed() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"

    assert not (app_root / "api_validation.py").exists()
    assert not (app_root / "logging_config.py").exists()
    assert not (app_root / "mem_utils.py").exists()


def test_upload_limit_removes_partial_file(tmp_path: Path) -> None:
    from app.core.http_validation import save_upload_with_limit

    destination = tmp_path / "oversized.bin"
    with pytest.raises(HTTPException) as error:
        save_upload_with_limit(BytesIO(b"too large"), destination, max_bytes=3)

    assert error.value.status_code == 413
    assert not destination.exists()


def test_obsolete_processing_storage_utils_is_removed() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    assert not (app_root / "processing" / "storage_utils.py").exists()


def test_retired_unreferenced_modules_are_removed() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"

    assert not (app_root / "rate_limit.py").exists()
    assert not (app_root / "processing" / "feature_writer.py").exists()
    assert not (app_root / "storage" / "experiment_tracking_db.py").exists()

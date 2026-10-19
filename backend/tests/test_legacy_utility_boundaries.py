"""Contracts for utilities relocated out of the application package root."""

from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException


def test_http_validation_facade_reexports_core_implementation() -> None:
    from app import api_validation
    from app.core import http_validation

    assert api_validation.validate_label is http_validation.validate_label
    assert api_validation.validate_language is http_validation.validate_language
    assert api_validation.validate_dialect is http_validation.validate_dialect
    assert api_validation.validate_job_id is http_validation.validate_job_id
    assert api_validation.save_upload_with_limit is http_validation.save_upload_with_limit


def test_logging_facade_reexports_bootstrap_implementation() -> None:
    from app import logging_config
    from app.bootstrap import logging as bootstrap_logging

    assert logging_config.configure_logging is bootstrap_logging.configure_logging


def test_memory_facade_reexports_celery_implementation() -> None:
    from app import mem_utils
    from app.infrastructure.celery import memory

    assert mem_utils.get_rss_mb is memory.get_rss_mb
    assert mem_utils.malloc_trim is memory.malloc_trim
    assert mem_utils.release_memory is memory.release_memory


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

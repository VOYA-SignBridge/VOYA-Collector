"""Reusable validation helpers at the HTTP boundary."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple

from fastapi import HTTPException

_LABEL_MAX_LEN = int(os.getenv("MAX_LABEL_LEN", "200"))
_LANG_RE = re.compile(os.getenv("LANGUAGE_REGEX", r"^[a-z0-9-]{1,16}$"))
_DIALECT_RE = re.compile(os.getenv("DIALECT_REGEX", r"^[a-z0-9-]{0,32}$"))


def validate_label(label: Optional[str]) -> str:
    if label is None:
        raise HTTPException(status_code=422, detail="label is required")
    value = str(label).strip()
    if not value:
        raise HTTPException(status_code=422, detail="label must be non-empty")
    if len(value) > _LABEL_MAX_LEN:
        raise HTTPException(status_code=422, detail=f"label too long (max {_LABEL_MAX_LEN})")
    if any(ord(character) < 32 for character in value):
        raise HTTPException(status_code=422, detail="label contains invalid characters")
    return value


def validate_language(language: Optional[str]) -> str:
    value = (language or "").strip().lower()
    if not value:
        return "vn"
    if not _LANG_RE.match(value):
        raise HTTPException(status_code=422, detail="invalid language")
    return value


def validate_dialect(dialect: Optional[str]) -> str:
    value = (dialect or "").strip().lower()
    if value in ("", "none"):
        return ""
    if not _DIALECT_RE.match(value) or "/" in value or "\\" in value or ".." in value:
        raise HTTPException(status_code=422, detail="invalid dialect")
    return value


def validate_job_id(job_id: str) -> str:
    value = (job_id or "").strip()
    if not value:
        raise HTTPException(status_code=422, detail="job_id required")
    try:
        uuid.UUID(value)
        return value
    except Exception:
        pass
    if not re.match(r"^[A-Za-z0-9_.:-]{8,128}$", value):
        raise HTTPException(status_code=400, detail="invalid job_id")
    return value


def save_upload_with_limit(src_file, dst_path: Path, *, max_bytes: int) -> Tuple[int, str]:
    """Stream an upload to disk, deleting partial output when it exceeds the limit."""
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with dst_path.open("wb") as output:
            while True:
                chunk = src_file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if max_bytes > 0 and written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"upload too large (max {max_bytes} bytes)",
                    )
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    except HTTPException:
        try:
            if dst_path.exists():
                dst_path.unlink()
        except Exception:
            pass
        raise
    return written, str(dst_path)

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
    s = str(label).strip()
    if not s:
        raise HTTPException(status_code=422, detail="label must be non-empty")
    if len(s) > _LABEL_MAX_LEN:
        raise HTTPException(status_code=422, detail=f"label too long (max {_LABEL_MAX_LEN})")
    # reject obvious control characters
    if any(ord(ch) < 32 for ch in s):
        raise HTTPException(status_code=422, detail="label contains invalid characters")
    return s


def validate_language(language: Optional[str]) -> str:
    s = (language or "").strip().lower()
    if not s:
        return "vn"
    if not _LANG_RE.match(s):
        raise HTTPException(status_code=422, detail="invalid language")
    return s


def validate_dialect(dialect: Optional[str]) -> str:
    s = (dialect or "").strip().lower()
    # allow empty dialect (treated as dialect-specific root)
    if s in ("", "none"):
        return ""
    if not _DIALECT_RE.match(s):
        raise HTTPException(status_code=422, detail="invalid dialect")
    # forbid path-ish values defensively
    if "/" in s or "\\" in s or ".." in s:
        raise HTTPException(status_code=422, detail="invalid dialect")
    return s


def validate_job_id(job_id: str) -> str:
    s = (job_id or "").strip()
    if not s:
        raise HTTPException(status_code=422, detail="job_id required")
    # Celery commonly uses UUID; accept UUID, or a conservative token format.
    try:
        uuid.UUID(s)
        return s
    except Exception:
        pass
    if not re.match(r"^[A-Za-z0-9_.:-]{8,128}$", s):
        raise HTTPException(status_code=400, detail="invalid job_id")
    return s


def save_upload_with_limit(src_file, dst_path: Path, *, max_bytes: int) -> Tuple[int, str]:
    """Stream UploadFile.file to disk with a hard size limit.

    Returns (bytes_written, dst_path_str). On limit exceeded, deletes partial file and raises 413.
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    chunk_size = 1024 * 1024  # 1 MiB
    try:
        with open(dst_path, "wb") as f:
            while True:
                chunk = src_file.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if max_bytes > 0 and written > max_bytes:
                    raise HTTPException(status_code=413, detail=f"upload too large (max {max_bytes} bytes)")
                f.write(chunk)
            f.flush()
            os.fsync(f.fileno())
    except HTTPException:
        # cleanup partial file
        try:
            if dst_path.exists():
                dst_path.unlink()
        except Exception:
            pass
        raise
    return written, str(dst_path)

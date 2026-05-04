from __future__ import annotations

import hashlib
import io
import json
import logging
import mimetypes
import os
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.config import settings
from app.dataset_manager import ClassMetadata
from app.processing.utils import atomic_write_json
from app.storage.minio_client import _get_minio_client, upload_file
from app.logging_utils import get_logger as get_structured_logger, OperationType, OperationStatus

logger = logging.getLogger(__name__)
slog = get_structured_logger("storage.operations")

_CLOUDINARY_HOST = "res.cloudinary.com"


class CloudinaryUploadError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        upload_url: str,
        public_id: str,
        resource_type: str,
        status_code: Optional[int] = None,
        response_body: str = "",
        response_json: Any = None,
    ) -> None:
        super().__init__(message)
        self.upload_url = upload_url
        self.public_id = public_id
        self.resource_type = resource_type
        self.status_code = status_code
        self.response_body = response_body
        self.response_json = response_json

    def to_debug_payload(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "upload_url": self.upload_url,
            "public_id": self.public_id,
            "resource_type": self.resource_type,
            "message": str(self),
        }
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        if self.response_body:
            payload["response_body"] = self.response_body
        if self.response_json is not None:
            payload["response_json"] = self.response_json
        return payload


def _safe_segment(value: str, *, default: str = "item", max_length: int = 80) -> str:
    text = (value or "").strip().lower().replace("\\", "/")
    text = text.replace("đ", "d").replace("Đ", "D")
    text = text.replace("/", "-")
    text = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "-" for ch in text)
    while "--" in text:
        text = text.replace("--", "-")
    text = text.strip("-_.")
    if not text:
        text = default
    if len(text) > max_length:
        text = text[:max_length].rstrip("-_.") or default
    return text


def _strip_extension(filename: str) -> str:
    name = Path(filename or "").name
    stem = Path(name).stem or "upload"
    return _safe_segment(stem, default="upload")


def _extension_or_default(filename: str, default: str = ".mp4") -> str:
    suffix = Path(filename or "").suffix.lower()
    return suffix if suffix else default


def _storage_scope(class_meta: ClassMetadata) -> str:
    return f"{class_meta.language}/{class_meta.dialect}/{class_meta.folder_name()}"


def build_raw_video_minio_key(
    class_meta: ClassMetadata,
    session_id: str,
    original_filename: str,
    upload_uid: str,
) -> str:
    safe_stem = _strip_extension(original_filename)
    ext = _extension_or_default(original_filename, default=".mp4")
    return f"raw_videos/{_storage_scope(class_meta)}/{_safe_segment(session_id, default='session')}/{safe_stem}_{upload_uid}{ext}"


def build_raw_video_cloudinary_public_id(
    class_meta: ClassMetadata,
    session_id: str,
    original_filename: str,
    upload_uid: str,
) -> str:
    safe_stem = _strip_extension(original_filename)
    return f"voya/raw/{_storage_scope(class_meta)}/{_safe_segment(session_id, default='session')}/{safe_stem}_{upload_uid}"


def build_sample_npz_key(
    class_meta: ClassMetadata,
    sample_uid: str,
    augment_id: int,
) -> str:
    return (
        f"features/{_storage_scope(class_meta)}/"
        f"aug_{int(augment_id):03d}/sample_{_safe_segment(sample_uid, default='sample')}.npz"
    )


def _dataset_local_path(relative_key: str) -> Path:
    return Path(settings.dataset_root) / relative_key


def _atomic_write_bytes(path: Path, content: bytes) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="voya_tmp_", suffix=path.suffix or ".bin", dir=str(path.parent))
    os.close(fd)
    try:
        with open(tmp_path, "wb") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
        return path
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def _cloudinary_ready() -> bool:
    if not bool(getattr(settings, "cloudinary_enabled", False)):
        return False
    if not bool(getattr(settings, "enable_cloudinary_mirror", True)):
        return False
    if not getattr(settings, "cloudinary_cloud_name", ""):
        return False
    if getattr(settings, "cloudinary_upload_preset", ""):
        return True
    return bool(getattr(settings, "cloudinary_api_key", "") and getattr(settings, "cloudinary_api_secret", ""))


def _coerce_bytes(file_data: Any) -> bytes:
    if isinstance(file_data, bytes):
        return file_data
    if isinstance(file_data, bytearray):
        return bytes(file_data)
    if isinstance(file_data, io.BytesIO):
        pos = file_data.tell()
        try:
            file_data.seek(0)
            return file_data.read()
        finally:
            try:
                file_data.seek(pos)
            except Exception:
                pass
    if isinstance(file_data, str):
        with open(file_data, "rb") as f:
            return f.read()
    raise TypeError(f"Unsupported file_data type: {type(file_data)!r}")


def _guess_mime(filename: str, fallback: str = "application/octet-stream") -> str:
    mime, _ = mimetypes.guess_type(filename or "")
    return mime or fallback


def _multipart_encode(
    fields: Dict[str, str],
    file_field_name: str,
    filename: str,
    file_bytes: bytes,
    content_type: str,
) -> tuple[bytes, str]:
    boundary = f"----voya{uuid.uuid4().hex}"
    buffer = io.BytesIO()

    def write_line(text: str = ""):
        buffer.write(text.encode("utf-8"))
        buffer.write(b"\r\n")

    for key, value in fields.items():
        write_line(f"--{boundary}")
        write_line(f'Content-Disposition: form-data; name="{key}"')
        write_line()
        write_line(str(value))

    write_line(f"--{boundary}")
    write_line(f'Content-Disposition: form-data; name="{file_field_name}"; filename="{filename}"')
    write_line(f"Content-Type: {content_type}")
    write_line()
    buffer.write(file_bytes)
    buffer.write(b"\r\n")
    write_line(f"--{boundary}--")
    body = buffer.getvalue()
    return body, f"multipart/form-data; boundary={boundary}"


def _cloudinary_signature(params: Dict[str, str]) -> str:
    secret = getattr(settings, "cloudinary_api_secret", "") or ""
    signing_parts = [
        f"{key}={value}"
        for key, value in sorted(params.items())
        if value not in (None, "") and key not in {"file", "api_key", "signature"}
    ]
    payload = "&".join(signing_parts)
    return hashlib.sha1((payload + secret).encode("utf-8")).hexdigest()


def _cloudinary_response_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "asset_id",
        "public_id",
        "resource_type",
        "type",
        "secure_url",
        "url",
        "duration",
        "format",
        "bytes",
        "width",
        "height",
        "version",
        "version_id",
        "created_at",
        "display_name",
        "asset_folder",
        "etag",
    )
    return {key: result[key] for key in keys if key in result and result[key] not in (None, "")}


def _cloudinary_upload_bytes(
    file_bytes: bytes,
    *,
    original_filename: str,
    public_id: str,
    resource_type: str = "video",
) -> Optional[Dict[str, Any]]:
    if not _cloudinary_ready():
        logger.info("[CLOUDINARY] not configured, skipping upload")
        return None

    content_type = _guess_mime(original_filename, fallback="application/octet-stream")
    fields: Dict[str, str] = {
        "public_id": public_id,
        "overwrite": "false",
    }

    if getattr(settings, "cloudinary_upload_preset", ""):
        fields["upload_preset"] = str(settings.cloudinary_upload_preset)
    else:
        fields["timestamp"] = str(int(time.time()))
        fields["api_key"] = str(settings.cloudinary_api_key)
        fields["signature"] = _cloudinary_signature({k: v for k, v in fields.items() if k not in {"signature", "api_key"}})

    upload_url = f"https://api.cloudinary.com/v1_1/{settings.cloudinary_cloud_name}/{resource_type}/upload"
    body, content_type_header = _multipart_encode(fields, "file", Path(original_filename).name or "upload.bin", file_bytes, content_type)

    request = urllib.request.Request(
        upload_url,
        data=body,
        headers={
            "Content-Type": content_type_header,
            "Content-Length": str(len(body)),
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=int(getattr(settings, "cloudinary_timeout_seconds", 60))) as response:
            payload = response.read().decode("utf-8")
        result = json.loads(payload)
        if not isinstance(result, dict):
            raise ValueError("Unexpected Cloudinary response")
        return result
    except urllib.error.HTTPError as exc:
        try:
            error_body = exc.read().decode("utf-8")
        except Exception:
            error_body = str(exc)
        try:
            error_json = json.loads(error_body)
        except Exception:
            error_json = None
        raise CloudinaryUploadError(
            "Cloudinary upload failed",
            upload_url=upload_url,
            public_id=public_id,
            resource_type=resource_type,
            status_code=getattr(exc, "code", None),
            response_body=error_body,
            response_json=error_json,
        ) from exc
    except Exception as exc:
        raise CloudinaryUploadError(
            f"Cloudinary upload failed: {exc}",
            upload_url=upload_url,
            public_id=public_id,
            resource_type=resource_type,
            response_body=str(exc),
        ) from exc


def delete_cloudinary_asset(public_id: str, *, resource_type: str = "video") -> bool:
    if not _cloudinary_ready():
        logger.info("[CLOUDINARY] not configured, skipping delete for public_id=%s", public_id)
        return True

    cloud_name = getattr(settings, "cloudinary_cloud_name", "") or ""
    api_key = getattr(settings, "cloudinary_api_key", "") or ""
    api_secret = getattr(settings, "cloudinary_api_secret", "") or ""
    if not cloud_name or not api_key or not api_secret:
        logger.warning("[CLOUDINARY] delete skipped because signed credentials are incomplete")
        return False

    fields = {
        "public_id": public_id,
        "timestamp": str(int(time.time())),
        "invalidate": "true",
        "api_key": api_key,
    }
    fields["signature"] = _cloudinary_signature(fields)

    destroy_url = f"https://api.cloudinary.com/v1_1/{cloud_name}/{resource_type}/destroy"
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(
        destroy_url,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(response_body)
        except Exception:
            payload = {"raw": response_body}
        result = str(payload.get("result", "")).lower()
        ok = result in {"ok", "not found"}
        if ok:
            logger.info("[CLOUDINARY] Deleted asset public_id=%s resource_type=%s", public_id, resource_type)
        else:
            logger.warning("[CLOUDINARY] Delete returned result=%s public_id=%s payload=%s", result, public_id, payload)
        return ok
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else str(exc)
        logger.error(
            "[CLOUDINARY] Delete failed public_id=%s resource_type=%s status=%s body=%s",
            public_id,
            resource_type,
            getattr(exc, "code", None),
            error_body,
        )
        return False
    except Exception as exc:
        logger.error("[CLOUDINARY] Delete error public_id=%s resource_type=%s: %s", public_id, resource_type, exc)
        return False


def store_raw_video(
    video_data: Any,
    class_meta: ClassMetadata,
    *,
    session_id: str,
    original_filename: str,
    include_debug: bool = False,
) -> Dict[str, Any]:
    op_id = f"raw_video_{session_id[:8]}"
    slog.start_operation(op_id)
    
    file_bytes = _coerce_bytes(video_data)
    upload_uid = uuid.uuid4().hex[:8]
    local_key = build_raw_video_minio_key(class_meta, session_id, original_filename, upload_uid)
    local_path = _atomic_write_bytes(_dataset_local_path(local_key), file_bytes)
    logger.info("[STORAGE] raw video stored locally: %s", local_path)

    storage_info: Dict[str, Any] = {
        "upload_uid": upload_uid,
        "storage_provider": "local",
        "storage_key": local_key,
        "storage_url": str(local_path),
        "local_path": str(local_path),
    }
    
    duration_ms = slog.end_operation(op_id) if _cloudinary_ready() else None

    if _cloudinary_ready():
        public_id = build_raw_video_cloudinary_public_id(class_meta, session_id, original_filename, upload_uid)
        try:
            result = _cloudinary_upload_bytes(
                file_bytes,
                original_filename=original_filename,
                public_id=public_id,
                resource_type="video",
            )
            if result and isinstance(result, dict):
                cloudinary_url = str(result.get("secure_url") or result.get("url") or "")
                if cloudinary_url:
                    logger.info("[STORAGE] raw video mirrored to Cloudinary: %s", cloudinary_url)
                    if include_debug or bool(getattr(settings, "cloudinary_debug_responses", False)):
                        logger.info(
                            "[CLOUDINARY][DEBUG] raw video response=%s",
                            json.dumps(_cloudinary_response_summary(result), ensure_ascii=False, default=str),
                        )
                    storage_info["storage_provider"] = "local+cloudinary"
                    storage_info["cloudinary_url"] = cloudinary_url
                    storage_info["cloudinary_public_id"] = public_id
                    
                    # Log success with structured logger
                    slog.log_storage(
                        storage_type="raw",
                        success=True,
                        local_path=str(local_path),
                        mirror_url=cloudinary_url,
                        provider="local+cloudinary",
                        storage_key=local_key,
                        duration_ms=slog.end_operation(op_id),
                    )
                    logger.info(
                        "[STORAGE][RAW] cloudinary_mirror=%s public_id=%s",
                        cloudinary_url,
                        public_id,
                    )
        except CloudinaryUploadError as exc:
            # Log failure with structured logger
            slog.log_storage(
                storage_type="raw",
                success=False,
                local_path=str(local_path),
                provider="local",
                storage_key=local_key,
                error_code="CLOUDINARY_UPLOAD_FAILED",
                error_message=str(exc),
                duration_ms=slog.end_operation(op_id),
            )
            logger.error("[STORAGE][CLOUDINARY] raw video mirror failed: %s", exc.to_debug_payload())
    else:
        # Log success (local-only)
        slog.log_storage(
            storage_type="raw",
            success=True,
            local_path=str(local_path),
            provider="local",
            storage_key=local_key,
            duration_ms=slog.end_operation(op_id),
        )
    
    return storage_info


def store_training_artifact_minio(
    file_data: Any,
    class_meta: ClassMetadata,
    *,
    sample_uid: str,
    augment_id: int,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    op_id = f"npz_{sample_uid}"
    slog.start_operation(op_id)
    
    storage_key = build_sample_npz_key(class_meta, sample_uid, augment_id)
    local_path = _atomic_write_bytes(_dataset_local_path(storage_key), _coerce_bytes(file_data))
    logger.info("[STORAGE] training artifact stored locally: %s", local_path)

    if metadata is not None:
        atomic_write_json(local_path.with_suffix(".json"), metadata, indent=2)

    storage_info: Dict[str, Any] = {
        "storage_provider": "local",
        "storage_key": storage_key,
        "storage_url": str(local_path),
        "local_path": str(local_path),
    }

    if bool(getattr(settings, "use_minio", False)):
        storage_url = upload_file(file_data, storage_key)
        if storage_url:
            logger.info("[STORAGE] training artifact mirrored to MinIO: %s", storage_url)
            storage_info["storage_provider"] = "local+minio"
            storage_info["minio_url"] = storage_url
            
            # Log success with structured logger
            slog.log_storage(
                storage_type="npz",
                success=True,
                local_path=str(local_path),
                mirror_url=storage_url,
                provider="local+minio",
                storage_key=storage_key,
                duration_ms=slog.end_operation(op_id),
            )
        else:
            logger.warning("[STORAGE] training artifact MinIO mirror skipped or failed for key=%s", storage_key)
            # Log partial success
            slog.log_storage(
                storage_type="npz",
                success=True,
                local_path=str(local_path),
                provider="local",
                storage_key=storage_key,
                duration_ms=slog.end_operation(op_id),
            )
    else:
        # Log success (local-only)
        slog.log_storage(
            storage_type="npz",
            success=True,
            local_path=str(local_path),
            provider="local",
            storage_key=storage_key,
            duration_ms=slog.end_operation(op_id),
        )
    
    logger.info(
        "[STORAGE][NPZ] local_save=%s provider=%s key=%s minio=%s",
        storage_info["local_path"],
        storage_info["storage_provider"],
        storage_info["storage_key"],
        storage_info.get("minio_url", ""),
    )
    return storage_info


def _download_http_url(source_url: str, target_path: Path) -> Path:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="dl_", suffix=target_path.suffix or ".bin", dir=str(target_path.parent))
    os.close(fd)
    try:
        with urllib.request.urlopen(source_url, timeout=int(getattr(settings, "storage_download_timeout_seconds", 120))) as response:
            with open(tmp_path, "wb") as f:
                shutil.copyfileobj(response, f)
                f.flush()
                os.fsync(f.fileno())
        os.replace(tmp_path, target_path)
        return target_path
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def download_to_path(source_uri: str, target_path: Path) -> Path:
    source = (source_uri or "").strip()
    target_path = Path(target_path)
    if not source:
        raise ValueError("Empty source URI")

    parsed = urllib.parse.urlparse(source)
    if parsed.scheme in {"http", "https"}:
        return _download_http_url(source, target_path)

    if parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        if not bucket or not key:
            raise ValueError(f"Invalid S3 URI: {source}")
        client = _get_minio_client()
        if not client:
            raise RuntimeError("MinIO is not configured")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        client.fget_object(bucket, key, str(target_path))
        return target_path

    local_path = Path(source)
    if local_path.exists():
        return local_path

    raise FileNotFoundError(f"Unsupported or missing source: {source}")


def materialize_sample_artifacts(
    samples: Iterable[Dict[str, Any]],
    cache_dir: Path,
    *,
    default_suffix: str = ".npz",
    max_workers: Optional[int] = None,
) -> List[Path]:
    rows = list(samples)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    resolved: List[Optional[Path]] = [None] * len(rows)
    download_jobs: List[tuple[int, Path, str]] = []

    for idx, row in enumerate(rows):
        sample_uid = str(row.get("sample_uid") or row.get("id") or f"sample_{idx}")
        file_path = str(row.get("file_path") or "").strip()
        storage_url = str(row.get("storage_url") or "").strip()
        source = file_path if file_path and Path(file_path).exists() else storage_url
        if not source:
            resolved[idx] = None
            continue

        parsed = urllib.parse.urlparse(source)
        source_path = Path(source)
        if source_path.exists() and not parsed.scheme:
            resolved[idx] = source_path
            continue

        suffix = Path(parsed.path).suffix or default_suffix
        target = cache_dir / f"{sample_uid}{suffix}"
        download_jobs.append((idx, target, source))

    if download_jobs:
        workers = max_workers or int(getattr(settings, "storage_download_workers", 4))
        workers = max(1, workers)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(download_to_path, source, target): idx
                for idx, target, source in download_jobs
            }
            for future in as_completed(future_map):
                idx = future_map[future]
                resolved[idx] = future.result()

    out: List[Path] = []
    for idx, row in enumerate(rows):
        path = resolved[idx]
        if path is None:
            source = str(row.get("storage_url") or row.get("file_path") or "").strip()
            if source:
                fallback = Path(source)
                if fallback.exists():
                    path = fallback
        if path is not None:
            out.append(Path(path))
    return out


def download_artifact_to_tempfile(source_uri: str) -> str:
    parsed = urllib.parse.urlparse((source_uri or "").strip())
    suffix = Path(parsed.path).suffix or ".bin"
    fd, tmp_path = tempfile.mkstemp(prefix="remote_", suffix=suffix)
    os.close(fd)
    try:
        download_to_path(source_uri, Path(tmp_path))
        return tmp_path
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise

"""
Professional structured logging utilities for VOYA-Collector backend.
Provides enterprise-grade logging with consistent schema across all operations.

Log Format: [OPERATION][STATUS] key1=val1 key2=val2 ... duration_ms=X error_code=Y

Example:
  [STORAGE][RAW][SUCCESS] local_path=/app/dataset/raw_videos/... provider=local+gdrive duration_ms=1234
  [STORAGE][NPZ][SUCCESS] local_path=/app/dataset/features/... mirror_url=gdrive://file-id duration_ms=567
  [UPLOAD][video][SUCCESS] job_id=abc123 session_id=xyz789 message=... duration_ms=2345
"""

import json
import logging
import time
from enum import Enum
from typing import Any, Dict, Optional


class OperationType(Enum):
    """Standard operation type identifiers."""
    UPLOAD_VIDEO = "UPLOAD_VIDEO"
    UPLOAD_CAMERA = "UPLOAD_CAMERA"
    CLASS_UPDATE = "CLASS_UPDATE"
    CLASS_DELETE = "CLASS_DELETE"
    SAMPLE_UPDATE = "SAMPLE_UPDATE"
    SAMPLE_DELETE = "SAMPLE_DELETE"
    RAW_UPLOAD = "RAW_UPLOAD"
    RAW_DELETE = "RAW_DELETE"
    STORAGE_RAW = "STORAGE_RAW"
    STORAGE_NPZ = "STORAGE_NPZ"
    GDRIVE_UPLOAD = "GDRIVE_UPLOAD"
    CATALOG_SYNC = "CATALOG_SYNC"
    CATALOG_ROLLBACK = "CATALOG_ROLLBACK"
    JOB_ENQUEUE = "JOB_ENQUEUE"
    VALIDATION = "VALIDATION"


class OperationStatus(Enum):
    """Standard operation status identifiers."""
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    IN_PROGRESS = "IN_PROGRESS"
    PARTIAL = "PARTIAL"


class StructuredLogger:
    """
    Enterprise-grade logger for backend operations.
    Ensures consistent format: [CATEGORY][OPERATION][STATUS] key=value ... duration_ms=X
    """

    def __init__(self, logger_name: str = __name__):
        self.logger = logging.getLogger(logger_name)
        self.start_times: Dict[str, float] = {}

    def start_operation(self, operation_id: str) -> None:
        """Mark the start of a timed operation."""
        self.start_times[operation_id] = time.time()

    def end_operation(self, operation_id: str) -> float:
        """Get elapsed time (ms) for an operation and remove from tracking."""
        if operation_id in self.start_times:
            elapsed = (time.time() - self.start_times[operation_id]) * 1000
            del self.start_times[operation_id]
            return elapsed
        return 0.0

    def log_operation(
        self,
        operation: OperationType,
        status: OperationStatus,
        details: Dict[str, Any],
        duration_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        log_level: int = logging.INFO,
    ) -> None:
        """
        Log a structured operation with consistent schema.

        Args:
            operation: Type of operation (UPLOAD_VIDEO, STORAGE_RAW, etc.)
            status: Operation result (SUCCESS, FAILURE, etc.)
            details: Dict of operation-specific key-value pairs
            duration_ms: Optional elapsed time in milliseconds
            error_code: Optional error code (e.g., "GDRIVE_TIMEOUT", "INSUFFICIENT_SPACE")
            error_message: Optional error message for debugging
            log_level: Python logging level (INFO, ERROR, WARNING, DEBUG)
        """
        parts = [f"[{operation.value}]", f"[{status.value}]"]

        # Build key=value details string
        detail_strs = []
        for key, val in details.items():
            if isinstance(val, str):
                # Quote strings with spaces or special chars
                if " " in val or "=" in val or "," in val:
                    detail_strs.append(f'{key}="{val}"')
                else:
                    detail_strs.append(f"{key}={val}")
            elif isinstance(val, (dict, list)):
                # Use compact JSON for complex types
                detail_strs.append(f"{key}={json.dumps(val, separators=(',', ':'))}")
            elif val is None:
                detail_strs.append(f"{key}=<null>")
            else:
                detail_strs.append(f"{key}={val}")

        # Append duration and error info
        if duration_ms is not None:
            detail_strs.append(f"duration_ms={duration_ms:.1f}")
        if error_code:
            detail_strs.append(f"error_code={error_code}")
        if error_message:
            # Escape quotes in error message
            msg = error_message.replace('"', '\\"')
            detail_strs.append(f'error_msg="{msg}"')

        message = " ".join(parts) + " " + " ".join(detail_strs)
        self.logger.log(log_level, message)

    def log_upload(
        self,
        endpoint: str,  # "video" or "camera"
        success: bool,
        session_id: str,
        job_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        file_size_bytes: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        """Convenience method for upload operations."""
        details = {
            "session_id": session_id,
            "file_size_bytes": file_size_bytes,
        }
        if job_id:
            details["job_id"] = job_id

        status = OperationStatus.SUCCESS if success else OperationStatus.FAILURE
        op = OperationType.UPLOAD_VIDEO if endpoint == "video" else OperationType.UPLOAD_CAMERA

        self.log_operation(
            operation=op,
            status=status,
            details=details,
            duration_ms=duration_ms,
            error_message=error_message,
            log_level=logging.ERROR if not success else logging.INFO,
        )

    def log_storage(
        self,
        storage_type: str,  # "raw" or "npz"
        success: bool,
        local_path: str,
        mirror_url: Optional[str] = None,
        provider: str = "local",
        storage_key: Optional[str] = None,
        duration_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """Convenience method for storage operations."""
        details = {
            "local_path": local_path,
            "provider": provider,
        }
        if mirror_url:
            details["mirror_url"] = mirror_url
        if storage_key:
            details["storage_key"] = storage_key

        status = OperationStatus.SUCCESS if success else OperationStatus.FAILURE
        op = OperationType.STORAGE_RAW if storage_type == "raw" else OperationType.STORAGE_NPZ

        self.log_operation(
            operation=op,
            status=status,
            details=details,
            duration_ms=duration_ms,
            error_code=error_code,
            error_message=error_message,
            log_level=logging.ERROR if not success else logging.INFO,
        )


# Global instance for convenience
_default_logger = StructuredLogger("backend.operations")


def get_logger(name: Optional[str] = None) -> StructuredLogger:
    """Get a structured logger instance."""
    if name is None:
        return _default_logger
    return StructuredLogger(name)

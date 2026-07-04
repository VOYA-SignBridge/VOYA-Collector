"""Domain enums & constants for the v2 schema (ERD v2 — 37 tables).

Single home for every status string / role name used across ORM,
services and seeds. No hardcoded strings elsewhere (Refactore task 2.6).
"""
from enum import Enum


class StrEnum(str, Enum):
    """str + Enum for painless use in SQLAlchemy defaults & JSON."""

    def __str__(self) -> str:  # pragma: no cover
        return self.value


# ── Domain 1: Auth & Legal ─────────────────────────────────────────
class SystemRole(StrEnum):
    SYS_ADMIN = "sys_admin"
    USER = "user"


class DocumentType(StrEnum):
    PRIVACY_POLICY = "privacy_policy"
    TERMS_OF_SERVICE = "terms_of_service"
    COOKIE_POLICY = "cookie_policy"
    GUIDELINE = "guideline"


# ── Domain 2: Org & Quota ──────────────────────────────────────────
class WorkspaceRole(StrEnum):
    OWNER = "ws_owner"
    MEMBER = "ws_member"


class ProjectRole(StrEnum):
    MANAGER = "prj_manager"
    CONTRIBUTOR = "prj_contributor"
    VIEWER = "prj_viewer"


class Visibility(StrEnum):
    PRIVATE = "private"
    WORKSPACE = "workspace"
    PUBLIC = "public"


# Quota defaults (WORKSPACE_QUOTAS — §4.2 erd_v2)
DEFAULT_STORAGE_QUOTA_MB = 5120
DEFAULT_MAX_PROJECTS = 10
DEFAULT_MAX_MEMBERS = 20
DEFAULT_MAX_CONCURRENT_TRAININGS = 1
DEFAULT_GPU_MINUTES_QUOTA = 600


# ── Domain 4: Sessions ─────────────────────────────────────────────
class SessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class SourceType(StrEnum):
    LIVE = "live"
    UPLOAD = "upload"


# ── Domain 5: Media ────────────────────────────────────────────────
class SampleStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class UploadStatus(StrEnum):
    PENDING = "pending"
    UPLOADING = "uploading"
    STORED = "stored"
    FAILED = "failed"


class ProcessingStatus(StrEnum):
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class ExportTarget(StrEnum):
    SAMPLES = "samples"
    LABELS = "labels"


# ── Domain 6: QA ───────────────────────────────────────────────────
class ReviewStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    CORRECTED = "corrected"


# ── Domain 7: MLOps ────────────────────────────────────────────────
class DatasetVersionStatus(StrEnum):
    DRAFT = "draft"
    FROZEN = "frozen"


class ModelSource(StrEnum):
    PLATFORM = "platform"  # trained on the platform (architecture required)
    EXTERNAL = "external"  # user-uploaded weights (no training job)


class TrainingStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelVersionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"  # deployed for realtime (Landing demo points here)
    ARCHIVED = "archived"


class WeightsFormat(StrEnum):
    PT = "pt"
    ONNX = "onnx"
    TFLITE = "tflite"


# ── Domain 8: Audit ────────────────────────────────────────────────
class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    REVOKE_TOKEN = "REVOKE_TOKEN"
    PUBLISH_LEGAL = "PUBLISH_LEGAL"
    PROMOTE_DATA = "PROMOTE_DATA"

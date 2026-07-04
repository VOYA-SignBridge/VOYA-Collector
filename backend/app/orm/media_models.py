"""Domain 5 — MEDIA & INFRA (6 tables). Spec: database_dictionary.md #21–#26.

v2 simplifications baked in (§11.4–§11.5 erd_v2):
- SAMPLE_SYNC_STATUS: only `gdrive_synced` (Sheets is a stateless snapshot).
- PROJECT_SHEET_EXPORTS: no rotation counters; watermark + snapshot path.
- RAW_UPLOADS: `size_bytes` for ETag verification + quota accounting.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.orm.base_model import Base, SoftDeleteMixin, TimestampMixin, uuid_pk


class RawUpload(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "raw_uploads"

    upload_uid = Column(Text, primary_key=True)
    session_uid = Column(
        String(64), ForeignKey("collection_sessions.session_uid"), nullable=False
    )
    original_filename = Column(Text)
    local_path = Column(Text)  # MinIO key: {ws}/{prj}/raw/...
    mime_type = Column(String(64))
    size_bytes = Column(BigInteger)
    status = Column(String(16), nullable=False, server_default=text("'pending'"))


class Sample(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "samples"

    sample_uid = Column(Text, primary_key=True)
    session_uid = Column(
        String(64), ForeignKey("collection_sessions.session_uid"), nullable=False
    )
    upload_uid = Column(Text, ForeignKey("raw_uploads.upload_uid"))
    status = Column(String(16), nullable=False, server_default=text("'pending'"))


class SampleMedia(Base):
    """1-1 physical file facts. `checksum` UNIQUE is the idempotency key
    for dedup, Zero-Upload Restoration and dev_promote."""

    __tablename__ = "sample_media"

    sample_uid = Column(Text, ForeignKey("samples.sample_uid"), primary_key=True)
    file_path = Column(Text)  # MinIO key
    storage_url = Column(Text)  # Google Drive URL (filled by Celery)
    checksum = Column(String(64), unique=True, nullable=False)
    fps_original = Column(Float)
    seq_len = Column(Integer)


class SampleProcessing(Base):
    __tablename__ = "sample_processing"

    sample_uid = Column(Text, ForeignKey("samples.sample_uid"), primary_key=True)
    processing_type = Column(String(32), primary_key=True)
    status = Column(String(16), nullable=False, server_default=text("'processing'"))
    result_file_path = Column(Text)  # off-database JSON


class SampleSyncStatus(Base):
    __tablename__ = "sample_sync_status"

    sample_uid = Column(Text, ForeignKey("samples.sample_uid"), primary_key=True)
    gdrive_synced = Column(Boolean, nullable=False, server_default=text("false"))


class ProjectSheetExport(Base):
    """Per-project Sheets report pointer (§11.4 — stateless snapshot)."""

    __tablename__ = "project_sheet_exports"

    id = uuid_pk()
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    export_target = Column(String(16), nullable=False, index=True)
    current_spreadsheet_id = Column(String(128))
    snapshot_file_path = Column(Text)  # samples_full.csv on Drive
    last_exported_at = Column(DateTime(timezone=True))  # watermark

"""Domain 7 — AI MLOPS (7 tables, redesigned per ADR-3/ADR-4).
Spec: database_dictionary.md #28–#34 & erd_v2_unified_design.md §4.

Identity (mutable) vs snapshot/result (immutable) vs process (job):
DATASETS → DATASET_VERSIONS;  MODELS → TRAINING_JOBS → MODEL_VERSIONS.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.orm.base_model import Base, SoftDeleteMixin, TimestampMixin, uuid_pk


class Dataset(Base, TimestampMixin, SoftDeleteMixin):
    """Logical dataset — the mutable identity ('bộ dataset')."""

    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("project_id", "slug", name="uq_datasets_project_slug"),)

    id = uuid_pk()
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    description = Column(Text)
    visibility = Column(String(16), nullable=False, server_default=text("'private'"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))


class DatasetVersion(Base):
    """Immutable snapshot after freeze (service blocks UPDATE past frozen_at)."""

    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id", "version_number", name="uq_dataset_versions_number"
        ),
    )

    id = uuid_pk()
    dataset_id = Column(UUID(as_uuid=True), ForeignKey("datasets.id"), nullable=False)
    version_number = Column(Integer, nullable=False)
    status = Column(String(16), nullable=False, server_default=text("'draft'"))
    manifest_file_path = Column(Text)
    manifest_checksum = Column(String(64))  # seals the off-DB manifest
    sample_count = Column(Integer)
    split_config = Column(JSONB)  # {train, val, test, seed} — Edge Case 4
    size_mb = Column(Integer)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    frozen_at = Column(DateTime(timezone=True))


class ModelArchitecture(Base):
    """Platform-provided catalog — seeded by the system, users only pick."""

    __tablename__ = "model_architectures"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(64), unique=True, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    task_type = Column(String(64))
    default_hyperparams = Column(JSONB)
    trainer_entrypoint = Column(Text)  # script in ai_training/
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class MlModel(Base, TimestampMixin, SoftDeleteMixin):
    """MODELS — logical model in a project. source: platform | external.
    CHECK: platform models must reference an architecture (§4.6)."""

    __tablename__ = "models"
    __table_args__ = (
        UniqueConstraint("project_id", "slug", name="uq_models_project_slug"),
        CheckConstraint(
            "source != 'platform' OR architecture_id IS NOT NULL",
            name="ck_models_platform_needs_architecture",
        ),
    )

    id = uuid_pk()
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    name = Column(Text, nullable=False)
    slug = Column(Text, nullable=False)
    source = Column(String(16), nullable=False)  # platform / external
    architecture_id = Column(Integer, ForeignKey("model_architectures.id"))
    description = Column(Text)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))


class TrainingJob(Base):
    """One 'Start Training' click. Composite index (status, created_at)
    serves both the GC sweep and the queue dashboard."""

    __tablename__ = "training_jobs"
    __table_args__ = (
        Index("ix_training_jobs_status_created", "status", "created_at"),
    )

    id = uuid_pk()
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=False)
    dataset_version_id = Column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id"), nullable=False
    )
    architecture_id = Column(
        Integer, ForeignKey("model_architectures.id"), nullable=False
    )
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    hyperparams = Column(JSONB)
    status = Column(String(16), nullable=False, server_default=text("'queued'"))
    progress = Column(Float, nullable=False, server_default=text("0"))
    celery_task_id = Column(String(64))
    log_file_path = Column(Text)
    error_message = Column(Text)
    submitted_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    started_at = Column(DateTime(timezone=True))
    finished_at = Column(DateTime(timezone=True))


class ModelVersion(Base, SoftDeleteMixin):
    """Released weights. training_job_id NULL ⇔ external upload (§4.8);
    UNIQUE(training_job_id): one job produces at most one version."""

    __tablename__ = "model_versions"
    __table_args__ = (
        UniqueConstraint("model_id", "version", name="uq_model_versions_version"),
    )

    id = uuid_pk()
    model_id = Column(UUID(as_uuid=True), ForeignKey("models.id"), nullable=False)
    version = Column(String(32), nullable=False)
    training_job_id = Column(
        UUID(as_uuid=True), ForeignKey("training_jobs.id"), unique=True
    )
    dataset_version_id = Column(
        UUID(as_uuid=True), ForeignKey("dataset_versions.id")
    )
    weights_path = Column(Text, nullable=False)
    format = Column(String(16))  # pt / onnx / tflite
    metadata_file_path = Column(Text)
    size_mb = Column(Integer)
    status = Column(String(16), nullable=False, server_default=text("'draft'"))
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class InferenceLog(Base):
    """Active Learning — points at the exact MODEL_VERSION that predicted."""

    __tablename__ = "inference_logs"

    id = uuid_pk()
    model_version_id = Column(
        UUID(as_uuid=True), ForeignKey("model_versions.id"), nullable=False
    )
    sample_uid = Column(Text, ForeignKey("samples.sample_uid"), nullable=False)
    is_hard_example = Column(Boolean, nullable=False, server_default=text("false"))
    log_file_path = Column(Text)
    timestamp = Column(DateTime(timezone=True), server_default=text("now()"))

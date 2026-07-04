"""Domain 2 — ORG & QUOTA (5 tables). Spec: database_dictionary.md #7–#11.

WORKSPACE = the tenant unit (ADR-1). Roles here are memberships, not
user attributes (ADR-2) — synced to Casbin g-rules in GĐ 2.
"""
from __future__ import annotations

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.orm.base_model import Base, SoftDeleteMixin, TimestampMixin, uuid_pk
from app.core.constants import (
    DEFAULT_GPU_MINUTES_QUOTA,
    DEFAULT_MAX_CONCURRENT_TRAININGS,
    DEFAULT_MAX_MEMBERS,
    DEFAULT_MAX_PROJECTS,
    DEFAULT_STORAGE_QUOTA_MB,
)


class Workspace(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "workspaces"

    id = uuid_pk()
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(Text, nullable=False)
    slug = Column(Text, unique=True, nullable=False)
    description = Column(Text)
    visibility = Column(String(16), nullable=False, server_default=text("'private'"))


class WorkspaceQuota(Base):
    """Quota (limit) vs usage (actual) — ADR-5. 1-1 with Workspace."""

    __tablename__ = "workspace_quotas"

    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    storage_quota_mb = Column(
        Integer, nullable=False, server_default=text(str(DEFAULT_STORAGE_QUOTA_MB))
    )
    storage_used_mb = Column(Integer, nullable=False, server_default=text("0"))
    max_projects = Column(
        Integer, nullable=False, server_default=text(str(DEFAULT_MAX_PROJECTS))
    )
    max_members = Column(
        Integer, nullable=False, server_default=text(str(DEFAULT_MAX_MEMBERS))
    )
    max_concurrent_trainings = Column(
        Integer,
        nullable=False,
        server_default=text(str(DEFAULT_MAX_CONCURRENT_TRAININGS)),
    )
    gpu_minutes_quota = Column(
        Integer, nullable=False, server_default=text(str(DEFAULT_GPU_MINUTES_QUOTA))
    )
    gpu_minutes_used = Column(Integer, nullable=False, server_default=text("0"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))


class WorkspaceMember(Base):
    __tablename__ = "workspace_members"

    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), primary_key=True
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role = Column(String(20), nullable=False)  # ws_owner / ws_member
    joined_at = Column(DateTime(timezone=True), server_default=text("now()"))


class Project(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True)  # structured id: PRJ-2606-VSL
    workspace_id = Column(
        UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False, index=True
    )
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    visibility = Column(String(16), nullable=False, server_default=text("'private'"))


class ProjectMember(Base):
    __tablename__ = "project_members"

    project_id = Column(String(64), ForeignKey("projects.id"), primary_key=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    project_role = Column(String(20), nullable=False)  # prj_manager/contributor/viewer
    joined_at = Column(DateTime(timezone=True), server_default=text("now()"))

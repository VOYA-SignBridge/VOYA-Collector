"""Domain 4 — DEVICES & SESSIONS (2 tables).
Spec: database_dictionary.md #19–#20 (3-step Commit Handshake).
"""
from __future__ import annotations

from sqlalchemy import Column, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.orm.base_model import Base, TimestampMixin, uuid_pk


class Device(Base):
    __tablename__ = "devices"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    browser_info = Column(Text)
    os_info = Column(Text)
    camera_specs = Column(Text)


class CollectionSession(Base, TimestampMixin):
    """session_uid: CS-YYMMDD-HHMM-[USER_4]. Composite index (status,
    created_at) keeps the nightly GC sweep off a full table scan."""

    __tablename__ = "collection_sessions"
    __table_args__ = (
        Index("ix_collection_sessions_status_created", "status", "created_at"),
    )

    session_uid = Column(String(64), primary_key=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=False)
    class_uid = Column(
        Text, ForeignKey("classes.class_uid", ondelete="RESTRICT"), nullable=False
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    device_id = Column(UUID(as_uuid=True), ForeignKey("devices.id"))
    source_type = Column(String(16), nullable=False)  # live / upload
    snapshot_dialect_code = Column(String(16))
    status = Column(String(16), nullable=False, server_default=text("'in_progress'"))

"""Domain 8 — AUDIT & LOG (3 tables). Spec: database_dictionary.md #35–#37.
ADR-6: 7-layer logging deferred; audit rows are INSERT-only.
"""
from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.orm.base_model import Base, uuid_pk


class SystemAuditLog(Base):
    __tablename__ = "system_audit_logs"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"))
    action = Column(String(32), nullable=False)
    entity_type = Column(Text, nullable=False)
    entity_id = Column(String(128))
    old_data = Column(JSONB)
    new_data = Column(JSONB)
    ip_address = Column(String(45))
    created_at = Column(
        DateTime(timezone=True), server_default=text("now()"), index=True
    )


class LogCategory(Base):
    __tablename__ = "log_categories"

    code = Column(String(32), primary_key=True)  # auth / error / media / gdrive
    name = Column(String(128), nullable=False)
    description = Column(Text)
    retention_days = Column(Integer, nullable=False, server_default=text("30"))


class SystemLogFile(Base):
    __tablename__ = "system_log_files"

    id = uuid_pk()
    category_code = Column(
        String(32), ForeignKey("log_categories.code"), nullable=False
    )
    file_name = Column(String(255), nullable=False)
    local_file_path = Column(Text)
    log_date = Column(Date, nullable=False)

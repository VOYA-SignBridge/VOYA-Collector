"""Domain 1 — AUTH & LEGAL (6 tables). Spec: database_dictionary.md #1–#6."""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.orm.base_model import Base, SoftDeleteMixin, TimestampMixin, uuid_pk


class Role(Base):
    """System-level role ONLY (`sys_admin`/`user`) — ADR-2.
    Workspace/Project permissions live in membership tables + Casbin."""

    __tablename__ = "roles"

    id = uuid_pk()
    name = Column(String(50), unique=True, nullable=False)
    description = Column(Text)


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id = uuid_pk()
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), nullable=False)
    email = Column(Text, unique=True)  # nulled on GDPR delete
    phone_number = Column(String(20), unique=True)
    password_hash = Column(Text)  # null for Google-OAuth accounts
    is_active = Column(Boolean, nullable=False, server_default=text("true"))


class UserProfile(Base):
    __tablename__ = "user_profiles"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True
    )
    username = Column(Text, unique=True, nullable=False)
    full_name = Column(Text)
    avatar_url = Column(Text)
    yob = Column(Integer)
    gender = Column(Text)
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))


class UserSession(Base):
    """Login session + refresh-token revocation (Redis denylist mirrors it)."""

    __tablename__ = "user_sessions"

    id = uuid_pk()
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    refresh_token_hash = Column(String(64), unique=True, nullable=False)
    device_info = Column(String(255))
    ip_address = Column(String(45))
    is_revoked = Column(Boolean, nullable=False, server_default=text("false"))
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))


class LegalDocument(Base):
    """One row = one IMMUTABLE version (`POL-PRIVACY-v2`) — §8.2 erd_v2.
    Partial unique index: one active version per document_type."""

    __tablename__ = "legal_documents"
    __table_args__ = (
        Index(
            "uq_legal_active_per_type",
            "document_type",
            unique=True,
            postgresql_where=text("is_active"),
        ),
    )

    document_code = Column(String(64), primary_key=True)
    document_type = Column(String(32), nullable=False, index=True)
    title = Column(Text)
    content_url = Column(Text, nullable=False)
    content_checksum = Column(String(64))
    effective_date = Column(DateTime(timezone=True))
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    published_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))
    updated_at = Column(DateTime(timezone=True), server_default=text("now()"))


class UserConsent(Base):
    """Append-only consent evidence — never UPDATE/DELETE (§8.2)."""

    __tablename__ = "user_consents"

    id = uuid_pk()
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    document_code = Column(
        String(64), ForeignKey("legal_documents.document_code"), nullable=False
    )
    is_agreed = Column(Boolean, nullable=False)
    consent_preferences = Column(JSONB)
    agreed_at = Column(DateTime(timezone=True), server_default=text("now()"))
    ip_address = Column(String(45))
    user_agent = Column(String(255))

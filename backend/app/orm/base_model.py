"""Declarative base + shared mixins for the v2 ORM (ERD v2 — 37 tables)."""
from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def uuid_pk() -> Column:
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def uuid_fk_type() -> UUID:
    return UUID(as_uuid=True)


class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """`deleted_at IS NULL` = alive; set = in the Trash (never hard-DELETE
    ahead of the GC job — Edge Case 1/5 in database_dictionary.md)."""

    deleted_at = Column(DateTime(timezone=True), nullable=True)

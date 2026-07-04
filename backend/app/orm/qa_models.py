"""Domain 6 — QA (1 table). Spec: database_dictionary.md #27."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import UUID

from app.orm.base_model import Base, uuid_pk


class SampleReview(Base):
    __tablename__ = "sample_reviews"

    id = uuid_pk()
    sample_uid = Column(Text, ForeignKey("samples.sample_uid"), nullable=False)
    reviewer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    suggested_class_uid = Column(Text, ForeignKey("classes.class_uid"))
    status = Column(String(16), nullable=False)  # approved/rejected/corrected
    notes = Column(Text)  # exported as `review_note` on Sheets
    created_at = Column(DateTime(timezone=True), server_default=text("now()"))

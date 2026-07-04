"""Domain 3 — TAXONOMY (7 tables, GLOBAL shared pool).
Spec: database_dictionary.md #12–#18. The only domain without workspace_id.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    text,
)

from app.orm.base_model import Base, SoftDeleteMixin


class Language(Base):
    __tablename__ = "languages"

    code = Column(String(16), primary_key=True)  # vd: vn
    name = Column(Text, nullable=False)


class Dialect(Base):
    __tablename__ = "dialects"

    code = Column(String(16), primary_key=True)  # vd: bac / trung / nam
    language_code = Column(
        String(16), ForeignKey("languages.code"), nullable=False
    )
    name = Column(Text, nullable=False)


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(Text, nullable=False)
    description = Column(Text)


class SignFeature(Base):
    __tablename__ = "sign_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    requires_two_hands = Column(Boolean, nullable=False, server_default=text("false"))
    requires_face_expression = Column(
        Boolean, nullable=False, server_default=text("false")
    )
    requires_body_movement = Column(
        Boolean, nullable=False, server_default=text("false")
    )


class SignClass(Base, SoftDeleteMixin):
    """CLASSES — the national shared dictionary. FK RESTRICT protects
    classes that still own videos (Edge Case 5)."""

    __tablename__ = "classes"

    class_uid = Column(Text, primary_key=True)
    dialect_code = Column(
        String(16), ForeignKey("dialects.code", ondelete="RESTRICT"), nullable=False
    )
    feature_id = Column(Integer, ForeignKey("sign_features.id"))
    slug = Column(Text, unique=True, nullable=False)  # map key for dev_promote
    label_original = Column(Text, nullable=False)
    description = Column(Text)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))


class ClassCategory(Base):
    __tablename__ = "class_categories"

    class_uid = Column(Text, ForeignKey("classes.class_uid"), primary_key=True)
    category_id = Column(Integer, ForeignKey("categories.id"), primary_key=True)


class ProjectClass(Base):
    """Vocabulary a project registered to collect (+ per-project target)."""

    __tablename__ = "project_classes"

    project_id = Column(String(64), ForeignKey("projects.id"), primary_key=True)
    class_uid = Column(Text, ForeignKey("classes.class_uid"), primary_key=True)
    custom_instructions = Column(Text)
    target_count = Column(Integer)  # feeds the Sheets `Progress` tab (§11.3)

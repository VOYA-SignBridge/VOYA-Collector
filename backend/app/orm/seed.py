"""Idempotent seed for the v2 database (Roadmap v2 — GĐ 1, task ③).

Run:  cd backend && ../.venv/Scripts/python -m app.orm.seed

Idempotency contract (tested in GĐ 1): running twice leaves the row
counts unchanged — every insert is keyed on the natural/unique key.
Casbin policies are seeded from core/rbac_policy_seed.csv in GĐ 2 when
the enforcer + adapter exist; this module seeds relational data only.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.constants import DocumentType, SystemRole
from app.core.logging import configure_logging, get_logger
from app.core.session import get_session_factory
from app.orm import (
    Dialect,
    Language,
    LegalDocument,
    LogCategory,
    ModelArchitecture,
    Role,
)

log = get_logger("orm.seed")


def _get_or_create(db: Session, model, defaults: dict | None = None, **keys):
    obj = db.query(model).filter_by(**keys).one_or_none()
    if obj:
        return obj, False
    obj = model(**keys, **(defaults or {}))
    db.add(obj)
    return obj, True


def seed_roles(db: Session) -> int:
    created = 0
    for role, desc in [
        (SystemRole.SYS_ADMIN, "Quản trị nền tảng: legal, classes global, architectures"),
        (SystemRole.USER, "Người dùng thường — quyền thực tế đến từ membership"),
    ]:
        _, was_created = _get_or_create(
            db, Role, name=role.value, defaults={"description": desc}
        )
        created += was_created
    return created


def seed_taxonomy(db: Session) -> int:
    created = 0
    _, c = _get_or_create(
        db, Language, code="vn", defaults={"name": "Vietnamese Sign Language"}
    )
    created += c
    # No ORM relationships are declared (kept lean until GĐ 3), so the
    # unit-of-work cannot infer INSERT order — flush parents explicitly.
    db.flush()
    for code, name in [
        ("bac", "VSL Miền Bắc"),
        ("trung", "VSL Miền Trung"),
        ("nam", "VSL Miền Nam"),
    ]:
        _, c = _get_or_create(
            db, Dialect, code=code, defaults={"language_code": "vn", "name": name}
        )
        created += c
    return created


def seed_model_architectures(db: Session) -> int:
    """Platform catalog (§4.5 erd_v2) — users pick, never create."""
    created = 0
    architectures = [
        dict(
            code="lstm_v1",
            name="LSTM Sequence Classifier",
            description="Nhẹ, train nhanh trên keypoints Mediapipe; phù hợp bộ từ vựng nhỏ.",
            task_type="sequence_classification",
            default_hyperparams={"epochs": 60, "lr": 0.001, "batch_size": 32},
            trainer_entrypoint="ai_training/train_utils/train_lstm.py",
        ),
        dict(
            code="yolov8_pose",
            name="YOLOv8-Pose",
            description="Phát hiện tư thế tay/thân; nặng hơn, cần GPU.",
            task_type="pose_detection",
            default_hyperparams={"epochs": 100, "imgsz": 640, "batch": 16},
            trainer_entrypoint="ai_training/train_utils/train_yolov8_pose.py",
        ),
        dict(
            code="timesformer",
            name="TimeSformer (video transformer)",
            description="Chính xác cao trên chuỗi dài, chi phí GPU lớn — cân nhắc quota.",
            task_type="video_classification",
            default_hyperparams={"epochs": 30, "lr": 0.00005, "batch_size": 8},
            trainer_entrypoint="ai_training/train_utils/train_timesformer.py",
        ),
    ]
    for arch in architectures:
        code = arch.pop("code")
        _, c = _get_or_create(db, ModelArchitecture, code=code, defaults=arch)
        created += c
    return created


def seed_log_categories(db: Session) -> int:
    created = 0
    for code, name, days in [
        ("auth", "Authentication events", 90),
        ("error", "Application errors", 30),
        ("media", "Upload/processing pipeline", 30),
        ("gdrive", "Drive/Sheets sync", 30),
    ]:
        _, c = _get_or_create(
            db,
            LogCategory,
            code=code,
            defaults={"name": name, "retention_days": days},
        )
        created += c
    return created


def seed_legal_documents(db: Session) -> int:
    """v1 of each policy — content .md files are uploaded to MinIO in GĐ 2
    (legal_service.publish); URLs here are their agreed bucket keys."""
    created = 0
    docs = [
        ("POL-PRIVACY-v1", DocumentType.PRIVACY_POLICY, "Chính sách quyền riêng tư"),
        ("POL-TOS-v1", DocumentType.TERMS_OF_SERVICE, "Điều khoản sử dụng"),
        ("POL-COOKIE-v1", DocumentType.COOKIE_POLICY, "Chính sách Cookie"),
    ]
    for code, dtype, title in docs:
        _, c = _get_or_create(
            db,
            LegalDocument,
            document_code=code,
            defaults={
                "document_type": dtype.value,
                "title": title,
                "content_url": f"legal-docs/{code.rsplit('-', 1)[0]}/{code.rsplit('-', 1)[1]}.md",
                "is_active": True,
            },
        )
        created += c
    return created


def run_seed() -> dict:
    configure_logging()
    db = get_session_factory()()
    try:
        result = {
            "roles": seed_roles(db),
            "taxonomy": seed_taxonomy(db),
            "model_architectures": seed_model_architectures(db),
            "log_categories": seed_log_categories(db),
            "legal_documents": seed_legal_documents(db),
        }
        db.commit()
        log.info("seed done — created: {}", result)
        return result
    finally:
        db.close()


if __name__ == "__main__":
    print(run_seed())

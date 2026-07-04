"""Component tests — ORM constraints on the real dev PostgreSQL (GĐ 1 §7.5).

Requires the dev stack: `docker compose -f docker-compose.dev.yml up -d`
and `alembic upgrade head`. Per Roadmap v2, a missing dev DB must FAIL
these tests (infrastructure is a GĐ 1 deliverable), never skip.

Each test runs inside a SAVEPOINT-wrapped session that is rolled back —
the dev database is left untouched.
"""
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.orm import (
    Dataset,
    DatasetVersion,
    LegalDocument,
    MlModel,
    Project,
    Role,
    Sample,
    SampleMedia,
    SignClass,
    User,
    Workspace,
    CollectionSession,
)

_settings = Settings(_env_file=None)
_engine = create_engine(_settings.database_url, future=True)
_Session = sessionmaker(bind=_engine, future=True)


@pytest.fixture()
def db():
    """Transaction-per-test: everything rolls back, DB stays pristine."""
    connection = _engine.connect()
    txn = connection.begin()
    session = _Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        txn.rollback()
        connection.close()


def _mk_user(db) -> User:
    role = db.query(Role).filter_by(name="user").one()
    user = User(role_id=role.id, email=f"{uuid.uuid4().hex}@t.dev")
    db.add(user)
    db.flush()
    return user


def _mk_workspace_project(db, user):
    ws = Workspace(owner_id=user.id, name="T", slug=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    db.flush()
    prj = Project(
        id=f"PRJ-{uuid.uuid4().hex[:8]}", workspace_id=ws.id, owner_id=user.id, name="P"
    )
    db.add(prj)
    db.flush()
    return ws, prj


class TestDatasetVersioning:
    def test_version_number_unique_per_dataset(self, db):
        user = _mk_user(db)
        ws, prj = _mk_workspace_project(db, user)
        ds = Dataset(
            project_id=prj.id, workspace_id=ws.id, name="D", slug="d", created_by=user.id
        )
        db.add(ds)
        db.flush()
        db.add(DatasetVersion(dataset_id=ds.id, version_number=1))
        db.flush()
        db.add(DatasetVersion(dataset_id=ds.id, version_number=1))
        with pytest.raises(IntegrityError):
            db.flush()

    def test_dataset_slug_unique_within_project(self, db):
        user = _mk_user(db)
        ws, prj = _mk_workspace_project(db, user)
        db.add(Dataset(project_id=prj.id, workspace_id=ws.id, name="A", slug="dup"))
        db.flush()
        db.add(Dataset(project_id=prj.id, workspace_id=ws.id, name="B", slug="dup"))
        with pytest.raises(IntegrityError):
            db.flush()


class TestModelRegistry:
    def test_platform_model_requires_architecture(self, db):
        """CHECK ck_models_platform_needs_architecture (§4.6 erd_v2)."""
        user = _mk_user(db)
        ws, prj = _mk_workspace_project(db, user)
        db.add(
            MlModel(
                project_id=prj.id,
                workspace_id=ws.id,
                name="M",
                slug="m",
                source="platform",  # no architecture_id -> must fail
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()

    def test_external_model_needs_no_architecture(self, db):
        user = _mk_user(db)
        ws, prj = _mk_workspace_project(db, user)
        db.add(
            MlModel(
                project_id=prj.id,
                workspace_id=ws.id,
                name="M",
                slug="m",
                source="external",
            )
        )
        db.flush()  # must NOT raise


class TestLegalPartialUnique:
    def test_only_one_active_version_per_document_type(self, db):
        """Partial unique uq_legal_active_per_type (§8.2 erd_v2)."""
        db.add(
            LegalDocument(
                document_code=f"POL-T-{uuid.uuid4().hex[:6]}-v1",
                document_type="test_policy",
                content_url="x",
                is_active=True,
            )
        )
        db.flush()
        db.add(
            LegalDocument(
                document_code=f"POL-T-{uuid.uuid4().hex[:6]}-v2",
                document_type="test_policy",
                content_url="y",
                is_active=True,
            )
        )
        with pytest.raises(IntegrityError):
            db.flush()

    def test_many_inactive_versions_are_allowed(self, db):
        for i in (1, 2, 3):
            db.add(
                LegalDocument(
                    document_code=f"POL-I-{uuid.uuid4().hex[:6]}-v{i}",
                    document_type="test_policy_inactive",
                    content_url="x",
                    is_active=False,
                )
            )
        db.flush()  # must NOT raise


class TestChecksumIdempotencyKey:
    def test_duplicate_checksum_is_rejected(self, db):
        """SAMPLE_MEDIA.checksum UNIQUE — dedup/restoration/promote key."""
        user = _mk_user(db)
        ws, prj = _mk_workspace_project(db, user)
        cls = SignClass(
            class_uid=f"C-{uuid.uuid4().hex[:8]}",
            dialect_code="nam",
            slug=f"s-{uuid.uuid4().hex[:8]}",
            label_original="x",
        )
        db.add(cls)
        db.flush()
        ses = CollectionSession(
            session_uid=f"CS-{uuid.uuid4().hex[:10]}",
            project_id=prj.id,
            class_uid=cls.class_uid,
            user_id=user.id,
            source_type="upload",
        )
        db.add(ses)
        db.flush()
        checksum = uuid.uuid4().hex + uuid.uuid4().hex  # 64 hex chars
        for n in (1, 2):
            s = Sample(sample_uid=f"S-{uuid.uuid4().hex[:10]}", session_uid=ses.session_uid)
            db.add(s)
            db.flush()
            db.add(SampleMedia(sample_uid=s.sample_uid, checksum=checksum))
            if n == 1:
                db.flush()
        with pytest.raises(IntegrityError):
            db.flush()


class TestSoftDelete:
    def test_soft_deleted_user_keeps_foreign_keys_alive(self, db):
        """Edge Case 1 (GDPR): nulling PII + deleted_at must not break FKs."""
        import datetime as dt

        user = _mk_user(db)
        ws, _ = _mk_workspace_project(db, user)
        user.email = None
        user.password_hash = None
        user.deleted_at = dt.datetime.now(dt.timezone.utc)
        db.flush()
        # workspace still points at the (soft-deleted) owner
        assert db.query(Workspace).filter_by(id=ws.id).one().owner_id == user.id

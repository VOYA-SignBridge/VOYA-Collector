"""Two real tenants, created through the real API, proving they cannot see each other.

Everything before this file argued about isolation with synthetic scopes and a
scratch database. This one does the thing the whole programme exists to make
possible: a platform operator creates tenant B, a person accepts an invitation
into it, that person's data is written through the ordinary code paths, and then
we check what each side can see.

It is the difference between "the policy is installed" and "the policy works on
this deployment, against this schema, with these code paths". Those are not the
same claim, and only the second one is worth anything.

Cleanup is thorough on purpose: this runs against the live database, so a
half-removed tenant would sit in the operator's list forever.
"""

from __future__ import annotations

import uuid

import pytest

from app import tenant_admin
from app.storage import metadata_db as db
from app.tenancy import DEFAULT_TENANT_ID
from app.tenant_context import system_scope, tenant_scope


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    db.ensure_tables()


@pytest.fixture
def two_tenants():
    """Tenant A (the bootstrap one) and a freshly created tenant B."""
    from conftest import purge_tenant

    tid = f"test-b-{uuid.uuid4().hex[:8]}"
    tenant_admin.create_tenant(tid, display_name="School B")
    yield DEFAULT_TENANT_ID, tid
    purge_tenant(tid)


@pytest.fixture
def accounts():
    created = []

    def _make() -> dict:
        from app.auth import create_user

        name = f"t{uuid.uuid4().hex[:10]}"
        user = create_user(
            username=name, email=f"{name}@example.test", password="correct horse battery"
        )
        created.append(user["id"])
        return user

    yield _make

    with system_scope("test cleanup"):
        for uid in created:
            db._execute("DELETE FROM tenant_members WHERE user_id = %s", (uid,))
            db._execute(
                "UPDATE tenant_invitations SET accepted_by = NULL WHERE accepted_by = %s",
                (uid,),
            )
            db._execute("DELETE FROM training_jobs WHERE auth_user_id = %s", (uid,))
            db._execute("DELETE FROM users WHERE id = %s", (uid,))


def _seed_class(tenant_id: str, uid: str) -> None:
    """Write one class row AS that tenant, through the scoped cursor.

    Not a system-scope insert: writing as the tenant is what exercises the
    policy's WITH CHECK, and a row written any other way would prove nothing
    about what the application does.

    `dialect='common'` resolves against the tenant's OWN dialect rows — the
    foreign key is composite, `(tenant_id, dialect)`. This works only because
    `create_tenant` clones the catalogue; without it the insert fails with a
    foreign-key error, which is exactly how that gap was found.
    """
    with tenant_scope(tenant_id):
        db._execute(
            "INSERT INTO classes(class_uid, slug, label_original, language, dialect, "
            "folder_name, tenant_id) VALUES(%s, %s, %s, 'vn', 'common', %s, %s)",
            (uid, f"slug-{uid}", f"label {uid}", f"folder_{uid}", tenant_id),
        )


class TestTheTenantsCannotSeeEachOther:
    def test_a_class_written_by_b_is_invisible_to_a(self, two_tenants):
        a, b = two_tenants
        uid_b = f"proof-b-{uuid.uuid4().hex[:8]}"
        _seed_class(b, uid_b)

        with tenant_scope(a):
            assert db._fetch_all(
                "SELECT class_uid FROM classes WHERE class_uid = %s", (uid_b,)
            ) == [], "tenant A read a class belonging to tenant B"

        # Negative control: B itself sees it. Without this the test would pass
        # just as well if the insert had silently failed.
        with tenant_scope(b):
            assert len(db._fetch_all(
                "SELECT class_uid FROM classes WHERE class_uid = %s", (uid_b,)
            )) == 1

    def test_a_cannot_count_bs_rows(self, two_tenants):
        """An aggregate leaks as surely as a row does. `COUNT(*)` with no WHERE
        is the query most likely to be written carelessly."""
        a, b = two_tenants
        before = None
        with tenant_scope(a):
            before = db._fetch_all("SELECT COUNT(*) AS n FROM classes")[0]["n"]
        _seed_class(b, f"proof-b-{uuid.uuid4().hex[:8]}")
        with tenant_scope(a):
            after = db._fetch_all("SELECT COUNT(*) AS n FROM classes")[0]["n"]
        assert after == before

    def test_a_cannot_write_into_b(self, two_tenants):
        """WITH CHECK, not just USING. A tenant that can insert a row it cannot
        read has moved data across the boundary in the one direction that does
        not show up in any read test."""
        a, b = two_tenants
        uid = f"proof-x-{uuid.uuid4().hex[:8]}"
        with pytest.raises(Exception) as exc:
            with tenant_scope(a):
                db._execute(
                    "INSERT INTO classes(class_uid, slug, label_original, language, "
                    "dialect, folder_name, tenant_id) "
                    "VALUES(%s, %s, %s, 'vn', 'common', %s, %s)",
                    (uid, f"slug-{uid}", "x", f"folder_{uid}", b),
                )
        assert "policy" in str(exc.value).lower()

    def test_a_cannot_steal_bs_row_with_an_update(self, two_tenants):
        a, b = two_tenants
        uid_b = f"proof-b-{uuid.uuid4().hex[:8]}"
        _seed_class(b, uid_b)
        with tenant_scope(a):
            db._execute(
                "UPDATE classes SET tenant_id = %s WHERE class_uid = %s", (a, uid_b)
            )
        with tenant_scope(b):
            rows = db._fetch_all(
                "SELECT tenant_id FROM classes WHERE class_uid = %s", (uid_b,)
            )
        assert rows and rows[0]["tenant_id"] == b, "tenant A moved B's row to itself"

    def test_an_unqualified_delete_only_empties_your_own_tenant(self, two_tenants):
        """`DELETE FROM classes` with no WHERE — the accident that would
        otherwise wipe every tenant on the deployment."""
        a, b = two_tenants
        uid_b = f"proof-b-{uuid.uuid4().hex[:8]}"
        _seed_class(b, uid_b)
        with tenant_scope(f"test-empty-{uuid.uuid4().hex[:8]}"):
            db._execute("DELETE FROM classes")
        with tenant_scope(b):
            assert len(db._fetch_all(
                "SELECT class_uid FROM classes WHERE class_uid = %s", (uid_b,)
            )) == 1


class TestTrainingJobsNoLongerLeak:
    """The leak that was demonstrable before RLS was added to this table.

    `list_training_jobs` reads `SELECT * FROM training_jobs ORDER BY created_at
    DESC LIMIT %s` — no tenant predicate at all. It was correct only because
    there was exactly one tenant.
    """

    @staticmethod
    def _job(tenant_id: str) -> str:
        job_id = f"proof-job-{uuid.uuid4().hex[:8]}"
        with tenant_scope(tenant_id):
            db.upsert_training_job({
                "job_id": job_id, "status": "completed", "model_type": "tcn",
                "config": {"note": "isolation proof"}, "auth_user_id": None,
                "created_at": None, "started_at": None, "completed_at": None,
                "current_epoch": 0, "total_epochs": 0, "checkpoint_path": None,
                "test_acc": None, "test_f1": None, "error_message": None,
                "promoted_at": None,
            })
        return job_id

    def test_the_job_list_does_not_cross_tenants(self, two_tenants):
        a, b = two_tenants
        job_b = self._job(b)

        with tenant_scope(a):
            visible = {r["job_id"] for r in db.list_training_jobs(limit=500)}
        assert job_b not in visible

        with tenant_scope(b):
            assert job_b in {r["job_id"] for r in db.list_training_jobs(limit=500)}

    def test_a_job_is_filed_under_the_writing_scope(self, two_tenants):
        """The upsert never carried `tenant_id`, so every job landed in the
        bootstrap tenant via the column default. Harmless with one tenant;
        wrong with two, and refused outright once WITH CHECK is on the table."""
        _, b = two_tenants
        job_b = self._job(b)
        with system_scope("test read"):
            rows = db._fetch_all(
                "SELECT tenant_id FROM training_jobs WHERE job_id = %s", (job_b,)
            )
        assert rows[0]["tenant_id"] == b

    def test_fetching_bs_job_by_its_exact_id_returns_nothing(self, two_tenants):
        """Guessing a primary key must not be a way around the boundary."""
        a, b = two_tenants
        job_b = self._job(b)
        with tenant_scope(a):
            assert db.get_training_job(job_b) is None


class TestUsersAreConstrainedInTheDataPlane:
    """RLS on `users`, with its guarantee stated honestly.

    The identity plane is exempt and must be — a login looks an account up
    before any tenant is known. What the policy does constrain is the data-plane
    joins that decorate rows with a contributor's name.
    """

    def test_a_cross_tenant_username_resolves_to_nothing(self, two_tenants, accounts):
        a, b = two_tenants
        user = accounts()
        tenant_admin.set_home_tenant(user["id"], b, role="editor")

        with tenant_scope(a):
            assert db._fetch_all(
                "SELECT username FROM users WHERE id = %s", (user["id"],)
            ) == []
        with tenant_scope(b):
            assert len(db._fetch_all(
                "SELECT username FROM users WHERE id = %s", (user["id"],)
            )) == 1

    def test_login_still_works_for_a_user_in_another_tenant(self, two_tenants, accounts):
        """The circularity check. Authentication reads `users` before the scope
        exists; if that read obeyed the policy it would match nothing and every
        account outside the ambient tenant would be locked out.

        This test is the reason `auth.py` is on the boundary allowlist rather
        than being 'cleaned up' later by someone who sees a system_scope call
        and assumes it is an oversight.
        """
        from app.auth import authenticate_user

        _, b = two_tenants
        user = accounts()
        tenant_admin.set_home_tenant(user["id"], b, role="editor")

        with tenant_scope(DEFAULT_TENANT_ID):
            authenticated = authenticate_user(user["email"], "correct horse battery")
        assert authenticated is not None
        assert authenticated["tenant_id"] == b


class TestStoragePartition:
    """A4: the tenant also decides where the .npz files land."""

    def test_each_tenant_gets_its_own_feature_root(self, two_tenants):
        from app.dataset_manager import FEATURES_ROOT, tenant_features_root

        a, b = two_tenants
        assert tenant_features_root(a) == FEATURES_ROOT
        assert tenant_features_root(b) == FEATURES_ROOT / "_tenants" / b
        assert tenant_features_root(a) != tenant_features_root(b)

    def test_the_ambient_scope_picks_the_root(self, two_tenants):
        """The path comes from the scope, not from an argument — so a handler
        cannot write into another tenant's tree by passing the wrong string."""
        from app.dataset_manager import ambient_tenant_features_root, tenant_features_root

        _, b = two_tenants
        with tenant_scope(b):
            assert ambient_tenant_features_root() == tenant_features_root(b)

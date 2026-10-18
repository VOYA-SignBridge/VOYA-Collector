"""`install_rls`: no DDL when policies are current, atomic per table when not.

The old boot path dropped and re-created every tenant policy, statement by
statement, on an autocommit connection: a deny-all window per table on every
worker start. See `storage/rls.install_rls`.
"""
from __future__ import annotations

import pytest

from app.storage import metadata_db as db
from app.storage.rls import (POLICY_NAME, RLS_TABLES, SHARED_CATALOGUE_TABLES, install_rls,
                             policy_fingerprint, policy_statements)


@pytest.fixture(scope="module", autouse=True)
def _schema():
    db.ensure_tables()


def _policy(table: str):
    with db._migration_cursor() as cur:
        cur.execute(
            "SELECT p.polname, obj_description(p.oid, 'pg_policy') FROM pg_policy p "
            "WHERE p.polrelid = to_regclass(%s) ORDER BY 1", (table,))
        return cur.fetchall()


def test_second_install_is_a_no_op():
    with db._migration_cursor() as cur:
        install_rls(cur)
        again = install_rls(cur)
    assert again["installed"] == 0
    assert again["failed"] == 0
    assert again["unchanged"] == len(RLS_TABLES) + len(SHARED_CATALOGUE_TABLES)


def test_policy_carries_the_fingerprint_of_its_statements():
    table = "dialects"
    assert (POLICY_NAME, policy_fingerprint(policy_statements(table))) in _policy(table)


def test_a_drifted_policy_is_reinstalled():
    table = "dialects"
    with db._migration_cursor() as cur:
        cur.execute(f"COMMENT ON POLICY {POLICY_NAME} ON {table} IS 'hand edited'")
        result = install_rls(cur)
    assert result["installed"] == 1
    assert (POLICY_NAME, policy_fingerprint(policy_statements(table))) in _policy(table)


def test_isolation_still_enforced_for_the_app_role():
    from app.tenant_context import tenant_scope

    with tenant_scope("mot-tenant-khac-0000"):
        assert db._fetch_all("SELECT 1 FROM dialects WHERE tenant_id = 'default' LIMIT 1") == []
    with tenant_scope("default"):
        assert db._fetch_all("SELECT 1 FROM dialects WHERE tenant_id = 'default' LIMIT 1")

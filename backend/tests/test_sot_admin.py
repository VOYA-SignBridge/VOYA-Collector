"""Tests for the SOT admin API + DB-backed writer registry.

Two easy layers, both against the real Postgres (like the other SOT tests):
  1. function-level DB CRUD + the reader-side union (effective_authorized_keys)
  2. HTTP endpoints, with admin auth bypassed via FastAPI dependency_overrides
     (no login dance needed)

Each test cleans up the keys it creates (names are prefixed test-<uuid>).
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.storage import metadata_db as db
from app.sot import keys as sot_keys
from app.sot import reader_sync


@pytest.fixture(scope="module", autouse=True)
def _ensure_schema():
    # Idempotent: creates sot_authorized_keys (and everything else) IF NOT EXISTS.
    db.ensure_tables()


def _fresh_pubkey() -> str:
    return sot_keys.public_key_b64(sot_keys.generate_private_key())


def _cleanup(prefix: str) -> None:
    db._execute("DELETE FROM sot_authorized_keys WHERE name LIKE %s", (f"{prefix}%",))


# ===========================================================================
# DB CRUD
# ===========================================================================

def test_add_list_revoke_roundtrip():
    prefix = f"test-{uuid.uuid4().hex[:8]}"
    pub = _fresh_pubkey()
    fp = sot_keys.fingerprint(pub)
    try:
        db.sot_add_authorized_key(name=f"{prefix}-m1", public_key=pub, fingerprint=fp,
                                  added_by="tester", note="hi")
        assert any(r["fingerprint"] == fp for r in db.sot_list_authorized_keys())

        assert db.sot_revoke_authorized_key(fp) is True
        assert not any(r["fingerprint"] == fp for r in db.sot_list_authorized_keys())
        assert db.sot_revoke_authorized_key(fp) is False          # already revoked

        # re-adding the SAME public key un-revokes it
        db.sot_add_authorized_key(name=f"{prefix}-m1", public_key=pub, fingerprint=fp)
        assert any(r["fingerprint"] == fp for r in db.sot_list_authorized_keys())
    finally:
        _cleanup(prefix)


def test_duplicate_name_with_different_key_rejected():
    prefix = f"test-{uuid.uuid4().hex[:8]}"
    try:
        db.sot_add_authorized_key(name=f"{prefix}-dup", public_key=_fresh_pubkey(), fingerprint="fpA")
        with pytest.raises(Exception):        # UNIQUE(name) violation
            db.sot_add_authorized_key(name=f"{prefix}-dup", public_key=_fresh_pubkey(), fingerprint="fpB")
    finally:
        _cleanup(prefix)


def test_effective_keys_unions_db_and_drops_revoked():
    prefix = f"test-{uuid.uuid4().hex[:8]}"
    pub = _fresh_pubkey()
    fp = sot_keys.fingerprint(pub)
    try:
        db.sot_add_authorized_key(name=f"{prefix}-eff", public_key=pub, fingerprint=fp)
        assert any(e.get("public_key") == pub for e in reader_sync.effective_authorized_keys())

        db.sot_revoke_authorized_key(fp)
        assert not any(e.get("public_key") == pub for e in reader_sync.effective_authorized_keys())
    finally:
        _cleanup(prefix)


# ===========================================================================
# HTTP endpoints (admin auth bypassed)
# ===========================================================================

@pytest.fixture
def client():
    from app.main import app
    from app.auth import require_admin

    app.dependency_overrides[require_admin] = lambda: {"id": "t", "username": "tester", "is_admin": True}
    yield TestClient(app)
    app.dependency_overrides.pop(require_admin, None)


def test_overview_endpoint_shape(client):
    r = client.get("/api/v1/admin/sot/overview")
    assert r.status_code == 200
    body = r.json()
    for key in ("machines", "db_counts", "schema_version", "this_machine"):
        assert key in body


def test_schema_endpoint_returns_shape_but_never_ddl(client):
    """The endpoint reports the schema's shape, not its DDL.

    It used to return export_schema_sql() and the admin page rendered the whole
    CREATE TABLE listing on screen. Admin auth controls who can call it, but not
    where the output ends up — a screenshot or a shared screen carried the full
    blueprint. The table/column inventory answers the same operational question
    ("is this deployment the expected shape?") without publishing it.
    """
    r = client.get("/api/v1/admin/sot/schema")
    assert r.status_code == 200
    body = r.json()

    # The DDL must be gone, under any key.
    assert "schema_sql" not in body
    assert "CREATE TABLE" not in json.dumps(body)

    # …and what remains still describes the schema usefully.
    assert isinstance(body["schema_version"], int)
    required = body["required_columns"]
    assert {"classes", "samples", "raw_uploads"} <= set(required)
    assert "sample_uid" in required["samples"]


def test_register_generate_returns_private_key_once_then_revoke(client):
    prefix = f"test-{uuid.uuid4().hex[:8]}"
    try:
        r = client.post("/api/v1/admin/sot/machines", json={"name": f"{prefix}-gen", "mode": "generate"})
        assert r.status_code == 201, r.text
        body = r.json()
        assert body.get("private_key")                     # returned exactly once
        fp = body["machine"]["fingerprint"]

        machines = client.get("/api/v1/admin/sot/overview").json()["machines"]
        assert any(m["fingerprint"] == fp for m in machines)

        d = client.delete(f"/api/v1/admin/sot/machines/{fp}")
        assert d.status_code == 200 and d.json()["revoked"] is True
    finally:
        _cleanup(prefix)


def test_register_public_key_and_validation(client):
    prefix = f"test-{uuid.uuid4().hex[:8]}"
    try:
        r = client.post(
            "/api/v1/admin/sot/machines",
            json={"name": f"{prefix}-pk", "mode": "public_key", "public_key": _fresh_pubkey()},
        )
        assert r.status_code == 201, r.text
        assert "private_key" not in r.json()               # not generated -> nothing to hand back

        # duplicate name -> 409
        dup = client.post(
            "/api/v1/admin/sot/machines",
            json={"name": f"{prefix}-pk", "mode": "public_key", "public_key": _fresh_pubkey()},
        )
        assert dup.status_code == 409

        # invalid public key (decodes to 5 bytes, not a 32-byte Ed25519 key) -> 400
        bad = client.post(
            "/api/v1/admin/sot/machines",
            json={"name": f"{prefix}-bad", "mode": "public_key", "public_key": "aGVsbG8="},
        )
        assert bad.status_code == 400
    finally:
        _cleanup(prefix)


def test_cannot_revoke_a_committed_key(client):
    committed = sot_keys.load_authorized_keys()
    if not committed:
        pytest.skip("no committed baseline keys to test against")
    fp = committed[0].get("fingerprint") or sot_keys.fingerprint(committed[0]["public_key"])
    r = client.delete(f"/api/v1/admin/sot/machines/{fp}")
    assert r.status_code == 400                            # committed keys are git-managed, not UI-revocable

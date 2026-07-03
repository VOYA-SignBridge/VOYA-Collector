"""Shared fixtures for the SignBridge test suite (GĐ 0 — Roadmap v2).

The `client` fixture serves the *legacy* FastAPI app for Characterization
Tests: it deliberately does NOT run lifespan/startup events, so no DB
init, TTS warm-up, or network calls happen at collection time.
"""
import socket

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app


def _db_reachable(timeout: float = 0.5) -> bool:
    """True when the configured PostgreSQL is reachable from this host.

    In the docker-compose stack Postgres is only exposed on the compose
    network (host `postgres`), so host-side runs typically skip
    `requires_db` tests unless a local Postgres is published.
    """
    try:
        with socket.create_connection(
            (settings.postgres_host, settings.postgres_port), timeout=timeout
        ):
            return True
    except OSError:
        return False


DB_AVAILABLE = _db_reachable()


def pytest_collection_modifyitems(config, items):
    skip_db = pytest.mark.skip(
        reason="PostgreSQL not reachable from host (see tests/conftest.py)"
    )
    for item in items:
        if "requires_db" in item.keywords and not DB_AVAILABLE:
            item.add_marker(skip_db)


@pytest.fixture(scope="session")
def client() -> TestClient:
    # No `with` block on purpose: startup events must not run (init_db,
    # TTS pre-warm). Route handlers themselves do not need them.
    return TestClient(app)

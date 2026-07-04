"""Shared fixtures for the SignBridge test suite (GĐ 0 — Roadmap v2).

The `client` fixture serves the *legacy* FastAPI app for Characterization
Tests: it deliberately does NOT run lifespan/startup events, so no DB
init, TTS warm-up, or network calls happen at collection time.

GĐ 0 tests are infrastructure-free by design. Tests that need a real
PostgreSQL/MinIO/Redis belong to GĐ 2+ (Roadmap v2 §7.5) and will run
against the dev compose stack — there, missing infrastructure must FAIL,
never silently skip.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="session")
def client() -> TestClient:
    # No `with` block on purpose: startup events must not run (init_db,
    # TTS pre-warm). Route handlers themselves do not need them.
    return TestClient(app)

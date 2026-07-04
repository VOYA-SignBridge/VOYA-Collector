"""SQLAlchemy engine + session factory for the v2 database (§2.10).

Connection Pool: bounded pool with pre-ping; every request borrows a
connection via the `get_db` dependency and returns it immediately after.

NOTE (Strangler Fig): this engine points at the V2 database
(`signbridge_v2`), NOT the legacy `signdb`. The two schemas never share
a database — the legacy one is read by `dev_promote`-style tooling only.
"""
from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=settings.db_pool_pre_ping,
            future=True,
        )
    return _engine


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False, future=True
        )
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: borrow a pooled connection, always give it back."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()

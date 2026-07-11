from __future__ import annotations

import logging
import os
import re
import threading
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

import psycopg2
from psycopg2 import pool as _pg_pool

from app.config import settings

logger = logging.getLogger(__name__)


def _format_host_part(parts, host: str) -> str:
    port = f":{parts.port}" if parts.port else ""
    if ":" in host and not host.startswith("["):
        return f"[{host}]{port}"
    return f"{host}{port}"


def _rewrite_host(database_url: str, host: str) -> str:
    parts = urlsplit(database_url)
    netloc = parts.netloc

    if "@" in netloc:
        auth_part, _ = netloc.rsplit("@", 1)
        host_part = _format_host_part(parts, host)
        return urlunsplit((parts.scheme, f"{auth_part}@{host_part}", parts.path, parts.query, parts.fragment))

    host_part = _format_host_part(parts, host)
    return urlunsplit((parts.scheme, host_part, parts.path, parts.query, parts.fragment))


def _candidate_hosts() -> Iterable[str]:
    current_url = settings.database_url
    parsed = urlsplit(current_url)
    current_host = parsed.hostname or ""

    raw_candidates = [
        current_host,
        getattr(settings, "postgres_host", ""),
        "postgres",
        "voya_postgres",
        "localhost",
        "127.0.0.1",
    ]

    seen: set[str] = set()
    for host in raw_candidates:
        host = (host or "").strip()
        if not host or host in seen:
            continue
        seen.add(host)
        yield host


def connect_postgres(*, connect_timeout: int = 5, application_name: str | None = None):
    """Connect to Postgres with host fallbacks.

    This keeps containerized deployments resilient when the configured host name
    differs from the runtime DNS alias that is actually available.
    """
    base_url = settings.database_url
    errors: list[str] = []

    for host in _candidate_hosts():
        dsn = _rewrite_host(base_url, host)
        try:
            kwargs = {"connect_timeout": connect_timeout}
            if application_name:
                kwargs["application_name"] = application_name
            return psycopg2.connect(dsn, **kwargs)
        except Exception as exc:
            message = str(exc)
            errors.append(f"{host}: {message}")

            if not re.search(r"could not translate host name|Name or service not known", message, re.IGNORECASE):
                raise

            logger.warning("Postgres host lookup failed for %s, trying next candidate", host)

    raise psycopg2.OperationalError(
        "Unable to connect to Postgres using any configured host candidate: " + "; ".join(errors)
    )


# ---------------------------------------------------------------------------
# Connection pool (for the high-frequency metadata_db path)
#
# Why: metadata_db opened a brand-new psycopg2 connection for every query and
# closed it. Under the npz upload flow (hundreds of insert/update per video)
# that meant hundreds of TCP+auth handshakes. A ThreadedConnectionPool reuses
# connections instead.
#
# Fork-safety: Celery prefork forks worker children. psycopg2 connections are
# NOT fork-safe, so the pool is keyed by PID and rebuilt in each child on first
# use (the pool is created lazily during a task, i.e. after the fork).
# ---------------------------------------------------------------------------

_pool: _pg_pool.ThreadedConnectionPool | None = None
_pool_pid: int | None = None
_pool_lock = threading.Lock()


def _resolve_working_dsn(connect_timeout: int) -> str:
    """Find the first host candidate that actually accepts a connection.

    Resolved once when the pool is built so every pooled connection targets a
    host we know is reachable (keeps the existing Docker DNS-fallback behavior).
    """
    base_url = settings.database_url
    errors: list[str] = []
    for host in _candidate_hosts():
        dsn = _rewrite_host(base_url, host)
        try:
            probe = psycopg2.connect(dsn, connect_timeout=connect_timeout)
            probe.close()
            return dsn
        except Exception as exc:
            message = str(exc)
            errors.append(f"{host}: {message}")
            if not re.search(r"could not translate host name|Name or service not known", message, re.IGNORECASE):
                raise
    raise psycopg2.OperationalError(
        "Unable to resolve a working Postgres host for the pool: " + "; ".join(errors)
    )


def _build_pool() -> _pg_pool.ThreadedConnectionPool:
    minconn = max(1, int(getattr(settings, "db_pool_min", 1)))
    maxconn = max(minconn, int(getattr(settings, "db_pool_max", 8)))
    connect_timeout = int(getattr(settings, "db_connect_timeout", 5))
    dsn = _resolve_working_dsn(connect_timeout)
    logger.info("[DB_POOL] building pool min=%d max=%d pid=%d", minconn, maxconn, os.getpid())
    return _pg_pool.ThreadedConnectionPool(
        minconn,
        maxconn,
        dsn,
        connect_timeout=connect_timeout,
        application_name="voya_pool_metadata_db",
    )


def get_pool() -> _pg_pool.ThreadedConnectionPool:
    """Return the process-local pool, (re)building it after a fork."""
    global _pool, _pool_pid
    pid = os.getpid()
    if _pool is None or _pool_pid != pid:
        with _pool_lock:
            if _pool is None or _pool_pid != pid:
                # A pool inherited across fork must not be reused; drop the ref.
                _pool = _build_pool()
                _pool_pid = pid
    return _pool


def get_pooled_conn():
    """Borrow a connection from the process-local pool."""
    return get_pool().getconn()


def put_pooled_conn(conn, *, close: bool = False) -> None:
    """Return a connection to the pool (or discard it if broken)."""
    if conn is None:
        return
    try:
        pool = get_pool()
        # A closed/broken connection must not go back into the pool.
        broken = close or bool(getattr(conn, "closed", 0))
        pool.putconn(conn, close=broken)
    except Exception as exc:
        logger.warning("[DB_POOL] putconn failed (%s); closing connection", exc)
        try:
            conn.close()
        except Exception:
            pass
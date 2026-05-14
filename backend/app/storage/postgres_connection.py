from __future__ import annotations

import logging
import re
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

import psycopg2

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
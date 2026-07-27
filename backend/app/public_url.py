"""Where the app publicly lives — derived from the request, not from env.

The reset-password link used to be built from FRONTEND_BASE_URL. That is an
environment variable, and Docker cannot change a running container's env: every
time the public URL moved (a tunnel hands out a new hostname on each restart)
the mailed link kept pointing at a dead domain until someone edited .env and
RECREATED the backend. Nothing else in the stack needed that redeploy — nginx
has no server_name, there is no TrustedHostMiddleware, cookies are host-only and
the SPA calls relative paths — so this single env var was the only reason a
domain change was a deploy.

Deriving the origin from the incoming request removes it. The catch: Host is
attacker-controlled. A forged `Host: evil.example` on a forgot-password call
would mail the victim a VALID reset token pointing at the attacker's site
(host-header injection → account takeover). So a host is honored only when it
appears in an allowlist; anything else falls back to FRONTEND_BASE_URL.

Two allowlist sources, both consulted:
  1. PUBLIC_HOSTS_FILE — a text file read at REQUEST time (mtime-cached, so it
     costs one stat per call). The repo is bind-mounted into the container, so
     editing it on the host applies to the next request with NO restart. This is
     the one to touch when the tunnel hostname changes.
  2. FRONTEND_TRUSTED_HOST_SUFFIXES — comma-separated env var, for deployments
     that keep all configuration in .env (changing it needs the usual recreate).

Entry syntax in both: a leading dot means "any sub-domain under this"
(".ngrok-free.dev"); anything else must equal the hostname exactly
("se.cit.ctu.edu.vn"). Prefer exact hostnames. ngrok-free.dev is a SHARED public
suffix, so trusting the whole suffix also trusts every other ngrok user's
tunnel — which re-opens the exact hole the allowlist exists to close.
"""

from __future__ import annotations

import os
import re
import threading
from typing import List, Optional, Tuple

from app.config import settings

# hostname[:port] and nothing else. This value is interpolated into an email we
# send to a user, so anything carrying whitespace, CR/LF or a full URL is
# rejected outright rather than sanitized into something plausible-looking.
_HOST_RE = re.compile(r"^[a-z0-9.\-]+(:\d{1,5})?$")

_cache_lock = threading.Lock()
_cache: Tuple[Optional[float], List[str]] = (None, [])


def _file_entries() -> List[str]:
    """Allowlist from PUBLIC_HOSTS_FILE, re-read whenever the file changes.

    A missing/unreadable file means an EMPTY allowlist (fail closed → the
    configured FRONTEND_BASE_URL is used), never "trust everything".
    """
    global _cache

    path = settings.public_hosts_file
    if not path:
        return []
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return []

    with _cache_lock:
        cached_mtime, cached_entries = _cache
        if cached_mtime == mtime:
            return cached_entries

    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return []

    entries = [
        stripped.lower()
        for stripped in (line.strip() for line in lines)
        if stripped and not stripped.startswith("#")
    ]
    with _cache_lock:
        _cache = (mtime, entries)
    return entries


def allowed_hosts() -> List[str]:
    """Every allowlist entry, file first then env."""
    return _file_entries() + settings.frontend_trusted_host_suffixes


def _first_hop(raw: str) -> str:
    """First value of a possibly comma-chained forwarding header."""
    return raw.split(",")[0].strip()


def forwarded_proto(request) -> str:
    """Scheme the BROWSER used, not the one this process was reached over.

    TLS is terminated upstream (campus proxy / ngrok / cloudflared) and the
    gateway speaks plain HTTP to us, so request.url.scheme is always "http"
    here. The browser's real scheme arrives in X-Forwarded-Proto, which nginx
    passes through from the fronting proxy.
    """
    proto = _first_hop(request.headers.get("x-forwarded-proto", "")).lower()
    if proto in ("http", "https"):
        return proto
    return (request.url.scheme or "http").lower()


def request_is_https(request) -> bool:
    return forwarded_proto(request) == "https"


def request_host(request) -> str:
    """Public host as the browser addressed it (X-Forwarded-Host wins)."""
    for header in ("x-forwarded-host", "host"):
        value = _first_hop(request.headers.get(header, "")).lower()
        if value:
            return value
    return (request.url.netloc or "").lower()


def is_trusted_host(host: str) -> bool:
    if not host or not _HOST_RE.match(host):
        return False
    hostname = host.rsplit(":", 1)[0] if ":" in host else host
    for entry in allowed_hosts():
        if entry.startswith("."):
            if hostname.endswith(entry):
                return True
        elif hostname == entry:
            return True
    return False


def resolve_frontend_base_url(request) -> str:
    """Public origin (+ sub-path) for links we email out.

    Falls back to the configured FRONTEND_BASE_URL whenever the request's host
    is not allowlisted — which is also what happens for requests that carry no
    usable Host at all.
    """
    configured = (settings.frontend_base_url or "").rstrip("/")
    host = request_host(request)
    if not is_trusted_host(host):
        return configured
    # A sub-path deploy (/voya) is stripped by the gateway before the backend
    # sees the path, so it cannot be recovered from the request — take it from
    # the same setting the cookies are scoped with.
    prefix = (settings.cookie_path_prefix or "").rstrip("/")
    return f"{forwarded_proto(request)}://{host}{prefix}"

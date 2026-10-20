"""The emailed reset link follows the request's host — but only a trusted one.

Two failures this guards, in opposite directions:

  1. Operational: a tunnel hands out a new hostname on every restart. If the
     link came from FRONTEND_BASE_URL (env, frozen at container start) it kept
     pointing at the dead one until someone recreated the backend.

  2. Security: Host is caller-controlled. `Host: evil.example` on a
     forgot-password call must NOT produce an email carrying a valid reset
     token that points at the attacker — that is account takeover by one
     header. Unknown hosts fall back to the configured base URL.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from starlette.requests import Request

from app import public_url


def _request(host: str | None, *, proto: str | None = None,
             forwarded_host: str | None = None, scheme: str = "http") -> Request:
    headers = []
    if host is not None:
        headers.append((b"host", host.encode()))
    if forwarded_host is not None:
        headers.append((b"x-forwarded-host", forwarded_host.encode()))
    if proto is not None:
        headers.append((b"x-forwarded-proto", proto.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/forgot-password",
            "query_string": b"",
            "headers": headers,
            "scheme": scheme,
            "server": ("backend", 8000),
        }
    )


@pytest.fixture
def allowlist(tmp_path):
    """Point the file allowlist at a temp file; return a writer for its entries."""
    path = tmp_path / "public_hosts.txt"

    def write(*entries: str) -> None:
        path.write_text("# comment line\n\n" + "\n".join(entries) + "\n", encoding="utf-8")

    write()
    with patch.object(public_url.settings, "public_hosts_file", str(path)), \
         patch.object(public_url.settings, "frontend_trusted_host_suffixes_raw", ""), \
         patch.object(public_url.settings, "frontend_base_url", "https://configured.example"), \
         patch.object(public_url.settings, "cookie_path_prefix", ""):
        # The module caches by mtime; a fresh temp path per test invalidates it.
        yield write


# ===========================================================================
# the operational half: allowlisted host defines the link
# ===========================================================================

def test_trusted_host_defines_the_link(allowlist):
    allowlist("frolic-fifteen-debating.ngrok-free.dev")
    req = _request("frolic-fifteen-debating.ngrok-free.dev", proto="https")
    assert public_url.resolve_frontend_base_url(req) == \
        "https://frolic-fifteen-debating.ngrok-free.dev"


def test_editing_the_file_takes_effect_without_restart(allowlist):
    """The whole point: no process restart between these two calls."""
    req = _request("moved-tunnel.ngrok-free.dev", proto="https")
    assert public_url.resolve_frontend_base_url(req) == "https://configured.example"

    allowlist("moved-tunnel.ngrok-free.dev")
    assert public_url.resolve_frontend_base_url(req) == "https://moved-tunnel.ngrok-free.dev"


def test_scheme_comes_from_forwarded_proto_not_the_local_hop(allowlist):
    """nginx reaches the backend over plain HTTP even on an HTTPS deploy."""
    allowlist("app.example.com")
    req = _request("app.example.com", proto="https", scheme="http")
    assert public_url.resolve_frontend_base_url(req).startswith("https://")


def test_forwarded_proto_chain_uses_first_hop(allowlist):
    allowlist("app.example.com")
    req = _request("app.example.com", proto="https, http")
    assert public_url.resolve_frontend_base_url(req) == "https://app.example.com"


def test_plain_http_deploy_keeps_http(allowlist):
    allowlist("localhost")
    req = _request("localhost", scheme="http")
    assert public_url.resolve_frontend_base_url(req) == "http://localhost"


def test_port_is_preserved(allowlist):
    allowlist("localhost")
    req = _request("localhost:8080")
    assert public_url.resolve_frontend_base_url(req) == "http://localhost:8080"


def test_subpath_deploy_keeps_its_prefix(allowlist):
    """The gateway strips /voya before we see the path — take it from config."""
    allowlist("se.cit.ctu.edu.vn")
    with patch.object(public_url.settings, "cookie_path_prefix", "/voya"):
        req = _request("se.cit.ctu.edu.vn", proto="https")
        assert public_url.resolve_frontend_base_url(req) == "https://se.cit.ctu.edu.vn/voya"


def test_forwarded_host_wins_over_host(allowlist):
    allowlist("public.example.com")
    req = _request("backend:8000", forwarded_host="public.example.com", proto="https")
    assert public_url.resolve_frontend_base_url(req) == "https://public.example.com"


def test_env_suffix_list_is_also_honored(allowlist):
    """Second source, for deployments that keep config in .env only."""
    with patch.object(public_url.settings, "frontend_trusted_host_suffixes_raw",
                      ".ngrok-free.dev, localhost"):
        req = _request("anything.ngrok-free.dev", proto="https")
        assert public_url.resolve_frontend_base_url(req) == "https://anything.ngrok-free.dev"


def test_host_matching_is_case_insensitive(allowlist):
    allowlist("app.example.com")
    req = _request("APP.Example.COM", proto="https")
    assert public_url.resolve_frontend_base_url(req) == "https://app.example.com"


# ===========================================================================
# the security half: everything else falls back
# ===========================================================================

def test_forged_host_falls_back_to_configured_base_url(allowlist):
    allowlist("frolic-fifteen-debating.ngrok-free.dev")
    req = _request("evil.example", proto="https")
    assert public_url.resolve_frontend_base_url(req) == "https://configured.example"


def test_lookalike_host_does_not_match_a_suffix_entry(allowlist):
    """"evil-ngrok-free.dev" must not satisfy ".ngrok-free.dev"."""
    allowlist(".ngrok-free.dev")
    req = _request("evil-ngrok-free.dev", proto="https")
    assert public_url.resolve_frontend_base_url(req) == "https://configured.example"


def test_suffix_entry_does_not_match_a_prefix_collision(allowlist):
    allowlist("app.example.com")
    req = _request("app.example.com.evil.test", proto="https")
    assert public_url.resolve_frontend_base_url(req) == "https://configured.example"


@pytest.mark.parametrize("host", [
    "app.example.com/../evil",          # path smuggled into the host
    "app.example.com evil.test",        # space
    "app.example.com\tevil",            # tab
    "https://app.example.com",          # a whole URL
    "",                                 # empty
])
def test_malformed_hosts_are_rejected(allowlist, host):
    allowlist("app.example.com")
    req = _request(host)
    assert public_url.resolve_frontend_base_url(req) == "https://configured.example"


def test_missing_allowlist_file_trusts_nothing(allowlist, tmp_path):
    with patch.object(public_url.settings, "public_hosts_file",
                      str(tmp_path / "does-not-exist.txt")):
        req = _request("app.example.com", proto="https")
        assert public_url.resolve_frontend_base_url(req) == "https://configured.example"


def test_empty_allowlist_trusts_nothing(allowlist):
    allowlist()  # only a comment and blank lines
    req = _request("app.example.com", proto="https")
    assert public_url.resolve_frontend_base_url(req) == "https://configured.example"


def test_comments_are_not_treated_as_hosts(allowlist, tmp_path):
    path = tmp_path / "public_hosts.txt"
    path.write_text("#app.example.com\n", encoding="utf-8")
    with patch.object(public_url.settings, "public_hosts_file", str(path)):
        req = _request("app.example.com", proto="https")
        assert public_url.resolve_frontend_base_url(req) == "https://configured.example"


def test_utf8_bom_does_not_break_the_first_entry(allowlist, tmp_path):
    """Notepad saves UTF-8 with a BOM, and this file is edited by hand.

    The BOM prefixes the FIRST line — the first hostname — so a plain utf-8
    read silently turns it into an entry that can never match, with the only
    symptom being links that keep using the fallback URL.
    """
    path = tmp_path / "public_hosts.txt"
    path.write_text("app.example.com\n", encoding="utf-8-sig")
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with patch.object(public_url.settings, "public_hosts_file", str(path)):
        req = _request("app.example.com", proto="https")
        assert public_url.resolve_frontend_base_url(req) == "https://app.example.com"


# ===========================================================================
# scheme detection (also drives the Secure cookie flag)
# ===========================================================================

@pytest.mark.parametrize("proto,scheme,expected", [
    ("https", "http", True),      # behind a TLS-terminating proxy
    ("http", "http", False),
    (None, "https", True),        # direct TLS, no proxy header
    (None, "http", False),
    ("garbage", "http", False),   # unusable header → fall back to the real hop
])
def test_request_is_https(proto, scheme, expected):
    assert public_url.request_is_https(_request("h.example", proto=proto, scheme=scheme)) is expected

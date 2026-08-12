"""Who the app thinks you are, when a proxy is telling it.

client_ip() is not a logging nicety. Its return value keys the per-IP flood
block, the generic per-IP limiter, and activity.get_block() — the list of
addresses an admin has banned. Anything a caller can choose here, a caller can
use to reset all three on every request.

Two rules carry that weight:

  1. A forwarding header is believed ONLY when the TCP peer is one of our own
     proxies (TRUSTED_PROXIES). Reached directly, the headers are somebody's
     unverified claim about themselves.
  2. Behind a trusted proxy, X-Real-IP wins because the nginx gateway overwrites
     it on every proxied location (the $rl_client map in nginx.conf). X-Forwarded
     -For is read RIGHT TO LEFT past our own proxies, because every hop APPENDS:
     Cloudflare adds the real client behind whatever arrived, so a forged
     "X-Forwarded-For: 1.2.3.4" lands as "1.2.3.4, <real client>" and the
     leftmost entry is the attacker's.
"""

from __future__ import annotations

import pytest

from starlette.requests import Request

from app.rate_limit import client_ip


def _request(*, real_ip: str | None = None, xff: str | None = None,
             peer: str | None = "10.0.0.9") -> Request:
    headers = []
    if real_ip is not None:
        headers.append((b"x-real-ip", real_ip.encode()))
    if xff is not None:
        headers.append((b"x-forwarded-for", xff.encode()))
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "query_string": b"",
        "headers": headers,
        "scheme": "http",
        "server": ("backend", 8000),
    }
    if peer is not None:
        scope["client"] = (peer, 51234)
    return Request(scope)


# ===========================================================================
# the security property
# ===========================================================================

def test_forged_forwarded_for_cannot_outrank_the_gateway():
    """The Cloudflare case, stated exactly.

    The caller sent "X-Forwarded-For: 1.2.3.4"; Cloudflare appended the real
    address behind it and nginx stamped that same real address into X-Real-IP.
    The attacker-chosen first hop must lose.
    """
    req = _request(real_ip="203.0.113.7", xff="1.2.3.4, 203.0.113.7")
    assert client_ip(req) == "203.0.113.7"


def test_rotating_a_fake_first_hop_does_not_change_identity():
    """Whole point of the fix: the ban/lockout key must stay put.

    Three requests from one attacker, each with a different forged first hop,
    must all resolve to the SAME identity — otherwise every request looks like
    a new client and no per-IP limit can ever accumulate.
    """
    seen = {
        client_ip(_request(real_ip="203.0.113.7", xff=f"{fake}, 203.0.113.7"))
        for fake in ("1.2.3.4", "5.6.7.8", "9.10.11.12")
    }
    assert seen == {"203.0.113.7"}


def test_x_real_ip_wins_even_when_forwarded_for_is_a_single_value():
    req = _request(real_ip="203.0.113.7", xff="1.2.3.4")
    assert client_ip(req) == "203.0.113.7"


# ===========================================================================
# fallbacks — the campus-proxy deploy has no Cloudflare in front
# ===========================================================================

def test_falls_back_to_forwarded_for_when_no_real_ip():
    """Deployments where something upstream sets only X-Forwarded-For.

    Still better than the socket peer, which behind the campus proxy is the
    proxy itself — shared by every user on campus.
    """
    req = _request(real_ip=None, xff="198.51.100.4, 172.16.0.1")
    assert client_ip(req) == "198.51.100.4"


def test_falls_back_to_socket_peer_when_no_headers():
    assert client_ip(_request(real_ip=None, xff=None)) == "10.0.0.9"


def test_unknown_when_there_is_nothing_at_all():
    """A test client / ASGI caller with no peer must not raise."""
    assert client_ip(_request(real_ip=None, xff=None, peer=None)) == "unknown"


# ===========================================================================
# malformed input — a header that is present but useless must not win
# ===========================================================================

@pytest.mark.parametrize("real_ip", ["", "   ", ","])
def test_empty_real_ip_falls_through_instead_of_returning_blank(real_ip):
    """An empty X-Real-IP must not become the identity.

    Returning "" would collapse every such caller into one bucket, which is
    the opposite of the intent: one shared key means one shared rate limit.
    """
    req = _request(real_ip=real_ip, xff="198.51.100.4")
    assert client_ip(req) == "198.51.100.4"


def test_whitespace_is_stripped():
    assert client_ip(_request(real_ip="  203.0.113.7  ")) == "203.0.113.7"


def test_real_ip_with_a_chain_takes_the_first_hop():
    """X-Real-IP should be a single address; be defensive if it is not."""
    assert client_ip(_request(real_ip="203.0.113.7, 172.16.0.1")) == "203.0.113.7"


# ===========================================================================
# trusted-proxy gate — a header is only evidence when OUR proxy sent it
# ===========================================================================

def test_headers_are_ignored_when_the_peer_is_not_our_proxy():
    """Reached directly, both headers are the caller talking about themselves.

    The backend is not published (compose uses `expose`), so this should not
    happen — but if it ever does, believing the header would hand every limiter
    and the admin ban list a free reset per request.
    """
    req = _request(real_ip="203.0.113.7", xff="1.2.3.4", peer="198.51.100.77")
    assert client_ip(req) == "198.51.100.77"


def test_non_ip_peer_is_not_trusted():
    """An ASGI caller with a name instead of an address (starlette's TestClient
    uses "testclient") must not unlock the headers either."""
    req = _request(real_ip="203.0.113.7", xff="1.2.3.4", peer="testclient")
    assert client_ip(req) == "testclient"


def test_chain_of_only_trusted_hops_falls_back_to_the_peer():
    """Nothing in the chain identifies an outside client, so don't invent one."""
    req = _request(real_ip=None, xff="10.1.2.3, 172.16.0.1", peer="10.0.0.9")
    assert client_ip(req) == "10.0.0.9"


def test_rightmost_untrusted_hop_wins_over_a_forged_one_on_the_left():
    """Two proxies deep: "<forged>, <real client>, <our edge>".

    Reading left-to-right would return the forged entry; reading right-to-left
    past our own proxy returns the real client.
    """
    req = _request(real_ip=None, xff="1.2.3.4, 198.51.100.4, 10.0.0.5", peer="10.0.0.9")
    assert client_ip(req) == "198.51.100.4"

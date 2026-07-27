"""The refresh cookie's Path must carry the deploy's sub-path prefix.

Bug this guards: under /voya the gateway strips "/voya" before the backend sees
the request, but the BROWSER still sends the refresh call to
"/voya/api/v1/auth/refresh". If the cookie Path stays "/api/v1/auth", the browser
never sends it back → the session cannot refresh → users get logged out every
time the access token expires. COOKIE_PATH_PREFIX fixes that.
"""

from __future__ import annotations

from unittest.mock import patch

from fastapi import Response

from app import cookie_auth


def _set_cookie_headers(resp: Response) -> list[str]:
    return [v.decode() for k, v in resp.raw_headers if k == b"set-cookie"]


def test_refresh_path_is_root_scoped_by_default():
    with patch.object(cookie_auth.settings, "cookie_path_prefix", ""):
        assert cookie_auth.refresh_cookie_path() == "/api/v1/auth"


def test_refresh_path_honors_subpath_prefix():
    with patch.object(cookie_auth.settings, "cookie_path_prefix", "/voya"):
        assert cookie_auth.refresh_cookie_path() == "/voya/api/v1/auth"


def test_refresh_path_tolerates_trailing_slash():
    with patch.object(cookie_auth.settings, "cookie_path_prefix", "/voya/"):
        assert cookie_auth.refresh_cookie_path() == "/voya/api/v1/auth"


def test_set_auth_cookies_scopes_refresh_under_prefix_but_others_at_root():
    with patch.object(cookie_auth.settings, "cookie_path_prefix", "/voya"):
        resp = Response()
        cookie_auth.set_auth_cookies(
            resp, access_token="a", refresh_token="r", csrf_token="c"
        )
    headers = _set_cookie_headers(resp)
    refresh = next(h for h in headers if h.startswith(f"{cookie_auth.REFRESH_COOKIE}="))
    access = next(h for h in headers if h.startswith(f"{cookie_auth.ACCESS_COOKIE}="))

    # Refresh cookie must sit under /voya so the browser sends it on refresh.
    assert "Path=/voya/api/v1/auth" in refresh
    assert refresh.split(";")[0].endswith("=r")
    # Access (and csrf/hint) stay at root so they apply to the whole SPA.
    assert "Path=/;" in access or access.rstrip().endswith("Path=/")


def test_clear_auth_cookies_deletes_refresh_at_same_prefixed_path():
    with patch.object(cookie_auth.settings, "cookie_path_prefix", "/voya"):
        resp = Response()
        cookie_auth.clear_auth_cookies(resp)
    headers = _set_cookie_headers(resp)
    refresh = next(h for h in headers if h.startswith(f"{cookie_auth.REFRESH_COOKIE}="))
    # Deletion must target the SAME path it was set with, or the cookie lingers.
    assert "Path=/voya/api/v1/auth" in refresh

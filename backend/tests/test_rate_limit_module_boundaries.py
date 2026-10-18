import pytest
from fastapi import HTTPException
from starlette.requests import Request


class FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}
        self.deleted = []

    def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def expire(self, key, seconds):
        self.ttls[key] = seconds

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def get(self, key):
        return self.values.get(key)

    def delete(self, *keys):
        self.deleted.append(keys)
        for key in keys:
            self.values.pop(key, None)


def _request(*headers):
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/login",
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers],
        "client": ("10.0.0.8", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    })


def test_rate_limit_facade_and_identity_exports_component_callables():
    from app import rate_limit
    from app.infrastructure.redis import connection
    from app.modules.identity import api as identity_api
    from app.modules.security import rate_limits

    assert connection.get_activity_client is connection.get_redis_client
    assert rate_limit._client is connection.get_redis_client
    assert rate_limit.check_login_allowed is rate_limits.check_login_allowed
    assert rate_limit.enforce_ip_limit is rate_limits.enforce_ip_limit
    assert identity_api.check_login_allowed is rate_limits.check_login_allowed
    assert identity_api.reset_login_attempts is rate_limits.reset_login_attempts


def test_login_limit_preserves_keys_window_and_reset(monkeypatch):
    from app.modules.security import rate_limits

    redis = FakeRedis()
    monkeypatch.setattr(rate_limits, "get_redis_client", lambda: redis)

    rate_limits.register_failed_login("203.0.113.9", "  User@Example.COM ")

    ip_key = "ratelimit:login:ip:203.0.113.9"
    identifier_key = "ratelimit:login:id:user@example.com"
    assert redis.values == {ip_key: 1, identifier_key: 1}
    assert redis.ttls == {
        ip_key: rate_limits.LOGIN_WINDOW_SECONDS,
        identifier_key: rate_limits.LOGIN_WINDOW_SECONDS,
    }

    redis.values[identifier_key] = rate_limits.LOGIN_MAX_ATTEMPTS
    redis.ttls[identifier_key] = 42
    with pytest.raises(HTTPException) as exc_info:
        rate_limits.check_login_allowed("203.0.113.9", "USER@example.com")
    assert exc_info.value.status_code == 429
    assert exc_info.value.headers == {"Retry-After": "42"}

    rate_limits.reset_login_attempts("203.0.113.9", "User@Example.com")
    assert redis.deleted[-1] == (ip_key, identifier_key)


def test_generic_ip_limit_uses_first_forwarded_hop(monkeypatch):
    from app.modules.security import rate_limits

    redis = FakeRedis()
    monkeypatch.setattr(rate_limits, "get_redis_client", lambda: redis)
    request = _request(("x-forwarded-for", "198.51.100.7, 10.0.0.1"))

    rate_limits.enforce_ip_limit(request, "forgot", max_calls=1, window=60)
    with pytest.raises(HTTPException) as exc_info:
        rate_limits.enforce_ip_limit(request, "forgot", max_calls=1, window=60)

    assert rate_limits.client_ip(request) == "198.51.100.7"
    assert redis.values["ratelimit:forgot:ip:198.51.100.7"] == 2
    assert exc_info.value.headers == {"Retry-After": "60"}


def test_rate_limits_fail_open_without_redis(monkeypatch):
    from app.modules.security import rate_limits

    monkeypatch.setattr(rate_limits, "get_redis_client", lambda: None)

    rate_limits.check_login_allowed("203.0.113.10", "user")
    rate_limits.register_failed_login("203.0.113.10", "user")
    rate_limits.reset_login_attempts("203.0.113.10", "user")
    rate_limits.enforce_ip_limit(_request(), "register", max_calls=1, window=60)

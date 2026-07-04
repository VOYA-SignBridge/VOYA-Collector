"""Characterization tests — legacy Auth API (GĐ 0, Roadmap v2 §7.5).

Captures CURRENT behaviour of the legacy app as a safety net for the
Strangler-Fig migration. If one of these fails after a refactor, the
refactor changed observable behaviour — stop and check.
Behaviour snapshot taken 2026-07 (see erd_v2_unified_design.md).

NOTE: DB-dependent auth cases (e.g. "login sai mật khẩu → 401") do NOT
belong here — they are GĐ 2 integration tests (Roadmap v2 §7.5), where a
dev-stack PostgreSQL is guaranteed and its absence must FAIL, not skip.
"""


class TestLoginValidation:
    def test_login_with_empty_body_returns_422(self, client):
        r = client.post("/api/v1/auth/login", json={})
        assert r.status_code == 422
        missing = {e["loc"][-1] for e in r.json()["detail"]}
        assert missing == {"identifier", "password"}

    def test_login_without_password_returns_422(self, client):
        r = client.post("/api/v1/auth/login", json={"identifier": "someone"})
        assert r.status_code == 422
        assert r.json()["detail"][0]["loc"] == ["body", "password"]

    def test_register_with_empty_body_returns_422(self, client):
        r = client.post("/api/v1/auth/register", json={})
        assert r.status_code == 422


class TestAuthGuard:
    def test_me_without_token_returns_401(self, client):
        r = client.get("/api/v1/auth/me")
        assert r.status_code == 401
        assert r.json() == {"detail": "Not authenticated"}

    def test_me_with_garbage_token_is_rejected(self, client):
        r = client.get(
            "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert r.status_code == 401

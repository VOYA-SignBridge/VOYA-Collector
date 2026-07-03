"""Characterization tests — legacy Upload API (GĐ 0, Roadmap v2 §7.5).

The legacy upload path is Browser → FastAPI multipart → disk → Drive.
Roadmap v2 GĐ 3 replaces it with presigned direct-to-MinIO (§11.5);
these tests pin the legacy contract until then.
"""


class TestUploadGuard:
    def test_upload_video_without_token_returns_401(self, client):
        r = client.post("/api/v1/upload/video")
        assert r.status_code == 401
        assert r.json() == {"detail": "Not authenticated"}

    def test_upload_camera_without_token_returns_401(self, client):
        r = client.post("/api/v1/upload/camera")
        assert r.status_code == 401

    def test_camera_preflight_options_is_open(self, client):
        # CORS preflight helper must NOT require auth (mobile Safari quirk).
        r = client.options("/upload/camera")
        assert r.status_code == 200
        assert r.json() == {"success": True}


class TestRouteInventory:
    """Snapshot of legacy upload/session routes the frontend depends on.

    If a route disappears from this list during refactoring, the FE breaks.
    """

    def test_expected_routes_exist(self, client):
        spec = client.get("/openapi.json")
        assert spec.status_code == 200
        paths = set(spec.json()["paths"].keys())
        expected = {
            "/api/v1/upload/video",
            "/api/v1/upload/camera",
            "/api/v1/classes/list",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/auth/me",
            "/api/v1/trash/samples",
            "/api/v1/health/live",
        }
        missing = expected - paths
        assert not missing, f"legacy routes disappeared: {missing}"

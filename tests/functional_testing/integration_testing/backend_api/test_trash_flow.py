"""Characterization tests — legacy Trash API (GĐ 0, Roadmap v2 §7.5).

Trash = soft delete (`deleted_at`), restore, and admin-only hard delete.
Every trash endpoint requires authentication.
"""


class TestTrashRequiresAuth:
    def test_list_trashed_samples_without_token_returns_401(self, client):
        r = client.get("/api/v1/trash/samples")
        assert r.status_code == 401
        assert r.json() == {"detail": "Not authenticated"}

    def test_list_trashed_classes_without_token_returns_401(self, client):
        r = client.get("/api/v1/trash/classes")
        assert r.status_code == 401

    def test_soft_delete_sample_without_token_returns_401(self, client):
        r = client.delete("/api/v1/trash/samples/some-sample-uid")
        assert r.status_code == 401

    def test_restore_sample_without_token_returns_401(self, client):
        r = client.post("/api/v1/trash/samples/some-sample-uid/restore")
        assert r.status_code == 401

    def test_hard_delete_sample_without_token_returns_401(self, client):
        r = client.delete("/api/v1/trash/samples/some-sample-uid/hard")
        assert r.status_code == 401

    def test_hard_delete_class_without_token_returns_401(self, client):
        r = client.delete("/api/v1/trash/classes/some-class/hard")
        assert r.status_code == 401


class TestHealth:
    def test_liveness_is_open_and_alive(self, client):
        r = client.get("/api/v1/health/live")
        assert r.status_code == 200
        assert r.json()["status"] == "alive"

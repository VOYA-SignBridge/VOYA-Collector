"""Characterization tests — legacy Labels/Classes API (GĐ 0, Roadmap v2 §7.5).

`GET /classes/list` reads the CSV catalog (no DB needed) — this is the
current source of truth for labels in the legacy app.
"""


class TestListLabels:
    def test_list_returns_200_with_count_and_items(self, client):
        r = client.get("/api/v1/classes/list")
        assert r.status_code == 200
        body = r.json()
        assert set(body.keys()) >= {"count", "items"}
        assert isinstance(body["items"], list)
        assert body["count"] == len(body["items"])

    def test_list_items_carry_legacy_catalog_fields(self, client):
        r = client.get("/api/v1/classes/list")
        items = r.json()["items"]
        if not items:  # empty catalog is a valid state on a fresh checkout
            return
        first = items[0]
        # Legacy CSV columns (LABEL_FIELDS in dataset_manager.py)
        assert {"class_uid", "slug", "label_original"} <= set(first.keys())

    def test_unversioned_alias_matches_v1(self, client):
        # Legacy serves the same router with and without /api/v1 prefix.
        r_plain = client.get("/classes/list")
        r_v1 = client.get("/api/v1/classes/list")
        assert r_plain.status_code == r_v1.status_code == 200
        assert r_plain.json()["count"] == r_v1.json()["count"]


class TestMutationsRequireAuth:
    def test_update_label_without_token_returns_401(self, client):
        r = client.put("/api/v1/classes/some-class", json={"label": "x"})
        assert r.status_code == 401
        assert r.json() == {"detail": "Not authenticated"}

    def test_delete_label_without_token_returns_401(self, client):
        r = client.delete("/api/v1/classes/some-class")
        assert r.status_code == 401

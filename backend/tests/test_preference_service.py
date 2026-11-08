"""Behavior and boundary tests for file-backed web preferences."""

from __future__ import annotations

import json

from app.routers import classes as classes_router
from app.services import preferences


def test_set_value_preserves_existing_preferences(tmp_path) -> None:
    path = tmp_path / "user_preferences.json"
    path.write_text(
        json.dumps({"languageSelected": "vn"}),
        encoding="utf-8",
    )

    preferences.set_value("dialectSelected", "hoa-de", path=path)

    assert preferences.load_preferences(path) == {
        "languageSelected": "vn",
        "dialectSelected": "hoa-de",
    }


def test_load_preferences_fails_open_for_invalid_json(tmp_path) -> None:
    path = tmp_path / "user_preferences.json"
    path.write_text("not-json", encoding="utf-8")

    assert preferences.load_preferences(path) == {}
    assert preferences.get_value("languageSelected", path=path) is None


def test_scoped_preferences_preserve_legacy_fallback(tmp_path) -> None:
    path = tmp_path / "user_preferences.json"
    path.write_text(json.dumps({"languageSelected": "vn"}), encoding="utf-8")

    assert preferences.get_scoped_value(
        "school-a::user-7", "languageSelected", path=path
    ) == "vn"

    preferences.set_scoped_value(
        "school-a::user-7", "languageSelected", "en", path=path
    )

    assert preferences.get_scoped_value(
        "school-a::user-7", "languageSelected", path=path
    ) == "en"
    assert preferences.load_preferences(path)["languageSelected"] == "vn"


def test_classes_router_partitions_preferences_by_tenant_and_user(monkeypatch) -> None:
    user = {"tenant_id": "school-a", "id": "user-7"}
    reads = []
    writes = []
    monkeypatch.setattr(
        classes_router.preferences,
        "get_scoped_value",
        lambda bucket, key: reads.append((bucket, key)) or "vn",
    )
    monkeypatch.setattr(
        classes_router.preferences,
        "set_scoped_value",
        lambda bucket, key, value: writes.append((bucket, key, value)),
    )

    assert classes_router.get_preference("languageSelected", current_user=user) == {
        "key": "languageSelected",
        "value": "vn",
    }
    assert classes_router.set_preference(
        {"key": "dialectSelected", "value": "common"}, current_user=user
    ) == {
        "success": True,
        "key": "dialectSelected",
        "value": "common",
    }
    assert reads == [("school-a::user-7", "languageSelected")]
    assert writes == [("school-a::user-7", "dialectSelected", "common")]

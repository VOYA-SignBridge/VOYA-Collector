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


def test_classes_router_delegates_preferences_to_service(monkeypatch) -> None:
    monkeypatch.setattr(preferences, "get_value", lambda key: f"saved:{key}")
    writes = []
    monkeypatch.setattr(
        preferences,
        "set_value",
        lambda key, value: writes.append((key, value)),
    )

    assert classes_router.get_preference("languageSelected") == {
        "key": "languageSelected",
        "value": "saved:languageSelected",
    }
    assert classes_router.set_preference({"key": "dialectSelected", "value": "common"}) == {
        "success": True,
        "key": "dialectSelected",
        "value": "common",
    }
    assert writes == [("dialectSelected", "common")]

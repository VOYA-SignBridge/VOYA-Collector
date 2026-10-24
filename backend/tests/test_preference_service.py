"""Behavior and boundary tests for file-backed web preferences."""

from __future__ import annotations

import json
from contextlib import nullcontext

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


def test_classes_router_partitions_preferences_by_tenant_and_user(monkeypatch) -> None:
    user = {"tenant_id": "school-a", "id": "user-7"}
    stored = {"school-a::user-7": {"languageSelected": "vn"}}
    writes = []
    monkeypatch.setattr(classes_router, "_load_prefs", lambda: stored)
    monkeypatch.setattr(classes_router, "_save_prefs", lambda value: writes.append(value))
    monkeypatch.setattr(classes_router, "FileLock", lambda _path: nullcontext())

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
    assert writes == [{
        "school-a::user-7": {
            "languageSelected": "vn",
            "dialectSelected": "common",
        }
    }]

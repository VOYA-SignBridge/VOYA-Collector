from __future__ import annotations

import json

import pytest

from app.modules.dataset import preparation_service, split_selection
from app.modules.training import tasks as training_tasks


def test_training_tasks_reexport_dataset_split_helpers():
    assert training_tasks._deployment_splits.__module__ == "app.modules.training.tasks"
    assert training_tasks._deployment_split_for.__module__ == "app.modules.training.tasks"


def test_deployment_split_selection_prefers_newest_covering_candidate(tmp_path):
    versions = tmp_path / "processed" / "splits" / "versions"
    for version in (2, 12):
        directory = versions / f"alphabet_deploy_v{version}"
        directory.mkdir(parents=True)
        for part in ("train", "val", "test"):
            (directory / f"{part}.csv").write_text(
                "dialect,class_idx\nalphabet,1\n",
                encoding="utf-8",
            )
        (directory / "split_metadata.json").write_text(
            json.dumps({"recognition_profile": "alphabet"}),
            encoding="utf-8",
        )

    selected = split_selection.deployment_split_for(["alphabet"], tmp_path)
    assert selected is not None
    assert selected["split_version"] == "alphabet_deploy_v12"


def test_queue_preparation_persists_before_dispatch():
    events = []

    result = preparation_service.queue_preparation(
        dialects=["hoa-de"],
        profiles=None,
        seed=7,
        profiles_for_dialects=lambda dialects: (["hoa_de"], []),
        next_version=lambda: "isds2026_v99",
        create_report=lambda *args: events.append(("report", args)),
        dispatch=lambda **kwargs: events.append(("dispatch", kwargs)),
    )

    assert [event[0] for event in events] == ["report", "dispatch"]
    assert result["manifest_version"] == "isds2026_v99"
    assert result["profiles"] == ["hoa_de"]


def test_queue_preparation_rejects_dialects_without_profiles():
    with pytest.raises(preparation_service.UnsupportedDialectsError) as raised:
        preparation_service.queue_preparation(
            dialects=["unknown"],
            profiles=None,
            seed=42,
            profiles_for_dialects=lambda dialects: ([], dialects),
        )
    assert raised.value.dialects == ["unknown"]

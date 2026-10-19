from __future__ import annotations

import pytest

from app.modules.training import inference_service
from app.routers import training as training_router


def test_router_reexports_inference_compatibility_symbols():
    assert training_router._MODEL_NAME_TO_REGISTRY_KEY is inference_service._MODEL_NAME_TO_REGISTRY_KEY
    assert training_router._import_models_registry is inference_service._import_models_registry
    assert training_router._load_model_from_checkpoint is inference_service._load_model_from_checkpoint


def test_resolve_label_accepts_rich_checkpoint_entry(tmp_path):
    checkpoint = {
        "idx_to_label": {
            "2": {"label_key": "vn/hoa-de/rang-muoi", "label_original": "Răng mười"}
        }
    }

    assert inference_service._resolve_label(checkpoint, 2, tmp_path / "missing.csv") == (
        "vn/hoa-de/rang-muoi",
        "Răng mười",
    )


def test_resolve_label_uses_csv_for_legacy_string_entry(tmp_path):
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text(
        "slug,label_original\nhello,Xin chào\n",
        encoding="utf-8",
    )

    assert inference_service._resolve_label(
        {"idx_to_label": ["vn/hello"]},
        0,
        labels_csv,
    ) == ("vn/hello", "Xin chào")


def test_predict_rejects_invalid_window_before_loading_model(tmp_path, monkeypatch):
    def fail_if_called(*args, **kwargs):
        raise AssertionError("model loader must not run for an invalid frame shape")

    monkeypatch.setattr(inference_service, "_load_model_from_checkpoint", fail_if_called)
    with pytest.raises(ValueError, match=r"Expected shape \(60, 126\)"):
        inference_service.predict_checkpoint(
            tmp_path / "model.pt",
            [[0.0]],
            workspace_root=tmp_path,
            labels_csv=tmp_path / "labels.csv",
        )

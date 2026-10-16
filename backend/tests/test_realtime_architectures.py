"""Guards for multi-architecture serving in the realtime inference service.

The checkpoint `model_type` -> registry-key table is duplicated: the backend uses
it to decide whether a job may be promoted, the realtime service uses it to build
the architecture. If the two drift, promotion accepts a checkpoint the serving
path then refuses, which surfaces as a failed promote instead of a clear message.
These tests pin them together and to the training registry they both target.
"""

from __future__ import annotations

import pytest

from app.routers.training import _MODEL_NAME_TO_REGISTRY_KEY as BACKEND_MAP
from realtime_service.app.model_loader import _MODEL_NAME_TO_REGISTRY_KEY as REALTIME_MAP


def test_backend_and_realtime_agree_on_architecture_names():
    assert BACKEND_MAP == REALTIME_MAP, (
        "promotion gate and serving path disagree about which model_type values "
        "are servable"
    )


def test_every_mapped_key_exists_in_the_training_registry():
    from processed.train_utils.models import MODEL_REGISTRY

    unknown = sorted(set(REALTIME_MAP.values()) - set(MODEL_REGISTRY))
    assert not unknown, f"mapped to registry keys that do not exist: {unknown}"


def test_all_trained_architectures_are_servable():
    """Every architecture the platform can train must be promotable.

    A model that can be trained through the web UI but never deployed is the gap
    this test exists to prevent reappearing.
    """
    from processed.train_utils.models import MODEL_REGISTRY

    # Registry aliases (hdgcn/hd_gcn) collapse onto the same class as handgcn.
    trainable = {key for key in MODEL_REGISTRY if key not in ("hdgcn", "hd_gcn")}
    servable = set(REALTIME_MAP.values())
    assert trainable <= servable, f"trainable but not servable: {sorted(trainable - servable)}"


@pytest.mark.parametrize(
    "model_type,expected",
    [
        ("HD-GCN", "handgcn"),      # what HandGCNModel.get_model_name() returns
        ("hdgcn", "handgcn"),
        ("BiGRU + Attention", "bigru_attention"),
        ("CNN", "cnn"),
        ("LSTM", "lstm"),
        ("TCN", "tcn"),
    ],
)
def test_checkpoint_model_type_strings_resolve(model_type, expected):
    assert REALTIME_MAP[model_type.lower()] == expected


def test_unknown_architecture_is_rejected_not_silently_treated_as_tcn():
    from realtime_service.app.model_loader import build_model_from_checkpoint

    with pytest.raises(ValueError, match="unsupported model_type"):
        build_model_from_checkpoint({"model_type": "Transformer", "model_config": {}})

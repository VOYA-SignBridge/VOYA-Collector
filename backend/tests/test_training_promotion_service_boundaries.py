"""Contract tests for the training promotion-service boundary."""

import json
from pathlib import Path

from app.modules.training import promotion_service
from app.routers import training


def test_router_reexports_promotion_contract() -> None:
    assert training.CHECKPOINTS_DIR is promotion_service.CHECKPOINTS_DIR
    assert training.REGISTRY_PATH is promotion_service.REGISTRY_PATH
    assert training.REALTIME_CHECKPOINTS_DIR is promotion_service.REALTIME_CHECKPOINTS_DIR
    assert training.REALTIME_CONTAINER_CHECKPOINTS == promotion_service.REALTIME_CONTAINER_CHECKPOINTS
    assert training._copy_checkpoint_to_deployment is promotion_service._copy_checkpoint_to_deployment
    assert training._registry_display_name is promotion_service._registry_display_name
    assert training._update_registry is promotion_service._update_registry
    assert training._notify_realtime_service_reload is promotion_service._notify_realtime_service_reload
    assert training.deploy_checkpoint is promotion_service.deploy_checkpoint


def test_deploy_checkpoint_runs_copy_registry_and_reload_in_order() -> None:
    calls = []

    def copy_checkpoint(src, model_id, destination):
        calls.append(("copy", model_id, destination))
        return "/deployed/model.pt"

    def display_name(dialect):
        calls.append(("display", dialect))
        return "Hòa đê"

    def update_registry(*args):
        calls.append(("registry", args[0], args[1]))
        return True

    def notify_reload(*args):
        calls.append(("reload", args[0], args[1]))
        return True

    result = promotion_service.deploy_checkpoint(
        src_path=Path("/source/model.pt"),
        job_id="job-1",
        model_type="TCN",
        dialect="hoa-de",
        language="vn",
        ckpt={"seq_len": 60, "feature_dim": 126},
        copy_checkpoint=copy_checkpoint,
        registry_display_name=display_name,
        update_registry=update_registry,
        notify_reload=notify_reload,
        checkpoints_dir=Path("/deployment"),
        container_checkpoints_dir="/runtime/checkpoints",
    )

    assert [call[0] for call in calls] == ["copy", "display", "registry", "reload"]
    assert result.model_id == "hoa-de"
    assert result.display_name == "Hòa đê"
    assert result.registry_updated is True
    assert result.realtime_reloaded is True
    assert result.message == "Model đã được đưa vào realtime và sẵn sàng sử dụng ngay"


def test_deploy_checkpoint_stops_when_copy_fails() -> None:
    try:
        promotion_service.deploy_checkpoint(
            src_path=Path("/missing/model.pt"),
            job_id="job-1",
            model_type="TCN",
            dialect="hoa-de",
            language="vn",
            ckpt={},
            copy_checkpoint=lambda *args: None,
        )
    except promotion_service.CheckpointCopyError as exc:
        assert str(exc) == "Copy checkpoint sang realtime service thất bại"
    else:
        raise AssertionError("copy failure must stop deployment")


def test_registry_replaces_dialect_entry_and_keeps_display_name(tmp_path, monkeypatch) -> None:
    registry_path = tmp_path / "models.json"
    registry_path.write_text(
        json.dumps({
            "schema_version": "1",
            "models": [
                {
                    "id": "old-hoa-de",
                    "name": "Hòa đê",
                    "dialect": "hoa-de",
                },
                {
                    "id": "tay-do",
                    "name": "Tây Đô",
                    "dialect": "tay-do",
                },
            ],
        }),
        encoding="utf-8",
    )
    monkeypatch.setattr(promotion_service, "REGISTRY_PATH", registry_path)

    updated = promotion_service._update_registry(
        "hoa-de",
        "checkpoints/new.pt",
        "fallback",
        {"seq_len": 60, "feature_dim": 126},
        "hoa-de",
        "vn",
    )

    assert updated is True
    models = json.loads(registry_path.read_text(encoding="utf-8"))["models"]
    hoa_de = [model for model in models if model.get("dialect") == "hoa-de"]
    assert len(hoa_de) == 1
    assert hoa_de[0]["id"] == "hoa-de"
    assert hoa_de[0]["name"] == "Hòa đê"
    assert any(model.get("id") == "tay-do" for model in models)

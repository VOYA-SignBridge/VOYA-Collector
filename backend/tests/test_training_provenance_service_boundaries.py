"""Contract tests for the training provenance-service module boundary."""

from app.modules.training import provenance_service
from app.routers import training


def test_router_reexports_provenance_helpers() -> None:
    assert training._CRITERION_LABELS is provenance_service._CRITERION_LABELS
    assert training._determinism_summary is provenance_service._determinism_summary
    assert training._load_research_validity is provenance_service._load_research_validity
    assert training._provenance_checks is provenance_service._provenance_checks
    assert training.build_provenance_report is provenance_service.build_provenance_report


def test_report_keeps_ui_fields_scalar(monkeypatch) -> None:
    monkeypatch.setattr(
        provenance_service,
        "_provenance_checks",
        lambda checkpoint, workspace_root=None: [{
            "id": "C1", "label": "test", "ok": True, "detail": "đạt",
        }],
    )

    report = provenance_service.build_provenance_report(
        "job-1",
        {
            "git_commit": "abc123",
            "determinism": {
                "cudnn_deterministic": True,
                "deterministic_algorithms": True,
                "warnings": [],
            },
            "model_type": "TCN",
        },
    )

    assert report["available"] is True
    assert report["reproducible"] is True
    assert report["code"]["determinism"] == "đầy đủ"
    for group in ("code", "data", "model"):
        assert not any(isinstance(value, (dict, list)) for value in report[group].values())

"""Contract tests for the training job-service module boundary."""

from app.modules.training import job_service
from app.routers import training


def test_router_reexports_job_service_contract() -> None:
    assert training.training_jobs is job_service.training_jobs
    assert training.TERMINAL_STATUSES is job_service.TERMINAL_STATUSES
    assert training._persist_job_sync is job_service._persist_job_sync
    assert training._persist_metric_sync is job_service._persist_metric_sync
    assert training._job_from_db_row is job_service._job_from_db_row
    assert training._split_prov_from_row is job_service._split_prov_from_row
    assert training._metrics_from_db_rows is job_service._metrics_from_db_rows
    assert training.restore_jobs_from_db is job_service.restore_jobs_from_db
    assert training._ensure_job_loaded is job_service._ensure_job_loaded


def test_db_row_conversion_preserves_nested_schema_types() -> None:
    job = job_service._job_from_db_row({
        "job_id": "job-1",
        "status": "running",
        "config": {"model_type": "tcn", "epochs": 3},
        "created_at": "2026-10-19T12:00:00",
        "current_epoch": 2,
        "total_epochs": 3,
        "split_provenance": {
            "split_mode": "signer_disjoint",
            "signer_disjoint": True,
        },
    })

    assert job.id == "job-1"
    assert job.config.model_type == "tcn"
    assert job.config.epochs == 3
    assert job.split_provenance is not None
    assert job.split_provenance.signer_disjoint is True

"""Integration tests for the training job lifecycle: submit -> monitor -> cancel -> promote.

These drive the real FastAPI router through HTTP, so routing, request validation,
auth dependencies, status transitions and guard ordering are all exercised. Only
the systems outside this process are replaced: Postgres, Redis, the Celery
dispatch and the realtime service.

What they are here to catch is behaviour that is easy to break and expensive to
lose: a submitted job that vanishes because the queue was down, a cancel that
reports success without signalling the trainer, a promote that skips its status
or architecture gate.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth import get_current_user, require_admin
from app.routers import training as training_module
from app.routers.training import TrainingConfig, TrainingJob, router, training_jobs

USER = {"id": "u-1", "username": "researcher", "role": "user"}
ADMIN = {"id": "a-1", "username": "boss", "role": "admin"}


@pytest.fixture
def client(monkeypatch):
    """A TestClient over the training router with external systems stubbed out."""
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: USER
    app.dependency_overrides[require_admin] = lambda: ADMIN

    # No Postgres: persistence is verified by call, not by round-trip.
    async def _no_db_persist(job, auth_user_id=None):
        return None

    monkeypatch.setattr(training_module, "_persist_job", _no_db_persist)
    # Every dialect is trainable unless a test says otherwise.
    monkeypatch.setattr(
        training_module, "_trainable_dialects_from_splits", lambda: {"hoa-de": 7}
    )

    training_jobs.clear()
    with TestClient(app) as c:
        yield c
    training_jobs.clear()


def _config(**overrides) -> dict:
    base = {
        "model_type": "tcn",
        "epochs": 5,
        "batch_size": 32,
        "dialects": ["hoa-de"],
        "languages": ["vn"],
    }
    base.update(overrides)
    return TrainingConfig(**base).dict()


def _seed_job(job_id: str, status: str, **fields) -> TrainingJob:
    """Put a job into the in-memory registry the router reads from."""
    job = TrainingJob(
        id=job_id,
        status=status,
        config=TrainingConfig(**{"dialects": ["hoa-de"], "languages": ["vn"]}),
        created_at=datetime.now().isoformat(),
        total_epochs=5,
        **fields,
    )
    training_jobs[job_id] = {"job": job, "progress": []}
    return job


# --------------------------------------------------------------------------
# Submit
# --------------------------------------------------------------------------

def test_submit_queues_job_and_dispatches_to_the_training_queue(client):
    with patch("app.training_tasks.run_training_job") as task:
        response = client.post("/training/start", json=_config())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"
    assert body["id"]

    task.apply_async.assert_called_once()
    # Must go to the dedicated trainer queue, not the default one: the default
    # worker has no GPU reservation and would run training on the API host.
    assert task.apply_async.call_args.kwargs["queue"] == "training"


def test_submit_persists_before_dispatching(client, monkeypatch):
    """A job must be recoverable if the backend dies between persist and dispatch."""
    order = []

    async def _record_persist(job, auth_user_id=None):
        order.append("persist")

    monkeypatch.setattr(training_module, "_persist_job", _record_persist)

    with patch("app.training_tasks.run_training_job") as task:
        task.apply_async.side_effect = lambda *a, **k: order.append("dispatch")
        client.post("/training/start", json=_config())

    assert order[:2] == ["persist", "dispatch"]


def test_submit_marks_job_failed_when_the_queue_is_down(client, monkeypatch):
    """A dispatch failure must be recorded, not silently swallowed."""
    persisted = []

    async def _capture(job, auth_user_id=None):
        persisted.append((job.id, job.status, job.error_message))

    monkeypatch.setattr(training_module, "_persist_job", _capture)

    with patch("app.training_tasks.run_training_job") as task:
        task.apply_async.side_effect = RuntimeError("redis down")
        response = client.post("/training/start", json=_config())

    assert response.status_code == 503
    # Persisted twice: queued first, then failed with a diagnosable reason.
    assert persisted[0][1] == "queued"
    assert persisted[-1][1] == "failed"
    assert "redis down" in (persisted[-1][2] or "")


def test_submit_rejects_dialects_without_enough_data(client, monkeypatch):
    """Caught up front — otherwise the trainer subprocess fails later with rc=1."""
    monkeypatch.setattr(training_module, "_trainable_dialects_from_splits", lambda: {"hoa-de": 1})

    with patch("app.training_tasks.run_training_job") as task:
        response = client.post("/training/start", json=_config(dialects=["hoa-de"]))

    assert response.status_code == 400
    assert "hoa-de" in response.json()["detail"]
    task.apply_async.assert_not_called()


# --------------------------------------------------------------------------
# Research mode
# --------------------------------------------------------------------------

SPLIT = {
    "split_version": "hoa_de_sample_v5",
    "dataset_version": "isds2026_v5",
    "recognition_profile": "hoa_de",
    "split_mode": "sample",
    "num_classes": 7,
    "counts": {"train": 311, "val": 66, "test": 68},
    "seed": 42,
    "dataset_manifest_checksum": "117749bedecf",
}


def test_research_mode_requires_a_split(client):
    with patch("app.training_tasks.run_training_job") as task:
        response = client.post("/training/start", json=_config(run_purpose="research"))

    assert response.status_code == 400
    task.apply_async.assert_not_called()


def test_research_mode_rejects_a_split_that_is_not_research_valid(client, monkeypatch):
    """Fail here with the list of usable splits, rather than letting train_tcn.py
    SystemExit in _enforce_research_preconditions after the job is queued."""
    monkeypatch.setattr(training_module, "_research_splits", lambda: [SPLIT])

    with patch("app.training_tasks.run_training_job") as task:
        response = client.post(
            "/training/start",
            json=_config(run_purpose="research", split_version="made_up_v9"),
        )

    assert response.status_code == 400
    assert "hoa_de_sample_v5" in response.json()["detail"]
    task.apply_async.assert_not_called()


def test_research_mode_pins_provenance_from_the_chosen_split(client, monkeypatch):
    """dataset_version/recognition_profile come from the split metadata, never
    from the client: a self-declared version could disagree with the real data."""
    monkeypatch.setattr(training_module, "_research_splits", lambda: [SPLIT])
    persisted = []

    async def _capture(job, auth_user_id=None):
        persisted.append(job)

    monkeypatch.setattr(training_module, "_persist_job", _capture)

    with patch("app.training_tasks.run_training_job"):
        response = client.post(
            "/training/start",
            json=_config(
                run_purpose="research",
                split_version="hoa_de_sample_v5",
                dataset_version="LIES",
                recognition_profile="LIES",
            ),
        )

    assert response.status_code == 200
    cfg = persisted[0].config
    assert cfg.dataset_version == "isds2026_v5"
    assert cfg.recognition_profile == "hoa_de"


def test_research_mode_skips_the_dialect_data_check(client, monkeypatch):
    """The split defines the data, so an unrelated empty dialect must not block it."""
    monkeypatch.setattr(training_module, "_research_splits", lambda: [SPLIT])
    monkeypatch.setattr(training_module, "_trainable_dialects_from_splits", lambda: {"hoa-de": 1})

    with patch("app.training_tasks.run_training_job"):
        response = client.post(
            "/training/start",
            json=_config(run_purpose="research", split_version="hoa_de_sample_v5",
                         dialects=["hoa-de"]),
        )

    assert response.status_code == 200


def test_research_command_passes_provenance_flags_and_drops_dialect_filters():
    from app.training_tasks import _build_cmd

    cmd = _build_cmd(
        {
            "model_type": "hdgcn",
            "run_purpose": "research",
            "split_version": "hoa_de_sample_v5",
            "dataset_version": "isds2026_v5",
            "recognition_profile": "hoa_de",
            "dialects": ["hoa-de"],
            "languages": ["vn"],
        },
        "metrics.jsonl",
    )

    assert "--run-purpose=research" in cmd
    assert "--split_version=hoa_de_sample_v5" in cmd
    assert "--dataset_version=isds2026_v5" in cmd
    assert any(a.startswith("--train_csv=") for a in cmd)
    # --recognition_profile puts the trainer in profile mode, where it cannot
    # infer the feature tree from the split CSV and aborts with
    # "Profile mode requires locating the 'features' folder".
    assert any(a.startswith("--features_root=") for a in cmd)
    # A dialect filter would slice the split and make the checkpoint disagree
    # with the split_version it claims.
    assert not any(a.startswith("--dialect=") for a in cmd)


def test_exploratory_command_keeps_dialect_filters_and_stays_smoke_test():
    from app.training_tasks import _build_cmd

    cmd = _build_cmd({"model_type": "tcn", "dialects": ["hoa-de"], "languages": ["vn"]}, "m.jsonl")

    assert "--dialect=hoa-de" in cmd
    assert not any(a.startswith("--run-purpose") for a in cmd)
    assert not any(a.startswith("--split_version") for a in cmd)


# --------------------------------------------------------------------------
# Monitor
# --------------------------------------------------------------------------

def test_job_status_is_readable_after_submit(client):
    with patch("app.training_tasks.run_training_job"):
        job_id = client.post("/training/start", json=_config()).json()["id"]

    response = client.get(f"/training/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "queued"


def test_unknown_job_is_404(client):
    with patch.object(training_module, "_ensure_job_loaded", return_value=None):
        assert client.get("/training/jobs/nope").status_code == 404


# --------------------------------------------------------------------------
# Cancel
# --------------------------------------------------------------------------

def test_cancel_signals_the_trainer_and_marks_the_job_cancelled(client, monkeypatch):
    _seed_job("j-run", "running")
    fake_redis = MagicMock()
    monkeypatch.setattr(training_module, "redis_client", fake_redis)

    response = client.post("/training/jobs/j-run/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    # The trainer polls this key; without it the subprocess keeps running and
    # the UI would report a cancellation that never happened.
    key = fake_redis.set.call_args.args[0]
    assert key == "training:cancel:j-run"


def test_cancel_still_marks_cancelled_when_redis_is_unreachable(client, monkeypatch):
    _seed_job("j-run", "running")
    fake_redis = MagicMock()
    fake_redis.set.side_effect = RuntimeError("connection refused")
    monkeypatch.setattr(training_module, "redis_client", fake_redis)

    response = client.post("/training/jobs/j-run/cancel")

    # Best-effort signalling: a dead Redis must not leave the user unable to cancel.
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


@pytest.mark.parametrize("status", ["completed", "failed", "cancelled"])
def test_cancel_rejects_a_job_that_already_finished(client, status):
    _seed_job(f"j-{status}", status)
    response = client.post(f"/training/jobs/j-{status}/cancel")
    assert response.status_code == 409


# --------------------------------------------------------------------------
# Promote
# --------------------------------------------------------------------------

def test_promote_rejects_a_job_that_is_not_completed(client):
    _seed_job("j-run", "running")
    assert client.post("/training/jobs/j-run/promote").status_code == 409


def test_promote_rejects_a_missing_checkpoint(client):
    _seed_job("j-done", "completed", checkpoint_path="/nowhere/model.pt")
    assert client.post("/training/jobs/j-done/promote").status_code == 404


def _promotable_job(tmp_path: Path, job_id: str) -> Path:
    ckpt = tmp_path / f"{job_id}.pt"
    ckpt.write_bytes(b"not-a-real-checkpoint")
    _seed_job(job_id, "completed", checkpoint_path=str(ckpt))
    return ckpt


def test_promote_rejects_an_unrecognized_architecture(client, tmp_path):
    _promotable_job(tmp_path, "j-alien")

    with patch.object(training_module.torch, "load", return_value={"model_type": "Transformer"}):
        response = client.post("/training/jobs/j-alien/promote")

    assert response.status_code == 400
    assert "Transformer" in response.json()["detail"]


def _reproducible_ckpt(**overrides) -> dict:
    ckpt = {
        "git_commit": "0475b78cabc9c35b3ab9345097a774f8b78818be",
        "seed": 42,
        "run_purpose": "research",
        "run_status": "completed",
        "determinism": {
            "seed": 42,
            "cudnn_deterministic": True,
            "deterministic_algorithms": True,
            "warnings": [],
        },
        "dataset_version": "isds2026_v6",
        "split_version": "hoa_de_loso_v5/test_S001",
        "dataset_manifest_checksum": "a95bc6d1ed3b",
        "model_type": "TCN",
        "num_classes": 7,
        "runtime_env": {
            "python_version": "3.11.15",
            "pytorch_version": "2.0.0+cu117",
            "numpy_version": "1.26.2",
            "device": "cuda",
        },
        "model_selection": {
            "criterion": "val_macro_f1",
            "restored_best_state": True,
            "best_epoch": 10,
        },
    }
    ckpt.update(overrides)
    return ckpt


def test_provenance_is_unavailable_without_a_checkpoint(client):
    _seed_job("j-nockpt", "completed")
    body = client.get("/training/jobs/j-nockpt/provenance").json()
    assert body["available"] is False


def test_provenance_is_unavailable_for_a_pre_provenance_checkpoint(client, tmp_path):
    """Older checkpoints predate provenance recording — say so, don't show blanks."""
    _promotable_job(tmp_path, "j-legacy")
    with patch.object(training_module.torch, "load", return_value={"model_type": "TCN"}):
        body = client.get("/training/jobs/j-legacy/provenance").json()
    assert body["available"] is False


def test_provenance_reports_a_fully_reproducible_run(client, tmp_path):
    _promotable_job(tmp_path, "j-good")
    with patch.object(training_module.torch, "load", return_value=_reproducible_ckpt()):
        body = client.get("/training/jobs/j-good/provenance").json()

    assert body["available"] is True
    assert body["reproducible"] is True
    assert body["code"]["seed"] == 42
    assert body["data"]["dataset_version"] == "isds2026_v6"
    assert all(check["ok"] for check in body["checks"])


def test_provenance_flags_a_smoke_test_run_as_not_reproducible(client, tmp_path):
    """The distinction the panel exists to make: usable model, unusable numbers."""
    _promotable_job(tmp_path, "j-smoke")
    ckpt = _reproducible_ckpt(run_purpose="smoke_test", dataset_manifest_checksum="")

    with patch.object(training_module.torch, "load", return_value=ckpt):
        body = client.get("/training/jobs/j-smoke/provenance").json()

    assert body["reproducible"] is False
    failed = {c["id"] for c in body["checks"] if not c["ok"]}
    assert failed == {"C1", "C5"}


def test_provenance_values_are_scalars_the_ui_can_render(client, tmp_path):
    """Regression: determinism is a dict in the checkpoint and rendered as
    '[object Object]' if passed through untouched."""
    _promotable_job(tmp_path, "j-scalar")
    with patch.object(training_module.torch, "load", return_value=_reproducible_ckpt()):
        body = client.get("/training/jobs/j-scalar/provenance").json()

    for group in ("code", "data", "model"):
        nested = [k for k, v in body[group].items() if isinstance(v, (dict, list))]
        assert not nested, f"{group} still exposes nested objects: {nested}"
    assert body["code"]["determinism"] == "đầy đủ"


def test_provenance_summarizes_partial_determinism_with_warnings(client, tmp_path):
    _promotable_job(tmp_path, "j-partial")
    ckpt = _reproducible_ckpt(
        determinism={"cudnn_deterministic": True, "deterministic_algorithms": False,
                     "warnings": ["cublas workspace unset"]}
    )
    with patch.object(training_module.torch, "load", return_value=ckpt):
        body = client.get("/training/jobs/j-partial/provenance").json()

    assert body["code"]["determinism"] == "một phần (1 cảnh báo)"


@pytest.mark.parametrize("model_type", ["TCN", "HD-GCN", "CNN", "LSTM", "BiGRU + Attention"])
def test_promote_accepts_every_trained_architecture(client, tmp_path, monkeypatch, model_type):
    """The realtime service builds each architecture from the training registry.

    Regression guard: promotion used to hard-code TCN, which left the strongest
    signer-independent model (HandGCN) trained but undeployable.
    """
    job_id = f"j-{model_type.replace(' ', '').replace('+', '')}"
    _promotable_job(tmp_path, job_id)

    monkeypatch.setattr(
        training_module, "_copy_checkpoint_to_deployment",
        lambda src, model_id, dst_dir=None: f"/deployed/{model_id}.pt",
    )
    monkeypatch.setattr(training_module, "_update_registry", lambda *a, **k: True)
    monkeypatch.setattr(
        training_module, "_notify_realtime_service_reload", lambda *a, **k: True
    )

    with patch.object(training_module.torch, "load", return_value={"model_type": model_type}), \
         patch("app.training_tasks.backup_promoted_checkpoint_task"):
        response = client.post(f"/training/jobs/{job_id}/promote")

    assert response.status_code == 200, response.text

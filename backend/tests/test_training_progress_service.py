from __future__ import annotations

import asyncio

from app.modules.training.progress_service import stream_job_progress
from app.modules.training.schemas import TrainingConfig, TrainingJob


def test_progress_stream_emits_metrics_then_terminal_status(monkeypatch):
    rows = [
        {"epoch": 1, "train_loss": 1, "train_acc": 0.5, "val_loss": 1, "val_acc": 0.4, "val_f1": 0.3},
        {"epoch": 2, "train_loss": 0.8, "train_acc": 0.6, "val_loss": 0.9, "val_acc": 0.5, "val_f1": 0.4},
    ]
    monkeypatch.setattr("app.storage.metadata_db.list_training_metrics", lambda job_id: rows)
    job = TrainingJob(
        id="j-1",
        status="completed",
        config=TrainingConfig(),
        created_at="2026-10-20T00:00:00",
    )
    events = []

    async def ensure_job(job_id):
        return {"job": job, "progress": []}

    async def send_json(message):
        events.append(message)

    asyncio.run(
        stream_job_progress(
            "j-1",
            send_json,
            ensure_job=ensure_job,
            poll_interval=0,
        )
    )

    assert [event["type"] for event in events] == ["metric", "metric", "status"]
    assert events[-1]["data"]["status"] == "completed"

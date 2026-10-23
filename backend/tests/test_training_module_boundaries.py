from pathlib import Path


def test_training_task_facade_is_removed():
    app_root = Path(__file__).resolve().parents[1] / "app"
    assert not (app_root / "training_tasks.py").exists()


def test_training_tasks_preserve_legacy_celery_names():
    from app.modules.training import tasks

    expected = {
        "backup_promoted_checkpoint_task": tasks.backup_promoted_checkpoint_task,
        "cleanup_training_artifacts": tasks.cleanup_training_artifacts,
        "run_training_job": tasks.run_training_job,
    }

    for name, task in expected.items():
        assert task.name == f"app.training_tasks.{name}"


def test_training_cleanup_beat_uses_legacy_task_name():
    from app.worker import celery_app

    schedule = celery_app.conf.beat_schedule["cleanup-training-artifacts-daily"]
    assert schedule["task"] == "app.training_tasks.cleanup_training_artifacts"

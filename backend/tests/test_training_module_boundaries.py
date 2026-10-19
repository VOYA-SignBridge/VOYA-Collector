def test_training_task_facade_aliases_implementation_module():
    import app.training_tasks as legacy_tasks
    from app.modules.training import tasks

    assert legacy_tasks is tasks


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

from pathlib import Path


def test_background_tasks_live_in_domain_modules():
    from app.modules.dataset import preparation_tasks
    from app.modules.google_sync import restore_tasks

    assert preparation_tasks.prepare_dataset.name == "app.dataset_prep_tasks.prepare_dataset"
    assert (
        restore_tasks.download_missing_files_to_local.name
        == "app.sync_tasks.download_missing_files_to_local"
    )


def test_drive_restore_beat_keeps_legacy_task_name():
    from app.worker import celery_app

    schedule = celery_app.conf.beat_schedule.get("pull-missing-files-from-drive")
    if schedule is not None:
        assert schedule["task"] == "app.sync_tasks.download_missing_files_to_local"


def test_worker_facade_uses_shared_celery_application():
    from app.infrastructure.celery.app import celery_app as shared_app
    from app.worker import celery_app as worker_app

    assert worker_app is shared_app


def test_video_task_facade_preserves_legacy_name():
    import app.tasks as legacy_tasks
    from app.modules.dataset import video_tasks

    assert legacy_tasks is video_tasks
    assert video_tasks.enqueue_process_video.name == "app.tasks.enqueue_process_video"


def test_obsolete_root_task_modules_are_removed():
    app_root = Path(__file__).resolve().parents[1] / "app"

    assert not (app_root / "dataset_prep_tasks.py").exists()
    assert not (app_root / "sync_tasks.py").exists()

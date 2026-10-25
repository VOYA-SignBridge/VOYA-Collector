"""Import Celery task modules exactly once for worker registration."""

from __future__ import annotations


def register_task_modules() -> None:
    """Load every task module; decorators register tasks on the shared app."""
    from app.modules.dataset import preparation_tasks, video_tasks
    from app.modules.google_sync import drive_tasks, restore_tasks, sheets_tasks
    from app.modules.saas import saas_tasks
    from app.modules.training import tasks as training_tasks

    _ = (
        preparation_tasks,
        video_tasks,
        drive_tasks,
        restore_tasks,
        sheets_tasks,
        saas_tasks,
        training_tasks,
    )

"""Periodic task schedule construction."""

from __future__ import annotations

from typing import Any, Dict


def build_beat_schedule(settings) -> Dict[str, Dict[str, Any]]:
    """Build the beat schedule from enabled integrations."""
    schedule: Dict[str, Dict[str, Any]] = {
        "cleanup-training-artifacts-daily": {
            "task": "app.training_tasks.cleanup_training_artifacts",
            "schedule": 86400.0,
        },
    }

    if str(settings.google_sheets_samples_spreadsheet_id).strip():
        schedule["export-samples-every-30s"] = {
            "task": "app.export_tasks.export_samples_to_sheets",
            "schedule": 30.0,
        }
    if str(settings.google_sheets_labels_spreadsheet_id).strip():
        schedule["export-labels-every-60s"] = {
            "task": "app.export_tasks.export_labels_to_sheets",
            "schedule": 60.0,
        }
    if settings.use_google_drive:
        schedule["mirror-catalog-csvs-every-5min"] = {
            "task": "app.export_tasks.mirror_catalog_csvs_to_drive",
            "schedule": 300.0,
        }
    if settings.use_google_drive and int(
        getattr(settings, "drive_pull_interval_hours", 0)
    ) > 0:
        schedule["pull-missing-files-from-drive"] = {
            "task": "app.sync_tasks.download_missing_files_to_local",
            "schedule": float(settings.drive_pull_interval_hours) * 3600.0,
        }
    return schedule

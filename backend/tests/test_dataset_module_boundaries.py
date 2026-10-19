def test_dataset_compatibility_imports_alias_component_modules():
    import app.dataset_manager as legacy_catalog
    import app.dataset_samples as legacy_samples
    import app.inference_loader as legacy_inference
    import app.raw_uploads as legacy_raw_uploads
    import app.signers as legacy_signers
    from app.modules.dataset import catalog, inference, raw_uploads, samples, signers

    assert legacy_catalog is catalog
    assert legacy_samples is samples
    assert legacy_raw_uploads is raw_uploads
    assert legacy_signers is signers
    assert legacy_inference is inference


def test_email_compatibility_import_aliases_service_module():
    import app.email_service as legacy_email
    from app.services import email

    assert legacy_email is email


def test_catalog_sync_compatibility_import_aliases_dataset_module():
    import app.catalog_sync as legacy_catalog_sync
    from app.modules.dataset import catalog_sync

    assert legacy_catalog_sync is catalog_sync


def test_google_sync_builds_only_dataset_relative_storage_keys(tmp_path):
    from app.modules.google_sync.catalog import dataset_storage_key

    dataset_root = tmp_path / "dataset"
    sample_path = dataset_root / "features" / "vi" / "sample.npz"
    outside_path = tmp_path / "outside" / "sample.npz"

    assert dataset_storage_key(sample_path, dataset_root=dataset_root) == "features/vi/sample.npz"
    assert dataset_storage_key(outside_path, dataset_root=dataset_root) is None


def test_google_task_facade_preserves_legacy_celery_names():
    import app.export_tasks as facade
    from app.modules.google_sync import drive_tasks, sheets_tasks

    expected = {
        "delete_gdrive_paths_task": drive_tasks.delete_gdrive_paths_task,
        "export_labels_to_sheets": sheets_tasks.export_labels_to_sheets,
        "export_samples_to_sheets": sheets_tasks.export_samples_to_sheets,
        "mirror_catalog_csvs_to_drive": drive_tasks.mirror_catalog_csvs_to_drive,
        "move_gdrive_paths_task": drive_tasks.move_gdrive_paths_task,
        "upload_npz_batch_to_gdrive_task": drive_tasks.upload_npz_batch_to_gdrive_task,
        "upload_npz_to_gdrive_task": drive_tasks.upload_npz_to_gdrive_task,
        "upload_raw_video_to_gdrive_task": drive_tasks.upload_raw_video_to_gdrive_task,
    }

    for name, task in expected.items():
        assert getattr(facade, name) is task
        assert task.name == f"app.export_tasks.{name}"

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

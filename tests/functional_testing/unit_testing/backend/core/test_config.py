"""Unit tests — ENVIRONMENT guard fail-fast (erd_v2 §12.1, GĐ 1)."""
import pytest

from app.core.config import EnvironmentGuardError, Settings


def make_settings(**overrides):
    # _env_file=None: tests must not be polluted by a local .env
    return Settings(_env_file=None, **overrides)


class TestEnvironmentGuard:
    def test_dev_defaults_are_valid(self):
        s = make_settings()
        assert s.environment == "dev"
        assert s.gdrive_enabled is False and s.sheets_enabled is False

    def test_dev_pointing_at_prod_resource_refuses_to_start(self):
        with pytest.raises(EnvironmentGuardError, match="PRODUCTION"):
            make_settings(
                environment="dev",
                prod_resource_ids="folder-prod-123,sheet-prod-456",
                gdrive_root_folder_id="folder-prod-123",
            )

    def test_staging_gets_the_same_protection_as_dev(self):
        with pytest.raises(EnvironmentGuardError):
            make_settings(
                environment="staging",
                prod_resource_ids="folder-prod-123",
                gdrive_root_folder_id="folder-prod-123",
            )

    def test_dev_with_non_prod_folder_is_fine(self):
        s = make_settings(
            environment="dev",
            prod_resource_ids="folder-prod-123",
            gdrive_root_folder_id="folder-DEV-999",
        )
        assert s.gdrive_root_folder_id == "folder-DEV-999"

    def test_prod_with_dev_default_secrets_refuses_to_start(self):
        with pytest.raises(EnvironmentGuardError, match="default dev"):
            make_settings(environment="prod")

    def test_prod_with_gdrive_enabled_but_no_folder_refuses(self):
        with pytest.raises(EnvironmentGuardError, match="gdrive_root_folder_id"):
            make_settings(
                environment="prod",
                jwt_secret_key="real-secret",
                user_ref_pepper="real-pepper",
                gdrive_enabled=True,
            )

    def test_prod_fully_configured_starts(self):
        s = make_settings(
            environment="prod",
            jwt_secret_key="real-secret",
            user_ref_pepper="real-pepper",
            gdrive_enabled=True,
            gdrive_root_folder_id="folder-prod-123",
            prod_resource_ids="folder-prod-123",
        )
        assert s.environment == "prod"


class TestDerivedValues:
    def test_database_url_is_assembled_from_parts(self):
        s = make_settings(v2_postgres_host="dbhost", v2_postgres_port=5555)
        assert s.database_url == (
            "postgresql://signbridge:signbridge@dbhost:5555/signbridge_v2"
        )

    def test_explicit_database_url_wins(self):
        s = make_settings(v2_database_url="postgresql://u:p@x:1/db")
        assert s.database_url == "postgresql://u:p@x:1/db"

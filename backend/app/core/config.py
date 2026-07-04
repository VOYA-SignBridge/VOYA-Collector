"""V2 application settings + environment guard (Roadmap v2 — GĐ 1).

Design: erd_v2_unified_design.md §12.1
- Every external resource id (Drive folder, spreadsheet, MinIO, DB) comes
  from environment variables. Hardcoding ids in code is forbidden.
- Fail-fast guard: the app REFUSES TO START when
    * ENVIRONMENT=dev|staging but a configured resource id appears in
      PROD_RESOURCE_IDS (someone grabbed the prod .env), or
    * ENVIRONMENT=prod but a critical secret/id is missing or left at
      its dev default.

This module is for the v2 stack. The legacy app keeps using
``app.config`` untouched (Strangler Fig — legacy dies in GĐ 6).
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Literal, Optional

from pydantic import BaseSettings, root_validator

# Secrets that must never survive into production.
_DEV_ONLY_DEFAULTS = {
    "dev-jwt-secret-change-me",
    "dev-user-ref-pepper-change-me",
}


class EnvironmentGuardError(RuntimeError):
    """Raised when the environment/resource configuration is inconsistent."""


class Settings(BaseSettings):
    # ── Environment ────────────────────────────────────────────────
    environment: Literal["dev", "staging", "prod"] = "dev"

    # Known PRODUCTION resource ids (comma separated). Used by the guard
    # to detect a prod .env being loaded on a dev machine.
    prod_resource_ids: str = ""

    # ── PostgreSQL (v2 schema — separate DB from the legacy `signdb`) ──
    v2_postgres_user: str = "signbridge"
    v2_postgres_password: str = "signbridge"
    v2_postgres_host: str = "localhost"
    v2_postgres_port: int = 5433
    v2_postgres_db: str = "signbridge_v2"
    v2_database_url: Optional[str] = None  # overrides the parts above

    # ── Redis ──────────────────────────────────────────────────────
    v2_redis_url: str = "redis://localhost:6380/0"

    # ── MinIO (hot storage — §11.1) ────────────────────────────────
    minio_endpoint: str = "localhost:9100"
    minio_access_key: str = "signbridge"
    minio_secret_key: str = "signbridge-dev"
    minio_secure: bool = False
    minio_bucket_media: str = "media"
    minio_bucket_legal: str = "legal-docs"

    # ── Google integrations (OFF by default in dev — §12.1) ───────
    gdrive_enabled: bool = False
    sheets_enabled: bool = False
    gdrive_root_folder_id: str = ""
    sheets_service_account_file: str = ""

    # ── Auth / crypto ──────────────────────────────────────────────
    jwt_secret_key: str = "dev-jwt-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 14
    # Pepper for pseudonymous `user_ref` exported to Sheets/CSV (§11.3).
    user_ref_pepper: str = "dev-user-ref-pepper-change-me"

    # ── DB pool (§2.10 Architecture) ───────────────────────────────
    db_pool_size: int = 10
    db_max_overflow: int = 10
    db_pool_pre_ping: bool = True

    class Config:
        env_file = os.getenv("V2_ENV_FILE", ".env")
        env_file_encoding = "utf-8"

    # ── Derived values ─────────────────────────────────────────────
    @property
    def database_url(self) -> str:
        if self.v2_database_url:
            return self.v2_database_url
        return (
            f"postgresql://{self.v2_postgres_user}:{self.v2_postgres_password}"
            f"@{self.v2_postgres_host}:{self.v2_postgres_port}/{self.v2_postgres_db}"
        )

    @property
    def prod_resource_id_set(self) -> List[str]:
        return [x.strip() for x in self.prod_resource_ids.split(",") if x.strip()]

    # ── Fail-fast guard (§12.1) ────────────────────────────────────
    @root_validator(skip_on_failure=True)
    def _environment_guard(cls, values):  # noqa: N805
        env = values.get("environment")
        prod_ids = {
            x.strip()
            for x in (values.get("prod_resource_ids") or "").split(",")
            if x.strip()
        }
        configured_ids = {
            values.get("gdrive_root_folder_id") or "",
        } - {""}

        if env != "prod":
            leaked = configured_ids & prod_ids
            if leaked:
                raise EnvironmentGuardError(
                    f"ENVIRONMENT={env} nhưng cấu hình trỏ vào tài nguyên "
                    f"PRODUCTION: {sorted(leaked)}. Bạn đang cầm nhầm .env của "
                    "prod — từ chối khởi động (erd_v2_unified_design.md §12.1)."
                )
        else:  # prod
            problems = []
            if values.get("jwt_secret_key") in _DEV_ONLY_DEFAULTS:
                problems.append("jwt_secret_key còn là default dev")
            if values.get("user_ref_pepper") in _DEV_ONLY_DEFAULTS:
                problems.append("user_ref_pepper còn là default dev")
            if values.get("gdrive_enabled") and not values.get("gdrive_root_folder_id"):
                problems.append("gdrive_enabled=true nhưng thiếu gdrive_root_folder_id")
            if problems:
                raise EnvironmentGuardError(
                    "ENVIRONMENT=prod nhưng cấu hình chưa an toàn: "
                    + "; ".join(problems)
                )
        return values


@lru_cache()
def get_settings() -> Settings:
    """Singleton settings — import-time fail-fast happens on first call."""
    return Settings()

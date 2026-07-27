import logging
import os
import json
from typing import List
from pydantic import BaseSettings, validator
from pathlib import Path


def _default_dataset_root() -> Path:
    """Resolve dataset root to repo-level ../dataset by default.
    This avoids writing inside backend/ and works cross-platform.
    """
    # app/config.py -> backend/app -> backend -> repo_root
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "dataset"


class Settings(BaseSettings):
    app_env: str = os.getenv("APP_ENV", "development")

    # CORS: comma-separated list of allowed origins, e.g.
    # "https://app.example.com,https://admin.example.com". Defaults to "*"
    # for local development. The API authenticates via Bearer tokens (no
    # cookies), so credentialed CORS is not required.
    cors_allowed_origins_raw: str = os.getenv("CORS_ALLOWED_ORIGINS", "*")

    # Postgres/PostgreSQL configuration
    postgres_user: str = os.getenv("POSTGRES_USER", "admin")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "admin")
    postgres_db: str = os.getenv("POSTGRES_DB", "signdb")
    postgres_host: str = os.getenv("POSTGRES_HOST", "postgres")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database_url: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}",
    )
    # Redis configuration
    broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
    result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

    # Postgres connection pool (used by the high-frequency metadata_db path).
    # Per-process pool; keep pool_max small so backend+worker+trainer combined
    # stay well under Postgres max_connections (default 100).
    db_pool_min: int = int(os.getenv("DB_POOL_MIN", "1"))
    db_pool_max: int = int(os.getenv("DB_POOL_MAX", "8"))
    db_connect_timeout: int = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))

    # Celery memory hygiene: recycle prefork children to release native
    # memory held by MediaPipe/OpenCV. Tune per host RAM.
    worker_max_tasks_per_child: int = int(os.getenv("WORKER_MAX_TASKS_PER_CHILD", "15"))
    # KB. Child restarts when it exceeds this (van an toàn chống OOM).
    worker_max_memory_per_child_kb: int = int(
        os.getenv("WORKER_MAX_MEMORY_PER_CHILD_KB", "1200000")
    )

    # Parallel download tuning for batch export / training materialization
    storage_download_workers: int = int(os.getenv("STORAGE_DOWNLOAD_WORKERS", "4"))
    storage_download_timeout_seconds: int = int(os.getenv("STORAGE_DOWNLOAD_TIMEOUT_SECONDS", "120"))

    # Support/appeal contact shown to users on a block/force-logout notice.
    support_email: str = os.getenv("SUPPORT_EMAIL", "")
    # Periodic Drive->local pull (download_missing). 0 = disabled (default);
    # set to e.g. 72 to auto-restore missing local files every 3 days.
    drive_pull_interval_hours: int = int(os.getenv("DRIVE_PULL_INTERVAL_HOURS", "0"))

    # Upload limits
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "1024"))
    max_camera_frames: int = int(os.getenv("MAX_CAMERA_FRAMES", "600"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Google Drive configuration
    use_google_drive: bool = bool(int(os.getenv("USE_GOOGLE_DRIVE", "0")))
    google_drive_credentials: str = os.getenv("GOOGLE_DRIVE_CREDENTIALS", "gdrive/credentials.json")
    google_drive_token: str = os.getenv("GOOGLE_DRIVE_TOKEN", "gdrive/token.json")
    google_drive_root_folder_id: str = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")
    google_drive_timeout_seconds: int = int(os.getenv("GOOGLE_DRIVE_TIMEOUT_SECONDS", "180"))
    google_drive_num_retries: int = int(os.getenv("GOOGLE_DRIVE_NUM_RETRIES", "5"))
    google_drive_chunk_mb: int = int(os.getenv("GOOGLE_DRIVE_CHUNK_MB", "8"))
    google_drive_download_chunk_mb: int = int(os.getenv("GOOGLE_DRIVE_DOWNLOAD_CHUNK_MB", "10"))
    google_drive_simple_upload_threshold_mb: int = int(os.getenv("GOOGLE_DRIVE_SIMPLE_UPLOAD_THRESHOLD_MB", "64"))
    gdrive_filename_suffix: str = os.getenv("GDRIVE_FILENAME_SUFFIX", "")
    google_sheets_labels_spreadsheet_id: str = os.getenv("GOOGLE_SHEETS_LABELS_SPREADSHEET_ID", "")
    google_sheets_labels_sheet_gid: int = int(os.getenv("GOOGLE_SHEETS_LABELS_SHEET_GID", "0"))
    google_sheets_samples_spreadsheet_id: str = os.getenv("GOOGLE_SHEETS_SAMPLES_SPREADSHEET_ID", "")
    google_sheets_samples_sheet_gid: int = int(os.getenv("GOOGLE_SHEETS_SAMPLES_SHEET_GID", "0"))

    # Processing constants (align live-capture and video)
    feature_dim: int = int(os.getenv("FEATURE_DIM", 126))
    seq_len: int = int(os.getenv("SEQ_LEN", 60))
    stride: int = int(os.getenv("STRIDE", 2))  # Default spec stride
    fps_target: int = int(os.getenv("FPS_TARGET", 30))
    augment_per_seq: int = int(os.getenv("AUG_PER_SEQ", 8))

    # Preprocessing policy flags
    # When enabled, per-frame vectors are wrist-centered and scale-normalized before canonicalization.
    # This makes mirroring robust even if upstream uses pixel coordinates.
    normalize_keypoints: bool = bool(int(os.getenv("NORMALIZE_KEYPOINTS", "0")))
    # Handedness/mirror canonicalization (recommended ON for left/right invariance)
    canonicalize_hands: bool = bool(int(os.getenv("CANONICALIZE_HANDS", "1")))
    canonicalize_mirror: bool = bool(int(os.getenv("CANONICALIZE_MIRROR", "1")))

    # Optional: mirror input frames before MediaPipe (video pipeline only)
    mirror_input: bool = bool(int(os.getenv("MIRROR_INPUT", "0")))
    resize_width: int = int(os.getenv("RESIZE_W", 640))
    resize_height: int = int(os.getenv("RESIZE_H", 480))
    # Live-capture processing flags
    enable_live_aug: bool = bool(int(os.getenv("ENABLE_LIVE_AUG", 1)))
    enable_live_smoothing: bool = bool(int(os.getenv("ENABLE_LIVE_SMOOTHING", 0)))
    live_completeness_threshold: float = float(os.getenv("LIVE_COMPLETENESS", 0.5))
    # Carry-forward missing hand frames vs zero-fill
    carry_forward_missing: bool = bool(int(os.getenv("CARRY_FORWARD_MISSING", 1)))
    # Debug logging toggle
    debug_logging: bool = bool(int(os.getenv("DEBUG_LOGGING", 0)))

    # Dataset root: prefer DATASET_ROOT; fallback to repo-level ../dataset
    dataset_root: Path = Path(os.getenv("DATASET_ROOT") or _default_dataset_root())

    # Video processing knobs
    # Threshold for window completeness when processing videos (0..1)
    video_completeness_threshold: float = float(os.getenv("VIDEO_COMPLETENESS", 0.8))
    # Override augmentation count for video windows (<=0 means use AUG_PER_SEQ)
    video_augment_per_seq: int = int(os.getenv("VIDEO_AUG_PER_SEQ", 8))
    # Skip intro frames until a hand is first detected
    video_skip_leading_no_hand: bool = bool(
        int(os.getenv("VIDEO_SKIP_LEADING_NO_HAND", 1))
    )
    # Stop processing after N consecutive frames with no detected hands (0 disables)
    video_stop_after_no_hand_frames: int = int(
        os.getenv("VIDEO_STOP_AFTER_NO_HAND_FRAMES", 0)
    )
    # Comma-separated list of speed variants (e.g., "1.0,1.2,0.8")
    speed_variants_raw: str = os.getenv("SPEED_VARIANTS", "1.0")
    # Maximum number of saved samples per class per job
    max_samples_per_class: int = int(os.getenv("MAX_SAMPLES_PER_CLASS", 200))
    # How many npz per batched Drive-upload Celery task (video pipeline).
    npz_upload_batch_size: int = int(os.getenv("NPZ_UPLOAD_BATCH_SIZE", 50))
    # Parsed list of speed variants; populated in __init__
    speed_variants: List[float] = [1.0, 1.2, 0.8]

    # ===== AUTH / JWT =====
    secret_key: str = os.getenv(
        "SECRET_KEY",
        os.getenv("AUTH_TOKEN_SECRET_KEY", "change-me-in-production"),
    )
    auth_token_secret_key: str = os.getenv("AUTH_TOKEN_SECRET_KEY", secret_key)

    algorithm: str = os.getenv("ALGORITHM", "HS256")

    access_token_expire_minutes: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60")
    )

    # Idle session cap. The refresh token is rotated on every use and lives this
    # long since its LAST rotation, so a session that goes this many minutes with
    # no refresh is dead server-side — the backstop behind the client-side
    # inactivity logout (both default to 90 min). Deliberately in *minutes*, not
    # days, so an idle-but-open browser can't hold a session alive overnight.
    # The short access token above is auto-renewed against it, so a stolen access
    # token is only useful for at most access_token_expire_minutes.
    refresh_token_expire_minutes: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_MINUTES", "90")
    )

    # ===== AUTH COOKIES =====
    # Tokens are delivered as httpOnly cookies (JS cannot read them → XSS can't
    # steal them). `Secure` requires HTTPS; keep it OFF for plain-HTTP dev and
    # turn it ON (COOKIE_SECURE=1) once served exclusively over TLS.
    cookie_secure: bool = bool(int(os.getenv("COOKIE_SECURE", "0")))
    # SameSite=Lax already blocks cross-site POST cookie sending (baseline CSRF
    # defense); the double-submit CSRF token is defense-in-depth on top.
    cookie_samesite: str = os.getenv("COOKIE_SAMESITE", "lax")
    # Leave empty to scope cookies to the exact host; set to share across
    # subdomains (e.g. ".voya.local").
    cookie_domain: str = os.getenv("COOKIE_DOMAIN", "")
    # Public sub-path the app is served under (e.g. "/voya"). The gateway strips
    # this before requests reach the backend, but the BROWSER still addresses
    # cookies at "/voya/...", so the path-scoped refresh cookie must carry the
    # prefix or it is never sent back on /voya/api/v1/auth/refresh (→ sessions
    # can't refresh under the sub-path). Empty = root. Match to VITE_BASE_PATH.
    cookie_path_prefix: str = os.getenv("COOKIE_PATH_PREFIX", "")

    # Optional auth behavior
    allow_guest_upload: bool = bool(
        int(os.getenv("ALLOW_GUEST_UPLOAD", "1"))
    )

    # Password policy
    min_password_length: int = int(
        os.getenv("MIN_PASSWORD_LENGTH", "8")
    )

    # Admin bootstrap
    admin_username: str = os.getenv("ADMIN_USERNAME", "")

    admin_password: str = os.getenv(
        "ADMIN_PASSWORD",
        "",
    )

    # Password reset
    password_reset_token_expire_minutes: int = int(
        os.getenv("PASSWORD_RESET_TOKEN_EXPIRE_MINUTES", "30")
    )
    # Base URL of the frontend app, used to build the reset-password link
    # sent by email, e.g. "https://app.example.com". FALLBACK only: when the
    # request arrives on an allowlisted host (below), the link is built from
    # that request instead, so a moving tunnel URL needs no redeploy.
    frontend_base_url: str = os.getenv("FRONTEND_BASE_URL", "http://localhost:5173")
    # Hosts allowed to DEFINE the emailed links, comma-separated. A leading dot
    # matches sub-domains (".ngrok-free.dev"), anything else is an exact
    # hostname. Empty = never trust the request, always use frontend_base_url.
    # Changing this needs a container recreate (it is env) — prefer the file
    # below for hosts that move. See app/public_url.py for the threat model.
    frontend_trusted_host_suffixes_raw: str = os.getenv(
        "FRONTEND_TRUSTED_HOST_SUFFIXES", ""
    )
    # Same allowlist, read from a FILE at request time. The repo is bind-mounted
    # into the container, so editing it applies to the next request with no
    # restart — the whole point, since a running container's env cannot change.
    # Default resolves inside the container first, then in a host checkout.
    public_hosts_file: str = os.getenv(
        "PUBLIC_HOSTS_FILE",
        "/workspace/deploy/public_hosts.txt"
        if os.path.isdir("/workspace/deploy")
        else str(Path(__file__).resolve().parents[2] / "deploy" / "public_hosts.txt"),
    )

    # SMTP (outbound email for password reset, etc.)
    # If smtp_host is empty, emails are logged instead of sent — safe default
    # for local development.
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_from: str = os.getenv("SMTP_FROM", "")
    smtp_use_tls: bool = bool(int(os.getenv("SMTP_USE_TLS", "1")))

    # Realtime inference service proxy
    realtime_service_url: str = os.getenv("REALTIME_SERVICE_URL", "http://localhost:8010")
    realtime_connect_timeout: float = float(os.getenv("REALTIME_CONNECT_TIMEOUT", "5.0"))
    realtime_read_timeout: float = float(os.getenv("REALTIME_READ_TIMEOUT", "10.0"))
    realtime_max_concurrent: int = int(os.getenv("REALTIME_MAX_CONCURRENT", "8"))
    realtime_max_body_bytes: int = int(os.getenv("REALTIME_MAX_BODY_BYTES", str(1 * 1024 * 1024)))

    # TTS (Text-to-Speech) configuration
    tts_redis_url: str = os.getenv("TTS_REDIS_URL", "redis://redis:6379/0")
    tts_cache_ttl_seconds: int = int(os.getenv("TTS_CACHE_TTL", "86400"))  # 24h
    tts_default_voice: str = os.getenv("TTS_DEFAULT_VOICE", "vi-VN-HoaiMyNeural")
    tts_max_text_length: int = int(os.getenv("TTS_MAX_TEXT_LENGTH", "200"))
    tts_max_concurrent_synth: int = int(os.getenv("TTS_MAX_CONCURRENT_SYNTH", "5"))
    tts_synth_timeout_seconds: float = float(os.getenv("TTS_SYNTH_TIMEOUT", "10"))
    tts_prewarm_on_startup: bool = bool(int(os.getenv("TTS_PREWARM_ON_STARTUP", "1")))
    tts_prewarm_top_percent: float = float(os.getenv("TTS_PREWARM_TOP_PERCENT", "0.2"))  # 20%

    @validator("speed_variants", pre=True, always=True)
    def _parse_speed_variants(cls, v, values):
        raw = values.get("speed_variants_raw")
        if raw:
            parts = [p.strip() for p in raw.split(",") if p.strip()]
            try:
                return [float(p) for p in parts] if parts else [1.0]
            except Exception:
                return [1.0]
        return v or [1.0]

    @property
    def cors_allowed_origins(self) -> List[str]:
        raw = self.cors_allowed_origins_raw.strip()
        if raw == "*" or not raw:
            return ["*"]
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @property
    def frontend_trusted_host_suffixes(self) -> List[str]:
        raw = self.frontend_trusted_host_suffixes_raw or ""
        return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]

    def __init__(self, **values):
        super().__init__(**values)
        # If running on POSIX (e.g., Docker/Linux) and DATASET_ROOT was a Windows path,
        # avoid creating a literal 'D:' folder; fallback to default.
        dr_str = str(self.dataset_root)
        if os.name == "posix" and (":\\" in dr_str or ":/" in dr_str):
            self.dataset_root = _default_dataset_root()

        # speed_variants is computed by validator; no assignment needed here

        self._check_placeholder_secrets()

    def _check_placeholder_secrets(self) -> None:
        """Refuse to run in production on secrets that are published in git.

        `.env.example` ships literal REPLACE_WITH_* values, and copying it is the
        documented way to start a new machine — so the default path for a fresh
        install produces a stack that boots happily while signing its sessions
        with a key anyone can read in the repository. Nothing warned about it.

        Only APP_ENV=production is hard-failed. Local work and the test suite run
        as "development" and merely get a warning, so this cannot turn into a
        surprise breakage for everyday use.
        """
        published = ("REPLACE_WITH",)
        problems = []

        for name, value in (
            ("SECRET_KEY", self.secret_key),
            ("AUTH_TOKEN_SECRET_KEY", self.auth_token_secret_key),
            ("ADMIN_PASSWORD", self.admin_password),
        ):
            text = str(value or "")
            if any(marker in text for marker in published):
                problems.append(f"{name} still holds the placeholder from .env.example")
            elif not text:
                problems.append(f"{name} is empty")
            elif name != "ADMIN_PASSWORD" and len(text) < 32:
                # 32 hex chars is what the documented
                # `python -c "import secrets; print(secrets.token_hex(32))"` yields.
                problems.append(f"{name} is only {len(text)} chars — generate a real random secret")

        if not problems:
            return

        detail = "; ".join(problems)
        if str(self.app_env).lower() == "production":
            raise RuntimeError(
                f"Refusing to start with insecure secrets ({detail}). "
                'Generate them with: python -c "import secrets; print(secrets.token_hex(32))"'
            )
        logging.getLogger(__name__).warning(
            "Insecure secrets in use (%s). This is tolerated because APP_ENV=%s, "
            "but the stack will refuse to start with APP_ENV=production.",
            detail,
            self.app_env,
        )

    class Config:
        env_file = ".env"
        extra = "ignore"

        @classmethod
        def parse_env_var(cls, field_name, raw_value):
            if field_name == "speed_variants":
                text = str(raw_value).strip()
                if not text:
                    return [1.0]

                if text.startswith("["):
                    try:
                        parsed = json.loads(text)
                        if isinstance(parsed, list):
                            return [float(item) for item in parsed]
                    except Exception:
                        pass

                parts = [part.strip() for part in text.split(",") if part.strip()]
                try:
                    return [float(part) for part in parts] if parts else [1.0]
                except Exception:
                    return [1.0]

            return super().parse_env_var(field_name, raw_value)


settings = Settings()

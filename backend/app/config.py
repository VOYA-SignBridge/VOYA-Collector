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

    # Parallel download tuning for batch export / training materialization
    storage_download_workers: int = int(os.getenv("STORAGE_DOWNLOAD_WORKERS", "4"))
    storage_download_timeout_seconds: int = int(os.getenv("STORAGE_DOWNLOAD_TIMEOUT_SECONDS", "120"))

    # Upload limits
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "1024"))
    max_camera_frames: int = int(os.getenv("MAX_CAMERA_FRAMES", "600"))

    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # Google Drive configuration
    use_google_drive: bool = bool(int(os.getenv("USE_GOOGLE_DRIVE", "1")))
    google_drive_credentials: str = os.getenv("GOOGLE_DRIVE_CREDENTIALS", "gdrive/credentials.json")
    google_drive_token: str = os.getenv("GOOGLE_DRIVE_TOKEN", "gdrive/token.json")
    google_drive_root_folder_id: str = os.getenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "")
    google_drive_timeout_seconds: int = int(os.getenv("GOOGLE_DRIVE_TIMEOUT_SECONDS", "180"))
    google_drive_num_retries: int = int(os.getenv("GOOGLE_DRIVE_NUM_RETRIES", "5"))
    google_drive_chunk_mb: int = int(os.getenv("GOOGLE_DRIVE_CHUNK_MB", "8"))
    google_drive_simple_upload_threshold_mb: int = int(os.getenv("GOOGLE_DRIVE_SIMPLE_UPLOAD_THRESHOLD_MB", "64"))

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
    max_samples_per_class: int = int(os.getenv("MAX_SAMPLES_PER_CLASS", 80))
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

    def __init__(self, **values):
        super().__init__(**values)
        # If running on POSIX (e.g., Docker/Linux) and DATASET_ROOT was a Windows path,
        # avoid creating a literal 'D:' folder; fallback to default.
        dr_str = str(self.dataset_root)
        if os.name == "posix" and (":\\" in dr_str or ":/" in dr_str):
            self.dataset_root = _default_dataset_root()

        # speed_variants is computed by validator; no assignment needed here

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

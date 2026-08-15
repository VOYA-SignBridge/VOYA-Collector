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

    # Separate DSN for schema changes (DDL). Deliberately NOT the same role the
    # application uses at runtime: a role that can run ALTER TABLE can also run
    # `ALTER TABLE ... DISABLE ROW LEVEL SECURITY`, so an application role with
    # DDL rights can switch off the very policies that isolate tenants. Splitting
    # the two makes the isolation guarantee non-self-revocable.
    #
    # Empty means "not split yet" — postgres_connection falls back to
    # database_url, so a deployment that has not run provision_db_roles keeps
    # working exactly as before.
    migration_database_url: str = os.getenv("MIGRATION_DATABASE_URL", "")

    # Refuse to boot when row-level security is enabled but the application role
    # can bypass it (superuser or BYPASSRLS). That combination is worse than no
    # RLS at all: pg_policies and pg_tables.rowsecurity both report success while
    # every query still returns every tenant's rows, so configuration-level checks
    # go green against behaviour that provides no isolation whatsoever.
    #
    # Default off so switching roles and enabling policies can be sequenced
    # without bricking a running deployment; set to 1 once DATABASE_URL points at
    # the non-superuser role. See docs/11-worklog/BACKEND_WORK_PLAN.md item A2.
    db_strict_isolation: bool = os.getenv("DB_STRICT_ISOLATION", "0").strip().lower() in {
        "1", "true", "yes", "on",
    }

    # Ai đang QUYẾT ĐỊNH phân quyền. Ba giá trị, và thứ tự chuyển giữa chúng là
    # nội dung của §44 PDM (Phase A → B → C):
    #
    #   legacy  Chỉ `users.is_admin` + `tenant_members.role`. Casbin không nạp,
    #           không chạy, không tốn gì. Đây là hành vi TRƯỚC khi có tệp này.
    #
    #   shadow  Hệ cũ vẫn quyết định; Casbin chạy song song và mọi bất đồng
    #           được ghi lại. KHÔNG có request nào bị đổi kết quả. Đây là mặc
    #           định, và nó phải chạy đủ lâu để bộ mismatch sạch trước khi đi
    #           tiếp — đó là toàn bộ giá trị của bước này.
    #
    #   casbin  Casbin quyết định. Nạp policy thất bại = tiến trình KHÔNG khởi
    #           động (§40, hỏng-thì-đóng), vì phương án còn lại là phục vụ mà
    #           không biết đang phục vụ cho ai.
    #
    # Mặc định là `shadow` chứ không phải `legacy`: một chế độ quan sát mà phải
    # bật thủ công mới chạy thì sẽ không ai bật, và lên thẳng enforcement với
    # mismatch chưa biết là đúng thứ trình tự này tồn tại để ngăn.
    authz_mode: str = os.getenv("AUTHZ_MODE", "shadow").strip().lower()

    # Rate limits for the write paths and for inference. Ceilings, not quotas:
    # set well above real usage so they catch a runaway loop or crude abuse
    # without interrupting a collector recording samples. See rate_limit_deps.py.
    rate_limit_upload_per_hour: int = int(os.getenv("RATE_LIMIT_UPLOAD_PER_HOUR", "400"))
    rate_limit_training_per_hour: int = int(os.getenv("RATE_LIMIT_TRAINING_PER_HOUR", "30"))
    rate_limit_catalog_per_hour: int = int(os.getenv("RATE_LIMIT_CATALOG_PER_HOUR", "300"))
    rate_limit_predict_per_minute: int = int(os.getenv("RATE_LIMIT_PREDICT_PER_MINUTE", "600"))

    # Which tenant an UNAUTHENTICATED request reads.
    #
    # Several catalogue endpoints are deliberately public (the labels browser and
    # the realtime demo read classes and samples without a session). Under
    # row-level security an unscoped request sees nothing, so those pages would
    # go blank; scoping anonymous traffic to one named tenant keeps them working
    # while still making every other tenant unreachable without authentication.
    #
    # This is a policy, not a fallback: it is the single tenant whose catalogue
    # is public. Set to an empty string to make anonymous requests see nothing at
    # all, which is the right setting for a deployment with no public catalogue.
    public_tenant_id: str = os.getenv("PUBLIC_TENANT_ID", "default")

    # How long an invitation link stays usable. Long enough to survive a weekend
    # and an email that lands in spam; short enough that a link forwarded once
    # and forgotten does not stay a way in for a year.
    invitation_ttl_hours: int = int(os.getenv("INVITATION_TTL_HOURS", "168"))

    # Phút dùng mô hình nhận diện mỗi ngày cho khách chưa đăng nhập.
    #
    # Đếm PHÚT CÓ HOẠT ĐỘNG, không đếm lượt gọi — xem app/trial.py. 60 chứ không
    # phải 30 vì đã đo: một lượt suy luận tốn 40 ms CPU (p50) và KHÔNG dùng GPU
    # trên bản triển khai này. Nếu mô hình chuyển sang GPU thì đo lại rồi chỉnh,
    # đừng đoán.
    trial_minutes_per_day: int = int(os.getenv("TRIAL_MINUTES_PER_DAY", "60"))

    # Múi giờ quyết định "một ngày" của hạn ngạch, tính bằng giờ lệch so với UTC.
    #
    # Không có giá trị này thì ranh giới ngày là nửa đêm UTC, tức **7 giờ sáng
    # giờ Việt Nam**: người dùng lúc 6h sáng bị chặn rồi được reset một tiếng
    # sau, còn "quay lại vào ngày mai" trong thông báo là sai. Mặc định +7 vì
    # đây là sản phẩm phục vụ người dùng Việt Nam.
    #
    # Là số giờ lệch chứ không phải tên vùng: `zoneinfo` cần gói `tzdata` vốn
    # không có sẵn trong image python:slim, và Việt Nam không có giờ mùa hè nên
    # một độ lệch cố định là mô tả đầy đủ.
    trial_reset_utc_offset_hours: int = int(
        os.getenv("TRIAL_RESET_UTC_OFFSET_HOURS", "7"))

    # Whether an unverified email address may hold a session.
    #
    # Default OFF, and that is not timidity — turning it on locks out every
    # account whose address was never verified, which on this deployment is all
    # of them. The intended order is: run `python -m app.cli.verify_existing_emails`
    # to grandfather the accounts that already exist, THEN set this. The CLI
    # exists so that sequence is a command rather than a paragraph someone has
    # to remember.
    require_email_verification: bool = os.getenv(
        "REQUIRE_EMAIL_VERIFICATION", "0"
    ).strip().lower() in {"1", "true", "yes", "on"}

    # --- Tự phục vụ và mặt phẳng thương mại -------------------------------
    #
    # Đăng ký KHÔNG kèm lời mời sẽ tạo một tenant riêng cho người đó, không
    # bao giờ thả họ vào tenant gốc. Tắt cờ này thì đăng ký không lời mời bị
    # từ chối thẳng — không có đường thứ ba, vì chính đường thứ ba (rơi vào
    # tenant gốc) là lỗ hổng mà v4 sinh ra để bịt.
    self_serve_signup: bool = os.getenv(
        "SELF_SERVE_SIGNUP", "1"
    ).strip().lower() in {"1", "true", "yes", "on"}

    # Gói cấp cho một tenant tự đăng ký. Phải tồn tại trong bảng `plans` và
    # phải có `is_self_serve = TRUE`; `tenant_admin` kiểm cả hai và từ chối
    # tạo tenant nếu sai, thay vì lặng lẽ cấp một gói không giới hạn.
    # v6: gói tự đăng ký là `free` — vĩnh viễn, không hết hạn. Gói `trial` đã
    # bị đổi tên thành nó, và cùng lượt đó khái niệm "dùng thử" biến mất khỏi
    # sản phẩm. Xem `docs/07-business/BILLING_MODEL_V6.md`.
    self_serve_plan_code: str = os.getenv("SELF_SERVE_PLAN_CODE", "free").strip() or "free"

    # Trần số nhãn tenant mà /metrics được phép phát. Prometheus tính chi phí
    # theo chuỗi thời gian, và mỗi tenant nhân số chuỗi lên; xem
    # docs/06-operations/OBSERVABILITY_PLAN.md. Vượt trần thì phần dư gộp vào nhãn "_other"
    # chứ không phải bỏ đi — tổng vẫn đúng, chỉ mất phân giải ở phần đuôi.
    metrics_max_tenant_labels: int = int(os.getenv("METRICS_MAX_TENANT_LABELS", "25"))

    # Số ngày một gói dữ liệu xuất ra còn tải được trước khi bị dọn. Bản xuất
    # chứa toàn bộ dữ liệu của một tenant, nên để nó nằm mãi trên đĩa là tự
    # tạo thêm một bản sao cần canh giữ.
    tenant_export_ttl_days: int = int(os.getenv("TENANT_EXPORT_TTL_DAYS", "7"))

    # Số ngày một tenant phải nằm trong trạng thái đã-xoá-mềm trước khi được
    # phép xoá vĩnh viễn. Đây là cái phanh cho thao tác không thể hoàn tác duy
    # nhất trong hệ thống.
    tenant_purge_grace_days: int = int(os.getenv("TENANT_PURGE_GRACE_DAYS", "30"))

    # Ân hạn sau khi một kỳ đăng ký kết thúc mà không tự gia hạn. Trong khoảng
    # này tổ chức vẫn GHI được (`past_due` nằm trong `WRITABLE_BILLING_STATUSES`);
    # hết khoảng này mới chuyển sang chỉ-đọc. Đặt 0 là bỏ hẳn ân hạn — hợp lệ,
    # nhưng khi đó một hoá đơn trễ một ngày khoá quyền ghi của cả một trường.
    subscription_grace_days: int = int(os.getenv("SUBSCRIPTION_GRACE_DAYS", "7"))

    # Tắt lượt quét vòng đời đăng ký. Có mặt để một bản triển khai chưa dùng
    # tới khái niệm kỳ hạn không bị nó chạm vào — và để tắt nhanh khi cần, thay
    # vì phải sửa lịch beat rồi dựng lại ảnh.
    subscription_sweep_enabled: bool = (
        os.getenv("SUBSCRIPTION_SWEEP_ENABLED", "1").strip().lower()
        not in ("0", "false", "no", "off")
    )

    # Key for HMAC-ing six-digit codes, held OUTSIDE the database on purpose.
    # There is NO default: a fallback value shipped in source would be public,
    # which is the same as no pepper at all. app/tokens.py refuses to hash a
    # code while this is empty rather than silently storing a reversible digest.
    otp_pepper: str = os.getenv("OTP_PEPPER", "")

    # How long a six-digit code stays usable. Short, because the code is weak:
    # ten minutes bounds an attacker's guessing window as much as the attempt cap
    # does, and it is long enough for an SMS to arrive and be typed.
    otp_ttl_minutes: int = int(os.getenv("OTP_TTL_MINUTES", "10"))

    # Wrong guesses before the challenge dies. One million codes and unlimited
    # attempts is a solved problem for an attacker; five is generous for a person
    # squinting at a notification.
    otp_max_attempts: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))

    # Minimum gap between two codes for the same person and purpose. Protects the
    # RECIPIENT, not the endpoint — without it, anyone who knows an address can
    # have the system text a stranger once a second.
    otp_resend_cooldown_seconds: int = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))

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
    # Live-capture QC, two-tier: WARN (strict, sample saved + flagged) vs
    # REJECT (lenient, sample refused with 422). Jitter values are in
    # image-normalized coordinates (0..1): p95 wrist displacement per frame.
    qc_enabled: bool = bool(int(os.getenv("QC_ENABLED", 1)))
    qc_warn_hands_ratio: float = float(os.getenv("QC_WARN_HANDS_RATIO", 0.80))
    qc_reject_hands_ratio: float = float(os.getenv("QC_REJECT_HANDS_RATIO", 0.30))
    qc_warn_jitter: float = float(os.getenv("QC_WARN_JITTER", 0.12))
    qc_reject_jitter: float = float(os.getenv("QC_REJECT_JITTER", 0.35))
    qc_min_valid_ratio: float = float(os.getenv("QC_MIN_VALID_RATIO", 0.7))
    # Identifies the threshold SET, not the code. Bump it whenever any qc_*
    # value above changes, so samples collected under different thresholds stay
    # distinguishable. The thresholds are ALSO snapshotted into every sample's
    # metadata (see qc_threshold_snapshot) — a version string alone would let
    # an env override change the meaning of already-collected data silently.
    quality_config_version: str = os.getenv("QUALITY_CONFIG_VERSION", "qc_v1_heuristic_2026-07")
    # --- Vocabulary schema v2 ---
    # RECOGNITION_PROFILES used to be declared here as a comma-separated env
    # override. Removed 2026-08-01: nothing ever read it, no .env ever set it,
    # and its value ("north,central,south,hoa_de") was missing "alphabet" — so
    # the only thing it did was suggest there was a place to configure this.
    # The real list is the recognition_profiles table (app/vocabulary_registry).
    # Campaign stamped on newly collected samples (lock per collection drive).
    collection_campaign: str = os.getenv("COLLECTION_CAMPAIGN", "isds2026_v1")
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
    # Số npz TỐI THIỂU của một lớp trước khi nó được phép vào huấn luyện.
    #
    # 25 = 5 lần quay × 5 npz mỗi lần. Giao diện đã hiển thị đúng quy ước này
    # (`Math.floor(samples_count / 5)` rồi so với 5, ở LabelsPage), nhưng cho
    # tới nay nó CHỈ là một nhãn: backend không kiểm gì ở mức lớp, nên huấn
    # luyện một lớp 3 mẫu vẫn chạy. Hằng số nằm ở đây để có đúng MỘT nguồn sự
    # thật, thay vì hai bản chép trong .tsx.
    #
    # Con số 25 là ngưỡng chọn theo kinh nghiệm, không phải kết quả đo. Nó ở
    # dạng cấu hình được vì mức đủ thật sự phụ thuộc số người ký và độ khó của
    # ký hiệu — hai thứ chưa có đủ dữ liệu để chốt.
    min_samples_per_class_for_training: int = int(
        os.getenv("MIN_SAMPLES_PER_CLASS_FOR_TRAINING", 25)
    )
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

    # Cửa sổ ân hạn khi một refresh token vừa bị xoay lại quay về.
    #
    # Đây là chỗ hai yêu cầu kéo ngược chiều nhau, nên con số phải là một lựa
    # chọn có ý thức chứ không phải mặc định tiện tay:
    #
    #   - Phát hiện tái sử dụng muốn ân hạn = 0: token đã revoke mà quay lại thì
    #     coi như bị đánh cắp, đốt cả họ.
    #   - Nhưng hai tab cùng mở sẽ đua nhau gọi /refresh một cách hoàn toàn hợp
    #     lệ. Ân hạn = 0 nghĩa là tab thua bị đá ra, và vì cookie dùng chung cho
    #     cả trình duyệt nên CẢ HAI tab cùng văng.
    #
    # 15 giây đủ dài cho một cuộc đua giữa các tab (chúng cách nhau mili-giây) và
    # quá ngắn để làm nền cho một cuộc tấn công thật. Cái giá phải trả, nói thẳng
    # ra: kẻ trộm dùng token trong vòng 15 giây kể từ lần xoay hợp lệ vẫn lọt.
    #
    # Đặt về 0 sẽ siết tối đa và đá oan người dùng nhiều tab — chỉ làm nếu khách
    # hàng chấp nhận đánh đổi đó một cách tường minh.
    refresh_grace_seconds: int = int(os.getenv("REFRESH_GRACE_SECONDS", "15"))

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

    @validator("authz_mode")
    def _check_authz_mode(cls, v):
        """Từ chối một chế độ viết sai thay vì âm thầm coi như `legacy`.

        `AUTHZ_MODE=cabsin` mà rơi về `legacy` là kịch bản tệ nhất có thể: người
        vận hành tin rằng Casbin đang cưỡng chế, còn thực tế `is_admin` vẫn là
        thứ duy nhất quyết định — và không có gì trên màn hình nói khác đi.
        """
        allowed = {"legacy", "shadow", "casbin"}
        if v not in allowed:
            raise ValueError(
                f"AUTHZ_MODE={v!r} khong hop le; chon mot trong {sorted(allowed)}"
            )
        return v

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

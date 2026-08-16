-- =============================================================================
-- CTU.SignBridge — Physical schema for PowerDesigner reverse engineering
-- Generated 2026-08-11 from backend/app/storage/metadata_db.py (PostgreSQL 17)
-- =============================================================================
-- This is NOT a copy-paste of DDL_STATEMENTS in metadata_db.py. That module
-- creates tables with an early column set, then applies MIGRATION_STATEMENTS
-- (ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...) to reach the columns the
-- running system actually has today. This script folds every migration into
-- the CREATE TABLE for its table, because PowerDesigner reverse-engineers
-- whatever this script says — it has no way to also read MIGRATION_STATEMENTS.
-- The result matches the CURRENT live schema, not the historical first
-- version of each table.
--
-- Only the five foreign keys that exist as real constraints in the source are
-- declared as FOREIGN KEY here (all reference users.id). Three relationships
-- that are logical/application-level only in the real system —
-- classes.class_uid <-> samples.class_uid, signers.signer_id <->
-- samples.signer_id, training_jobs.job_id <-> training_metrics.job_id — are
-- deliberately NOT declared as FK constraints below, because they are not
-- FK constraints in the actual database either. See the note at the bottom
-- of this file about what that means for CDM auto-generation.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- users — authentication and ownership root; every real FK in the schema
-- points here.
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id             UUID PRIMARY KEY,
    username       TEXT NOT NULL UNIQUE,
    email          TEXT NOT NULL UNIQUE,
    password_hash  TEXT NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT TRUE,
    is_admin       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- signers — canonical physical-performer identity, the only key used for
-- signer-disjoint partitioning. No FK to/from samples in the real schema;
-- samples.signer_id is a logical reference only.
-- ---------------------------------------------------------------------------
CREATE TABLE signers (
    signer_id        TEXT PRIMARY KEY,
    display_name     TEXT,
    regional_group    TEXT,
    external_user_id TEXT,
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMP WITH TIME ZONE
);

-- ---------------------------------------------------------------------------
-- classes — sign-class identity and vocabulary metadata. class_uid is
-- referenced logically (not by FK) from samples and raw_uploads.
-- ---------------------------------------------------------------------------
CREATE TABLE classes (
    class_uid             TEXT PRIMARY KEY,
    class_idx             INTEGER,
    slug                  TEXT,
    label_original        TEXT,
    language              TEXT,
    dialect               TEXT,
    is_common_global      BOOLEAN,
    is_common_language    BOOLEAN,
    folder_name           TEXT,
    created_at            TIMESTAMP WITH TIME ZONE,
    migrated_at           TIMESTAMP WITH TIME ZONE,
    deleted_at            TIMESTAMP WITH TIME ZONE,
    hands_required        INTEGER,
    -- Vocabulary schema v2 (dialect is deprecated as a semantic field)
    semantic_label        TEXT,
    vocabulary_scope       TEXT,
    recognition_profile   TEXT,
    vocabulary_group       TEXT,
    collection_campaign   TEXT,
    is_active             BOOLEAN DEFAULT TRUE,
    motion_type            TEXT
);

CREATE INDEX idx_classes_class_idx    ON classes(class_idx);
CREATE INDEX idx_classes_slug         ON classes(slug);
CREATE INDEX idx_classes_lang_dialect ON classes(language, dialect);

-- ---------------------------------------------------------------------------
-- samples — prepared, storage-referenced training samples. auth_user_id is
-- the only real FK on this table; class_uid and signer_id are logical
-- references maintained by application code, not by the database.
-- ---------------------------------------------------------------------------
CREATE TABLE samples (
    sample_uid                    TEXT PRIMARY KEY,
    class_uid                     TEXT,
    slug                           TEXT,
    label_original                 TEXT,
    language                       TEXT,
    dialect                        TEXT,
    source_type                    TEXT,
    user_id                        TEXT,
    auth_user_id                   UUID,
    session_id                     TEXT,
    fps_original                   TEXT,
    fps_processed                  TEXT,
    seq_len                        INTEGER,
    augment_id                     INTEGER,
    completeness                   REAL,
    file_path                      TEXT,
    storage_url                    TEXT,
    checksum                       TEXT,
    created_at                     TIMESTAMP WITH TIME ZONE,
    gdrive_synced                  BOOLEAN DEFAULT FALSE,
    deleted_at                     TIMESTAMP WITH TIME ZONE,
    left_hand_ratio                 REAL,
    right_hand_ratio                REAL,
    both_hands_ratio                REAL,
    jitter                         REAL,
    quality_flags                  TEXT,
    -- Migration-era additions (live schema, not the original create)
    sheets_synced                  BOOLEAN DEFAULT FALSE,
    signer_id                      TEXT,
    collection_campaign            TEXT,
    raw_landmarks_available        BOOLEAN,
    normalization_version          TEXT,
    preprocess_contract_version    TEXT,
    sequence_length_original       INTEGER,
    quality_status                  TEXT,
    CONSTRAINT samples_auth_user_id_fkey
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_samples_class_uid      ON samples(class_uid);
CREATE INDEX idx_samples_auth_user_id   ON samples(auth_user_id);
CREATE INDEX idx_samples_created_at     ON samples(created_at DESC);
CREATE INDEX idx_samples_signer_id      ON samples(signer_id);
CREATE INDEX idx_samples_sheets_synced  ON samples(sheets_synced) WHERE sheets_synced = FALSE;

-- ---------------------------------------------------------------------------
-- raw_uploads — incoming-file metadata for the wider platform (upload
-- staging before a sample is prepared). auth_user_id is the only real FK.
-- ---------------------------------------------------------------------------
CREATE TABLE raw_uploads (
    upload_uid          TEXT PRIMARY KEY,
    class_uid            TEXT,
    slug                 TEXT,
    label_original        TEXT,
    language             TEXT,
    dialect               TEXT,
    source_type          TEXT,
    user_id               TEXT,
    auth_user_id          UUID,
    session_id            TEXT,
    original_filename    TEXT,
    local_path            TEXT,
    storage_key           TEXT,
    storage_url           TEXT,
    created_at            TIMESTAMP WITH TIME ZONE,
    updated_at            TIMESTAMP WITH TIME ZONE,
    deleted_at            TIMESTAMP WITH TIME ZONE,
    CONSTRAINT raw_uploads_auth_user_id_fkey
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_raw_uploads_class_uid    ON raw_uploads(class_uid);
CREATE INDEX idx_raw_uploads_auth_user_id ON raw_uploads(auth_user_id);
CREATE INDEX idx_raw_uploads_created_at   ON raw_uploads(created_at DESC);

-- ---------------------------------------------------------------------------
-- training_jobs — persisted training lifecycle and experiment record.
-- auth_user_id is the only real FK. training_metrics references job_id
-- logically only (see training_metrics below).
-- ---------------------------------------------------------------------------
CREATE TABLE training_jobs (
    job_id               TEXT PRIMARY KEY,
    status                TEXT NOT NULL,
    model_type            TEXT,
    config                JSONB,
    auth_user_id          UUID,
    created_at            TIMESTAMP WITH TIME ZONE,
    started_at            TIMESTAMP WITH TIME ZONE,
    completed_at          TIMESTAMP WITH TIME ZONE,
    current_epoch         INTEGER NOT NULL DEFAULT 0,
    total_epochs          INTEGER NOT NULL DEFAULT 0,
    checkpoint_path        TEXT,
    test_acc               REAL,
    test_f1                REAL,
    error_message          TEXT,
    promoted_at            TIMESTAMP WITH TIME ZONE,
    evaluation             JSONB,
    split_provenance       JSONB,
    CONSTRAINT training_jobs_auth_user_id_fkey
        FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_training_jobs_created_at   ON training_jobs(created_at DESC);
CREATE INDEX idx_training_jobs_status       ON training_jobs(status);
CREATE INDEX idx_training_jobs_auth_user_id ON training_jobs(auth_user_id);

-- ---------------------------------------------------------------------------
-- training_metrics — epoch-level train/validation metrics. Composite primary
-- key (job_id, epoch). job_id is NOT a foreign key to training_jobs in the
-- real schema — this is a deliberate application-level-only relationship,
-- documented as such in the thesis (Section 3.4.2 / Appendix C).
-- ---------------------------------------------------------------------------
CREATE TABLE training_metrics (
    job_id       TEXT NOT NULL,
    epoch        INTEGER NOT NULL,
    train_loss   REAL,
    train_acc    REAL,
    val_loss     REAL,
    val_acc      REAL,
    val_f1       REAL,
    created_at   TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (job_id, epoch)
);

-- ---------------------------------------------------------------------------
-- google_sheets_sync_status — sync-rotation bookkeeping for the wider
-- platform; not part of research-validity data.
-- ---------------------------------------------------------------------------
CREATE TABLE google_sheets_sync_status (
    id                       SERIAL PRIMARY KEY,
    table_name               VARCHAR(50) UNIQUE NOT NULL,
    current_spreadsheet_id   VARCHAR(100) NOT NULL DEFAULT '',
    current_sheet_index      INT NOT NULL DEFAULT 1,
    current_data_rows        INT NOT NULL DEFAULT 0,
    max_rows_per_sheet       INT NOT NULL DEFAULT 500000,
    updated_at               TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- password_reset_tokens — forgot-password flow. Stores only a hash of the
-- reset token. ON DELETE CASCADE: a deleted user's outstanding reset tokens
-- become meaningless and are removed with it.
-- ---------------------------------------------------------------------------
CREATE TABLE password_reset_tokens (
    token_hash    TEXT PRIMARY KEY,
    user_id        UUID NOT NULL,
    expires_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at        TIMESTAMP WITH TIME ZONE,
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_password_reset_user
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_password_reset_user_id ON password_reset_tokens(user_id);

-- ---------------------------------------------------------------------------
-- refresh_tokens — cookie session flow. Only a sha256 hash of the token is
-- stored. ON DELETE CASCADE: a deleted user's sessions are removed with it.
-- ---------------------------------------------------------------------------
CREATE TABLE refresh_tokens (
    token_hash    TEXT PRIMARY KEY,
    user_id        UUID NOT NULL,
    expires_at     TIMESTAMP WITH TIME ZONE NOT NULL,
    revoked_at     TIMESTAMP WITH TIME ZONE,
    created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT refresh_tokens_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);

-- =============================================================================
-- End of script. 10 tables, 5 declared foreign keys (all -> users.id).
-- =============================================================================

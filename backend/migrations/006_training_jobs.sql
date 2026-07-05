-- 006: Persist training jobs + per-epoch metrics
--
-- Before this migration, training jobs lived only in backend process memory
-- and the entire job history was lost on every restart/deploy.
-- The backend also creates these tables automatically at startup
-- (metadata_db.DDL_STATEMENTS); this file documents the schema for
-- environments where migrations are applied manually.

CREATE TABLE IF NOT EXISTS training_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,              -- queued | running | completed | failed | cancelled
    model_type TEXT,
    config JSONB,
    auth_user_id UUID,
    created_at TIMESTAMP WITH TIME ZONE,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    current_epoch INTEGER NOT NULL DEFAULT 0,
    total_epochs INTEGER NOT NULL DEFAULT 0,
    checkpoint_path TEXT,
    test_acc REAL,
    test_f1 REAL,
    error_message TEXT,
    FOREIGN KEY (auth_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS training_metrics (
    job_id TEXT NOT NULL,
    epoch INTEGER NOT NULL,
    train_loss REAL,
    train_acc REAL,
    val_loss REAL,
    val_acc REAL,
    val_f1 REAL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    PRIMARY KEY (job_id, epoch)
);

CREATE INDEX IF NOT EXISTS idx_training_jobs_created_at ON training_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_training_jobs_status ON training_jobs(status);

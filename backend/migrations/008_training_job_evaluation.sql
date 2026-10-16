-- 008: Test-set evaluation for training jobs (Step 7 UI)
--
-- Stores the per-class breakdown computed by train_tcn.py on the test set:
--   { "labels": [...], "confusion_matrix": [[...]], "per_class": [
--       {"class_idx", "label_key", "precision", "recall", "f1", "support"} ] }
--
-- Written once by the trainer container when a job completes; read by
-- GET /api/v1/training/jobs/{id}/evaluation.
--
-- The backend also applies this automatically at startup
-- (metadata_db.MIGRATION_STATEMENTS).

ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS evaluation JSONB;

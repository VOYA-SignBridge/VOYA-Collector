-- 007: Admin-only model promotion for training jobs
--
-- Adds promoted_at to training_jobs: records when an admin promoted the
-- job's model to the realtime recognition tab via
-- POST /api/v1/training/jobs/{id}/promote (require_admin).
--
-- Flow change accompanying this migration:
--   - Training no longer auto-copies every finished checkpoint to the
--     deployment dir. outputs/ = experimental, promotion is explicit.
--   - Promote copies the job's exact checkpoint to
--     backend/realtime_service/config/checkpoints/, writes models.json,
--     and hot-swaps via the realtime /reload endpoint.
--
-- The backend also applies this automatically at startup
-- (metadata_db.MIGRATION_STATEMENTS).

ALTER TABLE training_jobs ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMP WITH TIME ZONE;

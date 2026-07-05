-- ============================================================================
-- Migration: 003
-- Created: 2026-06-06
-- Purpose: Add 'queued' status to experiments table
--
-- Adds the intermediate state between 'pending' and 'running' to represent
-- experiments that have been enqueued in Celery but not yet picked up by a
-- worker. Without this state a queued experiment is indistinguishable from an
-- actively executing one, making worker-down situations misleading in the UI.
--
-- State transitions added:
--   pending → queued   (endpoint: mark_experiment_starting sets status atomically)
--   failed  → queued   (retry path through /start endpoint)
--   queued  → running  (worker: run_training_job calls update_experiment_status)
--   queued  → pending  (endpoint: broker failure rollback)
--
-- No data migration needed. All existing rows hold status values
-- ('pending', 'running', 'completed', 'failed') that remain valid in the
-- updated constraint.
--
-- Compatibility: PostgreSQL 14+
-- ============================================================================

BEGIN TRANSACTION;

-- The inline CHECK constraint was defined in 002_mvp_schema.sql and was
-- auto-named 'experiments_status_check' by PostgreSQL
-- (convention: {table}_{column}_check for inline column constraints).
-- IF EXISTS guards against re-running on a DB where this migration already ran.

ALTER TABLE experiments
    DROP CONSTRAINT IF EXISTS experiments_status_check;

ALTER TABLE experiments
    ADD CONSTRAINT experiments_status_check
    CHECK (status IN ('pending', 'queued', 'running', 'completed', 'failed'));

COMMIT;

-- ============================================================================
-- END MIGRATION 003
-- ============================================================================

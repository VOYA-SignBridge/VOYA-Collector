-- ============================================================================
-- Migration: 005
-- Created: 2026-06-06
-- Purpose: Enforce at most one production model per dialect
--
-- Adds a partial unique index on model_versions(dialect) WHERE status='production'.
-- This is the database-level enforcement of the promotion invariant: exactly one
-- row per dialect can hold status='production' at any point in time.
--
-- Without this index, two concurrent POST /promote requests for the same dialect
-- can both succeed within the same transaction window, producing two production
-- rows. The index forces exactly one to succeed and the other to receive a
-- UniqueViolation (mapped to HTTP 409 by the promotion endpoint).
--
-- The existing idx_models_dialect index (non-unique, no WHERE predicate) is NOT
-- dropped — it continues to serve queries that filter on dialect regardless of
-- status. This new index adds the uniqueness constraint for production rows only.
--
-- Safe on current data (verified 2026-06-06):
--   - dialect='hoa-de': one production row (version_id=6)     → no violation
--   - dialect='all':    zero production rows                   → no violation
--   - No other dialects have production rows
--
-- IF NOT EXISTS: makes the migration idempotent; safe to re-run.
--
-- Dependency: Does not depend on Migration 004.
-- Both 004 and 005 must be applied before the promotion endpoint is deployed.
--
-- Compatibility: PostgreSQL 9.5+ (IF NOT EXISTS on CREATE INDEX)
-- ============================================================================

BEGIN TRANSACTION;

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_production_per_dialect
    ON model_versions (dialect)
    WHERE status = 'production';

COMMIT;

-- ============================================================================
-- END MIGRATION 005
-- ============================================================================

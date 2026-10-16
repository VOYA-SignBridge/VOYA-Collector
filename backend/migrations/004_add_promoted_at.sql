-- ============================================================================
-- Migration: 004
-- Created: 2026-06-06
-- Purpose: Add promoted_at timestamp to model_versions
--
-- Records the exact moment a model version was promoted to production status.
-- Distinct from created_at (when the checkpoint was registered) — a model
-- may sit in candidate status for days before promotion.
--
-- Used by:
--   - POST /api/v1/models/{version_id}/promote (sets promoted_at = NOW())
--   - Demotion / archive transitions (sets promoted_at = NULL)
--   - Audit queries: which model was production at a given point in time
--
-- Safe on current data: adds a nullable column, no existing rows are modified.
-- No data migration required.
--
-- Dependency: None. Can be applied before or after Migration 005.
-- Both must be applied before the promotion endpoint is deployed.
--
-- Compatibility: PostgreSQL 14+
-- ============================================================================

BEGIN TRANSACTION;

ALTER TABLE model_versions
    ADD COLUMN promoted_at TIMESTAMP WITHOUT TIME ZONE;

COMMIT;

-- ============================================================================
-- END MIGRATION 004
-- ============================================================================

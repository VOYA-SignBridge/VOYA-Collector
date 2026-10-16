-- ============================================================================
-- SignBridge MVP Schema: Lightweight Experiment Tracking
-- ============================================================================
-- Migration: 002
-- Created: 2026-06-03
-- Purpose: Minimal experiment tracking, metrics, and model registry for MVP
-- Compatibility: PostgreSQL 14+
-- Design Philosophy: Stateless, filesystem-first, integer PKs for simplicity
--
-- DEPLOYMENT STRATEGY:
-- This migration replaces the enterprise schema in 001_create_production_schema.sql
-- with a lean MVP schema optimized for SignBridge's current needs.
--
-- Key differences from 001:
-- - Integer SERIAL PKs instead of UUIDs (simpler, matches existing API layer)
-- - Dialect + subset_path as reproducibility anchor (not dataset_version_id)
-- - Per-epoch metrics stored as rows, not JSON blobs
-- - Simple 3-status enum for model_versions (candidate, production, archived)
-- - No user tracking, no deployment tracking, no audit log (Phase 1 MVP scope)
--
-- CONFLICT RESOLUTION:
-- If 001_create_production_schema.sql has been applied, this migration will
-- DROP the conflicting tables (experiments, experiment_metrics, model_versions)
-- along with their dependent tables from 001. Only 002's MVP schema is preserved.
--
-- BACKWARD COMPATIBILITY:
-- - If 001 hasn't been applied: 002 runs standalone (recommended)
-- - If 001 was applied: 002 cleanly replaces affected tables
-- - No manual data migration needed (MVP is fresh start)
-- - Original split CSVs and checkpoints remain on filesystem
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- CLEANUP: Drop 001's schema if it exists (CASCADE drops dependencies)
-- ============================================================================
-- This is safe because:
-- - 001 tables are empty (no deployed code uses them yet)
-- - Training outputs (subset folders, checkpoints) remain on filesystem
-- - API code expects 002's schema, not 001's

DROP TABLE IF EXISTS model_deployments CASCADE;
DROP TABLE IF EXISTS dataset_lineage CASCADE;
DROP TABLE IF EXISTS model_versions CASCADE;
DROP TABLE IF EXISTS experiment_metrics CASCADE;
DROP TABLE IF EXISTS experiments CASCADE;
DROP TABLE IF EXISTS dataset_splits CASCADE;
DROP TABLE IF EXISTS dataset_samples_mapping CASCADE;
DROP TABLE IF EXISTS dataset_versions CASCADE;
DROP TABLE IF EXISTS datasets CASCADE;

-- ============================================================================
-- TABLE 1: experiments
-- ============================================================================
-- Represents a single training run.
-- Reproducibility is anchored by subset_path (points to frozen snapshot dir).
-- Summary fields (best_epoch, best_val_acc, best_val_f1) are populated
-- after training completes via update_experiment_summary().
-- ============================================================================
CREATE TABLE experiments (
    experiment_id SERIAL PRIMARY KEY,

    -- Dialect being trained (e.g., 'hoa-de', 'can-tho')
    dialect VARCHAR(32) NOT NULL,

    -- Training status lifecycle
    status VARCHAR(16) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed')),

    -- Reproducibility anchor: path to frozen subset snapshot
    -- Example: 'outputs/subset_hoa-de_20260601_143022'
    -- This directory contains frozen train.csv, val.csv, test.csv, label mappings
    subset_path TEXT NOT NULL,

    -- Optional inline manifest of split counts/checksums for fast lookups
    -- Format: { "train_count": 150, "val_count": 30, "test_count": 20,
    --           "train_hash": "...", "val_hash": "...", "test_hash": "..." }
    split_manifest JSONB,

    -- Full training configuration as JSON
    -- Example: { "lr": 0.001, "batch_size": 32, "epochs": 80,
    --            "dropout": 0.3, "channels": 64, "levels": 3, "kernel_size": 5 }
    hyperparameters JSONB NOT NULL,

    -- Best validation metrics (populated after training ends)
    -- NULL while status='running' or 'pending'
    best_epoch INTEGER,
    best_val_acc REAL,
    best_val_f1 REAL,

    -- Timing
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP
);

-- ============================================================================
-- TABLE 2: experiment_metrics
-- ============================================================================
-- Per-epoch metrics from a single training run.
-- One row per (experiment_id, epoch) pair.
-- This is the primary metrics storage; no need for JSON blobs.
-- Learning curves are reconstructed via SELECT queries, not JSON parsing.
-- ============================================================================
CREATE TABLE experiment_metrics (
    metric_id BIGSERIAL PRIMARY KEY,

    -- Foreign key to experiment
    experiment_id INTEGER NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,

    -- Which epoch does this row represent?
    epoch INTEGER NOT NULL,

    -- Per-epoch loss values
    train_loss REAL,
    val_loss REAL,

    -- Per-epoch accuracy values (0.0 to 1.0)
    train_acc REAL,
    val_acc REAL,

    -- Validation F1-macro (for imbalanced datasets)
    val_f1 REAL,

    -- Learning rate at this epoch
    learning_rate REAL,

    -- Timestamp when this metric was recorded
    recorded_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Prevent duplicate rows for the same (experiment, epoch)
    UNIQUE (experiment_id, epoch)
);

-- ============================================================================
-- TABLE 3: model_versions
-- ============================================================================
-- Registered checkpoints ready for inference.
-- One row per trained model that has been explicitly registered.
-- Links back to the experiment that produced it via experiment_id.
-- ============================================================================
CREATE TABLE model_versions (
    version_id SERIAL PRIMARY KEY,

    -- Model family: encodes both dialect and architecture
    -- Example: 'hoa-de-tcn', 'can-tho-tcn', 'hoa-de-transformer' (future)
    -- Allows supporting multiple architectures per dialect without schema changes
    model_family VARCHAR(64) NOT NULL,

    -- Semantic version string, auto-generated as "{model_family}-v{experiment_id}"
    -- Example: 'hoa-de-tcn-v42', 'can-tho-tcn-v15'
    -- Unique per model_family; enables easy version comparisons
    version_string VARCHAR(128) NOT NULL,

    -- Which experiment produced this model?
    -- Foreign key for reproducibility: trace back to training config, metrics, subset
    experiment_id INTEGER NOT NULL REFERENCES experiments(experiment_id),

    -- Dialect this model is trained for (denormalized from model_family for queries)
    dialect VARCHAR(32) NOT NULL,

    -- Path to saved checkpoint (PyTorch .pt file)
    -- Example: 'outputs/tcn_hoa-de_20260601_143022.pt'
    checkpoint_path TEXT NOT NULL,

    -- Feature extraction contract: what input does this model expect?
    -- Essential for reproducibility if feature pipeline changes in future.
    -- Format: {
    --   "extractor": "mediapipe_hands",
    --   "extractor_version": "0.9.3",
    --   "input_shape": [60, 126],
    --   "num_hands": 2,
    --   "landmarks_per_hand": 21,
    --   "dimensions": 3,
    --   "normalization": "current_v1"
    -- }
    feature_contract JSONB NOT NULL,

    -- Optional: runtime environment snapshot for reproducibility
    -- Format: {
    --   "pytorch_version": "2.0.1",
    --   "python_version": "3.10.11",
    --   "cuda_version": "11.8"
    -- }
    runtime_env JSONB,

    -- Performance metrics from validation split
    accuracy REAL,
    f1_macro REAL,

    -- Model lifecycle status
    -- 'candidate': newly registered, not yet promoted
    -- 'production': actively serving in inference
    -- 'archived': deprecated, kept for historical reference
    status VARCHAR(16) NOT NULL DEFAULT 'candidate'
        CHECK (status IN ('candidate', 'production', 'archived')),

    -- When was this version registered?
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),

    -- Uniqueness constraint: only one version_string per model_family
    UNIQUE (model_family, version_string)
);

-- ============================================================================
-- INDEXES (PostgreSQL standard: CREATE INDEX separately)
-- ============================================================================
-- These indexes optimize common queries without being part of table definition.

CREATE INDEX idx_experiments_dialect ON experiments(dialect);
CREATE INDEX idx_experiments_status ON experiments(status);
CREATE INDEX idx_experiments_created_at ON experiments(created_at DESC);

CREATE INDEX idx_metrics_experiment_id ON experiment_metrics(experiment_id);
CREATE INDEX idx_metrics_epoch ON experiment_metrics(experiment_id, epoch);

CREATE INDEX idx_models_dialect ON model_versions(dialect);
CREATE INDEX idx_models_status ON model_versions(status);
CREATE INDEX idx_models_created_at ON model_versions(created_at DESC);

-- ============================================================================
-- CONSTRAINTS
-- ============================================================================
-- Database-level constraints ensure data integrity.

-- Experiments must have a non-empty subset path
ALTER TABLE experiments
    ADD CONSTRAINT chk_subset_path_not_empty
    CHECK (LENGTH(TRIM(subset_path)) > 0);

-- ============================================================================
-- SUMMARY
-- ============================================================================
-- Created tables:
--   - experiments (experiment_id SERIAL PK, 11 columns, 3 indexes)
--   - experiment_metrics (metric_id BIGSERIAL PK, 11 columns, 2 indexes)
--   - model_versions (version_id SERIAL PK, 15 columns, 3 indexes)
--
-- Total: 3 tables, 8 indexes, PostgreSQL 14+ compatible, transaction-safe
-- ============================================================================

COMMIT;

-- ============================================================================
-- END MIGRATION 002
-- ============================================================================

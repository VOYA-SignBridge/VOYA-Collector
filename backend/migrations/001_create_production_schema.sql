-- ============================================================================
-- SignBridge Production Schema: Dataset Versioning + Experiment Tracking
-- ============================================================================
-- Migration: 001
-- Created: 2026-06-01
-- Purpose: Add dataset versioning, experiment tracking, and model lifecycle
-- Compatibility: PostgreSQL 14+, backward compatible with existing schema
-- ============================================================================

BEGIN TRANSACTION;

-- ============================================================================
-- 1. DATASETS TABLE - Dataset container/definition
-- ============================================================================
CREATE TABLE IF NOT EXISTS datasets (
    dataset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL,
    description TEXT,
    language TEXT NOT NULL,
    dialect TEXT NOT NULL,

    -- Ownership
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    owner_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deprecated')),

    -- Metadata
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Auditing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (language, dialect, name)
);

CREATE INDEX idx_datasets_language_dialect ON datasets(language, dialect);
CREATE INDEX idx_datasets_status ON datasets(status);
CREATE INDEX idx_datasets_created_by ON datasets(created_by);
CREATE INDEX idx_datasets_created_at ON datasets(created_at DESC);


-- ============================================================================
-- 2. DATASET_VERSIONS TABLE - Immutable dataset snapshots
-- ============================================================================
CREATE TABLE IF NOT EXISTS dataset_versions (
    dataset_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id UUID NOT NULL REFERENCES datasets(dataset_id) ON DELETE CASCADE,

    -- Versioning
    version_number TEXT NOT NULL,
    version_tag TEXT,

    -- Composition
    total_samples INTEGER NOT NULL,
    total_augmentations INTEGER NOT NULL,
    unique_signers INTEGER,
    language TEXT NOT NULL,
    dialect TEXT NOT NULL,

    -- Data integrity
    data_hash TEXT NOT NULL,
    manifest_path TEXT,

    -- Metadata
    description TEXT,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approval_timestamp TIMESTAMP WITH TIME ZONE,

    -- Status
    is_frozen BOOLEAN NOT NULL DEFAULT FALSE,
    is_published BOOLEAN NOT NULL DEFAULT FALSE,

    -- Lineage
    parent_version_id UUID REFERENCES dataset_versions(dataset_version_id) ON DELETE SET NULL,

    -- Auditing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE,

    UNIQUE (dataset_id, version_number),
    CHECK (total_samples >= 0),
    CHECK (total_augmentations >= total_samples)
);

CREATE INDEX idx_dataset_versions_dataset_id ON dataset_versions(dataset_id);
CREATE INDEX idx_dataset_versions_version_number ON dataset_versions(version_number);
CREATE INDEX idx_dataset_versions_is_frozen ON dataset_versions(is_frozen);
CREATE INDEX idx_dataset_versions_parent_version ON dataset_versions(parent_version_id);
CREATE INDEX idx_dataset_versions_created_at ON dataset_versions(created_at DESC);


-- ============================================================================
-- 3. DATASET_SAMPLES_MAPPING TABLE - M:M join between versions and samples
-- ============================================================================
CREATE TABLE IF NOT EXISTS dataset_samples_mapping (
    mapping_id BIGSERIAL PRIMARY KEY,
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(dataset_version_id) ON DELETE CASCADE,
    sample_uid TEXT NOT NULL REFERENCES samples(sample_uid) ON DELETE RESTRICT,

    -- Augmentation context
    augment_id INTEGER NOT NULL,

    -- Inclusion reason
    inclusion_reason TEXT DEFAULT 'included',

    -- Ordering
    sort_order INTEGER NOT NULL,

    -- Auditing
    added_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (dataset_version_id, sample_uid, augment_id)
);

CREATE INDEX idx_mapping_dataset_version ON dataset_samples_mapping(dataset_version_id);
CREATE INDEX idx_mapping_sample_uid ON dataset_samples_mapping(sample_uid);


-- ============================================================================
-- 4. DATASET_SPLITS TABLE - Train/val/test partitioning
-- ============================================================================
CREATE TABLE IF NOT EXISTS dataset_splits (
    split_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(dataset_version_id) ON DELETE CASCADE,

    -- Split definition
    split_name TEXT NOT NULL,
    split_ratios JSONB NOT NULL,

    -- Composition
    train_count INTEGER NOT NULL,
    val_count INTEGER NOT NULL,
    test_count INTEGER NOT NULL,

    -- Storage
    train_manifest_path TEXT,
    val_manifest_path TEXT,
    test_manifest_path TEXT,

    -- Configuration
    random_seed INTEGER,
    stratify_by TEXT,
    stratify_by_value TEXT,

    -- Metadata
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    description TEXT,

    -- Auditing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (dataset_version_id, split_name)
);

CREATE INDEX idx_splits_dataset_version ON dataset_splits(dataset_version_id);


-- ============================================================================
-- 5. EXPERIMENTS TABLE - Training experiment records
-- ============================================================================
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL,
    description TEXT,

    -- Relationship to data
    dataset_version_id UUID NOT NULL REFERENCES dataset_versions(dataset_version_id) ON DELETE RESTRICT,
    dataset_split_id UUID NOT NULL REFERENCES dataset_splits(split_id) ON DELETE RESTRICT,

    -- Model info
    model_architecture TEXT NOT NULL,

    -- Hyperparameters
    hyperparameters JSONB NOT NULL,

    -- Status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'running', 'completed', 'failed', 'cancelled')
    ),

    -- Ownership
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    started_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Timing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,

    -- Error tracking
    error_message TEXT,
    error_traceback TEXT,

    -- Artifacts
    checkpoint_path TEXT,
    checkpoint_size_bytes BIGINT,

    -- Reproducibility
    random_seed INTEGER,

    -- Environment
    compute_environment TEXT,

    -- Tags
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],

    UNIQUE (name)
);

CREATE INDEX idx_experiments_dataset_version ON experiments(dataset_version_id);
CREATE INDEX idx_experiments_status ON experiments(status);
CREATE INDEX idx_experiments_created_by ON experiments(created_by);
CREATE INDEX idx_experiments_created_at ON experiments(created_at DESC);


-- ============================================================================
-- 6. EXPERIMENT_METRICS TABLE - Per-epoch metrics
-- ============================================================================
CREATE TABLE IF NOT EXISTS experiment_metrics (
    metric_id BIGSERIAL PRIMARY KEY,
    experiment_id UUID NOT NULL REFERENCES experiments(experiment_id) ON DELETE CASCADE,

    -- Timing
    epoch INTEGER NOT NULL,
    batch_count INTEGER,

    -- Metrics
    train_loss REAL,
    train_accuracy REAL,
    train_f1_macro REAL,
    val_loss REAL,
    val_accuracy REAL,
    val_f1_macro REAL,

    -- Per-class metrics
    per_class_metrics JSONB,

    -- Learning rate
    learning_rate REAL,

    -- Custom metrics
    custom_metrics JSONB,

    -- Timestamp
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (experiment_id, epoch)
);

CREATE INDEX idx_metrics_experiment_id ON experiment_metrics(experiment_id);
CREATE INDEX idx_metrics_epoch ON experiment_metrics(experiment_id, epoch);


-- ============================================================================
-- 7. MODEL_VERSIONS TABLE - Checkpoint registry
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_versions (
    model_version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity & Lineage
    model_id TEXT NOT NULL,
    version_string TEXT NOT NULL,

    -- Training provenance
    experiment_id UUID NOT NULL REFERENCES experiments(experiment_id) ON DELETE RESTRICT,

    -- Checkpoint
    checkpoint_path TEXT NOT NULL,
    checkpoint_hash TEXT,

    -- Model config
    model_architecture TEXT NOT NULL,
    input_shape TEXT NOT NULL,
    output_shape TEXT NOT NULL,

    -- Feature contract
    feature_contract JSONB NOT NULL,

    -- Performance
    accuracy REAL NOT NULL,
    f1_macro REAL NOT NULL,
    loss REAL,
    per_class_f1 JSONB,

    -- Testing
    test_accuracy REAL,
    test_f1_macro REAL,

    -- Status
    status TEXT NOT NULL DEFAULT 'candidate' CHECK (
        status IN ('candidate', 'staging', 'production', 'deprecated', 'archived')
    ),

    -- Metadata
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    approval_notes TEXT,

    -- Auditing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    published_at TIMESTAMP WITH TIME ZONE,
    deprecated_at TIMESTAMP WITH TIME ZONE,

    -- Tags
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],

    UNIQUE (model_id, version_string)
);

CREATE INDEX idx_model_versions_model_id ON model_versions(model_id);
CREATE INDEX idx_model_versions_status ON model_versions(status);
CREATE INDEX idx_model_versions_experiment ON model_versions(experiment_id);
CREATE INDEX idx_model_versions_created_at ON model_versions(created_at DESC);


-- ============================================================================
-- 8. MODEL_DEPLOYMENTS TABLE - Deployment tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_deployments (
    deployment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Deployment relationship
    model_version_id UUID NOT NULL REFERENCES model_versions(model_version_id) ON DELETE RESTRICT,

    -- Environment
    environment TEXT NOT NULL,
    region TEXT,

    -- Status
    deployment_status TEXT NOT NULL DEFAULT 'pending' CHECK (
        deployment_status IN ('pending', 'deploying', 'active', 'rolling_back', 'rolled_back', 'failed')
    ),

    -- Ownership
    deployed_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    approved_by UUID REFERENCES users(id) ON DELETE SET NULL,

    -- Timing
    deployment_requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    deployment_started_at TIMESTAMP WITH TIME ZONE,
    deployment_completed_at TIMESTAMP WITH TIME ZONE,

    -- Sync
    models_json_synced BOOLEAN NOT NULL DEFAULT FALSE,
    models_json_sync_timestamp TIMESTAMP WITH TIME ZONE,

    -- Traffic
    traffic_percentage INTEGER DEFAULT 100 CHECK (traffic_percentage >= 0 AND traffic_percentage <= 100),

    -- Rollback
    previous_model_version_id UUID REFERENCES model_versions(model_version_id) ON DELETE SET NULL,

    -- Monitoring
    health_check_status TEXT,
    health_check_timestamp TIMESTAMP WITH TIME ZONE,

    -- Notes
    deployment_notes TEXT,
    rollback_reason TEXT,

    -- Auditing
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    UNIQUE (environment, deployment_status) WHERE deployment_status = 'active'
);

CREATE INDEX idx_deployments_model_version ON model_deployments(model_version_id);
CREATE INDEX idx_deployments_environment ON model_deployments(environment);
CREATE INDEX idx_deployments_status ON model_deployments(deployment_status);
CREATE INDEX idx_deployments_deployed_by ON model_deployments(deployed_by);
CREATE INDEX idx_deployments_created_at ON model_deployments(created_at DESC);


-- ============================================================================
-- 9. AUDIT_LOG TABLE - Complete change history
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id BIGSERIAL PRIMARY KEY,

    -- What changed
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    entity_name TEXT,

    -- Change details
    action TEXT NOT NULL CHECK (
        action IN ('create', 'update', 'delete', 'publish', 'approve', 'deploy', 'rollback', 'archive')
    ),

    -- Who and when
    actor_user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,

    -- Change content
    old_values JSONB,
    new_values JSONB,

    -- Reason
    reason TEXT,

    -- Request tracking
    request_id TEXT,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_actor ON audit_log(actor_user_id);
CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC);


-- ============================================================================
-- 10. DATASET_LINEAGE TABLE - Explicit lineage tracking
-- ============================================================================
CREATE TABLE IF NOT EXISTS dataset_lineage (
    lineage_id BIGSERIAL PRIMARY KEY,

    -- Relationships
    child_dataset_version_id UUID NOT NULL REFERENCES dataset_versions(dataset_version_id) ON DELETE CASCADE,
    parent_dataset_version_id UUID REFERENCES dataset_versions(dataset_version_id) ON DELETE SET NULL,
    parent_experiment_id UUID REFERENCES experiments(experiment_id) ON DELETE SET NULL,

    -- Lineage type
    lineage_type TEXT NOT NULL CHECK (
        lineage_type IN ('version_from_split', 'filtered', 'merged', 'augmented', 'custom')
    ),

    -- Notes
    description TEXT,

    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_lineage_child ON dataset_lineage(child_dataset_version_id);
CREATE INDEX idx_lineage_parent_dataset ON dataset_lineage(parent_dataset_version_id);
CREATE INDEX idx_lineage_parent_experiment ON dataset_lineage(parent_experiment_id);


-- ============================================================================
-- 11. MATERIALIZED VIEWS - Performance optimization
-- ============================================================================

-- Current model versions by status
CREATE VIEW current_model_versions AS
SELECT DISTINCT ON (m.model_id)
    m.model_version_id,
    m.model_id,
    m.version_string,
    m.status,
    m.accuracy,
    m.f1_macro,
    m.created_at,
    d.environment,
    d.deployment_status,
    d.deployment_completed_at
FROM model_versions m
LEFT JOIN model_deployments d ON m.model_version_id = d.model_version_id
ORDER BY m.model_id,
         CASE WHEN m.status = 'production' THEN 0
              WHEN m.status = 'staging' THEN 1
              WHEN m.status = 'candidate' THEN 2
              ELSE 3 END,
         m.created_at DESC;

-- Experiment summary
CREATE VIEW experiment_summary AS
SELECT
    e.experiment_id,
    e.name,
    dv.dataset_id,
    d.name as dataset_name,
    d.dialect,
    e.status,
    dv.version_number,
    COUNT(DISTINCT em.epoch) as total_epochs,
    MAX(em.val_accuracy) as best_val_accuracy,
    MAX(em.val_f1_macro) as best_val_f1,
    MIN(em.val_loss) as best_val_loss,
    e.created_at,
    e.completed_at,
    e.duration_seconds,
    u.username as created_by
FROM experiments e
JOIN dataset_versions dv ON e.dataset_version_id = dv.dataset_version_id
JOIN datasets d ON dv.dataset_id = d.dataset_id
LEFT JOIN experiment_metrics em ON e.experiment_id = em.experiment_id
LEFT JOIN users u ON e.created_by = u.id
GROUP BY e.experiment_id, dv.dataset_id, d.name, d.dialect, u.username;

-- Model promotion readiness
CREATE VIEW model_promotion_readiness AS
SELECT
    m.model_version_id,
    m.model_id,
    m.version_string,
    m.status,
    m.accuracy,
    m.f1_macro,
    m.test_accuracy,
    m.test_f1_macro,
    e.name as trained_on_experiment,
    dv.version_number as trained_on_dataset,
    COUNT(DISTINCT md.deployment_id) as deployment_count,
    MAX(CASE WHEN d.environment = 'production' THEN TRUE ELSE FALSE END) as is_in_production,
    m.created_at,
    m.created_by
FROM model_versions m
JOIN experiments e ON m.experiment_id = e.experiment_id
JOIN dataset_versions dv ON e.dataset_version_id = dv.dataset_version_id
LEFT JOIN model_deployments md ON m.model_version_id = md.model_version_id
LEFT JOIN model_deployments d ON m.model_version_id = d.model_version_id
    AND d.deployment_status = 'active'
WHERE m.status IN ('candidate', 'staging', 'production')
GROUP BY m.model_version_id, e.name, dv.version_number;


-- ============================================================================
-- 12. AUDIT TRIGGER - Auto-log changes to model_versions
-- ============================================================================

CREATE OR REPLACE FUNCTION audit_model_versions()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        entity_type, entity_id, entity_name,
        action, actor_user_id, old_values, new_values,
        created_at
    )
    VALUES (
        'model_versions',
        NEW.model_version_id::text,
        CONCAT(NEW.model_id, ' v', NEW.version_string),
        CASE
            WHEN TG_OP = 'DELETE' THEN 'delete'
            WHEN TG_OP = 'INSERT' THEN 'create'
            WHEN TG_OP = 'UPDATE' THEN 'update'
        END,
        COALESCE(current_setting('app.user_id')::UUID,
                (SELECT created_by FROM model_versions WHERE model_version_id = NEW.model_version_id LIMIT 1)),
        to_jsonb(OLD),
        to_jsonb(NEW),
        NOW()
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER model_versions_audit
AFTER INSERT OR UPDATE OR DELETE ON model_versions
FOR EACH ROW
EXECUTE FUNCTION audit_model_versions();


-- ============================================================================
-- ANALYTICS CONFIGURATION
-- ============================================================================

-- Auto-vacuum settings for large tables
ALTER TABLE experiment_metrics SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_analyze_scale_factor = 0.005
);

ALTER TABLE audit_log SET (
    autovacuum_vacuum_scale_factor = 0.05,
    autovacuum_analyze_scale_factor = 0.02
);

-- Analyze all new tables
ANALYZE datasets;
ANALYZE dataset_versions;
ANALYZE dataset_samples_mapping;
ANALYZE dataset_splits;
ANALYZE experiments;
ANALYZE experiment_metrics;
ANALYZE model_versions;
ANALYZE model_deployments;
ANALYZE dataset_lineage;
ANALYZE audit_log;

-- ============================================================================
-- COMPLETION
-- ============================================================================

COMMIT;

-- Echo completion message
SELECT 'Production schema created successfully' as status;

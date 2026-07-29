"""What schema a published SOT version carries, and what a reader must guarantee.

`export_schema_sql()` snapshots the idempotent DDL the publisher embeds.
`REQUIRED_COLUMNS` is the "must not be missing" set the reader checks after
applying schema — the server may have MORE columns (superset ok), never fewer.
Every column listed here exists in metadata_db's CREATE TABLE statements, so a
correctly-migrated server never reports a false gap.
"""

from __future__ import annotations

from typing import Dict, List

# Columns each reader upsert writes — absence breaks data import, so these are
# the coverage guarantee ("bao hàm hết chưa").
REQUIRED_COLUMNS: Dict[str, List[str]] = {
    # NOTE: this list must stay a superset of metadata_db's _CLASS_DB_KEYS /
    # _SAMPLE_DB_KEYS / _RAW_UPLOAD_DB_KEYS — those tuples ARE the columns each
    # reader upsert writes. Six of them were missing here (classes.hands_required
    # and the five sample quality metrics), which defeated the purpose of the
    # check: a reader whose schema lacked them passed verification and only then
    # failed, mid-import, writing columns the manifest never promised existed.
    # tests/test_sot_schema_coverage.py pins the two lists together.
    "classes": [
        "class_uid", "class_idx", "slug", "label_original", "language", "dialect",
        "is_common_global", "is_common_language", "folder_name", "created_at",
        "migrated_at", "deleted_at", "hands_required",
        # Vocabulary schema v2. The ALTER TABLE ... ADD COLUMN IF NOT EXISTS
        # statements that create these live in metadata_db.MIGRATION_STATEMENTS,
        # which export_schema_sql() below snapshots — so a reader that applies
        # the published schema always has them.
        "semantic_label", "vocabulary_scope", "recognition_profile",
        "vocabulary_group", "collection_campaign", "is_active", "motion_type",
    ],
    "samples": [
        "sample_uid", "class_uid", "slug", "label_original", "language", "dialect",
        "source_type", "user_id", "auth_user_id", "session_id", "fps_original",
        "fps_processed", "seq_len", "augment_id", "completeness", "file_path",
        "storage_url", "checksum", "created_at", "gdrive_synced", "deleted_at",
        "left_hand_ratio", "right_hand_ratio", "both_hands_ratio", "jitter",
        "quality_flags",
        # Vocabulary schema v2 / research provenance. signer_id is the canonical
        # physical-performer identity the held-out-signer protocol depends on —
        # a reader missing it would import samples with no way to tell people
        # apart, which is exactly the failure the protocol exists to prevent.
        "signer_id", "collection_campaign", "raw_landmarks_available",
        "normalization_version", "preprocess_contract_version",
        "sequence_length_original", "quality_status",
    ],
    "raw_uploads": [
        "upload_uid", "class_uid", "slug", "label_original", "language", "dialect",
        "source_type", "user_id", "auth_user_id", "session_id", "original_filename",
        "local_path", "storage_key", "storage_url", "created_at", "updated_at",
        "deleted_at",
    ],
}


def export_schema_sql() -> str:
    """Idempotent DDL snapshot: CREATE TABLE / ALTER / INDEX, all IF NOT EXISTS.

    Statements are ';'-separated; the reader applies them one-by-one and ignores
    per-statement failures, so re-applying on an up-to-date server is a no-op.
    """
    from app.storage.metadata_db import (
        DDL_STATEMENTS,
        INDEX_STATEMENTS,
        MIGRATION_STATEMENTS,
    )

    parts: List[str] = []
    for stmt in list(DDL_STATEMENTS) + list(MIGRATION_STATEMENTS) + list(INDEX_STATEMENTS):
        cleaned = stmt.strip().rstrip(";").strip()
        if cleaned:
            parts.append(cleaned)
    return ";\n".join(parts) + ";\n"


def schema_version() -> int:
    from app.sot import SOT_SCHEMA_VERSION

    return SOT_SCHEMA_VERSION

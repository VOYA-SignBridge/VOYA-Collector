# Lược đồ vật lý đầy đủ — sinh từ CSDL đang chạy

**59 bảng · 641 cột · 124 khoá ngoại**

Ký hiệu: `PK` khoá chính · `FK` khoá ngoại · `U` duy nhất · `NN` không rỗng

## api_keys

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `key_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `name` | text |  | NN |
| 4 | `prefix` | text | U | NN |
| 5 | `key_hash` | text |  | NN |
| 6 | `scopes` | text |  | NN |
| 7 | `created_by` | uuid | FK |  |
| 8 | `created_at` | timestamptz |  | NN |
| 9 | `last_used_at` | timestamptz |  |  |
| 10 | `expires_at` | timestamptz |  |  |
| 11 | `revoked_at` | timestamptz |  |  |
| 12 | `revoked_by` | uuid | FK |  |

**Khoá ngoại:**

- `(created_by)` → **users**`(id)`
- `(revoked_by)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## audit_log

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `audit_id` | bigint | PK | NN |
| 2 | `tenant_id` | text | FK |  |
| 3 | `actor_user_id` | uuid | FK |  |
| 4 | `actor_label` | text |  |  |
| 5 | `action` | text |  | NN |
| 6 | `target_type` | text |  |  |
| 7 | `target_id` | text |  |  |
| 8 | `detail` | jsonb |  |  |
| 9 | `ip_hash` | text |  |  |
| 10 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(actor_user_id)` → **users**`(id)`

## capture_sessions

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `capture_session_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK U | NN |
| 3 | `class_uid` | text | FK U | NN |
| 4 | `session_id` | text | U | NN |
| 5 | `signer_id` | text | FK |  |
| 6 | `auth_user_id` | uuid | FK |  |
| 7 | `source_type` | text |  |  |
| 8 | `started_at` | timestamptz |  |  |
| 9 | `ended_at` | timestamptz |  |  |
| 10 | `note` | text |  |  |
| 11 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(tenant_id, signer_id)` → **signers**`(tenant_id, signer_id)`
- `(tenant_id, class_uid)` → **classes**`(tenant_id, class_uid)`
- `(auth_user_id)` → **users**`(id)`

## classes

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `class_uid` | text | PK | NN |
| 2 | `class_idx` | integer |  |  |
| 3 | `slug` | text |  |  |
| 4 | `label_original` | text |  |  |
| 5 | `language` | text | FK |  |
| 6 | `dialect` | text | FK |  |
| 7 | `is_common_global` | boolean |  |  |
| 8 | `is_common_language` | boolean |  |  |
| 9 | `folder_name` | text |  |  |
| 10 | `created_at` | timestamptz |  |  |
| 11 | `migrated_at` | timestamptz |  |  |
| 12 | `deleted_at` | timestamptz |  |  |
| 13 | `description` | text |  |  |
| 14 | `is_active` | boolean |  |  |
| 15 | `hands_required` | integer |  |  |
| 16 | `semantic_label` | text |  |  |
| 17 | `vocabulary_scope` | text |  |  |
| 18 | `recognition_profile` | text | FK |  |
| 19 | `vocabulary_group` | text | FK |  |
| 20 | `collection_campaign` | text |  |  |
| 21 | `motion_type` | text |  |  |
| 22 | `tenant_id` | text | FK | NN |
| 23 | `region` | text | FK | NN |

**Khoá ngoại:**

- `(tenant_id, recognition_profile)` → **recognition_profiles**`(tenant_id, profile_id)`
- `(language)` → **languages**`(code)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(region)` → **regions**`(code)`
- `(tenant_id, vocabulary_group)` → **vocabulary_groups**`(tenant_id, group_id)`
- `(tenant_id, dialect)` → **dialects**`(tenant_id, dialect_id)`

## community_dialects

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `dialect_id` | text | PK | NN |
| 2 | `display_name` | text |  | NN |
| 3 | `language` | text |  | NN |
| 4 | `is_alphabet` | boolean |  | NN |
| 5 | `display_order` | integer |  | NN |
| 6 | `is_active` | boolean |  | NN |
| 7 | `note` | text |  |  |
| 8 | `updated_by` | uuid | FK |  |
| 9 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(updated_by)` → **users**`(id)`

## community_profiles

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `profile_id` | text | PK | NN |
| 2 | `display_name` | text |  | NN |
| 3 | `is_trainable` | boolean |  | NN |
| 4 | `display_order` | integer |  | NN |
| 5 | `is_active` | boolean |  | NN |
| 6 | `note` | text |  |  |
| 7 | `updated_by` | uuid | FK |  |
| 8 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(updated_by)` → **users**`(id)`

## community_versions

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `version` | bigint | PK | NN |
| 2 | `content_hash` | text |  | NN |
| 3 | `snapshot` | jsonb |  | NN |
| 4 | `note` | text |  |  |
| 5 | `created_by` | uuid | FK |  |
| 6 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(created_by)` → **users**`(id)`

## dialect_aliases

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `old_dialect_id` | text | PK | NN |
| 3 | `new_dialect_id` | text | FK | NN |
| 4 | `merged_at` | timestamptz |  | NN |
| 5 | `merged_by` | uuid | FK |  |

**Khoá ngoại:**

- `(tenant_id, new_dialect_id)` → **dialects**`(tenant_id, dialect_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(merged_by)` → **users**`(id)`

## dialects

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `dialect_id` | text | PK | NN |
| 3 | `display_name` | text |  | NN |
| 4 | `language` | text | FK | NN |
| 5 | `is_alphabet` | boolean |  | NN |
| 6 | `is_active` | boolean |  | NN |
| 7 | `status` | text |  | NN |
| 8 | `merged_into` | text | FK |  |
| 9 | `created_by` | uuid | FK |  |
| 10 | `approved_by` | uuid | FK |  |
| 11 | `created_at` | timestamptz |  | NN |
| 12 | `approved_at` | timestamptz |  |  |
| 13 | `note` | text |  |  |
| 14 | `display_order` | integer |  | NN |

**Khoá ngoại:**

- `(tenant_id, merged_into)` → **dialects**`(tenant_id, dialect_id)`
- `(approved_by)` → **users**`(id)`
- `(created_by)` → **users**`(id)`
- `(language)` → **languages**`(code)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## event_outbox

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `event_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK |  |
| 3 | `event_type_code` | text |  | NN |
| 4 | `payload` | jsonb |  | NN |
| 5 | `occurred_at` | timestamptz |  | NN |
| 6 | `created_at` | timestamptz |  | NN |
| 7 | `dispatch_status` | text |  | NN |
| 8 | `attempts` | integer |  | NN |
| 9 | `available_at` | timestamptz |  | NN |
| 10 | `processed_at` | timestamptz |  |  |
| 11 | `last_error` | text |  |  |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`

## google_sheets_sync_status

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `id` | integer | PK | NN |
| 2 | `table_name` | varchar(50) | U | NN |
| 3 | `current_spreadsheet_id` | varchar(100) |  | NN |
| 4 | `current_sheet_index` | integer |  | NN |
| 5 | `current_data_rows` | integer |  | NN |
| 6 | `max_rows_per_sheet` | integer |  | NN |
| 7 | `updated_at` | timestamptz |  |  |

## languages

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `code` | varchar(50) | PK | NN |
| 2 | `name` | text |  | NN |

## legal_document_drafts

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `draft_id` | uuid | PK | NN |
| 2 | `kind` | text |  | NN |
| 3 | `title` | text |  | NN |
| 4 | `language` | text |  | NN |
| 5 | `body` | text |  | NN |
| 6 | `body_format` | text |  | NN |
| 7 | `change_summary` | text |  | NN |
| 8 | `target_version` | text |  | NN |
| 9 | `requires_reconsent` | boolean |  | NN |
| 10 | `effective_from` | timestamptz |  |  |
| 11 | `status` | text |  | NN |
| 12 | `revision` | integer |  | NN |
| 13 | `based_on_version` | text |  |  |
| 14 | `published_version` | text |  |  |
| 15 | `storage_key` | text |  |  |
| 16 | `content_hash` | text |  |  |
| 17 | `byte_size` | integer |  | NN |
| 18 | `created_by` | uuid | FK |  |
| 19 | `updated_by` | uuid | FK |  |
| 20 | `created_at` | timestamptz |  | NN |
| 21 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(updated_by)` → **users**`(id)`
- `(created_by)` → **users**`(id)`

## legal_document_events

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `event_id` | bigint | PK | NN |
| 2 | `occurred_at` | timestamptz |  | NN |
| 3 | `actor_user_id` | uuid |  |  |
| 4 | `actor_label` | text |  | NN |
| 5 | `action` | text |  | NN |
| 6 | `kind` | text |  |  |
| 7 | `version` | text |  |  |
| 8 | `draft_id` | uuid |  |  |
| 9 | `revision` | integer |  |  |
| 10 | `storage_key` | text |  |  |
| 11 | `content_hash` | text |  |  |
| 12 | `detail` | jsonb |  |  |

## legal_documents

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `doc_id` | uuid | PK | NN |
| 2 | `kind` | text | U | NN |
| 3 | `version` | text | U | NN |
| 4 | `effective_from` | timestamptz |  | NN |
| 5 | `content_hash` | text |  | NN |
| 6 | `url` | text |  | NN |
| 7 | `title` | text |  | NN |
| 8 | `requires_reconsent` | boolean |  | NN |
| 9 | `body` | text |  | NN |
| 10 | `body_format` | text |  | NN |
| 11 | `language` | text |  | NN |
| 12 | `change_summary` | text |  | NN |
| 13 | `published_at` | timestamptz |  | NN |
| 14 | `published_by` | uuid | FK |  |
| 15 | `storage_backend` | text |  | NN |
| 16 | `storage_key` | text |  |  |
| 17 | `byte_size` | integer |  | NN |
| 18 | `file_key` | text |  |  |
| 19 | `file_name` | text |  |  |
| 20 | `file_mime` | text |  |  |
| 21 | `file_size` | bigint |  |  |

**Khoá ngoại:**

- `(published_by)` → **users**`(id)`

## memberships

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `membership_id` | uuid | PK U | NN |
| 2 | `user_id` | uuid | FK U | NN |
| 3 | `scope_level` | text |  | NN |
| 4 | `tenant_id` | text | FK | NN |
| 5 | `workspace_id` | uuid | FK |  |
| 6 | `project_id` | uuid | FK |  |
| 7 | `parent_membership_id` | uuid | FK |  |
| 8 | `legacy_role` | text |  |  |
| 9 | `status` | text |  | NN |
| 10 | `joined_at` | timestamptz |  |  |
| 11 | `suspended_at` | timestamptz |  |  |
| 12 | `left_at` | timestamptz |  |  |
| 13 | `created_at` | timestamptz |  | NN |
| 14 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(parent_membership_id, user_id)` → **memberships**`(membership_id, user_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(tenant_id, workspace_id, project_id)` → **projects**`(tenant_id, workspace_id, project_id)`
- `(tenant_id, workspace_id)` → **workspaces**`(tenant_id, workspace_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(user_id)` → **users**`(id)`

## notifications

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `notification_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `user_id` | uuid | FK | NN |
| 4 | `kind` | text |  | NN |
| 5 | `title` | text |  | NN |
| 6 | `body` | text |  | NN |
| 7 | `link` | text |  |  |
| 8 | `severity` | text |  | NN |
| 9 | `read_at` | timestamptz |  |  |
| 10 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(user_id)` → **users**`(id)`

## password_reset_tokens

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `token_hash` | text | PK | NN |
| 2 | `user_id` | uuid | FK | NN |
| 3 | `expires_at` | timestamptz |  | NN |
| 4 | `used_at` | timestamptz |  |  |
| 5 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(user_id)` → **users**`(id)`

## permissions

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `permission_code` | text | PK | NN |
| 2 | `description` | text |  | NN |
| 3 | `applicable_scope` | text |  | NN |
| 4 | `risk_level` | text |  | NN |
| 5 | `requires_passcode` | boolean |  | NN |
| 6 | `is_api_assignable` | boolean |  | NN |
| 7 | `is_active` | boolean |  | NN |
| 8 | `created_at` | timestamptz |  | NN |
| 9 | `is_custom_role_allowed` | boolean |  | NN |

## plans

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `plan_code` | text | PK | NN |
| 2 | `display_name` | text |  | NN |
| 3 | `description` | text |  | NN |
| 4 | `max_seats` | integer |  |  |
| 5 | `max_samples` | integer |  |  |
| 6 | `max_storage_mb` | integer |  |  |
| 7 | `max_classes` | integer |  |  |
| 8 | `max_training_jobs_per_month` | integer |  |  |
| 9 | `max_concurrent_training_jobs` | integer |  |  |
| 10 | `max_queued_training_jobs` | integer |  |  |
| 11 | `max_api_keys` | integer |  |  |
| 12 | `max_webhook_endpoints` | integer |  |  |
| 13 | `price_cents` | bigint |  |  |
| 14 | `currency` | text |  | NN |
| 15 | `billing_period` | text |  | NN |
| 16 | `is_self_serve` | boolean |  | NN |
| 17 | `is_listed` | boolean |  | NN |
| 18 | `trial_days` | integer |  | NN |
| 19 | `sort_order` | integer |  | NN |
| 20 | `created_at` | timestamptz |  | NN |
| 21 | `updated_at` | timestamptz |  | NN |
| 22 | `max_workspaces` | integer |  |  |
| 23 | `max_projects` | integer |  |  |
| 24 | `included_training_credits` | integer |  |  |
| 25 | `audit_retention_days` | integer |  |  |

## platform_settings

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `key` | text | PK | NN |
| 2 | `value` | text |  | NN |
| 3 | `updated_by` | uuid | FK |  |
| 4 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(updated_by)` → **users**`(id)`

## project_allocations

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `project_id` | uuid | PK FK | NN |
| 3 | `metric` | text | PK | NN |
| 4 | `allocated` | bigint |  |  |
| 5 | `note` | text |  | NN |
| 6 | `updated_by` | uuid | FK |  |
| 7 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(tenant_id, project_id)` → **projects**`(tenant_id, project_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(updated_by)` → **users**`(id)`

## projects

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `project_id` | uuid | PK U | NN |
| 2 | `tenant_id` | text | FK U | NN |
| 3 | `workspace_id` | uuid | FK U | NN |
| 4 | `name` | text |  | NN |
| 5 | `description` | text |  | NN |
| 6 | `status` | text |  | NN |
| 7 | `is_default` | boolean |  | NN |
| 8 | `created_at` | timestamptz |  | NN |
| 9 | `archived_at` | timestamptz |  |  |
| 10 | `deleted_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(tenant_id, workspace_id)` → **workspaces**`(tenant_id, workspace_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## raw_uploads

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `upload_uid` | text | PK | NN |
| 2 | `class_uid` | text | FK |  |
| 3 | `slug` | text |  |  |
| 4 | `label_original` | text |  |  |
| 5 | `language` | text | FK |  |
| 6 | `dialect` | text | FK |  |
| 7 | `source_type` | text |  |  |
| 8 | `user_id` | text |  |  |
| 9 | `auth_user_id` | uuid | FK |  |
| 10 | `session_id` | text |  |  |
| 11 | `original_filename` | text |  |  |
| 12 | `local_path` | text |  |  |
| 13 | `storage_key` | text |  |  |
| 14 | `storage_url` | text |  |  |
| 15 | `created_at` | timestamptz |  |  |
| 16 | `updated_at` | timestamptz |  |  |
| 17 | `deleted_at` | timestamptz |  |  |
| 18 | `status` | varchar(20) |  |  |
| 19 | `session_uid` | text |  |  |
| 20 | `username` | text |  |  |
| 21 | `tenant_id` | text | FK | NN |

**Khoá ngoại:**

- `(language)` → **languages**`(code)`
- `(tenant_id, dialect)` → **dialects**`(tenant_id, dialect_id)`
- `(auth_user_id)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(tenant_id, class_uid)` → **classes**`(tenant_id, class_uid)`

## recognition_profiles

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `profile_id` | text | PK | NN |
| 3 | `display_name` | text |  | NN |
| 4 | `is_trainable` | boolean |  | NN |
| 5 | `is_active` | boolean |  | NN |
| 6 | `created_at` | timestamptz |  | NN |
| 7 | `display_order` | integer |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`

## refresh_tokens

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `token_hash` | text | PK | NN |
| 2 | `user_id` | uuid | FK | NN |
| 3 | `expires_at` | timestamptz |  | NN |
| 4 | `revoked_at` | timestamptz |  |  |
| 5 | `created_at` | timestamptz |  | NN |
| 6 | `family_id` | uuid |  |  |
| 7 | `replaced_by` | text |  |  |
| 8 | `reuse_detected_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(user_id)` → **users**`(id)`

## regions

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `code` | text | PK | NN |
| 2 | `name_vi` | text |  | NN |
| 3 | `name_en` | text |  | NN |
| 4 | `status` | text |  | NN |
| 5 | `sort_order` | integer |  | NN |
| 6 | `is_active` | boolean |  | NN |
| 7 | `note` | text |  |  |
| 8 | `updated_at` | timestamptz |  | NN |

## registry_versions

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `version` | bigint | PK | NN |
| 3 | `content_hash` | text |  | NN |
| 4 | `snapshot` | jsonb |  | NN |
| 5 | `note` | text |  |  |
| 6 | `created_by` | uuid | FK |  |
| 7 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(created_by)` → **users**`(id)`

## role_assignments

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `assignment_id` | uuid | PK | NN |
| 2 | `user_id` | uuid | FK | NN |
| 3 | `role_id` | uuid | FK | NN |
| 4 | `membership_id` | uuid | FK |  |
| 5 | `assigned_by_user_id` | uuid | FK | NN |
| 6 | `assigned_at` | timestamptz |  | NN |
| 7 | `revoked_by_user_id` | uuid | FK |  |
| 8 | `revoked_at` | timestamptz |  |  |
| 9 | `revoke_reason` | text |  |  |

**Khoá ngoại:**

- `(membership_id, user_id)` → **memberships**`(membership_id, user_id)`
- `(assigned_by_user_id)` → **users**`(id)`
- `(role_id)` → **roles**`(role_id)`
- `(user_id)` → **users**`(id)`
- `(revoked_by_user_id)` → **users**`(id)`

## role_permissions

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `role_id` | uuid | PK FK | NN |
| 2 | `permission_code` | text | PK FK | NN |
| 3 | `granted_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(permission_code)` → **permissions**`(permission_code)`
- `(role_id)` → **roles**`(role_id)`

## roles

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `role_id` | uuid | PK U | NN |
| 2 | `role_code` | varchar(50) |  | NN |
| 3 | `description` | text |  |  |
| 4 | `tenant_id` | text | FK |  |
| 5 | `scope_level` | text | U |  |
| 6 | `is_builtin` | boolean |  | NN |
| 7 | `is_active` | boolean |  | NN |
| 8 | `created_at` | timestamptz |  | NN |
| 9 | `role_name` | text |  |  |
| 10 | `tenant_type_constraint` | text |  |  |
| 11 | `created_by_user_id` | uuid | FK |  |
| 12 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(created_by_user_id)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## samples

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `sample_uid` | text | PK | NN |
| 2 | `class_uid` | text | FK |  |
| 3 | `slug` | text |  |  |
| 4 | `label_original` | text |  |  |
| 5 | `language` | text | FK |  |
| 6 | `dialect` | text | FK |  |
| 7 | `source_type` | text |  |  |
| 8 | `user_id` | text |  |  |
| 9 | `auth_user_id` | uuid | FK |  |
| 10 | `session_id` | text |  |  |
| 11 | `fps_original` | text |  |  |
| 12 | `fps_processed` | text |  |  |
| 13 | `seq_len` | integer |  |  |
| 14 | `augment_id` | integer |  |  |
| 15 | `completeness` | real |  |  |
| 16 | `file_path` | text |  |  |
| 17 | `storage_url` | text |  |  |
| 18 | `checksum` | text |  |  |
| 19 | `created_at` | timestamptz |  |  |
| 20 | `sheets_synced` | boolean |  |  |
| 21 | `gdrive_synced` | boolean |  |  |
| 22 | `status` | varchar(20) |  |  |
| 23 | `error_log` | text |  |  |
| 24 | `updated_at` | timestamptz |  |  |
| 25 | `storage_key` | text |  |  |
| 26 | `session_uid` | text |  |  |
| 27 | `username` | text |  |  |
| 28 | `deleted_at` | timestamptz |  |  |
| 29 | `left_hand_ratio` | real |  |  |
| 30 | `right_hand_ratio` | real |  |  |
| 31 | `both_hands_ratio` | real |  |  |
| 32 | `jitter` | real |  |  |
| 33 | `quality_flags` | text |  |  |
| 34 | `signer_id` | text | FK |  |
| 35 | `collection_campaign` | text |  |  |
| 36 | `raw_landmarks_available` | boolean |  |  |
| 37 | `normalization_version` | text |  |  |
| 38 | `preprocess_contract_version` | text |  |  |
| 39 | `sequence_length_original` | integer |  |  |
| 40 | `quality_status` | text |  |  |
| 41 | `tenant_id` | text | FK | NN |
| 42 | `capture_session_id` | uuid | FK |  |
| 43 | `review_status` | text |  | NN |
| 44 | `reviewed_by` | uuid | FK |  |
| 45 | `reviewed_at` | timestamptz |  |  |
| 46 | `review_note` | text |  |  |

**Khoá ngoại:**

- `(tenant_id, class_uid)` → **classes**`(tenant_id, class_uid)`
- `(tenant_id, dialect)` → **dialects**`(tenant_id, dialect_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(auth_user_id)` → **users**`(id)`
- `(tenant_id, signer_id)` → **signers**`(tenant_id, signer_id)`
- `(capture_session_id)` → **capture_sessions**`(capture_session_id)`
- `(reviewed_by)` → **users**`(id)`
- `(class_uid)` → **classes**`(class_uid)`
- `(language)` → **languages**`(code)`

## schema_migrations

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `version` | integer | PK | NN |
| 2 | `applied_at` | timestamptz | PK | NN |
| 3 | `applied_by` | text |  | NN |
| 4 | `applied_on` | text |  |  |
| 5 | `note` | text |  |  |
| 6 | `migration_checksum` | text |  |  |

## signer_aliases

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `old_signer_id` | text | PK | NN |
| 3 | `new_signer_id` | text | FK | NN |
| 4 | `reason` | text |  |  |
| 5 | `merged_at` | timestamptz |  | NN |
| 6 | `merged_by` | uuid | FK |  |

**Khoá ngoại:**

- `(merged_by)` → **users**`(id)`
- `(tenant_id, new_signer_id)` → **signers**`(tenant_id, signer_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## signer_consents

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `consent_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `signer_id` | text | FK | NN |
| 4 | `scope` | text |  | NN |
| 5 | `kind` | text | FK | NN |
| 6 | `version` | text | FK | NN |
| 7 | `granted_at` | timestamptz |  | NN |
| 8 | `withdrawn_at` | timestamptz |  |  |
| 9 | `guardian_name` | text |  |  |
| 10 | `evidence` | text |  |  |
| 11 | `recorded_by` | uuid | FK |  |

**Khoá ngoại:**

- `(kind, version)` → **legal_documents**`(kind, version)`
- `(recorded_by)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(tenant_id, signer_id)` → **signers**`(tenant_id, signer_id)`

## signers

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `signer_id` | text | PK | NN |
| 2 | `display_name` | text |  |  |
| 3 | `regional_group` | text |  |  |
| 4 | `external_user_id` | uuid | FK |  |
| 5 | `is_active` | boolean |  |  |
| 6 | `created_at` | timestamptz |  |  |
| 7 | `tenant_id` | text | FK | NN |
| 8 | `note` | text |  |  |
| 9 | `display_order` | integer |  | NN |

**Khoá ngoại:**

- `(external_user_id)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## sot_authorized_keys

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `public_key` | text | PK | NN |
| 2 | `name` | text | U | NN |
| 3 | `fingerprint` | text |  | NN |
| 4 | `note` | text |  |  |
| 5 | `added_by` | text |  |  |
| 6 | `added_at` | timestamptz |  | NN |
| 7 | `revoked_at` | timestamptz |  |  |

## support_messages

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `message_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `ticket_id` | uuid | FK | NN |
| 4 | `author_id` | uuid | FK |  |
| 5 | `author_label` | text |  | NN |
| 6 | `is_staff` | boolean |  | NN |
| 7 | `body` | text |  | NN |
| 8 | `created_at` | timestamptz |  | NN |
| 9 | `author_kind` | text |  |  |

**Khoá ngoại:**

- `(author_id)` → **users**`(id)`
- `(ticket_id)` → **support_tickets**`(ticket_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## support_tickets

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `ticket_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `user_id` | uuid | FK |  |
| 4 | `subject` | text |  | NN |
| 5 | `category` | text |  | NN |
| 6 | `status` | text |  | NN |
| 7 | `priority` | text |  | NN |
| 8 | `created_at` | timestamptz |  | NN |
| 9 | `updated_at` | timestamptz |  | NN |
| 10 | `resolved_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(user_id)` → **users**`(id)`

## tenant_exports

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `export_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `requested_by` | uuid | FK |  |
| 4 | `status` | text |  | NN |
| 5 | `scope` | text |  | NN |
| 6 | `file_path` | text |  |  |
| 7 | `size_bytes` | bigint |  |  |
| 8 | `row_counts` | jsonb |  |  |
| 9 | `error` | text |  |  |
| 10 | `created_at` | timestamptz |  | NN |
| 11 | `completed_at` | timestamptz |  |  |
| 12 | `expires_at` | timestamptz |  |  |
| 13 | `export_purpose` | text |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(requested_by)` → **users**`(id)`

## tenant_invitations

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `invitation_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `email` | text |  | NN |
| 4 | `role` | text |  |  |
| 5 | `token_hash` | text | U | NN |
| 6 | `invited_by` | uuid | FK |  |
| 7 | `created_at` | timestamptz |  | NN |
| 8 | `expires_at` | timestamptz |  | NN |
| 9 | `accepted_at` | timestamptz |  |  |
| 10 | `accepted_by` | uuid | FK |  |
| 11 | `revoked_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(accepted_by)` → **users**`(id)`
- `(invited_by)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## tenant_purges

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `purge_id` | uuid | PK | NN |
| 2 | `tenant_id` | text |  | NN |
| 3 | `display_name` | text |  | NN |
| 4 | `requested_by` | uuid |  |  |
| 5 | `row_counts` | jsonb |  |  |
| 6 | `files_removed` | integer |  | NN |
| 7 | `bytes_removed` | bigint |  | NN |
| 8 | `export_id` | uuid |  |  |
| 9 | `reason` | text |  | NN |
| 10 | `created_at` | timestamptz |  | NN |

## tenant_subscriptions

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `subscription_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `plan_code` | text | FK | NN |
| 4 | `status` | text |  | NN |
| 5 | `started_at` | timestamptz |  | NN |
| 6 | `ended_at` | timestamptz |  |  |
| 7 | `changed_by` | uuid | FK |  |
| 8 | `note` | text |  | NN |
| 9 | `created_at` | timestamptz |  | NN |
| 10 | `current_period_start` | timestamptz |  |  |
| 11 | `current_period_end` | timestamptz |  |  |
| 12 | `auto_renew` | boolean |  | NN |
| 13 | `grace_until` | timestamptz |  |  |
| 14 | `trial_ends_at` | timestamptz |  |  |
| 15 | `last_reminder_days` | integer |  |  |

**Khoá ngoại:**

- `(changed_by)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(plan_code)` → **plans**`(plan_code)`

## tenant_usage_daily

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `usage_date` | date | PK | NN |
| 3 | `metric` | text | PK | NN |
| 4 | `value` | bigint |  | NN |
| 5 | `computed_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`

## tenants

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK | NN |
| 2 | `display_name` | text |  |  |
| 3 | `slug` | text | U |  |
| 4 | `is_active` | boolean |  | NN |
| 5 | `created_at` | timestamptz |  | NN |
| 6 | `deleted_at` | timestamptz |  |  |
| 7 | `cloned_from_community_version` | bigint | FK |  |
| 8 | `cloned_at` | timestamptz |  |  |
| 9 | `plan_code` | text | FK | NN |
| 10 | `billing_status` | text |  | NN |
| 11 | `trial_ends_at` | timestamptz |  |  |
| 12 | `current_period_start` | timestamptz |  |  |
| 13 | `current_period_end` | timestamptz |  |  |
| 14 | `is_self_serve` | boolean |  | NN |
| 15 | `owner_user_id` | uuid | FK |  |
| 16 | `suspended_at` | timestamptz |  |  |
| 17 | `suspended_reason` | text |  |  |
| 18 | `tenant_type` | text |  | NN |
| 19 | `is_system_reserved` | boolean |  | NN |
| 20 | `billing_exempt` | boolean |  | NN |

**Khoá ngoại:**

- `(cloned_from_community_version)` → **community_versions**`(version)`
- `(owner_user_id)` → **users**`(id)`
- `(plan_code)` → **plans**`(plan_code)`

## training_job_classes

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `job_id` | text | PK FK | NN |
| 2 | `class_idx` | integer | PK | NN |
| 3 | `class_uid` | text | FK |  |
| 4 | `label` | text |  | NN |
| 5 | `tenant_id` | text | FK | NN |

**Khoá ngoại:**

- `(class_uid)` → **classes**`(class_uid)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(job_id)` → **training_jobs**`(job_id)`

## training_jobs

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `job_id` | text | PK U | NN |
| 2 | `status` | text |  | NN |
| 3 | `model_type` | text |  |  |
| 4 | `config` | jsonb |  |  |
| 5 | `auth_user_id` | uuid | FK |  |
| 6 | `created_at` | timestamptz |  |  |
| 7 | `started_at` | timestamptz |  |  |
| 8 | `completed_at` | timestamptz |  |  |
| 9 | `current_epoch` | integer |  | NN |
| 10 | `total_epochs` | integer |  | NN |
| 11 | `checkpoint_path` | text |  |  |
| 12 | `test_acc` | real |  |  |
| 13 | `test_f1` | real |  |  |
| 14 | `error_message` | text |  |  |
| 15 | `promoted_at` | timestamptz |  |  |
| 16 | `evaluation` | jsonb |  |  |
| 17 | `superseded_at` | timestamptz |  |  |
| 18 | `tenant_id` | text | FK U | NN |
| 19 | `registry_version` | bigint | FK |  |

**Khoá ngoại:**

- `(auth_user_id)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`
- `(tenant_id, registry_version)` → **registry_versions**`(tenant_id, version)`

## training_metrics

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `job_id` | text | PK FK | NN |
| 2 | `epoch` | integer | PK | NN |
| 3 | `train_loss` | real |  |  |
| 4 | `train_acc` | real |  |  |
| 5 | `val_loss` | real |  |  |
| 6 | `val_acc` | real |  |  |
| 7 | `val_f1` | real |  |  |
| 8 | `created_at` | timestamptz |  | NN |
| 9 | `tenant_id` | text | FK | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(tenant_id, job_id)` → **training_jobs**`(tenant_id, job_id)`
- `(job_id)` → **training_jobs**`(job_id)`

## user_action_passcodes

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `user_id` | uuid | PK FK | NN |
| 2 | `passcode_hash` | text |  | NN |
| 3 | `status` | text |  | NN |
| 4 | `failed_count` | smallint |  | NN |
| 5 | `created_at` | timestamptz |  | NN |
| 6 | `updated_at` | timestamptz |  | NN |
| 7 | `locked_until` | timestamptz |  |  |
| 8 | `revoked_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(user_id)` → **users**`(id)`

## user_consents

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `consent_id` | uuid | PK | NN |
| 2 | `user_id` | uuid | FK | NN |
| 3 | `kind` | text | FK | NN |
| 4 | `version` | text | FK | NN |
| 5 | `accepted_at` | timestamptz |  | NN |
| 6 | `ip_hash` | text |  |  |
| 7 | `user_agent` | text |  |  |
| 8 | `withdrawn_at` | timestamptz |  |  |
| 9 | `source` | text |  | NN |
| 10 | `note` | text |  | NN |
| 11 | `recorded_by` | uuid | FK |  |

**Khoá ngoại:**

- `(kind, version)` → **legal_documents**`(kind, version)`
- `(recorded_by)` → **users**`(id)`
- `(user_id)` → **users**`(id)`

## user_recovery_codes

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `code_hash` | text | PK | NN |
| 2 | `user_id` | uuid | FK | NN |
| 3 | `used_at` | timestamptz |  |  |
| 4 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(user_id)` → **users**`(id)`

## user_totp

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `user_id` | uuid | PK FK | NN |
| 2 | `secret_enc` | text |  | NN |
| 3 | `confirmed_at` | timestamptz |  |  |
| 4 | `last_used_step` | bigint |  |  |
| 5 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(user_id)` → **users**`(id)`

## users

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `id` | uuid | PK | NN |
| 2 | `username` | text | U | NN |
| 3 | `email` | text | U | NN |
| 4 | `password_hash` | text |  | NN |
| 5 | `is_active` | boolean |  | NN |
| 6 | `is_admin` | boolean |  | NN |
| 7 | `created_at` | timestamptz |  | NN |
| 8 | `role_id` | uuid | FK |  |
| 9 | `phone_number` | varchar(20) | U |  |
| 10 | `updated_at` | timestamptz |  |  |
| 11 | `deleted_at` | timestamptz |  |  |
| 12 | `tenant_id` | text | FK | NN |
| 13 | `email_verified_at` | timestamptz |  |  |
| 14 | `phone_verified_at` | timestamptz |  |  |
| 15 | `sessions_invalid_before` | timestamptz |  |  |
| 16 | `active_tenant_id` | text |  |  |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`
- `(role_id)` → **roles**`(role_id)`

## verification_codes

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `challenge_id` | uuid | PK | NN |
| 2 | `user_id` | uuid | FK |  |
| 3 | `purpose` | text |  | NN |
| 4 | `channel` | text |  | NN |
| 5 | `destination` | text |  | NN |
| 6 | `code_hash` | text |  | NN |
| 7 | `attempts` | integer |  | NN |
| 8 | `max_attempts` | integer |  | NN |
| 9 | `created_at` | timestamptz |  | NN |
| 10 | `expires_at` | timestamptz |  | NN |
| 11 | `consumed_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(user_id)` → **users**`(id)`

## vocabulary_groups

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `group_id` | text | PK | NN |
| 3 | `display_name` | text |  | NN |
| 4 | `display_order` | integer |  | NN |
| 5 | `is_active` | boolean |  | NN |
| 6 | `created_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`

## vocabulary_registry_meta

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `tenant_id` | text | PK FK | NN |
| 2 | `version` | bigint |  | NN |
| 3 | `updated_at` | timestamptz |  | NN |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`

## webhook_deliveries

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `delivery_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `endpoint_id` | uuid | FK | NN |
| 4 | `event_type` | text |  | NN |
| 5 | `payload` | jsonb |  | NN |
| 6 | `status` | text |  | NN |
| 7 | `attempts` | integer |  | NN |
| 8 | `last_status_code` | integer |  |  |
| 9 | `last_error` | text |  |  |
| 10 | `next_attempt_at` | timestamptz |  | NN |
| 11 | `created_at` | timestamptz |  | NN |
| 12 | `delivered_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(endpoint_id)` → **webhook_endpoints**`(endpoint_id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## webhook_endpoints

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `endpoint_id` | uuid | PK | NN |
| 2 | `tenant_id` | text | FK | NN |
| 3 | `url` | text |  | NN |
| 4 | `secret` | text |  | NN |
| 5 | `event_types` | text |  | NN |
| 6 | `is_active` | boolean |  | NN |
| 7 | `description` | text |  | NN |
| 8 | `created_by` | uuid | FK |  |
| 9 | `created_at` | timestamptz |  | NN |
| 10 | `last_success_at` | timestamptz |  |  |
| 11 | `last_failure_at` | timestamptz |  |  |
| 12 | `failure_streak` | integer |  | NN |
| 13 | `disabled_at` | timestamptz |  |  |
| 14 | `disabled_reason` | text |  |  |

**Khoá ngoại:**

- `(created_by)` → **users**`(id)`
- `(tenant_id)` → **tenants**`(tenant_id)`

## workspaces

| # | Cột | Kiểu | Khoá | NN |
|---|---|---|---|---|
| 1 | `workspace_id` | uuid | PK U | NN |
| 2 | `tenant_id` | text | FK U | NN |
| 3 | `name` | text |  | NN |
| 4 | `description` | text |  | NN |
| 5 | `status` | text |  | NN |
| 6 | `is_default` | boolean |  | NN |
| 7 | `created_at` | timestamptz |  | NN |
| 8 | `archived_at` | timestamptz |  |  |
| 9 | `deleted_at` | timestamptz |  |  |

**Khoá ngoại:**

- `(tenant_id)` → **tenants**`(tenant_id)`

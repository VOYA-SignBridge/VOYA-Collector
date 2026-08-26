# Bảng cơ sở dữ liệu v8 — nguồn cho PDM

Sinh thẳng từ catalog của `signdb` (sản xuất) ngày 26/08/2026, lược đồ **v8**,
checksum `fb5b9b90c553`. Không gõ tay dòng nào: 62 bảng, 131 khoá ngoại.

Cách đọc cardinality: cột **Cha** là `1` khi mọi cột khoá ngoại đều NOT NULL,
và `0..1` khi có cột cho phép NULL — tức là con **có thể chưa** nối cha.

## 1. Sáu mươi hai bảng theo tám nhóm

### A. Tenant & Access Management — 12 bảng, 132 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `api_keys` | `key_id` | 12 | 3 | 0 | ✓ | ✓ |
| `memberships` | `membership_id` | 14 | 6 | 2 | ✓ | ✓ |
| `permissions` | `permission_code` | 9 | 0 | 1 | — | — |
| `project_allocations` | `tenant_id+project_id+metric` | 7 | 4 | 0 | ✓ | ✓ |
| `projects` | `project_id` | 10 | 2 | 2 | ✓ | ✓ |
| `role_assignments` | `assignment_id` | 9 | 5 | 0 | — | — |
| `role_permissions` | `role_id+permission_code` | 3 | 2 | 0 | — | — |
| `roles` | `role_id` | 12 | 2 | 3 | ✓ | ✓ |
| `tenant_invitations` | `invitation_id` | 11 | 3 | 0 | ✓ | ✓ |
| `tenants` | `tenant_id` | 20 | 3 | 39 | ✓ | ✓ |
| `users` | `id` | 16 | 2 | 46 | ✓ | ✓ |
| `workspaces` | `workspace_id` | 9 | 1 | 2 | ✓ | ✓ |

### B. Authentication & User Security — 6 bảng, 41 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `password_reset_tokens` | `token_hash` | 5 | 1 | 0 | — | — |
| `refresh_tokens` | `token_hash` | 8 | 1 | 0 | — | — |
| `user_action_passcodes` | `user_id` | 8 | 1 | 0 | — | — |
| `user_recovery_codes` | `code_hash` | 4 | 1 | 0 | — | — |
| `user_totp` | `user_id` | 5 | 1 | 0 | — | — |
| `verification_codes` | `challenge_id` | 11 | 1 | 0 | — | — |

### C. VSL Vocabulary & Registry — 12 bảng, 98 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `classes` | `class_uid` | 23 | 6 | 5 | ✓ | ✓ |
| `community_dialects` | `dialect_id` | 9 | 1 | 0 | — | — |
| `community_profiles` | `profile_id` | 8 | 1 | 0 | — | — |
| `community_versions` | `version` | 6 | 1 | 1 | — | — |
| `dialect_aliases` | `tenant_id+old_dialect_id` | 5 | 3 | 0 | ✓ | ✓ |
| `dialects` | `tenant_id+dialect_id` | 14 | 5 | 5 | ✓ | ✓ |
| `languages` | `code` | 2 | 0 | 4 | — | — |
| `recognition_profiles` | `tenant_id+profile_id` | 7 | 1 | 1 | ✓ | ✓ |
| `regions` | `code` | 8 | 0 | 1 | — | — |
| `registry_versions` | `tenant_id+version` | 7 | 2 | 2 | ✓ | ✓ |
| `vocabulary_groups` | `tenant_id+group_id` | 6 | 1 | 1 | ✓ | ✓ |
| `vocabulary_registry_meta` | `tenant_id` | 3 | 2 | 0 | ✓ | ✓ |

### D. VSL Collection & Dataset — 6 bảng, 103 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `capture_sessions` | `capture_session_id` | 12 | 5 | 2 | ✓ | ✓ |
| `collection_sessions` | `collection_session_id` | 9 | 2 | 1 | ✓ | ✓ |
| `raw_uploads` | `upload_uid` | 21 | 5 | 0 | ✓ | ✓ |
| `samples` | `sample_uid` | 46 | 10 | 0 | ✓ | ✓ |
| `signer_aliases` | `tenant_id+old_signer_id` | 6 | 3 | 0 | ✓ | ✓ |
| `signers` | `signer_id` | 9 | 2 | 4 | ✓ | ✓ |

### E. Legal, Consent & Governance — 9 bảng, 116 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `audit_log` | `audit_id` | 10 | 2 | 0 | ✓ | ✓ |
| `legal_document_drafts` | `draft_id` | 21 | 2 | 0 | — | — |
| `legal_document_events` | `event_id` | 12 | 0 | 0 | — | — |
| `legal_documents` | `doc_id` | 21 | 1 | 2 | — | — |
| `signer_consents` | `consent_id` | 11 | 4 | 0 | ✓ | ✓ |
| `sot_authorized_keys` | `public_key` | 7 | 0 | 0 | — | — |
| `tenant_exports` | `export_id` | 13 | 2 | 0 | ✓ | ✓ |
| `tenant_purges` | `purge_id` | 10 | 0 | 0 | — | ✓ |
| `user_consents` | `consent_id` | 11 | 3 | 0 | — | — |

### F. Training & Evaluation — 3 bảng, 33 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `training_job_classes` | `job_id+class_idx` | 5 | 3 | 0 | ✓ | ✓ |
| `training_jobs` | `job_id` | 19 | 3 | 3 | ✓ | ✓ |
| `training_metrics` | `job_id+epoch` | 9 | 3 | 0 | ✓ | ✓ |

### G. Plan, Billing & Storage — 5 bảng, 54 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `plans` | `plan_code` | 25 | 0 | 2 | — | — |
| `storage_reservations` | `reservation_id` | 5 | 1 | 0 | ✓ | ✓ |
| `tenant_storage` | `tenant_id` | 4 | 1 | 0 | ✓ | ✓ |
| `tenant_subscriptions` | `subscription_id` | 15 | 3 | 0 | ✓ | ✓ |
| `tenant_usage_daily` | `tenant_id+usage_date+metric` | 5 | 1 | 0 | ✓ | ✓ |

### H. Integration & Operations — 9 bảng, 83 cột

| Bảng | Khoá chính | Cột | FK ra | FK vào | RLS | Có `tenant_id` |
|---|---|---:|---:|---:|:--:|:--:|
| `event_outbox` | `event_id` | 11 | 1 | 0 | ✓ | ✓ |
| `google_sheets_sync_status` | `id` | 7 | 0 | 0 | — | — |
| `notifications` | `notification_id` | 10 | 2 | 0 | ✓ | ✓ |
| `platform_settings` | `key` | 4 | 1 | 0 | — | — |
| `schema_migrations` | `version+applied_at` | 6 | 0 | 0 | — | — |
| `support_messages` | `message_id` | 9 | 3 | 0 | ✓ | ✓ |
| `support_tickets` | `ticket_id` | 10 | 2 | 1 | ✓ | ✓ |
| `webhook_deliveries` | `delivery_id` | 12 | 2 | 0 | ✓ | ✓ |
| `webhook_endpoints` | `endpoint_id` | 14 | 2 | 1 | ✓ | ✓ |

## 2. Hai mươi bảy khoá ngoại GHÉP — rào cản xuyên tenant

Đây là nhóm đáng nói nhất trong luận văn. Khoá ngoại ghép `(tenant_id, <khoá>)`
khiến việc trỏ sang hàng của tổ chức khác **không biểu diễn được** ở tầng lược
đồ, chứ không phải chỉ bị chặn bởi mã ứng dụng. Trên ERD nên vẽ chúng khác
kiểu với khoá ngoại một cột.

| Con | Cột con | Cha | Cột cha | Cha | Con | ON DELETE |
|---|---|---|---|:--:|:--:|---|
| `capture_sessions` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 1 | 0..N | NO ACTION |
| `capture_sessions` | `tenant_id+collection_session_id` | `collection_sessions` | `tenant_id+collection_session_id` | 0..1 | 0..N | SET NULL |
| `capture_sessions` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 0..1 | 0..N | NO ACTION |
| `classes` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION |
| `classes` | `tenant_id+recognition_profile` | `recognition_profiles` | `tenant_id+profile_id` | 0..1 | 0..N | NO ACTION |
| `classes` | `tenant_id+vocabulary_group` | `vocabulary_groups` | `tenant_id+group_id` | 0..1 | 0..N | NO ACTION |
| `dialect_aliases` | `tenant_id+new_dialect_id` | `dialects` | `tenant_id+dialect_id` | 1 | 0..N | NO ACTION |
| `dialects` | `tenant_id+merged_into` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION |
| `memberships` | `parent_membership_id+user_id` | `memberships` | `membership_id+user_id` | 0..1 | 0..N | CASCADE |
| `memberships` | `tenant_id+workspace_id+project_id` | `projects` | `tenant_id+workspace_id+project_id` | 0..1 | 0..N | CASCADE |
| `memberships` | `tenant_id+workspace_id` | `workspaces` | `tenant_id+workspace_id` | 0..1 | 0..N | CASCADE |
| `project_allocations` | `tenant_id+project_id` | `projects` | `tenant_id+project_id` | 1 | 0..N | CASCADE |
| `projects` | `tenant_id+workspace_id` | `workspaces` | `tenant_id+workspace_id` | 1 | 0..N | RESTRICT |
| `raw_uploads` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 0..1 | 0..N | NO ACTION |
| `raw_uploads` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION |
| `role_assignments` | `membership_id+user_id` | `memberships` | `membership_id+user_id` | 0..1 | 0..N | CASCADE |
| `samples` | `tenant_id+capture_session_id` | `capture_sessions` | `tenant_id+capture_session_id` | 0..1 | 0..N | SET NULL |
| `samples` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 0..1 | 0..N | NO ACTION |
| `samples` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 0..1 | 0..N | NO ACTION |
| `samples` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION |
| `signer_aliases` | `tenant_id+new_signer_id` | `signers` | `tenant_id+signer_id` | 1 | 0..N | NO ACTION |
| `signer_consents` | `kind+version` | `legal_documents` | `kind+version` | 1 | 0..N | RESTRICT |
| `signer_consents` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 1 | 0..N | NO ACTION |
| `training_jobs` | `tenant_id+registry_version` | `registry_versions` | `tenant_id+version` | 0..1 | 0..N | NO ACTION |
| `training_metrics` | `tenant_id+job_id` | `training_jobs` | `tenant_id+job_id` | 1 | 0..N | CASCADE |
| `user_consents` | `kind+version` | `legal_documents` | `kind+version` | 1 | 0..N | RESTRICT |
| `vocabulary_registry_meta` | `tenant_id+version` | `registry_versions` | `tenant_id+version` | 0..1 | 0..1 | NO ACTION |

## 3. Toàn bộ 131 khoá ngoại

| Con | Cột con | Cha | Cột cha | Cha | Con | ON DELETE | Tên ràng buộc |
|---|---|---|---|:--:|:--:|---|---|
| `api_keys` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `api_keys_created_by_fkey` |
| `api_keys` | `revoked_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `api_keys_revoked_by_fkey` |
| `api_keys` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_api_keys_tenant` |
| `audit_log` | `actor_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `audit_log_actor_user_id_fkey` |
| `audit_log` | `tenant_id` | `tenants` | `tenant_id` | 0..1 | 0..N | RESTRICT | `fk_audit_log_tenant` |
| `capture_sessions` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `capture_sessions_auth_user_id_fkey` |
| `capture_sessions` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 1 | 0..N | NO ACTION | `fk_capture_sessions_class` |
| `capture_sessions` | `tenant_id+collection_session_id` | `collection_sessions` | `tenant_id+collection_session_id` | 0..1 | 0..N | SET NULL | `fk_capture_sessions_collection` |
| `capture_sessions` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 0..1 | 0..N | NO ACTION | `fk_capture_sessions_signer` |
| `capture_sessions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_capture_sessions_tenant` |
| `classes` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `classes_dialect_fkey` |
| `classes` | `region` | `regions` | `code` | 1 | 0..N | NO ACTION | `classes_region_fkey` |
| `classes` | `language` | `languages` | `code` | 0..1 | 0..N | NO ACTION | `fk_classes_language` |
| `classes` | `tenant_id+recognition_profile` | `recognition_profiles` | `tenant_id+profile_id` | 0..1 | 0..N | NO ACTION | `fk_classes_recognition_profile` |
| `classes` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_classes_tenant` |
| `classes` | `tenant_id+vocabulary_group` | `vocabulary_groups` | `tenant_id+group_id` | 0..1 | 0..N | NO ACTION | `fk_classes_vocabulary_group` |
| `collection_sessions` | `opened_by_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `collection_sessions_opened_by_user_id_fkey` |
| `collection_sessions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_collection_sessions_tenant` |
| `community_dialects` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `community_dialects_updated_by_fkey` |
| `community_profiles` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `community_profiles_updated_by_fkey` |
| `community_versions` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `community_versions_created_by_fkey` |
| `dialect_aliases` | `merged_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `dialect_aliases_merged_by_fkey` |
| `dialect_aliases` | `tenant_id+new_dialect_id` | `dialects` | `tenant_id+dialect_id` | 1 | 0..N | NO ACTION | `fk_dialect_aliases_new` |
| `dialect_aliases` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_dialect_aliases_tenant` |
| `dialects` | `approved_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `dialects_approved_by_fkey` |
| `dialects` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `dialects_created_by_fkey` |
| `dialects` | `language` | `languages` | `code` | 1 | 0..N | NO ACTION | `fk_dialects_language` |
| `dialects` | `tenant_id+merged_into` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `fk_dialects_merged_into` |
| `dialects` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_dialects_tenant` |
| `event_outbox` | `tenant_id` | `tenants` | `tenant_id` | 0..1 | 0..N | RESTRICT | `fk_event_outbox_tenant` |
| `legal_document_drafts` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `legal_document_drafts_created_by_fkey` |
| `legal_document_drafts` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `legal_document_drafts_updated_by_fkey` |
| `legal_documents` | `published_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `legal_documents_published_by_fkey` |
| `memberships` | `parent_membership_id+user_id` | `memberships` | `membership_id+user_id` | 0..1 | 0..N | CASCADE | `fk_memberships_parent` |
| `memberships` | `tenant_id+workspace_id+project_id` | `projects` | `tenant_id+workspace_id+project_id` | 0..1 | 0..N | CASCADE | `fk_memberships_project` |
| `memberships` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_memberships_tenant` |
| `memberships` | `tenant_id+workspace_id` | `workspaces` | `tenant_id+workspace_id` | 0..1 | 0..N | CASCADE | `fk_memberships_workspace` |
| `memberships` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | CASCADE | `memberships_tenant_id_fkey` |
| `memberships` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `memberships_user_id_fkey` |
| `notifications` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_notifications_tenant` |
| `notifications` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `notifications_user_id_fkey` |
| `password_reset_tokens` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `password_reset_tokens_user_id_fkey` |
| `platform_settings` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `platform_settings_updated_by_fkey` |
| `project_allocations` | `tenant_id+project_id` | `projects` | `tenant_id+project_id` | 1 | 0..N | CASCADE | `fk_project_allocations_project` |
| `project_allocations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_project_allocations_tenant` |
| `project_allocations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | CASCADE | `project_allocations_tenant_id_fkey` |
| `project_allocations` | `updated_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `project_allocations_updated_by_fkey` |
| `projects` | `tenant_id+workspace_id` | `workspaces` | `tenant_id+workspace_id` | 1 | 0..N | RESTRICT | `fk_inv_ten_02_project_workspace` |
| `projects` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_projects_tenant` |
| `raw_uploads` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 0..1 | 0..N | NO ACTION | `fk_raw_uploads_class_tenant` |
| `raw_uploads` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `fk_raw_uploads_dialect` |
| `raw_uploads` | `language` | `languages` | `code` | 0..1 | 0..N | NO ACTION | `fk_raw_uploads_language` |
| `raw_uploads` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_raw_uploads_tenant` |
| `raw_uploads` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `raw_uploads_auth_user_id_fkey` |
| `recognition_profiles` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_recognition_profiles_tenant` |
| `refresh_tokens` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `refresh_tokens_user_id_fkey` |
| `registry_versions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_registry_versions_tenant` |
| `registry_versions` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `registry_versions_created_by_fkey` |
| `role_assignments` | `membership_id+user_id` | `memberships` | `membership_id+user_id` | 0..1 | 0..N | CASCADE | `fk_role_assignments_membership` |
| `role_assignments` | `assigned_by_user_id` | `users` | `id` | 1 | 0..N | RESTRICT | `role_assignments_assigned_by_user_id_fkey` |
| `role_assignments` | `revoked_by_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `role_assignments_revoked_by_user_id_fkey` |
| `role_assignments` | `role_id` | `roles` | `role_id` | 1 | 0..N | RESTRICT | `role_assignments_role_id_fkey` |
| `role_assignments` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `role_assignments_user_id_fkey` |
| `role_permissions` | `permission_code` | `permissions` | `permission_code` | 1 | 0..N | RESTRICT | `fk_role_permissions_permission` |
| `role_permissions` | `role_id` | `roles` | `role_id` | 1 | 0..N | CASCADE | `fk_role_permissions_role` |
| `roles` | `created_by_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `fk_roles_creator` |
| `roles` | `tenant_id` | `tenants` | `tenant_id` | 0..1 | 0..N | CASCADE | `fk_roles_tenant` |
| `samples` | `capture_session_id` | `capture_sessions` | `capture_session_id` | 0..1 | 0..N | SET NULL | `fk_samples_capture_session` |
| `samples` | `tenant_id+capture_session_id` | `capture_sessions` | `tenant_id+capture_session_id` | 0..1 | 0..N | SET NULL | `fk_samples_capture_session_tenant` |
| `samples` | `tenant_id+class_uid` | `classes` | `tenant_id+class_uid` | 0..1 | 0..N | NO ACTION | `fk_samples_class_tenant` |
| `samples` | `language` | `languages` | `code` | 0..1 | 0..N | NO ACTION | `fk_samples_language` |
| `samples` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 0..1 | 0..N | NO ACTION | `fk_samples_signer` |
| `samples` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_samples_tenant` |
| `samples` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `samples_auth_user_id_fkey` |
| `samples` | `class_uid` | `classes` | `class_uid` | 0..1 | 0..N | NO ACTION | `samples_class_uid_fkey` |
| `samples` | `tenant_id+dialect` | `dialects` | `tenant_id+dialect_id` | 0..1 | 0..N | NO ACTION | `samples_dialect_fkey` |
| `samples` | `reviewed_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `samples_reviewed_by_fkey` |
| `signer_aliases` | `tenant_id+new_signer_id` | `signers` | `tenant_id+signer_id` | 1 | 0..N | NO ACTION | `fk_signer_aliases_new` |
| `signer_aliases` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_signer_aliases_tenant` |
| `signer_aliases` | `merged_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `signer_aliases_merged_by_fkey` |
| `signer_consents` | `kind+version` | `legal_documents` | `kind+version` | 1 | 0..N | RESTRICT | `fk_signer_consents_document` |
| `signer_consents` | `tenant_id+signer_id` | `signers` | `tenant_id+signer_id` | 1 | 0..N | NO ACTION | `fk_signer_consents_signer` |
| `signer_consents` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_signer_consents_tenant` |
| `signer_consents` | `recorded_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `signer_consents_recorded_by_fkey` |
| `signers` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_signers_tenant` |
| `signers` | `external_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `fk_signers_user` |
| `storage_reservations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_storage_reservations_tenant` |
| `support_messages` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_support_messages_tenant` |
| `support_messages` | `author_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `support_messages_author_id_fkey` |
| `support_messages` | `ticket_id` | `support_tickets` | `ticket_id` | 1 | 0..N | CASCADE | `support_messages_ticket_id_fkey` |
| `support_tickets` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_support_tickets_tenant` |
| `support_tickets` | `user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `support_tickets_user_id_fkey` |
| `tenant_exports` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_exports_tenant` |
| `tenant_exports` | `requested_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_exports_requested_by_fkey` |
| `tenant_invitations` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_invitations_tenant` |
| `tenant_invitations` | `accepted_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_invitations_accepted_by_fkey` |
| `tenant_invitations` | `invited_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_invitations_invited_by_fkey` |
| `tenant_storage` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..1 | RESTRICT | `fk_tenant_storage_tenant` |
| `tenant_subscriptions` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_subscriptions_tenant` |
| `tenant_subscriptions` | `changed_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `tenant_subscriptions_changed_by_fkey` |
| `tenant_subscriptions` | `plan_code` | `plans` | `plan_code` | 1 | 0..N | NO ACTION | `tenant_subscriptions_plan_code_fkey` |
| `tenant_usage_daily` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_tenant_usage_daily_tenant` |
| `tenants` | `cloned_from_community_version` | `community_versions` | `version` | 0..1 | 0..N | NO ACTION | `fk_tenants_cloned_version` |
| `tenants` | `owner_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `fk_tenants_owner_user` |
| `tenants` | `plan_code` | `plans` | `plan_code` | 1 | 0..N | RESTRICT | `fk_tenants_plan` |
| `training_job_classes` | `class_uid` | `classes` | `class_uid` | 0..1 | 0..N | SET NULL | `fk_training_job_classes_class` |
| `training_job_classes` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_training_job_classes_tenant` |
| `training_job_classes` | `job_id` | `training_jobs` | `job_id` | 1 | 0..N | CASCADE | `training_job_classes_job_id_fkey` |
| `training_jobs` | `tenant_id+registry_version` | `registry_versions` | `tenant_id+version` | 0..1 | 0..N | NO ACTION | `fk_training_jobs_registry` |
| `training_jobs` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_training_jobs_tenant` |
| `training_jobs` | `auth_user_id` | `users` | `id` | 0..1 | 0..N | SET NULL | `training_jobs_auth_user_id_fkey` |
| `training_metrics` | `job_id` | `training_jobs` | `job_id` | 1 | 0..N | CASCADE | `fk_training_metrics_job` |
| `training_metrics` | `tenant_id+job_id` | `training_jobs` | `tenant_id+job_id` | 1 | 0..N | CASCADE | `fk_training_metrics_job_tenant` |
| `training_metrics` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_training_metrics_tenant` |
| `user_action_passcodes` | `user_id` | `users` | `id` | 1 | 0..1 | CASCADE | `user_action_passcodes_user_id_fkey` |
| `user_consents` | `kind+version` | `legal_documents` | `kind+version` | 1 | 0..N | RESTRICT | `user_consents_kind_version_fkey` |
| `user_consents` | `recorded_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `user_consents_recorded_by_fkey` |
| `user_consents` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `user_consents_user_id_fkey` |
| `user_recovery_codes` | `user_id` | `users` | `id` | 1 | 0..N | CASCADE | `user_recovery_codes_user_id_fkey` |
| `user_totp` | `user_id` | `users` | `id` | 1 | 0..1 | CASCADE | `user_totp_user_id_fkey` |
| `users` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_users_tenant` |
| `users` | `role_id` | `roles` | `role_id` | 0..1 | 0..N | NO ACTION | `users_role_id_fkey` |
| `verification_codes` | `user_id` | `users` | `id` | 0..1 | 0..N | CASCADE | `verification_codes_user_id_fkey` |
| `vocabulary_groups` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_vocabulary_groups_tenant` |
| `vocabulary_registry_meta` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..1 | RESTRICT | `fk_vocabulary_registry_meta_tenant` |
| `vocabulary_registry_meta` | `tenant_id+version` | `registry_versions` | `tenant_id+version` | 0..1 | 0..1 | NO ACTION | `fk_vocabulary_registry_meta_version` |
| `webhook_deliveries` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_webhook_deliveries_tenant` |
| `webhook_deliveries` | `endpoint_id` | `webhook_endpoints` | `endpoint_id` | 1 | 0..N | CASCADE | `webhook_deliveries_endpoint_id_fkey` |
| `webhook_endpoints` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_webhook_endpoints_tenant` |
| `webhook_endpoints` | `created_by` | `users` | `id` | 0..1 | 0..N | SET NULL | `webhook_endpoints_created_by_fkey` |
| `workspaces` | `tenant_id` | `tenants` | `tenant_id` | 1 | 0..N | RESTRICT | `fk_workspaces_tenant` |

## 4. Bảng bị trỏ tới nhiều nhất (quyết định bố cục hình)

Bảng càng nhiều mũi tên vào thì càng phải đặt ở trung tâm, nếu không hình sẽ
thành mạng dây.

| Bảng cha | Số khoá ngoại trỏ vào |
|---|---:|
| `users` | 46 |
| `tenants` | 39 |
| `classes` | 5 |
| `dialects` | 5 |
| `signers` | 4 |
| `languages` | 4 |
| `roles` | 3 |
| `training_jobs` | 3 |
| `memberships` | 2 |
| `projects` | 2 |
| `workspaces` | 2 |
| `capture_sessions` | 2 |

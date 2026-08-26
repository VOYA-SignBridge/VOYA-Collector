# Bảng vẽ ERD theo nhóm A–H

Sinh từ catalog `signdb` v8 ngày 26/08/2026. **Entity, cột khoá ngoại,
cardinality, ON DELETE là dữ liệu hệ thống.** Tên quan hệ thì không —
đặt tên là việc mô hình hoá.

## Ba loại nguồn tên

| Loại | Nghĩa | Có tên tự động không |
|---|---|---|
| **A** | Tên cột TỰ CHỨA động từ: `created_by`, `reviewed_by`, `opened_by_user_id`… | có — tên cột là dữ liệu |
| **B** | Tham chiếu/sở hữu cấu trúc: `tenant_id`, `user_id`, `class_uid`, `language`… | **không** |
| **C** | Quan hệ miền qua khoá GHÉP `(tenant_id, …)` | **không** |

Bản trước xếp `tenant_id` → *owns* và `auth_user_id` → *operates* vào loại A.
Sai: hai cột đó không chứa động từ nào; đó là suy diễn ngữ nghĩa của công cụ.
Loại B và C chỉ có tên khi người duyệt đã chốt — cột **Đã chốt** đánh dấu.

| | số |
|---|---:|
| tổng quan hệ | 131 |
| loại A (tên cột có động từ) | 21 |
| loại B (tham chiếu cấu trúc) | 83 |
| loại C (khoá ghép) | 27 |
| **đã có tên** | **131** |
| **còn phải đặt tay** | **0** |

## A. Tenant & Access Management — 33 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `users` | `api_keys` | User creates API Key | `USER_CREATES_API_KEY` | `created_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `api_keys` | User revokes API Key | `USER_REVOKES_API_KEY` | `revoked_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `tenants` | `api_keys` | Tenant scopes API Key | `TENANT_SCOPES_API_KEY` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `memberships` | `memberships` | Membership is parent of Membership for Same User | `MEMBERSHIP_IS_PARENT_OF_MEMBERSHIP_FOR_SAME_USER` | `parent_membership_id, user_id` → `membership_id, user_id` | ✓ | 0..1 — 0..N | CASCADE | hierarchy | C |
| `projects` | `memberships` | Project scopes Membership | `PROJECT_SCOPES_MEMBERSHIP` | `tenant_id, workspace_id, project_id` → `tenant_id, workspace_id, project_id` | ✓ | 0..1 — 0..N | CASCADE | scope | C |
| `tenants` | `memberships` | Tenant scopes Membership | `TENANT_SCOPES_MEMBERSHIP` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `workspaces` | `memberships` | Workspace scopes Membership | `WORKSPACE_SCOPES_MEMBERSHIP` | `tenant_id, workspace_id` → `tenant_id, workspace_id` | ✓ | 0..1 — 0..N | CASCADE | scope | C |
| `tenants` | `memberships` | Tenant scopes Membership | `TENANT_SCOPES_MEMBERSHIP` | `tenant_id` → `tenant_id` | — | 1 — 0..N | CASCADE | — | B |
| `users` | `memberships` | User holds Membership | `USER_HOLDS_MEMBERSHIP` | `user_id` → `id` | — | 1 — 0..N | CASCADE | — | B |
| `projects` | `project_allocations` | Project has Project Allocation | `PROJECT_HAS_PROJECT_ALLOCATION` | `tenant_id, project_id` → `tenant_id, project_id` | ✓ | 1 — 0..N | CASCADE | allocation | C |
| `tenants` | `project_allocations` | Tenant scopes Project Allocation | `TENANT_SCOPES_PROJECT_ALLOCATION_RESTRICT` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `tenants` | `project_allocations` | Tenant scopes Project Allocation | `TENANT_SCOPES_PROJECT_ALLOCATION_CASCADE` | `tenant_id` → `tenant_id` | — | 1 — 0..N | CASCADE | scope | B |
| `users` | `project_allocations` | User updates Project Allocation | `USER_UPDATES_PROJECT_ALLOCATION` | `updated_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `workspaces` | `projects` | Workspace contains Project | `WORKSPACE_CONTAINS_PROJECT` | `tenant_id, workspace_id` → `tenant_id, workspace_id` | ✓ | 1 — 0..N | RESTRICT | — | C |
| `tenants` | `projects` | Tenant scopes Project | `TENANT_SCOPES_PROJECT` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `memberships` | `role_assignments` | Membership carries Role Assignment | `MEMBERSHIP_CARRIES_ROLE_ASSIGNMENT` | `membership_id, user_id` → `membership_id, user_id` | ✓ | 0..1 — 0..N | CASCADE | RBAC scope | C |
| `users` | `role_assignments` | User grants Role through Role Assignment | `USER_GRANTS_ROLE_THROUGH_ROLE_ASSIGNMENT` | `assigned_by_user_id` → `id` | — | 1 — 0..N | RESTRICT | actor/action | B |
| `users` | `role_assignments` | User revokes Role Assignment | `USER_REVOKES_ROLE_ASSIGNMENT` | `revoked_by_user_id` → `id` | — | 0..1 — 0..N | SET NULL | actor/action | B |
| `roles` | `role_assignments` | Role is granted through Role Assignment | `ROLE_IS_GRANTED_THROUGH_ROLE_ASSIGNMENT` | `role_id` → `role_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `role_assignments` | User receives Role Assignment | `USER_RECEIVES_ROLE_ASSIGNMENT` | `user_id` → `id` | — | 1 — 0..N | CASCADE | subject | B |
| `permissions` | `role_permissions` | Permission is granted through Role Permission | `PERMISSION_IS_GRANTED_THROUGH_ROLE_PERMISSION` | `permission_code` → `permission_code` | — | 1 — 0..N | RESTRICT | RBAC | B |
| `roles` | `role_permissions` | Role contains Role Permission | `ROLE_CONTAINS_ROLE_PERMISSION` | `role_id` → `role_id` | — | 1 — 0..N | CASCADE | RBAC | B |
| `users` | `roles` | User creates Role | `USER_CREATES_ROLE` | `created_by_user_id` → `id` | — | 0..1 — 0..N | SET NULL | actor/action | B |
| `tenants` | `roles` | Tenant scopes Custom Role | `TENANT_SCOPES_CUSTOM_ROLE` | `tenant_id` → `tenant_id` | — | 0..1 — 0..N | CASCADE | scope | B |
| `tenants` | `tenant_invitations` | Tenant scopes Tenant Invitation | `TENANT_SCOPES_TENANT_INVITATION` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `users` | `tenant_invitations` | User accepts Tenant Invitation | `USER_ACCEPTS_TENANT_INVITATION` | `accepted_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `tenant_invitations` | User invites Tenant Invitation | `USER_INVITES_TENANT_INVITATION` | `invited_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `community_versions` | `tenants` | Community Version seeds Tenant | `COMMUNITY_VERSION_SEEDS_TENANT` | `cloned_from_community_version` → `version` | — | 0..1 — 0..N | NO ACTION | provenance | B |
| `users` | `tenants` | User owns Tenant | `USER_OWNS_TENANT` | `owner_user_id` → `id` | — | 0..1 — 0..N | SET NULL | ownership | B |
| `plans` | `tenants` | Plan defines Tenant Entitlements | `PLAN_DEFINES_TENANT_ENTITLEMENTS` | `plan_code` → `plan_code` | — | 1 — 0..N | RESTRICT | entitlement | B |
| `tenants` | `users` | Tenant provides Default Context for User | `TENANT_PROVIDES_DEFAULT_CONTEXT_FOR_USER` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | context | B |
| `roles` | `users` | Legacy Role is referenced by User | `LEGACY_ROLE_IS_REFERENCED_BY_USER` | `role_id` → `role_id` | — | 0..1 — 0..N | NO ACTION | legacy | B |
| `tenants` | `workspaces` | Tenant contains Workspace | `TENANT_CONTAINS_WORKSPACE` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |

## B. Authentication & User Security — 6 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `users` | `password_reset_tokens` | User has Password Reset Token | `USER_HAS_PASSWORD_RESET_TOKEN` | `user_id` → `id` | — | 1 — 0..N | CASCADE | password recovery | B |
| `users` | `refresh_tokens` | User holds Refresh Token | `USER_HOLDS_REFRESH_TOKEN` | `user_id` → `id` | — | 1 — 0..N | CASCADE | session credential | B |
| `users` | `user_action_passcodes` | User has Action Passcode | `USER_HAS_ACTION_PASSCODE` | `user_id` → `id` | — | 1 — 0..1 | CASCADE | privileged action credential | B |
| `users` | `user_recovery_codes` | User has Recovery Code | `USER_HAS_RECOVERY_CODE` | `user_id` → `id` | — | 1 — 0..N | CASCADE | account recovery | B |
| `users` | `user_totp` | User has TOTP Credential | `USER_HAS_TOTP_CREDENTIAL` | `user_id` → `id` | — | 1 — 0..1 | CASCADE | MFA credential | B |
| `users` | `verification_codes` | User is associated with Verification Code | `USER_IS_ASSOCIATED_WITH_VERIFICATION_CODE` | `user_id` → `id` | — | 0..1 — 0..N | CASCADE | optional verification subject | B |

## C. VSL Vocabulary & Registry — 23 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `dialects` | `classes` | Dialect varies Class | `DIALECT_VARIES_CLASS` | `tenant_id, dialect` → `tenant_id, dialect_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `regions` | `classes` | Region localizes Class | `REGION_LOCALIZES_CLASS` | `region` → `code` | — | 1 — 0..N | NO ACTION | — | B |
| `languages` | `classes` | Language categorizes Class | `LANGUAGE_CATEGORIZES_CLASS` | `language` → `code` | — | 0..1 — 0..N | NO ACTION | — | B |
| `recognition_profiles` | `classes` | Recognition Profile profiles Class | `RECOGNITION_PROFILE_PROFILES_CLASS` | `tenant_id, recognition_profile` → `tenant_id, profile_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `tenants` | `classes` | Tenant owns Class | `TENANT_OWNS_CLASS` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `vocabulary_groups` | `classes` | Vocabulary Group groups Class | `VOCABULARY_GROUP_GROUPS_CLASS` | `tenant_id, vocabulary_group` → `tenant_id, group_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `users` | `community_dialects` | User updates Community Dialect | `USER_UPDATES_COMMUNITY_DIALECT` | `updated_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `community_profiles` | User updates Community Profile | `USER_UPDATES_COMMUNITY_PROFILE` | `updated_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `community_versions` | User creates Community Version | `USER_CREATES_COMMUNITY_VERSION` | `created_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `dialect_aliases` | User merges Dialect Alias | `USER_MERGES_DIALECT_ALIAS` | `merged_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `dialects` | `dialect_aliases` | Dialect is target of Dialect Alias | `DIALECT_IS_TARGET_OF_DIALECT_ALIAS` | `tenant_id, new_dialect_id` → `tenant_id, dialect_id` | ✓ | 1 — 0..N | NO ACTION | — | C |
| `tenants` | `dialect_aliases` | Tenant scopes Dialect Alias | `TENANT_SCOPES_DIALECT_ALIAS` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `dialects` | User approves Dialect | `USER_APPROVES_DIALECT` | `approved_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `dialects` | User creates Dialect | `USER_CREATES_DIALECT` | `created_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `languages` | `dialects` | Language includes Dialect | `LANGUAGE_INCLUDES_DIALECT` | `language` → `code` | — | 1 — 0..N | NO ACTION | — | B |
| `dialects` | `dialects` | Dialect is merge target of Dialect | `DIALECT_IS_MERGE_TARGET_OF_DIALECT` | `tenant_id, merged_into` → `tenant_id, dialect_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `tenants` | `dialects` | Tenant scopes Dialect | `TENANT_SCOPES_DIALECT` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `tenants` | `recognition_profiles` | Tenant scopes Recognition Profile | `TENANT_SCOPES_RECOGNITION_PROFILE` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `tenants` | `registry_versions` | Tenant scopes Registry Version | `TENANT_SCOPES_REGISTRY_VERSION` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `registry_versions` | User creates Registry Version | `USER_CREATES_REGISTRY_VERSION` | `created_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `tenants` | `vocabulary_groups` | Tenant scopes Vocabulary Group | `TENANT_SCOPES_VOCABULARY_GROUP` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `tenants` | `vocabulary_registry_meta` | Tenant maintains Vocabulary Registry Metadata | `TENANT_MAINTAINS_VOCABULARY_REGISTRY_METADATA` | `tenant_id` → `tenant_id` | — | 1 — 0..1 | RESTRICT | — | B |
| `registry_versions` | `vocabulary_registry_meta` | Registry Version is selected by Vocabulary Registry Metadata | `REGISTRY_VERSION_IS_SELECTED_BY_VOCABULARY_REGISTRY_METADATA` | `tenant_id, version` → `tenant_id, version` | ✓ | 0..1 — 0..1 | NO ACTION | — | C |

## D. VSL Collection & Dataset — 27 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `users` | `capture_sessions` | User operates Capture Session | `USER_OPERATES_CAPTURE_SESSION` | `auth_user_id` → `id` | — | 0..1 — 0..N | SET NULL | — | B |
| `classes` | `capture_sessions` | Class is captured in Capture Session | `CLASS_IS_CAPTURED_IN_CAPTURE_SESSION` | `tenant_id, class_uid` → `tenant_id, class_uid` | ✓ | 1 — 0..N | NO ACTION | — | C |
| `collection_sessions` | `capture_sessions` | Collection Session contains Capture Session | `COLLECTION_SESSION_CONTAINS_CAPTURE_SESSION` | `tenant_id, collection_session_id` → `tenant_id, collection_session_id` | ✓ | 0..1 — 0..N | SET NULL | — | C |
| `signers` | `capture_sessions` | Capture Session references summarized Signer | `CAPTURE_SESSION_REFERENCES_SUMMARIZED_SIGNER` | `tenant_id, signer_id` → `tenant_id, signer_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `tenants` | `capture_sessions` | Tenant owns Capture Session | `TENANT_OWNS_CAPTURE_SESSION` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `collection_sessions` | User opens Collection Session | `USER_OPENS_COLLECTION_SESSION` | `opened_by_user_id` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `tenants` | `collection_sessions` | Tenant owns Collection Session | `TENANT_OWNS_COLLECTION_SESSION` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `classes` | `raw_uploads` | Class classifies Raw Upload | `CLASS_CLASSIFIES_RAW_UPLOAD` | `tenant_id, class_uid` → `tenant_id, class_uid` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `dialects` | `raw_uploads` | Dialect categorizes Raw Upload | `DIALECT_CATEGORIZES_RAW_UPLOAD` | `tenant_id, dialect` → `tenant_id, dialect_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `languages` | `raw_uploads` | Language categorizes Raw Upload | `LANGUAGE_CATEGORIZES_RAW_UPLOAD` | `language` → `code` | — | 0..1 — 0..N | NO ACTION | — | B |
| `tenants` | `raw_uploads` | Tenant owns Raw Upload | `TENANT_OWNS_RAW_UPLOAD` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `raw_uploads` | User uploads Raw Upload | `USER_UPLOADS_RAW_UPLOAD` | `auth_user_id` → `id` | — | 0..1 — 0..N | SET NULL | — | B |
| `capture_sessions` | `samples` | Capture Session contains Sample (legacy key) | `CAPTURE_SESSION_CONTAINS_SAMPLE_LEGACY_KEY` | `capture_session_id` → `capture_session_id` | — | 0..1 — 0..N | SET NULL | — | B |
| `capture_sessions` | `samples` | Capture Session contains Sample | `CAPTURE_SESSION_CONTAINS_SAMPLE` | `tenant_id, capture_session_id` → `tenant_id, capture_session_id` | ✓ | 0..1 — 0..N | SET NULL | — | C |
| `classes` | `samples` | Class labels Sample | `CLASS_LABELS_SAMPLE` | `tenant_id, class_uid` → `tenant_id, class_uid` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `languages` | `samples` | Language categorizes Sample | `LANGUAGE_CATEGORIZES_SAMPLE` | `language` → `code` | — | 0..1 — 0..N | NO ACTION | — | B |
| `signers` | `samples` | Signer performs Sample | `SIGNER_PERFORMS_SAMPLE` | `tenant_id, signer_id` → `tenant_id, signer_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `tenants` | `samples` | Tenant owns Sample | `TENANT_OWNS_SAMPLE` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `samples` | User records Sample | `USER_RECORDS_SAMPLE` | `auth_user_id` → `id` | — | 0..1 — 0..N | SET NULL | — | B |
| `classes` | `samples` | Class labels Sample (legacy key) | `CLASS_LABELS_SAMPLE_LEGACY_KEY` | `class_uid` → `class_uid` | — | 0..1 — 0..N | NO ACTION | — | B |
| `dialects` | `samples` | Dialect categorizes Sample | `DIALECT_CATEGORIZES_SAMPLE` | `tenant_id, dialect` → `tenant_id, dialect_id` | ✓ | 0..1 — 0..N | NO ACTION | — | C |
| `users` | `samples` | User reviews Sample | `USER_REVIEWS_SAMPLE` | `reviewed_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `signers` | `signer_aliases` | Signer is target of Signer Alias | `SIGNER_IS_TARGET_OF_SIGNER_ALIAS` | `tenant_id, new_signer_id` → `tenant_id, signer_id` | ✓ | 1 — 0..N | NO ACTION | — | C |
| `tenants` | `signer_aliases` | Tenant scopes Signer Alias | `TENANT_SCOPES_SIGNER_ALIAS` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `signer_aliases` | User merges Signer Alias | `USER_MERGES_SIGNER_ALIAS` | `merged_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `tenants` | `signers` | Tenant manages Signer | `TENANT_MANAGES_SIGNER` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | — | B |
| `users` | `signers` | User Account corresponds to Signer | `USER_ACCOUNT_CORRESPONDS_TO_SIGNER` | `external_user_id` → `id` | — | 0..1 — 0..N | SET NULL | — | B |

## E. Legal, Consent & Governance — 14 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `users` | `audit_log` | User is recorded as Actor in Audit Log | `USER_IS_RECORDED_AS_ACTOR_IN_AUDIT_LOG` | `actor_user_id` → `id` | — | 0..1 — 0..N | SET NULL | audit actor | B |
| `tenants` | `audit_log` | Tenant scopes Audit Log Entry | `TENANT_SCOPES_AUDIT_LOG_ENTRY` | `tenant_id` → `tenant_id` | — | 0..1 — 0..N | RESTRICT | optional scope | B |
| `users` | `legal_document_drafts` | User creates Legal Document Draft | `USER_CREATES_LEGAL_DOCUMENT_DRAFT` | `created_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `legal_document_drafts` | User updates Legal Document Draft | `USER_UPDATES_LEGAL_DOCUMENT_DRAFT` | `updated_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `users` | `legal_documents` | User publishes Legal Document | `USER_PUBLISHES_LEGAL_DOCUMENT` | `published_by` → `id` | — | 0..1 — 0..N | SET NULL | actor/action | B |
| `legal_documents` | `signer_consents` | Legal Document Version anchors Signer Consent | `LEGAL_DOCUMENT_VERSION_ANCHORS_SIGNER_CONSENT` | `kind, version` → `kind, version` | ✓ | 1 — 0..N | RESTRICT | legal evidence | C |
| `signers` | `signer_consents` | Signer is subject of Signer Consent | `SIGNER_IS_SUBJECT_OF_SIGNER_CONSENT` | `tenant_id, signer_id` → `tenant_id, signer_id` | ✓ | 1 — 0..N | NO ACTION | consent subject | C |
| `tenants` | `signer_consents` | Tenant scopes Signer Consent | `TENANT_SCOPES_SIGNER_CONSENT` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `users` | `signer_consents` | User records Signer Consent | `USER_RECORDS_SIGNER_CONSENT` | `recorded_by` → `id` | — | 0..1 — 0..N | SET NULL | recorder | B |
| `tenants` | `tenant_exports` | Tenant scopes Tenant Export | `TENANT_SCOPES_TENANT_EXPORT` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `users` | `tenant_exports` | User requests Tenant Export | `USER_REQUESTS_TENANT_EXPORT` | `requested_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `legal_documents` | `user_consents` | Legal Document Version anchors User Consent | `LEGAL_DOCUMENT_VERSION_ANCHORS_USER_CONSENT` | `kind, version` → `kind, version` | ✓ | 1 — 0..N | RESTRICT | legal evidence | C |
| `users` | `user_consents` | User records User Consent | `USER_RECORDS_USER_CONSENT` | `recorded_by` → `id` | — | 0..1 — 0..N | SET NULL | recorder | B |
| `users` | `user_consents` | User is subject of User Consent | `USER_IS_SUBJECT_OF_USER_CONSENT` | `user_id` → `id` | — | 1 — 0..N | CASCADE | consent subject | B |

## F. Training & Evaluation — 9 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `classes` | `training_job_classes` | Class is referenced by Training Job Class | `CLASS_IS_REFERENCED_BY_TRAINING_JOB_CLASS` | `class_uid` → `class_uid` | — | 0..1 — 0..N | SET NULL | class mapping | B |
| `tenants` | `training_job_classes` | Tenant scopes Training Job Class | `TENANT_SCOPES_TRAINING_JOB_CLASS` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `training_jobs` | `training_job_classes` | Training Job contains Training Job Class | `TRAINING_JOB_CONTAINS_TRAINING_JOB_CLASS` | `job_id` → `job_id` | — | 1 — 0..N | CASCADE | job composition | B |
| `registry_versions` | `training_jobs` | Registry Version anchors Training Job | `REGISTRY_VERSION_ANCHORS_TRAINING_JOB` | `tenant_id, registry_version` → `tenant_id, version` | ✓ | 0..1 — 0..N | NO ACTION | provenance | C |
| `tenants` | `training_jobs` | Tenant scopes Training Job | `TENANT_SCOPES_TRAINING_JOB` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `users` | `training_jobs` | User is recorded as Actor for Training Job | `USER_IS_RECORDED_AS_ACTOR_FOR_TRAINING_JOB` | `auth_user_id` → `id` | — | 0..1 — 0..N | SET NULL | optional actor | B |
| `training_jobs` | `training_metrics` | Training Job records Training Metric (legacy key) | `TRAINING_JOB_RECORDS_TRAINING_METRIC_LEGACY_KEY` | `job_id` → `job_id` | — | 1 — 0..N | CASCADE | legacy key | B |
| `training_jobs` | `training_metrics` | Training Job records Training Metric | `TRAINING_JOB_RECORDS_TRAINING_METRIC` | `tenant_id, job_id` → `tenant_id, job_id` | ✓ | 1 — 0..N | CASCADE | tenant-aware | C |
| `tenants` | `training_metrics` | Tenant scopes Training Metric | `TENANT_SCOPES_TRAINING_METRIC` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |

## G. Plan, Billing & Storage — 6 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `tenants` | `storage_reservations` | Tenant has Storage Reservation | `TENANT_HAS_STORAGE_RESERVATION` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | quota reservation | B |
| `tenants` | `tenant_storage` | Tenant maintains Storage Counter | `TENANT_MAINTAINS_STORAGE_COUNTER` | `tenant_id` → `tenant_id` | — | 1 — 0..1 | RESTRICT | storage accounting | B |
| `tenants` | `tenant_subscriptions` | Tenant has Subscription Record | `TENANT_HAS_SUBSCRIPTION_RECORD` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | subscription history | B |
| `users` | `tenant_subscriptions` | User changes Tenant Subscription | `USER_CHANGES_TENANT_SUBSCRIPTION` | `changed_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `plans` | `tenant_subscriptions` | Plan is selected by Tenant Subscription | `PLAN_IS_SELECTED_BY_TENANT_SUBSCRIPTION` | `plan_code` → `plan_code` | — | 1 — 0..N | NO ACTION | entitlement history | B |
| `tenants` | `tenant_usage_daily` | Tenant records Daily Usage | `TENANT_RECORDS_DAILY_USAGE` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | usage accounting | B |

## H. Integration & Operations — 13 quan hệ, còn 0 phải đặt tay

| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |
|---|---|---|---|---|:--:|---|---|---|:--:|
| `tenants` | `event_outbox` | Tenant scopes Outbox Event | `TENANT_SCOPES_OUTBOX_EVENT` | `tenant_id` → `tenant_id` | — | 0..1 — 0..N | RESTRICT | optional scope | B |
| `tenants` | `notifications` | Tenant scopes Notification | `TENANT_SCOPES_NOTIFICATION` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `users` | `notifications` | User receives Notification | `USER_RECEIVES_NOTIFICATION` | `user_id` → `id` | — | 1 — 0..N | CASCADE | recipient | B |
| `users` | `platform_settings` | User updates Platform Setting | `USER_UPDATES_PLATFORM_SETTING` | `updated_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |
| `tenants` | `support_messages` | Tenant scopes Support Message | `TENANT_SCOPES_SUPPORT_MESSAGE` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope / RLS | B |
| `users` | `support_messages` | User is recorded as Author of Support Message | `USER_IS_RECORDED_AS_AUTHOR_OF_SUPPORT_MESSAGE` | `author_id` → `id` | — | 0..1 — 0..N | SET NULL | optional author | B |
| `support_tickets` | `support_messages` | Support Ticket contains Support Message | `SUPPORT_TICKET_CONTAINS_SUPPORT_MESSAGE` | `ticket_id` → `ticket_id` | — | 1 — 0..N | CASCADE | support hierarchy | B |
| `tenants` | `support_tickets` | Tenant scopes Support Ticket | `TENANT_SCOPES_SUPPORT_TICKET` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `users` | `support_tickets` | User opens Support Ticket | `USER_OPENS_SUPPORT_TICKET` | `user_id` → `id` | — | 0..1 — 0..N | SET NULL | requester | B |
| `tenants` | `webhook_deliveries` | Tenant scopes Webhook Delivery | `TENANT_SCOPES_WEBHOOK_DELIVERY` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `webhook_endpoints` | `webhook_deliveries` | Webhook Endpoint is target of Webhook Delivery | `WEBHOOK_ENDPOINT_IS_TARGET_OF_WEBHOOK_DELIVERY` | `endpoint_id` → `endpoint_id` | — | 1 — 0..N | CASCADE | delivery lifecycle | B |
| `tenants` | `webhook_endpoints` | Tenant scopes Webhook Endpoint | `TENANT_SCOPES_WEBHOOK_ENDPOINT` | `tenant_id` → `tenant_id` | — | 1 — 0..N | RESTRICT | scope | B |
| `users` | `webhook_endpoints` | User creates Webhook Endpoint | `USER_CREATES_WEBHOOK_ENDPOINT` | `created_by` → `id` | — | 0..1 — 0..N | SET NULL | — | A |

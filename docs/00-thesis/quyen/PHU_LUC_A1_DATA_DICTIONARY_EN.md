# A.1. DATA DICTIONARY

The data dictionary documents the physical structure and purpose of each
relation in the CTU.SignBridge database. Tables are grouped according to the
same functional domains used in the physical database model.

Structure — data type, nullability, keys, defaults and permitted value sets —
is read directly from the `signdb` catalog at schema version **v8**
(63 tables, 672 columns). Descriptions are authored and reviewed separately;
the database itself carries no column comments.


## A. Identity and access

### users

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| id | Uuid | Primary Key | Account identifier. |
| username | Text | Unique, Not Null | Login name. |
| email | Text | Unique, Not Null | Email address; also usable as a login credential. |
| password_hash | Text | Not Null | Password hash. The system has no path back to the original password. |
| is_active | Boolean | Not Null, Default: true | Whether the account is still active. |
| is_admin | Boolean | Not Null, Default: false | PLATFORM administration flag, not a role inside any organization. Platform administration and organization administration do not inherit from each other. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the account was created. |
| role_id | Uuid | Foreign Key -> roles | Legacy role reference. This is NOT the authorization path in force today. |
| phone_number | Varchar(20) | Unique | Phone number used for SMS verification codes. |
| updated_at | Timestamptz |  | Timestamp of the most recent update. |
| deleted_at | Timestamptz |  | Soft-deletion timestamp for the account. Null means the record is still in the working set. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization used as the account's default/fallback context; authoritative membership and access are expressed through Membership. This table carries an isolation policy with a system-scope escape path, because login resolution runs before the organization is known. |
| email_verified_at | Timestamptz |  | Timestamp when control of the email address was verified. |
| phone_verified_at | Timestamptz |  | Timestamp when control of the phone number was verified. |
| sessions_invalid_before | Timestamptz |  | Session revocation cutoff: every token issued before this moment is invalid. This is level two of the three-level revocation mechanism. |
| active_tenant_id | Text |  | Organization the user is currently SELECTING as working context. |

### refresh_tokens

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| token_hash | Text | Primary Key | SHA-256 hash of the refresh token. The table does NOT store the token itself. |
| user_id | Uuid | Foreign Key -> users, Not Null | Account holding this token. |
| expires_at | Timestamptz | Not Null | Timestamp when the token expires naturally. |
| revoked_at | Timestamptz |  | Timestamp when the token was revoked. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the token was issued. |
| family_id | Uuid |  | Token FAMILY identifier: the whole rotation chain descending from one login. |
| replaced_by | Text |  | Logical reference to the refresh token that replaced this one in the rotation chain, stored as the successor's hash. |
| reuse_detected_at | Timestamptz |  | Timestamp when a replaced refresh token was seen used again OUTSIDE the grace window — treated as theft. |

### password_reset_tokens

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| token_hash | Text | Primary Key | SHA-256 hash of the password-reset token. The table does NOT store the token itself. |
| user_id | Uuid | Foreign Key -> users, Not Null | Account this reset token belongs to. |
| expires_at | Timestamptz | Not Null | Timestamp when the token stops being valid. |
| used_at | Timestamptz |  | Timestamp when the token was consumed; null means unused. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the token was issued. |

### verification_codes

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| challenge_id | Uuid | Primary Key | Identifier of one verification challenge. |
| user_id | Uuid | Foreign Key -> users, Unique (composite) | Account tied to the challenge, if one already exists; may be null for challenges raised BEFORE registration completes. |
| purpose | Text | Unique (composite), Not Null, Allowed values: verify_email, verify_phone, reset_password | Purpose for issuing the code. |
| channel | Text | Not Null, Allowed values: email, sms | Delivery channel used to send the code. |
| destination | Text | Not Null | Address or phone number the code was sent to. A code proves control of THIS destination, not authority over an account. |
| code_hash | Text | Not Null | HMAC-SHA256 hash of the code, keyed with a pepper held OUTSIDE the database. |
| attempts | Integer | Not Null, Default: 0 | Number of entry attempts made so far. |
| max_attempts | Integer | Not Null, Default: 5 | Attempt ceiling before the challenge dies; default 5. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the challenge was issued. |
| expires_at | Timestamptz | Not Null | Timestamp when the challenge times out. |
| consumed_at | Timestamptz |  | Timestamp when the code was consumed; null means unused. |

### user_totp

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| user_id | Uuid | Primary Key, Foreign Key -> users | Account owning this TOTP configuration. The column is both primary key and foreign key, so each account has at most ONE configuration. |
| secret_enc | Text | Not Null | TOTP secret, ENCRYPTED (Fernet) — not hashed. |
| confirmed_at | Timestamptz |  | Timestamp when the user confirmed the secret and two-factor authentication became active; null means the secret exists but is not yet in force. |
| last_used_step | Bigint |  | Most recently accepted TOTP time step — the replay guard. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when TOTP enrolment started. |

### user_recovery_codes

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| code_hash | Text | Primary Key | HMAC-SHA256 hash of one recovery code. The table does NOT store the code itself. |
| user_id | Uuid | Foreign Key -> users, Not Null | Account owning this set of recovery codes. |
| used_at | Timestamptz |  | Timestamp when the code was consumed; null means unused. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the code was issued. |

### user_action_passcodes

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| user_id | Uuid | Primary Key, Foreign Key -> users | Account owning the action passcode. The column is both primary key and foreign key, so each account has at most ONE configuration. |
| passcode_hash | Text | Not Null | Hash of the action passcode, produced by the SAME hashing routine as the login password. |
| status | Text | Not Null, Default: 'ACTIVE', Allowed values: ACTIVE, LOCKED, REVOKED | Current status of the passcode. |
| failed_count | Smallint | Not Null, Default: 0 | Cumulative number of incorrect entries. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the passcode was set. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent update. |
| locked_until | Timestamptz |  | Timestamp when the lock imposed after repeated failures expires; null means not locked. |
| revoked_at | Timestamptz |  | Timestamp when the passcode was revoked. |

### api_keys

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| key_id | Uuid | Primary Key | API key identifier. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization that scopes the key. |
| name | Text | Not Null, Default: '' | Operator-assigned key name. |
| prefix | Text | Unique, Not Null | Public prefix of the key, used to identify it without exposing it. |
| key_hash | Text | Not Null | Hash of the key. The table does NOT store the key itself. |
| scopes | Text | Not Null, Default: 'read' | Operations the key is permitted to perform. |
| created_by | Uuid | Foreign Key -> users | Account that created the key. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the key was created. |
| last_used_at | Timestamptz |  | Timestamp when the key was most recently used. |
| expires_at | Timestamptz |  | Timestamp when the key expires. |
| revoked_at | Timestamptz |  | Timestamp when the key was revoked. The plan ceiling counts only keys NOT yet revoked. |
| revoked_by | Uuid | Foreign Key -> users | Account that revoked the key. |


## B. Organizations and authorization

### tenants

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key | Organization identifier; the value every tenant-isolation policy matches against. |
| display_name | Text |  | Organization name shown to users. |
| slug | Text | Unique | Short, URL-friendly form of the organization name. |
| is_active | Boolean | Not Null, Default: true | Whether the organization is still operating. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the organization was created. |
| deleted_at | Timestamptz |  | Soft-deletion timestamp for the organization. |
| cloned_from_community_version | Bigint | Foreign Key -> community_versions | Community catalog version the organization was cloned from at provisioning time. |
| cloned_at | Timestamptz |  | Timestamp when the catalog was cloned. |
| plan_code | Text | Foreign Key -> plans, Not Null, Default: 'free' | Plan currently in force; the value every quota check READS. |
| billing_status | Text | Not Null, Default: 'active', Allowed values: trialing, active, past_due, suspended, cancelled | Billing/service status of the organization; decides whether the organization may still write data. |
| trial_ends_at | Timestamptz |  | Timestamp when the trial period ends. |
| current_period_start | Timestamptz |  | Start of the current subscription period. |
| current_period_end | Timestamptz |  | End of the current subscription period; the anchor for renewal reminders and for opening the next period. |
| is_self_serve | Boolean | Not Null, Default: false | Whether the organization signed itself up or was created by a platform administrator. |
| owner_user_id | Uuid | Foreign Key -> users | Account designated as organization owner; may be null. |
| suspended_at | Timestamptz |  | Timestamp when service was suspended. |
| suspended_reason | Text |  | Reason for the suspension. |
| tenant_type | Text | Unique, Not Null, Default: 'ORGANIZATION', Allowed values: COMMUNITY, ORGANIZATION | Organization category, distinguishing the community tenant from ordinary organizations. |
| is_system_reserved | Boolean | Not Null, Default: false | Organization reserved by the platform; it cannot be deleted. |
| billing_exempt | Boolean | Not Null, Default: false | Whether the organization is exempt from commercial quotas. |

### workspaces

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| workspace_id | Uuid | Primary Key, Unique (composite), Default: generated UUID | Workspace identifier. |
| tenant_id | Text | Foreign Key -> tenants, Unique, Not Null | Organization containing this workspace. |
| name | Text | Unique (composite), Not Null | Workspace name, unique within the organization among workspaces not soft-deleted. |
| description | Text | Not Null, Default: '' | Description of the workspace. |
| status | Text | Not Null, Default: 'ACTIVE', Allowed values: ACTIVE, ARCHIVED, DELETED | Lifecycle status of the workspace. |
| is_default | Boolean | Not Null, Default: false | Whether this is the organization's default workspace. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the workspace was created. |
| archived_at | Timestamptz |  | Timestamp when the workspace was archived. |
| deleted_at | Timestamptz |  | Soft-deletion timestamp. |

### projects

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| project_id | Uuid | Primary Key, Unique (composite), Default: generated UUID | Project identifier. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization containing this project. |
| workspace_id | Uuid | Foreign Key -> workspaces (composite key), Unique (composite), Not Null | Workspace containing this project. |
| name | Text | Unique (composite), Not Null | Project name, unique within its workspace. |
| description | Text | Not Null, Default: '' | Description of the project. |
| status | Text | Not Null, Default: 'ACTIVE', Allowed values: ACTIVE, ARCHIVED, DELETED | Lifecycle status of the project. |
| is_default | Boolean | Not Null, Default: false | Whether this is the workspace's default project. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the project was created. |
| archived_at | Timestamptz |  | Timestamp when the project was archived. |
| deleted_at | Timestamptz |  | Soft-deletion timestamp. |

### project_allocations

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants | Organization that scopes the allocation. |
| project_id | Uuid | Primary Key, Foreign Key -> projects (composite key) | Project receiving the allocation. |
| metric | Text | Primary Key | Quota being divided: samples, storage_mb or training_jobs_per_month. |
| allocated | Bigint |  | Share of the quota reserved for this project. Null means UNLIMITED — not 'not yet filled in'. |
| note | Text | Not Null, Default: '' | Operator note about the allocation. |
| updated_by | Uuid | Foreign Key -> users | Account that last adjusted the allocation. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent adjustment. |

### memberships

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| membership_id | Uuid | Primary Key, Unique (composite), Default: generated UUID | Membership identifier. |
| user_id | Uuid | Foreign Key -> users, Unique (composite), Not Null | Account holding this membership. |
| scope_level | Text | Not Null, Default: 'TENANT', Allowed values: TENANT, WORKSPACE, PROJECT | Scope level at which the membership grants standing. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization that scopes the membership. |
| workspace_id | Uuid | Foreign Key -> workspaces (composite key), Unique (composite) | Workspace of the membership. Null when scope_level = TENANT; not null for WORKSPACE and PROJECT. |
| project_id | Uuid | Foreign Key -> projects (composite key), Unique (composite) | Project of the membership. Not null only when scope_level = PROJECT. |
| parent_membership_id | Uuid | Foreign Key -> memberships (composite key) | Parent membership in the scope tree, belonging to the SAME person. |
| legacy_role | Text | Allowed values: admin, editor | Backward-compatible role value, usable only on a tenant-level membership. |
| status | Text | Not Null, Default: 'ACTIVE', Allowed values: ACTIVE, INVITED, SUSPENDED, REMOVED | Current status of the membership. |
| joined_at | Timestamptz |  | Timestamp when the member joined. |
| suspended_at | Timestamptz |  | Timestamp when the membership was suspended. |
| left_at | Timestamptz |  | Timestamp when the member left. A CHECK forces this column to carry a value IF AND ONLY IF status = REMOVED. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the record was created. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent update. |

### roles

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| role_id | Uuid | Primary Key, Unique (composite), Default: generated UUID | Role identifier. |
| role_code | Varchar(50) | Unique, Not Null | Stable role code, the value application code looks the role up by. |
| description | Text | Default: '' | Description of the role for operators. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite) | Organization owning a CUSTOM role. Null for roles built into the platform. |
| scope_level | Text | Unique (composite), Allowed values: SYSTEM, TENANT, WORKSPACE, PROJECT | Scope at which the role may be assigned. |
| is_builtin | Boolean | Not Null, Default: false | Whether the role ships with the platform or was created by an organization. |
| is_active | Boolean | Not Null, Default: true | Whether the role is still usable or has been retired. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the role was created. |
| role_name | Text |  | Display name of the role. |
| tenant_type_constraint | Text | Allowed values: COMMUNITY, ORGANIZATION | Restricts the role to one organization type; null means no restriction. |
| created_by_user_id | Uuid | Foreign Key -> users | Account that created the custom role. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent update. |

### permissions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| permission_code | Text | Primary Key | Permission code, written as domain.action. |
| description | Text | Not Null, Default: '' | Description of the permission for operators. |
| applicable_scope | Text | Not Null, Allowed values: SYSTEM, TENANT, WORKSPACE, PROJECT | Scope tier at which the permission applies. |
| risk_level | Text | Not Null, Default: 'NORMAL', Allowed values: NORMAL, SENSITIVE, CRITICAL | Security risk classification of the permission. |
| requires_passcode | Boolean | Not Null, Default: false | Whether the permission demands re-authentication by action passcode before use. |
| is_api_assignable | Boolean | Not Null, Default: false | Whether the permission may be granted to an API key. |
| is_active | Boolean | Not Null, Default: true | Whether the permission is still in force or has been retired. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the permission was declared. |
| is_custom_role_allowed | Boolean | Not Null, Default: true | Whether the permission may be included in an organization's custom role. |

### role_permissions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| role_id | Uuid | Primary Key, Foreign Key -> roles | Role receiving the permission. |
| permission_code | Text | Primary Key, Foreign Key -> permissions | Permission granted to the role. |
| granted_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the permission was attached to the role. |

### role_assignments

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| assignment_id | Uuid | Primary Key, Default: generated UUID | Role-assignment identifier. |
| user_id | Uuid | Foreign Key -> users, Unique (composite), Not Null | Account RECEIVING the role — the subject of the grant. |
| role_id | Uuid | Foreign Key -> roles, Unique (composite), Not Null | Role being granted. |
| membership_id | Uuid | Foreign Key -> memberships (composite key), Unique (composite) | Membership this assignment is anchored to. |
| assigned_by_user_id | Uuid | Foreign Key -> users, Not Null | Account that PERFORMED the grant — the actor. |
| assigned_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the role was granted. |
| revoked_by_user_id | Uuid | Foreign Key -> users | Account that PERFORMED the revocation — the revoking actor. |
| revoked_at | Timestamptz |  | Timestamp when the role was revoked. |
| revoke_reason | Text |  | Reason for the revocation. |

### tenant_invitations

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| invitation_id | Uuid | Primary Key | Invitation identifier. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization issuing the invitation. |
| email | Text | Unique (composite), Not Null | Email address of the invitee, normalized on write. |
| role | Text | Allowed values: admin, editor | Role offered to the invitee on joining. |
| token_hash | Text | Unique, Not Null | Hash of the invitation token. The table does NOT store the token itself. |
| invited_by | Uuid | Foreign Key -> users | Account that issued the invitation. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the invitation was issued. |
| expires_at | Timestamptz | Not Null | Timestamp when the invitation expires. |
| accepted_at | Timestamptz |  | Timestamp when the invitation was accepted. |
| accepted_by | Uuid | Foreign Key -> users | Account that accepted the invitation. |
| revoked_at | Timestamptz |  | Timestamp when the invitation was revoked. |


## C. Sample data repository

### collection_sessions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| collection_session_id | Uuid | Primary Key, Unique (composite) | Collection-session identifier. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization owning the record; the scope tenant isolation applies to. |
| session_code | Text | Unique (composite), Not Null | Client-generated session code, unique within one organization. |
| opened_by_user_id | Uuid | Foreign Key -> users | Account that opened the collection session. This is the OPERATOR, not the signer. |
| source_type | Text |  | Capture channel: live camera or uploaded video. |
| started_at | Timestamptz |  | Timestamp when the collection session started. |
| ended_at | Timestamptz |  | Timestamp when the collection session ended; null while it is still open. |
| note | Text |  | Free-form operator note. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the record was created. |

### capture_sessions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| capture_session_id | Uuid | Primary Key, Unique (composite) | Identifier of one capture session for a single sign class. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization owning the record. |
| class_uid | Text | Foreign Key -> classes (composite key), Unique (composite), Not Null | Sign class captured in this session. |
| session_id | Text | Unique (composite), Not Null | Client-supplied session code; unique per (organization, class), NOT unique on its own. |
| signer_id | Text | Foreign Key -> signers (composite key) | SUMMARY signer of the session, kept from the earlier design. Measurement contradicts the one-session-one-signer assumption, so this column is NOT the authoritative identity source; its tenant-aware foreign key nevertheless remains in force. |
| auth_user_id | Uuid | Foreign Key -> users | Account that performed the capture session. This is distinct from signer identity. |
| source_type | Text |  | Capture channel of the session. |
| started_at | Timestamptz |  | Timestamp when the session started. |
| ended_at | Timestamptz |  | Timestamp when the session ended. |
| note | Text |  | Free-form note. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the record was created. |
| collection_session_id | Uuid | Foreign Key -> collection_sessions (composite key) | Collection session containing this capture session; null for data predating the hierarchy. |
| visibility | Text | Not Null, Default: 'private' | Who may see the session: private (owner and editors only) or tenant (the owner opened it to ordinary members of the same organization). Enforced by the API, not by a CHECK. |

### samples

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| sample_uid | Text | Primary Key | Sample identifier. |
| class_uid | Text | Foreign Key -> classes (composite key) | Sign class this sample is labelled with. |
| slug | Text |  | Copy of the class slug as it stood when the sample was written. |
| label_original | Text |  | Copy of the class's original label as it stood when the sample was written. |
| language | Text | Foreign Key -> languages | Sign language of the sample. |
| dialect | Text | Foreign Key -> dialects (composite key) | Dialect of the sample. |
| source_type | Text |  | Capture channel: camera or uploaded video. |
| user_id | Text |  | Signer/account label as free text, kept for the legacy data contract; the current write path still fills it. This is NOT a foreign key to users. |
| auth_user_id | Uuid | Foreign Key -> users | Account that performed the capture or upload of this sample. |
| session_id | Text |  | Client-supplied session code at capture time. |
| fps_original | Text |  | Frame rate of the original source. |
| fps_processed | Text |  | Frame rate after preprocessing. |
| seq_len | Integer |  | Sequence length after padding to the target length. |
| augment_id | Integer |  | Augmentation variant index; 0 is the original. |
| completeness | Real |  | Proportion of frames carrying a valid hand. |
| file_path | Text |  | Path of the feature file, relative to the dataset root. |
| storage_url | Text |  | Path or URL where the file currently resides. |
| checksum | Text |  | Checksum of the feature file. |
| created_at | Timestamptz |  | Timestamp when the sample was written. |
| sheets_synced | Boolean | Default: false | Whether the metadata has been synchronized to Google Sheets. |
| gdrive_synced | Boolean | Default: true | Whether the file has been synchronized to Google Drive. |
| status | Varchar(20) | Default: 'PENDING' | No longer updated by any write path. |
| error_log | Text | Default: '' | Processing error message, if any. |
| updated_at | Timestamptz |  | Timestamp of the most recent update. |
| storage_key | Text | Default: '' | File key in the object store, relative to the dataset root. |
| session_uid | Text |  | Second session code, distinct from session_id. |
| username | Text |  | Copy of the account name; survives only on legacy data. |
| deleted_at | Timestamptz |  | Soft-deletion timestamp. The file REMAINS on disk until the Trash is purged. |
| left_hand_ratio | Real |  | Proportion of frames in which the left hand was detected. |
| right_hand_ratio | Real |  | Proportion of frames in which the right hand was detected. |
| both_hands_ratio | Real |  | Proportion of frames in which both hands were detected. |
| jitter | Real |  | Landmark jitter of the sequence, 95th percentile. |
| quality_flags | Text |  | Quality warnings raised for this capture. |
| signer_id | Text | Foreign Key -> signers (composite key) | Normalized signer identity, where it has been resolved. |
| collection_campaign | Text |  | Collection campaign the sample belongs to. |
| raw_landmarks_available | Boolean |  | Whether a raw landmark record exists in the raw archive. |
| normalization_version | Text |  | Version of the normalization algorithm applied to the sample. |
| preprocess_contract_version | Text |  | Version of the preprocessing contract applied. |
| sequence_length_original | Integer |  | Number of frames before padding or truncation. |
| quality_status | Text |  | Quality verdict: passed, or flagged. |
| tenant_id | Text | Foreign Key -> tenants, Not Null, Default: 'default' | Organization owning the sample; the scope tenant isolation applies to. |
| capture_session_id | Uuid | Foreign Key -> capture_sessions (composite key) | Capture session containing this sample. |
| review_status | Text | Not Null, Default: 'pending', Allowed values: pending, approved, rejected | Moderation status of the sample. |
| reviewed_by | Uuid | Foreign Key -> users | Account that reviewed the sample. |
| reviewed_at | Timestamptz |  | Timestamp when the review was recorded. |
| review_note | Text | Default: '' | Reviewer's note. |

### raw_uploads

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| upload_uid | Text | Primary Key | Upload identifier; also the idempotency key when a client retries. |
| class_uid | Text | Foreign Key -> classes (composite key) | Sign class of the video. |
| slug | Text |  | Copy of the class slug. |
| label_original | Text |  | Copy of the class's original label. |
| language | Text | Foreign Key -> languages | Sign language. |
| dialect | Text | Foreign Key -> dialects (composite key) | Dialect. |
| source_type | Text |  | Source type of the upload; the current write path sets the value video. |
| user_id | Text |  | Signer/account label as free text, kept for the legacy data contract; the current write path still fills it. This is NOT a foreign key to users. |
| auth_user_id | Uuid | Foreign Key -> users | Account that uploaded the video. |
| session_id | Text |  | Session code at upload time. |
| original_filename | Text |  | Filename supplied by the user, after sanitization. |
| local_path | Text |  | Path of the video on server disk. |
| storage_key | Text |  | File key relative to the dataset root. |
| storage_url | Text |  | Current location of the video; updated after the push to Drive. |
| created_at | Timestamptz |  | Timestamp when the video was uploaded. |
| updated_at | Timestamptz |  | Timestamp of the most recent update. |
| deleted_at | Timestamptz |  | Soft-deletion timestamp; the file remains on disk. |
| status | Varchar(20) | Default: 'PENDING' | Processing status of the upload. |
| session_uid | Text |  | Second session code. |
| username | Text |  | Copy of the account name; survives only on legacy data. |
| tenant_id | Text | Foreign Key -> tenants, Not Null, Default: 'default' | Organization owning the video. |

### signers

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| signer_id | Text | Primary Key, Unique (composite) | Normalized signer identifier; the PRIMARY KEY of the whole table. The pair (tenant_id, signer_id) carries its own unique index so it can be the TARGET of the tenant-aware foreign keys from samples and capture_sessions. |
| display_name | Text |  | Display name of the signer. |
| regional_group | Text |  | Regional group of the signer. |
| external_user_id | Uuid | Foreign Key -> users | Matching platform account, where the signer also holds one; null otherwise. |
| is_active | Boolean | Default: true | Whether the signer still takes part in collection. |
| created_at | Timestamptz |  | Timestamp when the signer was registered. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null, Default: 'default' | Organization maintaining the signer record. |
| note | Text |  | Free-form note. |
| display_order | Integer | Not Null, Default: 0 | Display order set by the operator. |

### signer_aliases

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants | Organization owning the merge record. |
| old_signer_id | Text | Primary Key | Signer identifier that was merged away. |
| new_signer_id | Text | Foreign Key -> signers (composite key), Not Null | Canonical signer identifier remaining after the merge. |
| reason | Text |  | Reason for the merge. |
| merged_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the merge happened. |
| merged_by | Uuid | Foreign Key -> users | Account that performed the merge. |

### classes

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| class_uid | Text | Primary Key, Unique (composite) | Sign class identifier. |
| class_idx | Integer | Unique (composite) | Class index used during training. |
| slug | Text | Unique (composite) | Short form of the label, used to name folders and files. |
| label_original | Text |  | Original label as entered by the user. |
| language | Text | Foreign Key -> languages, Unique (composite) | Classification dimension: sign language of the class. |
| dialect | Text | Foreign Key -> dialects (composite key), Unique (composite) | Classification dimension: dialect of the class. |
| is_common_global | Boolean |  | Whether the class belongs to the vocabulary common to every language. |
| is_common_language | Boolean |  | Whether the class belongs to the vocabulary common within one language. |
| folder_name | Text |  | Name of the physical folder holding the class's samples. |
| created_at | Timestamptz |  | Timestamp when the class was registered. |
| migrated_at | Timestamptz |  | Timestamp when the class was moved into the current hierarchical layout. |
| deleted_at | Timestamptz |  | Soft-deletion timestamp for the class. |
| description | Text | Default: '' | Description of the class. |
| is_active | Boolean | Default: true | Whether the class still accepts new samples. |
| hands_required | Integer |  | Number of hands the sign requires: 1 or 2. |
| semantic_label | Text |  | Normalized semantic label of the class. |
| vocabulary_scope | Text |  | Vocabulary scope the class belongs to. |
| recognition_profile | Text | Foreign Key -> recognition_profiles (composite key) | Classification dimension: recognition profile of the class. |
| vocabulary_group | Text | Foreign Key -> vocabulary_groups (composite key) | Classification dimension: vocabulary group of the class. |
| collection_campaign | Text |  | Collection campaign the class was created in. |
| motion_type | Text |  | Whether the sign is static or moving. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null, Default: 'default' | Organization that scopes the class. |
| region | Text | Foreign Key -> regions, Unique (composite), Not Null, Default: 'unclassified' | Regional classification dimension of the class; part of the NATURAL unique key of a class that is not soft-deleted. |


## D. Catalog and registry

### languages

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| code | Varchar(50) | Primary Key | Sign-language code. |
| name | Text | Not Null | Name of the sign language. |

### regions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| code | Text | Primary Key | Region code. |
| name_vi | Text | Not Null | Vietnamese name of the region. |
| name_en | Text | Not Null, Default: '' | English name of the region. |
| status | Text | Not Null, Default: 'approved' | Approval status of the region entry. |
| sort_order | Integer | Not Null, Default: 0 | Display order. |
| is_active | Boolean | Not Null, Default: true | Whether the region is still selectable or has been retired. |
| note | Text |  | Operator note. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent update. |

### dialects

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants, Default: 'default' | Organization that SCOPES the dialect entry. |
| dialect_id | Text | Primary Key | Dialect identifier, unique within the organization. |
| display_name | Text | Not Null | Human-readable dialect name. |
| language | Text | Foreign Key -> languages, Not Null, Default: 'vn' | Sign language containing this dialect. |
| is_alphabet | Boolean | Not Null, Default: false | Whether this dialect entry is a fingerspelling alphabet. |
| is_active | Boolean | Not Null, Default: true | Whether the dialect is still offered in selection lists. |
| status | Text | Not Null, Default: 'pending' | Lifecycle status of the PROPOSAL to add the dialect. |
| merged_into | Text | Foreign Key -> dialects (composite key) | Target dialect when this entry has been merged away. |
| created_by | Uuid | Foreign Key -> users | Account that proposed the dialect. |
| approved_by | Uuid | Foreign Key -> users | Account that approved it. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the proposal was raised. |
| approved_at | Timestamptz |  | Timestamp when it was approved. |
| note | Text |  | Operator note. |
| display_order | Integer | Not Null, Default: 0 | Display order set by the operator. |

### dialect_aliases

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants, Default: 'default' | Organization that scopes the merge record. |
| old_dialect_id | Text | Primary Key | Former identifier, now redirected to another entry. |
| new_dialect_id | Text | Foreign Key -> dialects (composite key), Not Null | Dialect the old entry was merged into. |
| merged_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the merge happened. |
| merged_by | Uuid | Foreign Key -> users | Account that performed the merge. |

### recognition_profiles

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants, Default: 'default' | Organization that scopes the recognition profile. |
| profile_id | Text | Primary Key | Recognition-profile identifier, unique within the organization. |
| display_name | Text | Not Null | Human-readable profile name. |
| is_trainable | Boolean | Not Null, Default: true | Flag carried along in the registry snapshot. |
| is_active | Boolean | Not Null, Default: true | Whether the profile is still selectable or has been retired. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the profile was created. |
| display_order | Integer | Not Null, Default: 0 | Display order. |

### vocabulary_groups

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants | Organization that scopes the vocabulary group. |
| group_id | Text | Primary Key | Vocabulary-group identifier, unique within the organization. |
| display_name | Text | Not Null | Human-readable group name. |
| display_order | Integer | Not Null, Default: 0 | Display order. |
| is_active | Boolean | Not Null, Default: true | Whether the group is still selectable or has been retired. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the group was created. |

### vocabulary_registry_meta

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants, Default: 'default' | Organization this pointer belongs to. |
| version | Bigint | Foreign Key -> registry_versions (composite key) | POINTER to the organization's currently published registry version. Null means no version has been published. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the pointer was last moved. |

### registry_versions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants | Organization owning this registry version. |
| version | Bigint | Primary Key | Registry version number WITHIN one organization. |
| content_hash | Text | Not Null | Content hash of the snapshot. |
| snapshot | Jsonb | Not Null | Immutable snapshot of the organization's entire catalog at publication time. |
| note | Text |  | Note attached to the publication. |
| created_by | Uuid | Foreign Key -> users | Account that published the version. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of publication. |

### community_dialects

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| dialect_id | Text | Primary Key | Dialect identifier in the platform TEMPLATE. |
| display_name | Text | Not Null | Dialect name in the template. |
| language | Text | Not Null, Default: 'vn' | Sign language of the template entry. |
| is_alphabet | Boolean | Not Null, Default: false | Whether the entry is a fingerspelling alphabet. |
| display_order | Integer | Not Null, Default: 0 | Display order in the template. |
| is_active | Boolean | Not Null, Default: true | Whether the entry is cloned in an active state. |
| note | Text |  | Note by the platform administrator. |
| updated_by | Uuid | Foreign Key -> users | Account that last edited the template. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent template edit. |

### community_profiles

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| profile_id | Text | Primary Key | Recognition-profile identifier in the platform TEMPLATE. |
| display_name | Text | Not Null | Profile name in the template. |
| is_trainable | Boolean | Not Null, Default: true | Flag cloned into a new organization's recognition_profiles. |
| display_order | Integer | Not Null, Default: 0 | Display order in the template. |
| is_active | Boolean | Not Null, Default: true | Whether the profile is cloned at all. |
| note | Text |  | Note by the platform administrator. |
| updated_by | Uuid | Foreign Key -> users | Account that last edited the template. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent template edit. |

### community_versions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| version | Bigint | Primary Key | Version number of the platform TEMPLATE. |
| content_hash | Text | Not Null | Content hash of the template at freeze time. |
| snapshot | Jsonb | Not Null | Immutable snapshot of the template at publication time. |
| note | Text |  | Note attached to the template publication. |
| created_by | Uuid | Foreign Key -> users | Account that published the template. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the template publication. |


## E. Training and models

### training_jobs

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| job_id | Text | Primary Key, Unique (composite) | Training-job identifier. |
| status | Text | Not Null | Lifecycle status: queued, running, completed, failed or cancelled. |
| model_type | Text |  | Model architecture used by the job. |
| config | Jsonb |  | Training configuration actually used, as JSON. |
| auth_user_id | Uuid | Foreign Key -> users | Account recorded as the actor behind the job. |
| created_at | Timestamptz |  | Timestamp when the job was created. |
| started_at | Timestamptz |  | Timestamp when execution began; null while not yet running. |
| completed_at | Timestamptz |  | Timestamp when execution finished; null while not yet finished. |
| current_epoch | Integer | Not Null, Default: 0 | Epoch currently running, counted from 1. |
| total_epochs | Integer | Not Null, Default: 0 | Total number of epochs planned. |
| checkpoint_path | Text |  | Path of the model checkpoint file produced by training. |
| test_acc | Real |  | Accuracy on the test set, on a 0..1 scale. |
| test_f1 | Real |  | MACRO F1 on the test set, on a 0..1 scale. |
| error_message | Text |  | Reason the job failed or was cancelled. |
| promoted_at | Timestamptz |  | Timestamp when an administrator promoted this model into real-time recognition service. |
| evaluation | Jsonb |  | Additional evaluation results, as JSON. |
| superseded_at | Timestamptz |  | Timestamp when a LATER promotion for the same dialect took over the serving slot. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization that scopes the training job. |
| registry_version | Bigint | Foreign Key -> registry_versions (composite key) | The organization's own registry version, anchored to the job so the provenance of the label space at run time is preserved. |

### training_job_classes

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| job_id | Text | Primary Key, Foreign Key -> training_jobs | Training job this class mapping belongs to. |
| class_idx | Integer | Primary Key | Class index inside the label space OF THIS JOB ALONE. |
| class_uid | Text | Foreign Key -> classes | Corresponding source sign class, where the mapping can still be tied to a live class. |
| label | Text | Not Null | Class label captured at training time. This IS the output contract. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization that scopes the training class mapping. |

### training_metrics

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| job_id | Text | Primary Key, Foreign Key -> training_jobs (composite key) | Training job this metric row belongs to. |
| epoch | Integer | Primary Key | Epoch this metric set was recorded at, counted from 1. |
| train_loss | Real |  | Loss on the training data at that epoch. |
| train_acc | Real |  | Accuracy on the training data at that epoch, on a 0..1 scale. |
| val_loss | Real |  | Loss on the validation data at that epoch. |
| val_acc | Real |  | Accuracy on the validation data at that epoch, on a 0..1 scale. |
| val_f1 | Real |  | MACRO F1 on the validation data at that epoch, on a 0..1 scale. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the metric row was written. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization that scopes the metric. |


## F. Subscription, service and integrations

### plans

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| plan_code | Text | Primary Key | Plan code; stable, and the value every quota check looks up. |
| display_name | Text | Not Null | Plan name shown to users. |
| description | Text | Not Null, Default: '' | Plan description for the pricing page. |
| max_seats | Integer |  | Seat count declared in the plan configuration. |
| max_samples | Integer |  | Sample count declared in the plan configuration. |
| max_storage_mb | Integer |  | Storage ceiling for the organization, in MB. ENFORCED. |
| max_classes | Integer |  | Class count declared in the plan configuration. |
| max_training_jobs_per_month | Integer |  | Monthly training-job count declared in the plan configuration. |
| max_concurrent_training_jobs | Integer | Default: 1 | Number of training jobs allowed to run at once. ENFORCED, but as an OPERATIONAL SAFETY control for the GPU runner, not as a commercial quota. |
| max_queued_training_jobs | Integer | Default: 3 | Number of training jobs allowed to queue. ENFORCED, also an operational safety control. |
| max_api_keys | Integer | Default: 0 | Ceiling on live API keys. ENFORCED. |
| max_webhook_endpoints | Integer | Default: 0 | Ceiling on enabled webhook endpoints. ENFORCED. |
| price_cents | Bigint | Default: 0 | LIST price of the plan, in the smallest unit of the plan currency. |
| currency | Text | Not Null, Default: 'VND' | Currency of the list price; defaults to VND. |
| billing_period | Text | Not Null, Default: 'monthly', Allowed values: monthly, yearly, none | Billing interval declared for the plan. |
| is_self_serve | Boolean | Not Null, Default: false | Whether an organization may sign itself up on this plan. |
| is_listed | Boolean | Not Null, Default: true | Whether the plan appears on the public pricing page. |
| trial_days | Integer | Not Null, Default: 0 | Number of trial days granted when the first period opens. |
| sort_order | Integer | Not Null, Default: 0 | Display order on the pricing page. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the plan was created. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent plan edit. |
| max_workspaces | Integer |  | Workspace count declared in the plan configuration. |
| max_projects | Integer |  | Project count declared in the plan configuration. |
| included_training_credits | Integer |  | Training credits INCLUDED with the plan. |
| audit_retention_days | Integer |  | Audit-log retention window declared in the plan configuration. |

### tenant_subscriptions

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| subscription_id | Uuid | Primary Key | Identifier of one subscription-history row. |
| tenant_id | Text | Foreign Key -> tenants, Unique, Not Null | Organization this history row belongs to. |
| plan_code | Text | Foreign Key -> plans, Not Null | Plan selected at this history row. |
| status | Text | Not Null, Default: 'active' | Status of the subscription row. |
| started_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when this subscription row began. |
| ended_at | Timestamptz |  | Timestamp when this subscription row ended; null while it is the open row. |
| changed_by | Uuid | Foreign Key -> users | Account that performed the plan change. |
| note | Text | Not Null, Default: '' | Note attached to the plan change. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the row was written. |
| current_period_start | Timestamptz |  | Start of the current period. |
| current_period_end | Timestamptz |  | End of the current period; the anchor for renewal reminders, for opening the next period, and for computing grace. |
| auto_renew | Boolean | Not Null, Default: true | Whether the period reopens automatically on expiry. |
| grace_until | Timestamptz |  | End of the grace window after the period closed; null while grace has not begun. |
| trial_ends_at | Timestamptz |  | Timestamp when the trial ends. |
| last_reminder_days | Integer |  | REMINDER ALREADY SENT, expressed as the days remaining at the time it was sent. |

### tenant_usage_daily

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants | Organization the measurement belongs to. |
| usage_date | Date | Primary Key | Date of the measurement, in UTC. |
| metric | Text | Primary Key | Metric name: samples_created, raw_uploads_created, training_jobs_started, training_seconds, storage_mb or active_users. |
| value | Bigint | Not Null, Default: 0 | Value of the metric for that date. |
| computed_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the measurement was computed. |

### tenant_storage

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| tenant_id | Text | Primary Key, Foreign Key -> tenants | Organization owning the counter. The column is both primary key and foreign key, so each organization has at most ONE row. |
| bytes_used | Bigint | Not Null, Default: 0 | Bytes ALREADY on disk according to the counter — the settled portion. |
| reconciled_at | Timestamptz |  | Timestamp when the counter was last rebuilt from a real disk walk. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the counter last changed. |

### storage_reservations

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| reservation_id | Uuid | Primary Key | Identifier of one in-flight reservation. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization the reservation belongs to. |
| bytes | Bigint | Not Null | Bytes held provisionally for a write that has NOT yet completed. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the reservation was taken. |
| expires_at | Timestamptz | Not Null | Timestamp when the reservation lapses. |

### tenant_exports

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| export_id | Uuid | Primary Key | Data-export identifier. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization requesting the export. |
| requested_by | Uuid | Foreign Key -> users | Account that requested it. |
| status | Text | Not Null, Default: 'pending', Allowed values: pending, running, ready, failed, expired | Processing status of the export. |
| scope | Text | Not Null, Default: 'metadata', Allowed values: metadata, full | Data scope included in the export. |
| file_path | Text |  | Path of the resulting file. |
| size_bytes | Bigint |  | Size of the resulting file, in bytes. |
| row_counts | Jsonb |  | Rows exported per table, as JSON. |
| error | Text |  | Error message recorded when the export failed. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the export was requested. |
| completed_at | Timestamptz |  | Timestamp when the export completed. |
| expires_at | Timestamptz |  | Timestamp when the export file expires and is swept. |
| export_purpose | Text | Not Null, Default: 'tenant_portability', Allowed values: tenant_portability, internal_training, research_release, public_library | Declared purpose of the release. This is the value consent enforcement is checked against. |

### personal_exports

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| export_id | Uuid | Primary Key, Default: generated UUID | Identifier of one personal data export. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization the requester was acting in. Always the request's own scope, never a path parameter — unlike tenant_exports. |
| user_id | Uuid | Foreign Key -> users, Not Null | Account that requested the export AND owns every row in the package: only samples whose auth_user_id equals this value are included. ON DELETE CASCADE. |
| status | Text | Not Null, Default: 'pending', Allowed values: pending, running, ready, failed, expired | Processing status: pending, running, ready, failed or expired. |
| file_path | Text |  | Server path of the resulting zip, under <dataset_root>/_exports/personal/; NULL once expired and cleaned. |
| size_bytes | Bigint |  | Size of the resulting file. |
| sample_count | Integer |  | Number of sample rows written to the package's samples.csv (feature files may be fewer if no longer on disk). |
| error | Text |  | Error message when the export failed; truncated to 500 characters. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the request. |
| completed_at | Timestamptz |  | Timestamp of completion, successful or not. |
| expires_at | Timestamptz | Not Null | Timestamp after which the file is cleaned up; same TTL as organization exports. |

### tenant_purges

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| purge_id | Uuid | Primary Key | Identifier of one organization purge. |
| tenant_id | Text | Not Null | Identifier of the organization that was purged. Held as TEXT: it is a historical trace, not a link. |
| display_name | Text | Not Null, Default: '' | Organization name as it stood at purge time. |
| requested_by | Uuid |  | Account that requested the purge. A trace; there is no foreign key. |
| row_counts | Jsonb |  | Rows deleted per table, as JSON. |
| files_removed | Integer | Not Null, Default: 0 | Number of files removed from storage. |
| bytes_removed | Bigint | Not Null, Default: 0 | Number of bytes released. |
| export_id | Uuid |  | Data export taken before the purge, if any. |
| reason | Text | Not Null, Default: '' | Reason for the purge. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the purge ran. |

### webhook_endpoints

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| endpoint_id | Uuid | Primary Key | Endpoint identifier. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization owning the endpoint. |
| url | Text | Not Null | HTTP address receiving the events. |
| secret | Text | Not Null | Webhook signing secret, stored UNENCRYPTED (whsec_ plus 32 random bytes). |
| event_types | Text | Not Null, Default: '*' | Event types this endpoint subscribes to. |
| is_active | Boolean | Not Null, Default: true | Whether the endpoint still receives events. |
| description | Text | Not Null, Default: '' | Operator-supplied description of the endpoint. |
| created_by | Uuid | Foreign Key -> users | Account that created the endpoint. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the endpoint was created. |
| last_success_at | Timestamptz |  | Timestamp of the most recent successful delivery. |
| last_failure_at | Timestamptz |  | Timestamp of the most recent failed delivery. |
| failure_streak | Integer | Not Null, Default: 0 | Number of CONSECUTIVE failures; resets to 0 the moment one delivery succeeds. |
| disabled_at | Timestamptz |  | Timestamp when the endpoint was disabled. |
| disabled_reason | Text |  | Reason the endpoint was disabled. |

### webhook_deliveries

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| delivery_id | Uuid | Primary Key | Identifier of one delivery attempt record. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization owning the delivery. |
| endpoint_id | Uuid | Foreign Key -> webhook_endpoints, Not Null | Destination endpoint of the delivery. |
| event_type | Text | Not Null | Business event type being delivered. |
| payload | Jsonb | Not Null | Request body to be sent to the endpoint, as JSON. |
| status | Text | Not Null, Default: 'pending', Allowed values: pending, delivered, failed, dropped | Delivery status. |
| attempts | Integer | Not Null, Default: 0 | Number of attempts made. 0 means nothing has been sent yet. |
| last_status_code | Integer |  | HTTP status code of the most recent attempt; null on a network error or timeout. |
| last_error | Text |  | Error description from the most recent attempt, truncated to 500 characters. |
| next_attempt_at | Timestamptz | Not Null, Default: current timestamp | Earliest time a retry may be made. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the delivery was queued. |
| delivered_at | Timestamptz |  | Timestamp when delivery succeeded; null while it has not. |

### support_tickets

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| ticket_id | Uuid | Primary Key, Default: generated UUID | Support-ticket identifier. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization holding the ticket. |
| user_id | Uuid | Foreign Key -> users | Account that OPENED the ticket. |
| subject | Text | Not Null | Subject line of the ticket. |
| category | Text | Not Null, Default: 'other', Allowed values: account, billing, data, bug, other | Category assigned to the ticket. |
| status | Text | Not Null, Default: 'open', Allowed values: open, pending, resolved, closed | Current status of the ticket. |
| priority | Text | Not Null, Default: 'normal', Allowed values: low, normal, high, urgent | Priority assigned to the ticket. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the ticket was opened. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent update. |
| resolved_at | Timestamptz |  | Timestamp relating to completion of the ticket. |

### support_messages

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| message_id | Uuid | Primary Key, Default: generated UUID | Identifier of one message inside a ticket. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization holding the message. |
| ticket_id | Uuid | Foreign Key -> support_tickets, Not Null | Ticket containing this message. |
| author_id | Uuid | Foreign Key -> users | Account that wrote the message; null when the author is not a person. |
| author_label | Text | Not Null | Author label, captured AT SEND TIME. It is historical evidence and is never rewritten. |
| is_staff | Boolean | Not Null, Default: false | Whether the SENDER was support staff at the moment of sending. |
| body | Text | Not Null | Message body. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the message was sent. |
| author_kind | Text | Default: 'user', Allowed values: user, staff, bot | Category of the message author. |

### notifications

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| notification_id | Uuid | Primary Key, Default: generated UUID | Notification identifier. |
| tenant_id | Text | Foreign Key -> tenants, Not Null | Organization context of the notification. |
| user_id | Uuid | Foreign Key -> users, Not Null | Account RECEIVING the notification. |
| kind | Text | Not Null | Notification type. |
| title | Text | Not Null | Notification title. |
| body | Text | Not Null, Default: '' | Notification body. |
| link | Text |  | In-application link the recipient follows to open the related item. |
| severity | Text | Not Null, Default: 'info', Allowed values: info, success, warning, critical | Severity used to present the notification. |
| read_at | Timestamptz |  | Timestamp when the recipient read it; null while unread. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the notification was raised. |

### event_outbox

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| event_id | Uuid | Primary Key, Default: generated UUID | Identifier of one event in the outbox. |
| tenant_id | Text | Foreign Key -> tenants | Organization the event arose in; null for platform-level events. |
| event_type_code | Text | Not Null | Event type code. |
| payload | Jsonb | Not Null, Default: '{}' | Data carried with the event, as JSON. |
| occurred_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the event OCCURRED — the watermark each reader uses to know how far it has consumed. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the row was written. |
| dispatch_status | Text | Not Null, Default: 'PENDING', Allowed values: PENDING, IN_FLIGHT, DONE, FAILED | Dispatch state of the event. |
| attempts | Integer | Not Null, Default: 0 | Number of dispatch attempts. |
| available_at | Timestamptz | Not Null, Default: current timestamp | Earliest time the event may be retried. |
| processed_at | Timestamptz |  | Timestamp when the event finished processing. |
| last_error | Text |  | Error from the most recent dispatch attempt. |

### google_sheets_sync_status

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| id | Integer | Primary Key, Auto-increment | Identifier of the sync-cursor row. |
| table_name | Varchar(50) | Unique, Not Null | Source table this cursor tracks. |
| current_spreadsheet_id | Varchar(100) | Not Null, Default: '' | Identifier of the Google SPREADSHEET currently being written to — not a Drive folder. |
| current_sheet_index | Integer | Not Null, Default: 1 | Index of the current worksheet, counted from 1. |
| current_data_rows | Integer | Not Null, Default: 0 | Number of data rows already written into the current worksheet. |
| max_rows_per_sheet | Integer | Not Null, Default: 500000 | Row threshold per worksheet before rolling to the next; default 500,000. |
| updated_at | Timestamptz | Default: current timestamp | Timestamp when the cursor was last updated. |


## G. Legal, audit and platform

### legal_documents

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| doc_id | Uuid | Primary Key | Identifier of one published legal document. |
| kind | Text | Unique (composite), Not Null, Allowed values: terms, privacy, data_contribution, guardian | Document type. |
| version | Text | Unique (composite), Not Null | Document version. |
| effective_from | Timestamptz | Unique (composite), Not Null, Default: current timestamp | Timestamp from which the document takes effect. |
| content_hash | Text | Not Null | Content hash at publication time; the anchor a consent signature points at. |
| url | Text | Not Null | Public address of the document. |
| title | Text | Not Null, Default: '' | Document title. |
| requires_reconsent | Boolean | Not Null, Default: false | Whether this version forces anyone who accepted an earlier version to accept again. |
| body | Text | Not Null, Default: '' | Document body stored directly in the database. |
| body_format | Text | Not Null, Default: 'markdown', Allowed values: markdown, text, file | Format the body is stored and rendered in. |
| language | Text | Not Null, Default: 'vi' | Language of this version of the document. |
| change_summary | Text | Not Null, Default: '' | Summary of the change against the previous version. |
| published_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of publication. |
| published_by | Uuid | Foreign Key -> users | Account that published the document. |
| storage_backend | Text | Not Null, Default: 'local' | Where the body is held when it is not in the body column. |
| storage_key | Text |  | Lookup key for the body in the content-addressed store. |
| byte_size | Integer | Not Null, Default: 0 | Size of the body, in bytes. |
| file_key | Text |  | Lookup key for the attached file when body_format = 'file'. |
| file_name | Text |  | Original filename of a file-form document. |
| file_mime | Text |  | MIME type of the attached file. |
| file_size | Bigint |  | Size of the attached file, in bytes. |

### legal_document_drafts

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| draft_id | Uuid | Primary Key | Draft identifier. |
| kind | Text | Unique, Not Null, Allowed values: terms, privacy, data_contribution, guardian | Document type this draft targets. |
| title | Text | Not Null, Default: '' | Intended title. |
| language | Text | Not Null, Default: 'vi' | Language of the draft. |
| body | Text | Not Null, Default: '' | Draft body. |
| body_format | Text | Not Null, Default: 'markdown' | Format of the draft body. |
| change_summary | Text | Not Null, Default: '' | Summary of the intended change. |
| target_version | Text | Not Null, Default: '' | Version number to assign when the draft is published. |
| requires_reconsent | Boolean | Not Null, Default: false | Whether publishing from this draft will force re-consent. |
| effective_from | Timestamptz |  | Intended effective timestamp. |
| status | Text | Not Null, Default: 'draft', Allowed values: draft, in_review, approved, published, discarded | Lifecycle status of the draft. |
| revision | Integer | Not Null, Default: 1 | Number of times the draft has been revised, starting at 1. |
| based_on_version | Text |  | Published version the draft is based on. |
| published_version | Text |  | Version actually published from this draft. |
| storage_key | Text |  | Lookup key for the draft body in the store. |
| content_hash | Text |  | Content hash of the draft. |
| byte_size | Integer | Not Null, Default: 0 | Size of the draft body, in bytes. |
| created_by | Uuid | Foreign Key -> users | Account that created the draft. |
| updated_by | Uuid | Foreign Key -> users | Account that last edited the draft. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the draft was created. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent edit. |

### legal_document_events

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| event_id | Bigint | Primary Key, Auto-increment | Sequence number of the event in the ledger. |
| occurred_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the event occurred. |
| actor_user_id | Uuid |  | Account that acted. Kept as a trace; there is deliberately NO foreign key. |
| actor_label | Text | Not Null, Default: '' | Actor label, filled in at write time. |
| action | Text | Not Null | Action recorded. |
| kind | Text |  | Document type involved. A trace, not a link. |
| version | Text |  | Document version involved. A trace, not a link. |
| draft_id | Uuid |  | Draft involved. A trace, not a link. |
| revision | Integer |  | Revision number of the draft at the time of the event. |
| storage_key | Text |  | Content lookup key at the time of the event. |
| content_hash | Text |  | Content hash at the time of the event. |
| detail | Jsonb |  | Additional event data, as JSON. |

### user_consents

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| consent_id | Uuid | Primary Key | Identifier of one account consent record. |
| user_id | Uuid | Foreign Key -> users, Unique (composite), Not Null | Account that IS THE SUBJECT of the consent. |
| kind | Text | Foreign Key -> legal_documents (composite key), Unique (composite), Not Null | Type of document consented to. |
| version | Text | Foreign Key -> legal_documents (composite key), Not Null | Version of the document consented to. |
| accepted_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of acceptance. |
| ip_hash | Text |  | Hash of the IP address at acceptance time; the column does NOT store the address itself. |
| user_agent | Text |  | User-agent string at acceptance time. |
| withdrawn_at | Timestamptz |  | Timestamp when consent was withdrawn. |
| source | Text | Not Null, Default: 'user', Allowed values: user, backfill, import | Origin of the record. |
| note | Text | Not Null, Default: '' | Note attached to the consent record. |
| recorded_by | Uuid | Foreign Key -> users | Account that WROTE this record. |

### signer_consents

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| consent_id | Uuid | Primary Key | Identifier of one signer consent record. |
| tenant_id | Text | Foreign Key -> tenants, Unique (composite), Not Null | Organization that scopes the record. |
| signer_id | Text | Foreign Key -> signers (composite key), Unique (composite), Not Null | Signer who IS THE SUBJECT of the consent. |
| scope | Text | Unique (composite), Not Null, Allowed values: internal_training, research_release, public_library | Permitted use of the data. A release may not exceed the scope granted here. |
| kind | Text | Foreign Key -> legal_documents (composite key), Not Null | Type of document consented to. |
| version | Text | Foreign Key -> legal_documents (composite key), Not Null | Version of the document consented to. |
| granted_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when permission was granted. |
| withdrawn_at | Timestamptz |  | Timestamp when permission was withdrawn. Withdrawal is withdrawal: the sample can no longer be released. |
| guardian_name | Text |  | Name of the guardian where the signer is not old enough to consent alone. |
| evidence | Text |  | Description of the evidence for the grant. |
| recorded_by | Uuid | Foreign Key -> users | Account that wrote this record. |

### audit_log

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| audit_id | Bigint | Primary Key, Auto-increment | Sequence number of the audit row. |
| tenant_id | Text | Foreign Key -> tenants | Organization the action belongs to. Null for PLATFORM-level actions. |
| actor_user_id | Uuid | Foreign Key -> users | Account that performed the action. |
| actor_label | Text |  | Actor label, captured at write time. |
| action | Text | Not Null | Action recorded. |
| target_type | Text |  | Type of the object acted upon. |
| target_id | Text |  | Identifier of the object acted upon. |
| detail | Jsonb |  | Additional data, as JSON. |
| ip_hash | Text |  | Hash of the request's IP address; the column does NOT store the address itself. |
| created_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the audit row was written. |

### sot_authorized_keys

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| public_key | Text | Primary Key | Public key of a machine authorized to write the source of truth. |
| name | Text | Unique, Not Null | Name of the writer machine. |
| fingerprint | Text | Not Null | Key fingerprint, used for quick comparison. |
| note | Text |  | Operator note. |
| added_by | Text |  | Who added the key, held as TEXT. |
| added_at | Timestamptz | Not Null, Default: current timestamp | Timestamp when the key was added. |
| revoked_at | Timestamptz |  | Timestamp when the key was revoked. |

### platform_settings

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| key | Text | Primary Key | Platform-level configuration key. |
| value | Text | Not Null | Configuration value, stored as TEXT. |
| updated_by | Uuid | Foreign Key -> users | Account that last changed the setting. |
| updated_at | Timestamptz | Not Null, Default: current timestamp | Timestamp of the most recent change. |

### schema_migrations

| Field Name | Data Type | Constraint | Description |
|---|---|---|---|
| version | Integer | Primary Key | Schema version this application brings the database to. |
| applied_at | Timestamptz | Primary Key, Default: current timestamp | Timestamp of the application. |
| applied_by | Text | Not Null | Database role that ran the application. |
| applied_on | Text |  | Identity of the MACHINE that ran the command. |
| note | Text |  | Operator note attached to the application. |
| migration_checksum | Text |  | SHA-256 hash of the migration payload in the FORWARD (up) direction for that version. |


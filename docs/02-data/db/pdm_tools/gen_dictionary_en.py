# -*- coding: utf-8 -*-
"""Sinh Phu luc A.1 - Data Dictionary (ban TIENG ANH, luoc do v8).

Hai nguon tach bach, giong het gen_dictionary.py:
  * CAU TRUC (kieu, NULL, khoa, mac dinh, tap gia tri) -> evidence/*.csv, lay
    thang tu catalog cua signdb. KHONG dong nao go tay.
  * MO TA nghiep vu -> DESC ben duoi, dich tu evidence/pdm_v8_descriptions.csv
    (ban tieng Viet da duoc duyet). Giu tach roi de nguoi doc phan biet duoc
    dong nao cua he thong, dong nao cua tac gia.

Cong may cuoi tep SE HONG neu mot cot cua catalog khong co mo ta tieng Anh —
mot phu luc thieu mo ta im lang la dung thu tai lieu nay ton tai de tranh.
"""
import csv, io, pathlib, collections, sys

HERE = pathlib.Path(__file__).resolve().parent
EVIDENCE = HERE.parent / "evidence"


def doc(p):
    return list(csv.DictReader(io.StringIO(pathlib.Path(p).read_text(encoding="utf-8"))))


cols = doc(EVIDENCE / "pdm_v8_columns.csv")
fks = doc(EVIDENCE / "pdm_v8_foreign_keys.csv")
chks = doc(EVIDENCE / "pdm_v8_checks.csv")
uqs = doc(EVIDENCE / "pdm_v8_uniques.csv")

# --------------------------------------------------------------------------
# Nhom bang. Bay nhom, giu dung ten muc dang dung trong quyen thuyet minh.
# --------------------------------------------------------------------------
GROUPS = [
    ("A", "Identity and access",
     ["users", "refresh_tokens", "password_reset_tokens", "verification_codes",
      "user_totp", "user_recovery_codes", "user_action_passcodes", "api_keys"]),
    ("B", "Organizations and authorization",
     ["tenants", "workspaces", "projects", "project_allocations", "memberships",
      "roles", "permissions", "role_permissions", "role_assignments",
      "tenant_invitations"]),
    ("C", "Sample data repository",
     ["collection_sessions", "capture_sessions", "samples", "raw_uploads",
      "signers", "signer_aliases", "classes"]),
    ("D", "Catalog and registry",
     ["languages", "regions", "dialects", "dialect_aliases",
      "recognition_profiles", "vocabulary_groups", "vocabulary_registry_meta",
      "registry_versions", "community_dialects", "community_profiles",
      "community_versions"]),
    ("E", "Training and models",
     ["training_jobs", "training_job_classes", "training_metrics"]),
    ("F", "Subscription, service and integrations",
     ["plans", "tenant_subscriptions", "tenant_usage_daily", "tenant_storage",
      "storage_reservations", "tenant_exports", "personal_exports", "tenant_purges",
      "webhook_endpoints", "webhook_deliveries", "support_tickets",
      "support_messages", "notifications", "event_outbox",
      "google_sheets_sync_status"]),
    ("G", "Legal, audit and platform",
     ["legal_documents", "legal_document_drafts", "legal_document_events",
      "user_consents", "signer_consents", "audit_log", "sot_authorized_keys",
      "platform_settings", "schema_migrations"]),
]

# --------------------------------------------------------------------------
# Kieu du lieu: ten PostgreSQL -> ten trinh bay trong phu luc.
# --------------------------------------------------------------------------
TYPE = {
    "uuid": "Uuid", "text": "Text", "boolean": "Boolean",
    "timestamp with time zone": "Timestamptz", "integer": "Integer",
    "bigint": "Bigint", "smallint": "Smallint", "jsonb": "Jsonb",
    "real": "Real", "date": "Date",
    "character varying(20)": "Varchar(20)",
    "character varying(50)": "Varchar(50)",
    "character varying(100)": "Varchar(100)",
}

# --------------------------------------------------------------------------
# Mac dinh: bieu thuc PostgreSQL -> cach doc trong phu luc.
# --------------------------------------------------------------------------
def ve_default(d):
    if not d:
        return None
    if d.startswith("nextval("):
        return "AUTO"
    if d == "now()":
        return "current timestamp"
    if d == "gen_random_uuid()":
        return "generated UUID"
    # Bo ep kieu tuong minh cua PostgreSQL. Cat chung chung, khong liet ke tung
    # kieu: lan truoc liet ke tay va `'PENDING'::character varying` lot luoi.
    if "::" in d:
        d = d.split("::", 1)[0]
    return d


# --------------------------------------------------------------------------
# Tap gia tri hop le, rut tu CHECK mot cot dang `= ANY (ARRAY[...])`.
# --------------------------------------------------------------------------
def rut_enum(rule):
    if "ANY (ARRAY[" not in rule:
        return None
    body = rule.split("ANY (ARRAY[", 1)[1]
    body = body.split("])", 1)[0]
    ra = []
    for phan in body.split(","):
        phan = phan.strip()
        if phan.startswith("'"):
            ra.append(phan.split("'")[1])
    return ra or None


enum = {}
for c in chks:
    if "+" in c["columns"]:
        continue
    e = rut_enum(c["rule"])
    if e:
        enum[(c["table_name"], c["columns"])] = e

# --------------------------------------------------------------------------
# Duy nhat: cot tham gia mot PRIMARY KEY / UNIQUE / chi muc duy nhat nao do.
# --------------------------------------------------------------------------
# Phan biet DUY NHAT MOT COT voi DUY NHAT GHEP. Gop hai thu lam mot se noi doi:
# `users.tenant_id` nam trong (tenant_id, username) — mot minh no KHONG duy nhat.
uniq_don, uniq_ghep = set(), set()
for u in uqs:
    if u["kind"] == "PRIMARY KEY":
        continue
    cs = [c.strip() for c in u["columns"].split("+")]
    for c in cs:
        (uniq_don if len(cs) == 1 else uniq_ghep).add((u["table_name"], c))

# --------------------------------------------------------------------------
# Khoa ngoai. Voi cot `tenant_id` ta in `-> tenants`: do la quan he SO HUU.
# Cac khoa ngoai ghep tenant-aware duoc dac ta rieng o phu luc quan he; nhet
# chung vao mot o cot se lam nguoi doc hieu sai chieu tham chieu.
# --------------------------------------------------------------------------
fk_col = collections.defaultdict(list)
for r in fks:
    for c in r["child_cols"].split("+"):
        fk_col[(r["child_table"], c)].append(r)


def hop_ten(col, parent):
    """Ten cot co tro DUNG vao bang cha nay khong.

    Can thiet vi mot cot nam trong NHIEU khoa ngoai ghep: `memberships.user_id`
    vua thuoc (user_id -> users) vua thuoc (parent_membership_id, user_id ->
    memberships). Chi xep theo so cot se in ra `-> memberships`, noi doi ve
    chieu tham chieu cua cot.
    """
    goc = col
    for duoi in ("_id", "_uid", "_code"):
        if goc.endswith(duoi):
            goc = goc[: -len(duoi)]
            break
    for so_it in (parent, parent[:-1], parent[:-2]):
        if so_it and goc.endswith(so_it):
            return True
    return False


def ve_fk(tbl, col):
    rs = fk_col.get((tbl, col))
    if not rs:
        return None
    if col == "tenant_id":
        for r in rs:
            if r["parent_table"] == "tenants" and int(r["n_cols"]) == 1:
                return "tenants", False
    khop = [r for r in rs if hop_ten(col, r["parent_table"])] or rs
    r = sorted(khop, key=lambda r: -int(r["n_cols"]))[0]
    return r["parent_table"], int(r["n_cols"]) > 1


def ve_constraint(c):
    t, col = c["table_name"], c["column_name"]
    ra = []
    if c["is_pk"]:
        ra.append("Primary Key")
    f = ve_fk(t, col)
    if f:
        ra.append("Foreign Key -> %s%s" % (f[0], " (composite key)" if f[1] else ""))
    if (t, col) in uniq_don:
        ra.append("Unique")
    elif (t, col) in uniq_ghep:
        ra.append("Unique (composite)")
    d = ve_default(c["column_default"])
    if d == "AUTO":
        ra.append("Auto-increment")
        d = None
    if c["nullable"] == "NO" and not c["is_pk"]:
        ra.append("Not Null")
    if d:
        ra.append("Default: %s" % d)
    e = enum.get((t, col))
    if e:
        ra.append("Allowed values: %s" % ", ".join(e))
    return ", ".join(ra)


# --------------------------------------------------------------------------
# MO TA NGHIEP VU (tieng Anh). Dich tu evidence/pdm_v8_descriptions.csv.
# --------------------------------------------------------------------------
DESC = {
# ---- A. Identity and access ----------------------------------------------
("users","id"): "Account identifier.",
("users","username"): "Login name.",
("users","email"): "Email address; also usable as a login credential.",
("users","password_hash"): "Password hash. The system has no path back to the original password.",
("users","is_active"): "Whether the account is still active.",
("users","is_admin"): "PLATFORM administration flag, not a role inside any organization. Platform administration and organization administration do not inherit from each other.",
("users","created_at"): "Timestamp when the account was created.",
("users","role_id"): "Legacy role reference. This is NOT the authorization path in force today.",
("users","phone_number"): "Phone number used for SMS verification codes.",
("users","updated_at"): "Timestamp of the most recent update.",
("users","deleted_at"): "Soft-deletion timestamp for the account. Null means the record is still in the working set.",
("users","tenant_id"): "Organization used as the account's default/fallback context; authoritative membership and access are expressed through Membership. This table carries an isolation policy with a system-scope escape path, because login resolution runs before the organization is known.",
("users","email_verified_at"): "Timestamp when control of the email address was verified.",
("users","phone_verified_at"): "Timestamp when control of the phone number was verified.",
("users","sessions_invalid_before"): "Session revocation cutoff: every token issued before this moment is invalid. This is level two of the three-level revocation mechanism.",
("users","active_tenant_id"): "Organization the user is currently SELECTING as working context.",

("refresh_tokens","token_hash"): "SHA-256 hash of the refresh token. The table does NOT store the token itself.",
("refresh_tokens","user_id"): "Account holding this token.",
("refresh_tokens","expires_at"): "Timestamp when the token expires naturally.",
("refresh_tokens","revoked_at"): "Timestamp when the token was revoked.",
("refresh_tokens","created_at"): "Timestamp when the token was issued.",
("refresh_tokens","family_id"): "Token FAMILY identifier: the whole rotation chain descending from one login.",
("refresh_tokens","replaced_by"): "Logical reference to the refresh token that replaced this one in the rotation chain, stored as the successor's hash.",
("refresh_tokens","reuse_detected_at"): "Timestamp when a replaced refresh token was seen used again OUTSIDE the grace window — treated as theft.",

("password_reset_tokens","token_hash"): "SHA-256 hash of the password-reset token. The table does NOT store the token itself.",
("password_reset_tokens","user_id"): "Account this reset token belongs to.",
("password_reset_tokens","expires_at"): "Timestamp when the token stops being valid.",
("password_reset_tokens","used_at"): "Timestamp when the token was consumed; null means unused.",
("password_reset_tokens","created_at"): "Timestamp when the token was issued.",

("verification_codes","challenge_id"): "Identifier of one verification challenge.",
("verification_codes","user_id"): "Account tied to the challenge, if one already exists; may be null for challenges raised BEFORE registration completes.",
("verification_codes","purpose"): "Purpose for issuing the code.",
("verification_codes","channel"): "Delivery channel used to send the code.",
("verification_codes","destination"): "Address or phone number the code was sent to. A code proves control of THIS destination, not authority over an account.",
("verification_codes","code_hash"): "HMAC-SHA256 hash of the code, keyed with a pepper held OUTSIDE the database.",
("verification_codes","attempts"): "Number of entry attempts made so far.",
("verification_codes","max_attempts"): "Attempt ceiling before the challenge dies; default 5.",
("verification_codes","created_at"): "Timestamp when the challenge was issued.",
("verification_codes","expires_at"): "Timestamp when the challenge times out.",
("verification_codes","consumed_at"): "Timestamp when the code was consumed; null means unused.",

("user_totp","user_id"): "Account owning this TOTP configuration. The column is both primary key and foreign key, so each account has at most ONE configuration.",
("user_totp","secret_enc"): "TOTP secret, ENCRYPTED (Fernet) — not hashed.",
("user_totp","confirmed_at"): "Timestamp when the user confirmed the secret and two-factor authentication became active; null means the secret exists but is not yet in force.",
("user_totp","last_used_step"): "Most recently accepted TOTP time step — the replay guard.",
("user_totp","created_at"): "Timestamp when TOTP enrolment started.",

("user_recovery_codes","code_hash"): "HMAC-SHA256 hash of one recovery code. The table does NOT store the code itself.",
("user_recovery_codes","user_id"): "Account owning this set of recovery codes.",
("user_recovery_codes","used_at"): "Timestamp when the code was consumed; null means unused.",
("user_recovery_codes","created_at"): "Timestamp when the code was issued.",

("user_action_passcodes","user_id"): "Account owning the action passcode. The column is both primary key and foreign key, so each account has at most ONE configuration.",
("user_action_passcodes","passcode_hash"): "Hash of the action passcode, produced by the SAME hashing routine as the login password.",
("user_action_passcodes","status"): "Current status of the passcode.",
("user_action_passcodes","failed_count"): "Cumulative number of incorrect entries.",
("user_action_passcodes","created_at"): "Timestamp when the passcode was set.",
("user_action_passcodes","updated_at"): "Timestamp of the most recent update.",
("user_action_passcodes","locked_until"): "Timestamp when the lock imposed after repeated failures expires; null means not locked.",
("user_action_passcodes","revoked_at"): "Timestamp when the passcode was revoked.",

("api_keys","key_id"): "API key identifier.",
("api_keys","tenant_id"): "Organization that scopes the key.",
("api_keys","name"): "Operator-assigned key name.",
("api_keys","prefix"): "Public prefix of the key, used to identify it without exposing it.",
("api_keys","key_hash"): "Hash of the key. The table does NOT store the key itself.",
("api_keys","scopes"): "Operations the key is permitted to perform.",
("api_keys","created_by"): "Account that created the key.",
("api_keys","created_at"): "Timestamp when the key was created.",
("api_keys","last_used_at"): "Timestamp when the key was most recently used.",
("api_keys","expires_at"): "Timestamp when the key expires.",
("api_keys","revoked_at"): "Timestamp when the key was revoked. The plan ceiling counts only keys NOT yet revoked.",
("api_keys","revoked_by"): "Account that revoked the key.",

# ---- B. Organizations and authorization -----------------------------------
("tenants","tenant_id"): "Organization identifier; the value every tenant-isolation policy matches against.",
("tenants","display_name"): "Organization name shown to users.",
("tenants","slug"): "Short, URL-friendly form of the organization name.",
("tenants","is_active"): "Whether the organization is still operating.",
("tenants","created_at"): "Timestamp when the organization was created.",
("tenants","deleted_at"): "Soft-deletion timestamp for the organization.",
("tenants","cloned_from_community_version"): "Community catalog version the organization was cloned from at provisioning time.",
("tenants","cloned_at"): "Timestamp when the catalog was cloned.",
("tenants","plan_code"): "Plan currently in force; the value every quota check READS.",
("tenants","billing_status"): "Billing/service status of the organization; decides whether the organization may still write data.",
("tenants","trial_ends_at"): "Timestamp when the trial period ends.",
("tenants","current_period_start"): "Start of the current subscription period.",
("tenants","current_period_end"): "End of the current subscription period; the anchor for renewal reminders and for opening the next period.",
("tenants","is_self_serve"): "Whether the organization signed itself up or was created by a platform administrator.",
("tenants","owner_user_id"): "Account designated as organization owner; may be null.",
("tenants","suspended_at"): "Timestamp when service was suspended.",
("tenants","suspended_reason"): "Reason for the suspension.",
("tenants","tenant_type"): "Organization category, distinguishing the community tenant from ordinary organizations.",
("tenants","is_system_reserved"): "Organization reserved by the platform; it cannot be deleted.",
("tenants","billing_exempt"): "Whether the organization is exempt from commercial quotas.",

("workspaces","workspace_id"): "Workspace identifier.",
("workspaces","tenant_id"): "Organization containing this workspace.",
("workspaces","name"): "Workspace name, unique within the organization among workspaces not soft-deleted.",
("workspaces","description"): "Description of the workspace.",
("workspaces","status"): "Lifecycle status of the workspace.",
("workspaces","is_default"): "Whether this is the organization's default workspace.",
("workspaces","created_at"): "Timestamp when the workspace was created.",
("workspaces","archived_at"): "Timestamp when the workspace was archived.",
("workspaces","deleted_at"): "Soft-deletion timestamp.",

("projects","project_id"): "Project identifier.",
("projects","tenant_id"): "Organization containing this project.",
("projects","workspace_id"): "Workspace containing this project.",
("projects","name"): "Project name, unique within its workspace.",
("projects","description"): "Description of the project.",
("projects","status"): "Lifecycle status of the project.",
("projects","is_default"): "Whether this is the workspace's default project.",
("projects","created_at"): "Timestamp when the project was created.",
("projects","archived_at"): "Timestamp when the project was archived.",
("projects","deleted_at"): "Soft-deletion timestamp.",

("project_allocations","tenant_id"): "Organization that scopes the allocation.",
("project_allocations","project_id"): "Project receiving the allocation.",
("project_allocations","metric"): "Quota being divided: samples, storage_mb or training_jobs_per_month.",
("project_allocations","allocated"): "Share of the quota reserved for this project. Null means UNLIMITED — not 'not yet filled in'.",
("project_allocations","note"): "Operator note about the allocation.",
("project_allocations","updated_by"): "Account that last adjusted the allocation.",
("project_allocations","updated_at"): "Timestamp of the most recent adjustment.",

("memberships","membership_id"): "Membership identifier.",
("memberships","user_id"): "Account holding this membership.",
("memberships","scope_level"): "Scope level at which the membership grants standing.",
("memberships","tenant_id"): "Organization that scopes the membership.",
("memberships","workspace_id"): "Workspace of the membership. Null when scope_level = TENANT; not null for WORKSPACE and PROJECT.",
("memberships","project_id"): "Project of the membership. Not null only when scope_level = PROJECT.",
("memberships","parent_membership_id"): "Parent membership in the scope tree, belonging to the SAME person.",
("memberships","legacy_role"): "Backward-compatible role value, usable only on a tenant-level membership.",
("memberships","status"): "Current status of the membership.",
("memberships","joined_at"): "Timestamp when the member joined.",
("memberships","suspended_at"): "Timestamp when the membership was suspended.",
("memberships","left_at"): "Timestamp when the member left. A CHECK forces this column to carry a value IF AND ONLY IF status = REMOVED.",
("memberships","created_at"): "Timestamp when the record was created.",
("memberships","updated_at"): "Timestamp of the most recent update.",

("roles","role_id"): "Role identifier.",
("roles","role_code"): "Stable role code, the value application code looks the role up by.",
("roles","description"): "Description of the role for operators.",
("roles","tenant_id"): "Organization owning a CUSTOM role. Null for roles built into the platform.",
("roles","scope_level"): "Scope at which the role may be assigned.",
("roles","is_builtin"): "Whether the role ships with the platform or was created by an organization.",
("roles","is_active"): "Whether the role is still usable or has been retired.",
("roles","created_at"): "Timestamp when the role was created.",
("roles","role_name"): "Display name of the role.",
("roles","tenant_type_constraint"): "Restricts the role to one organization type; null means no restriction.",
("roles","created_by_user_id"): "Account that created the custom role.",
("roles","updated_at"): "Timestamp of the most recent update.",

("permissions","permission_code"): "Permission code, written as domain.action.",
("permissions","description"): "Description of the permission for operators.",
("permissions","applicable_scope"): "Scope tier at which the permission applies.",
("permissions","risk_level"): "Security risk classification of the permission.",
("permissions","requires_passcode"): "Whether the permission demands re-authentication by action passcode before use.",
("permissions","is_api_assignable"): "Whether the permission may be granted to an API key.",
("permissions","is_active"): "Whether the permission is still in force or has been retired.",
("permissions","created_at"): "Timestamp when the permission was declared.",
("permissions","is_custom_role_allowed"): "Whether the permission may be included in an organization's custom role.",

("role_permissions","role_id"): "Role receiving the permission.",
("role_permissions","permission_code"): "Permission granted to the role.",
("role_permissions","granted_at"): "Timestamp when the permission was attached to the role.",

("role_assignments","assignment_id"): "Role-assignment identifier.",
("role_assignments","user_id"): "Account RECEIVING the role — the subject of the grant.",
("role_assignments","role_id"): "Role being granted.",
("role_assignments","membership_id"): "Membership this assignment is anchored to.",
("role_assignments","assigned_by_user_id"): "Account that PERFORMED the grant — the actor.",
("role_assignments","assigned_at"): "Timestamp when the role was granted.",
("role_assignments","revoked_by_user_id"): "Account that PERFORMED the revocation — the revoking actor.",
("role_assignments","revoked_at"): "Timestamp when the role was revoked.",
("role_assignments","revoke_reason"): "Reason for the revocation.",

("tenant_invitations","invitation_id"): "Invitation identifier.",
("tenant_invitations","tenant_id"): "Organization issuing the invitation.",
("tenant_invitations","email"): "Email address of the invitee, normalized on write.",
("tenant_invitations","role"): "Role offered to the invitee on joining.",
("tenant_invitations","token_hash"): "Hash of the invitation token. The table does NOT store the token itself.",
("tenant_invitations","invited_by"): "Account that issued the invitation.",
("tenant_invitations","created_at"): "Timestamp when the invitation was issued.",
("tenant_invitations","expires_at"): "Timestamp when the invitation expires.",
("tenant_invitations","accepted_at"): "Timestamp when the invitation was accepted.",
("tenant_invitations","accepted_by"): "Account that accepted the invitation.",
("tenant_invitations","revoked_at"): "Timestamp when the invitation was revoked.",

# ---- C. Sample data repository --------------------------------------------
("collection_sessions","collection_session_id"): "Collection-session identifier.",
("collection_sessions","tenant_id"): "Organization owning the record; the scope tenant isolation applies to.",
("collection_sessions","session_code"): "Client-generated session code, unique within one organization.",
("collection_sessions","opened_by_user_id"): "Account that opened the collection session. This is the OPERATOR, not the signer.",
("collection_sessions","source_type"): "Capture channel: live camera or uploaded video.",
("collection_sessions","started_at"): "Timestamp when the collection session started.",
("collection_sessions","ended_at"): "Timestamp when the collection session ended; null while it is still open.",
("collection_sessions","note"): "Free-form operator note.",
("collection_sessions","created_at"): "Timestamp when the record was created.",

("capture_sessions","capture_session_id"): "Identifier of one capture session for a single sign class.",
("capture_sessions","tenant_id"): "Organization owning the record.",
("capture_sessions","class_uid"): "Sign class captured in this session.",
("capture_sessions","session_id"): "Client-supplied session code; unique per (organization, class), NOT unique on its own.",
("capture_sessions","signer_id"): "SUMMARY signer of the session, kept from the earlier design. Measurement contradicts the one-session-one-signer assumption, so this column is NOT the authoritative identity source; its tenant-aware foreign key nevertheless remains in force.",
("capture_sessions","auth_user_id"): "Account that performed the capture session. This is distinct from signer identity.",
("capture_sessions","source_type"): "Capture channel of the session.",
("capture_sessions","started_at"): "Timestamp when the session started.",
("capture_sessions","ended_at"): "Timestamp when the session ended.",
("capture_sessions","note"): "Free-form note.",
("capture_sessions","created_at"): "Timestamp when the record was created.",
("capture_sessions","collection_session_id"): "Collection session containing this capture session; null for data predating the hierarchy.",
("capture_sessions","visibility"): "Who may see the session: private (owner and editors only) or tenant (the owner opened it to ordinary members of the same organization). Enforced by the API, not by a CHECK.",

("samples","sample_uid"): "Sample identifier.",
("samples","class_uid"): "Sign class this sample is labelled with.",
("samples","slug"): "Copy of the class slug as it stood when the sample was written.",
("samples","label_original"): "Copy of the class's original label as it stood when the sample was written.",
("samples","language"): "Sign language of the sample.",
("samples","dialect"): "Dialect of the sample.",
("samples","source_type"): "Capture channel: camera or uploaded video.",
("samples","user_id"): "Signer/account label as free text, kept for the legacy data contract; the current write path still fills it. This is NOT a foreign key to users.",
("samples","auth_user_id"): "Account that performed the capture or upload of this sample.",
("samples","session_id"): "Client-supplied session code at capture time.",
("samples","fps_original"): "Frame rate of the original source.",
("samples","fps_processed"): "Frame rate after preprocessing.",
("samples","seq_len"): "Sequence length after padding to the target length.",
("samples","augment_id"): "Augmentation variant index; 0 is the original.",
("samples","completeness"): "Proportion of frames carrying a valid hand.",
("samples","file_path"): "Path of the feature file, relative to the dataset root.",
("samples","storage_url"): "Path or URL where the file currently resides.",
("samples","checksum"): "Checksum of the feature file.",
("samples","created_at"): "Timestamp when the sample was written.",
("samples","sheets_synced"): "Whether the metadata has been synchronized to Google Sheets.",
("samples","gdrive_synced"): "Whether the file has been synchronized to Google Drive.",
("samples","status"): "No longer updated by any write path.",
("samples","error_log"): "Processing error message, if any.",
("samples","updated_at"): "Timestamp of the most recent update.",
("samples","storage_key"): "File key in the object store, relative to the dataset root.",
("samples","session_uid"): "Second session code, distinct from session_id.",
("samples","username"): "Copy of the account name; survives only on legacy data.",
("samples","deleted_at"): "Soft-deletion timestamp. The file REMAINS on disk until the Trash is purged.",
("samples","left_hand_ratio"): "Proportion of frames in which the left hand was detected.",
("samples","right_hand_ratio"): "Proportion of frames in which the right hand was detected.",
("samples","both_hands_ratio"): "Proportion of frames in which both hands were detected.",
("samples","jitter"): "Landmark jitter of the sequence, 95th percentile.",
("samples","quality_flags"): "Quality warnings raised for this capture.",
("samples","signer_id"): "Normalized signer identity, where it has been resolved.",
("samples","collection_campaign"): "Collection campaign the sample belongs to.",
("samples","raw_landmarks_available"): "Whether a raw landmark record exists in the raw archive.",
("samples","normalization_version"): "Version of the normalization algorithm applied to the sample.",
("samples","preprocess_contract_version"): "Version of the preprocessing contract applied.",
("samples","sequence_length_original"): "Number of frames before padding or truncation.",
("samples","quality_status"): "Quality verdict: passed, or flagged.",
("samples","tenant_id"): "Organization owning the sample; the scope tenant isolation applies to.",
("samples","capture_session_id"): "Capture session containing this sample.",
("samples","review_status"): "Moderation status of the sample.",
("samples","reviewed_by"): "Account that reviewed the sample.",
("samples","reviewed_at"): "Timestamp when the review was recorded.",
("samples","review_note"): "Reviewer's note.",

("raw_uploads","upload_uid"): "Upload identifier; also the idempotency key when a client retries.",
("raw_uploads","class_uid"): "Sign class of the video.",
("raw_uploads","slug"): "Copy of the class slug.",
("raw_uploads","label_original"): "Copy of the class's original label.",
("raw_uploads","language"): "Sign language.",
("raw_uploads","dialect"): "Dialect.",
("raw_uploads","source_type"): "Source type of the upload; the current write path sets the value video.",
("raw_uploads","user_id"): "Signer/account label as free text, kept for the legacy data contract; the current write path still fills it. This is NOT a foreign key to users.",
("raw_uploads","auth_user_id"): "Account that uploaded the video.",
("raw_uploads","session_id"): "Session code at upload time.",
("raw_uploads","original_filename"): "Filename supplied by the user, after sanitization.",
("raw_uploads","local_path"): "Path of the video on server disk.",
("raw_uploads","storage_key"): "File key relative to the dataset root.",
("raw_uploads","storage_url"): "Current location of the video; updated after the push to Drive.",
("raw_uploads","created_at"): "Timestamp when the video was uploaded.",
("raw_uploads","updated_at"): "Timestamp of the most recent update.",
("raw_uploads","deleted_at"): "Soft-deletion timestamp; the file remains on disk.",
("raw_uploads","status"): "Processing status of the upload.",
("raw_uploads","session_uid"): "Second session code.",
("raw_uploads","username"): "Copy of the account name; survives only on legacy data.",
("raw_uploads","tenant_id"): "Organization owning the video.",

("signers","signer_id"): "Normalized signer identifier; the PRIMARY KEY of the whole table. The pair (tenant_id, signer_id) carries its own unique index so it can be the TARGET of the tenant-aware foreign keys from samples and capture_sessions.",
("signers","display_name"): "Display name of the signer.",
("signers","regional_group"): "Regional group of the signer.",
("signers","external_user_id"): "Matching platform account, where the signer also holds one; null otherwise.",
("signers","is_active"): "Whether the signer still takes part in collection.",
("signers","created_at"): "Timestamp when the signer was registered.",
("signers","tenant_id"): "Organization maintaining the signer record.",
("signers","note"): "Free-form note.",
("signers","display_order"): "Display order set by the operator.",

("signer_aliases","tenant_id"): "Organization owning the merge record.",
("signer_aliases","old_signer_id"): "Signer identifier that was merged away.",
("signer_aliases","new_signer_id"): "Canonical signer identifier remaining after the merge.",
("signer_aliases","reason"): "Reason for the merge.",
("signer_aliases","merged_at"): "Timestamp when the merge happened.",
("signer_aliases","merged_by"): "Account that performed the merge.",

("classes","class_uid"): "Sign class identifier.",
("classes","class_idx"): "Class index used during training.",
("classes","slug"): "Short form of the label, used to name folders and files.",
("classes","label_original"): "Original label as entered by the user.",
("classes","language"): "Classification dimension: sign language of the class.",
("classes","dialect"): "Classification dimension: dialect of the class.",
("classes","is_common_global"): "Whether the class belongs to the vocabulary common to every language.",
("classes","is_common_language"): "Whether the class belongs to the vocabulary common within one language.",
("classes","folder_name"): "Name of the physical folder holding the class's samples.",
("classes","created_at"): "Timestamp when the class was registered.",
("classes","migrated_at"): "Timestamp when the class was moved into the current hierarchical layout.",
("classes","deleted_at"): "Soft-deletion timestamp for the class.",
("classes","description"): "Description of the class.",
("classes","is_active"): "Whether the class still accepts new samples.",
("classes","hands_required"): "Number of hands the sign requires: 1 or 2.",
("classes","semantic_label"): "Normalized semantic label of the class.",
("classes","vocabulary_scope"): "Vocabulary scope the class belongs to.",
("classes","recognition_profile"): "Classification dimension: recognition profile of the class.",
("classes","vocabulary_group"): "Classification dimension: vocabulary group of the class.",
("classes","collection_campaign"): "Collection campaign the class was created in.",
("classes","motion_type"): "Whether the sign is static or moving.",
("classes","tenant_id"): "Organization that scopes the class.",
("classes","region"): "Regional classification dimension of the class; part of the NATURAL unique key of a class that is not soft-deleted.",

# ---- D. Catalog and registry ----------------------------------------------
("languages","code"): "Sign-language code.",
("languages","name"): "Name of the sign language.",

("regions","code"): "Region code.",
("regions","name_vi"): "Vietnamese name of the region.",
("regions","name_en"): "English name of the region.",
("regions","status"): "Approval status of the region entry.",
("regions","sort_order"): "Display order.",
("regions","is_active"): "Whether the region is still selectable or has been retired.",
("regions","note"): "Operator note.",
("regions","updated_at"): "Timestamp of the most recent update.",

("dialects","tenant_id"): "Organization that SCOPES the dialect entry.",
("dialects","dialect_id"): "Dialect identifier, unique within the organization.",
("dialects","display_name"): "Human-readable dialect name.",
("dialects","language"): "Sign language containing this dialect.",
("dialects","is_alphabet"): "Whether this dialect entry is a fingerspelling alphabet.",
("dialects","is_active"): "Whether the dialect is still offered in selection lists.",
("dialects","status"): "Lifecycle status of the PROPOSAL to add the dialect.",
("dialects","merged_into"): "Target dialect when this entry has been merged away.",
("dialects","created_by"): "Account that proposed the dialect.",
("dialects","approved_by"): "Account that approved it.",
("dialects","created_at"): "Timestamp when the proposal was raised.",
("dialects","approved_at"): "Timestamp when it was approved.",
("dialects","note"): "Operator note.",
("dialects","display_order"): "Display order set by the operator.",

("dialect_aliases","tenant_id"): "Organization that scopes the merge record.",
("dialect_aliases","old_dialect_id"): "Former identifier, now redirected to another entry.",
("dialect_aliases","new_dialect_id"): "Dialect the old entry was merged into.",
("dialect_aliases","merged_at"): "Timestamp when the merge happened.",
("dialect_aliases","merged_by"): "Account that performed the merge.",

("recognition_profiles","tenant_id"): "Organization that scopes the recognition profile.",
("recognition_profiles","profile_id"): "Recognition-profile identifier, unique within the organization.",
("recognition_profiles","display_name"): "Human-readable profile name.",
("recognition_profiles","is_trainable"): "Flag carried along in the registry snapshot.",
("recognition_profiles","is_active"): "Whether the profile is still selectable or has been retired.",
("recognition_profiles","created_at"): "Timestamp when the profile was created.",
("recognition_profiles","display_order"): "Display order.",

("vocabulary_groups","tenant_id"): "Organization that scopes the vocabulary group.",
("vocabulary_groups","group_id"): "Vocabulary-group identifier, unique within the organization.",
("vocabulary_groups","display_name"): "Human-readable group name.",
("vocabulary_groups","display_order"): "Display order.",
("vocabulary_groups","is_active"): "Whether the group is still selectable or has been retired.",
("vocabulary_groups","created_at"): "Timestamp when the group was created.",

("vocabulary_registry_meta","tenant_id"): "Organization this pointer belongs to.",
("vocabulary_registry_meta","version"): "POINTER to the organization's currently published registry version. Null means no version has been published.",
("vocabulary_registry_meta","updated_at"): "Timestamp when the pointer was last moved.",

("registry_versions","tenant_id"): "Organization owning this registry version.",
("registry_versions","version"): "Registry version number WITHIN one organization.",
("registry_versions","content_hash"): "Content hash of the snapshot.",
("registry_versions","snapshot"): "Immutable snapshot of the organization's entire catalog at publication time.",
("registry_versions","note"): "Note attached to the publication.",
("registry_versions","created_by"): "Account that published the version.",
("registry_versions","created_at"): "Timestamp of publication.",

("community_dialects","dialect_id"): "Dialect identifier in the platform TEMPLATE.",
("community_dialects","display_name"): "Dialect name in the template.",
("community_dialects","language"): "Sign language of the template entry.",
("community_dialects","is_alphabet"): "Whether the entry is a fingerspelling alphabet.",
("community_dialects","display_order"): "Display order in the template.",
("community_dialects","is_active"): "Whether the entry is cloned in an active state.",
("community_dialects","note"): "Note by the platform administrator.",
("community_dialects","updated_by"): "Account that last edited the template.",
("community_dialects","updated_at"): "Timestamp of the most recent template edit.",

("community_profiles","profile_id"): "Recognition-profile identifier in the platform TEMPLATE.",
("community_profiles","display_name"): "Profile name in the template.",
("community_profiles","is_trainable"): "Flag cloned into a new organization's recognition_profiles.",
("community_profiles","display_order"): "Display order in the template.",
("community_profiles","is_active"): "Whether the profile is cloned at all.",
("community_profiles","note"): "Note by the platform administrator.",
("community_profiles","updated_by"): "Account that last edited the template.",
("community_profiles","updated_at"): "Timestamp of the most recent template edit.",

("community_versions","version"): "Version number of the platform TEMPLATE.",
("community_versions","content_hash"): "Content hash of the template at freeze time.",
("community_versions","snapshot"): "Immutable snapshot of the template at publication time.",
("community_versions","note"): "Note attached to the template publication.",
("community_versions","created_by"): "Account that published the template.",
("community_versions","created_at"): "Timestamp of the template publication.",

# ---- E. Training and models ------------------------------------------------
("training_jobs","job_id"): "Training-job identifier.",
("training_jobs","status"): "Lifecycle status: queued, running, completed, failed or cancelled.",
("training_jobs","model_type"): "Model architecture used by the job.",
("training_jobs","config"): "Training configuration actually used, as JSON.",
("training_jobs","auth_user_id"): "Account recorded as the actor behind the job.",
("training_jobs","created_at"): "Timestamp when the job was created.",
("training_jobs","started_at"): "Timestamp when execution began; null while not yet running.",
("training_jobs","completed_at"): "Timestamp when execution finished; null while not yet finished.",
("training_jobs","current_epoch"): "Epoch currently running, counted from 1.",
("training_jobs","total_epochs"): "Total number of epochs planned.",
("training_jobs","checkpoint_path"): "Path of the model checkpoint file produced by training.",
("training_jobs","test_acc"): "Accuracy on the test set, on a 0..1 scale.",
("training_jobs","test_f1"): "MACRO F1 on the test set, on a 0..1 scale.",
("training_jobs","error_message"): "Reason the job failed or was cancelled.",
("training_jobs","promoted_at"): "Timestamp when an administrator promoted this model into real-time recognition service.",
("training_jobs","evaluation"): "Additional evaluation results, as JSON.",
("training_jobs","superseded_at"): "Timestamp when a LATER promotion for the same dialect took over the serving slot.",
("training_jobs","tenant_id"): "Organization that scopes the training job.",
("training_jobs","registry_version"): "The organization's own registry version, anchored to the job so the provenance of the label space at run time is preserved.",

("training_job_classes","job_id"): "Training job this class mapping belongs to.",
("training_job_classes","class_idx"): "Class index inside the label space OF THIS JOB ALONE.",
("training_job_classes","class_uid"): "Corresponding source sign class, where the mapping can still be tied to a live class.",
("training_job_classes","label"): "Class label captured at training time. This IS the output contract.",
("training_job_classes","tenant_id"): "Organization that scopes the training class mapping.",

("training_metrics","job_id"): "Training job this metric row belongs to.",
("training_metrics","epoch"): "Epoch this metric set was recorded at, counted from 1.",
("training_metrics","train_loss"): "Loss on the training data at that epoch.",
("training_metrics","train_acc"): "Accuracy on the training data at that epoch, on a 0..1 scale.",
("training_metrics","val_loss"): "Loss on the validation data at that epoch.",
("training_metrics","val_acc"): "Accuracy on the validation data at that epoch, on a 0..1 scale.",
("training_metrics","val_f1"): "MACRO F1 on the validation data at that epoch, on a 0..1 scale.",
("training_metrics","created_at"): "Timestamp when the metric row was written.",
("training_metrics","tenant_id"): "Organization that scopes the metric.",

# ---- F. Subscription, service and integrations -----------------------------
("plans","plan_code"): "Plan code; stable, and the value every quota check looks up.",
("plans","display_name"): "Plan name shown to users.",
("plans","description"): "Plan description for the pricing page.",
("plans","max_seats"): "Seat count declared in the plan configuration.",
("plans","max_samples"): "Sample count declared in the plan configuration.",
("plans","max_storage_mb"): "Storage ceiling for the organization, in MB. ENFORCED.",
("plans","max_classes"): "Class count declared in the plan configuration.",
("plans","max_training_jobs_per_month"): "Monthly training-job count declared in the plan configuration.",
("plans","max_concurrent_training_jobs"): "Number of training jobs allowed to run at once. ENFORCED, but as an OPERATIONAL SAFETY control for the GPU runner, not as a commercial quota.",
("plans","max_queued_training_jobs"): "Number of training jobs allowed to queue. ENFORCED, also an operational safety control.",
("plans","max_api_keys"): "Ceiling on live API keys. ENFORCED.",
("plans","max_webhook_endpoints"): "Ceiling on enabled webhook endpoints. ENFORCED.",
("plans","price_cents"): "LIST price of the plan, in the smallest unit of the plan currency.",
("plans","currency"): "Currency of the list price; defaults to VND.",
("plans","billing_period"): "Billing interval declared for the plan.",
("plans","is_self_serve"): "Whether an organization may sign itself up on this plan.",
("plans","is_listed"): "Whether the plan appears on the public pricing page.",
("plans","trial_days"): "Number of trial days granted when the first period opens.",
("plans","sort_order"): "Display order on the pricing page.",
("plans","created_at"): "Timestamp when the plan was created.",
("plans","updated_at"): "Timestamp of the most recent plan edit.",
("plans","max_workspaces"): "Workspace count declared in the plan configuration.",
("plans","max_projects"): "Project count declared in the plan configuration.",
("plans","included_training_credits"): "Training credits INCLUDED with the plan.",
("plans","audit_retention_days"): "Audit-log retention window declared in the plan configuration.",

("tenant_subscriptions","subscription_id"): "Identifier of one subscription-history row.",
("tenant_subscriptions","tenant_id"): "Organization this history row belongs to.",
("tenant_subscriptions","plan_code"): "Plan selected at this history row.",
("tenant_subscriptions","status"): "Status of the subscription row.",
("tenant_subscriptions","started_at"): "Timestamp when this subscription row began.",
("tenant_subscriptions","ended_at"): "Timestamp when this subscription row ended; null while it is the open row.",
("tenant_subscriptions","changed_by"): "Account that performed the plan change.",
("tenant_subscriptions","note"): "Note attached to the plan change.",
("tenant_subscriptions","created_at"): "Timestamp when the row was written.",
("tenant_subscriptions","current_period_start"): "Start of the current period.",
("tenant_subscriptions","current_period_end"): "End of the current period; the anchor for renewal reminders, for opening the next period, and for computing grace.",
("tenant_subscriptions","auto_renew"): "Whether the period reopens automatically on expiry.",
("tenant_subscriptions","grace_until"): "End of the grace window after the period closed; null while grace has not begun.",
("tenant_subscriptions","trial_ends_at"): "Timestamp when the trial ends.",
("tenant_subscriptions","last_reminder_days"): "REMINDER ALREADY SENT, expressed as the days remaining at the time it was sent.",

("tenant_usage_daily","tenant_id"): "Organization the measurement belongs to.",
("tenant_usage_daily","usage_date"): "Date of the measurement, in UTC.",
("tenant_usage_daily","metric"): "Metric name: samples_created, raw_uploads_created, training_jobs_started, training_seconds, storage_mb or active_users.",
("tenant_usage_daily","value"): "Value of the metric for that date.",
("tenant_usage_daily","computed_at"): "Timestamp when the measurement was computed.",

("tenant_storage","tenant_id"): "Organization owning the counter. The column is both primary key and foreign key, so each organization has at most ONE row.",
("tenant_storage","bytes_used"): "Bytes ALREADY on disk according to the counter — the settled portion.",
("tenant_storage","reconciled_at"): "Timestamp when the counter was last rebuilt from a real disk walk.",
("tenant_storage","updated_at"): "Timestamp when the counter last changed.",

("storage_reservations","reservation_id"): "Identifier of one in-flight reservation.",
("storage_reservations","tenant_id"): "Organization the reservation belongs to.",
("storage_reservations","bytes"): "Bytes held provisionally for a write that has NOT yet completed.",
("storage_reservations","created_at"): "Timestamp when the reservation was taken.",
("storage_reservations","expires_at"): "Timestamp when the reservation lapses.",

("tenant_exports","export_id"): "Data-export identifier.",
("tenant_exports","tenant_id"): "Organization requesting the export.",
("tenant_exports","requested_by"): "Account that requested it.",
("tenant_exports","status"): "Processing status of the export.",
("tenant_exports","scope"): "Data scope included in the export.",
("tenant_exports","file_path"): "Path of the resulting file.",
("tenant_exports","size_bytes"): "Size of the resulting file, in bytes.",
("tenant_exports","row_counts"): "Rows exported per table, as JSON.",
("tenant_exports","error"): "Error message recorded when the export failed.",
("tenant_exports","created_at"): "Timestamp when the export was requested.",
("tenant_exports","completed_at"): "Timestamp when the export completed.",
("tenant_exports","expires_at"): "Timestamp when the export file expires and is swept.",
("tenant_exports","export_purpose"): "Declared purpose of the release. This is the value consent enforcement is checked against.",

("personal_exports","export_id"): "Identifier of one personal data export.",
("personal_exports","tenant_id"): "Organization the requester was acting in. Always the request's own scope, never a path parameter — unlike tenant_exports.",
("personal_exports","user_id"): "Account that requested the export AND owns every row in the package: only samples whose auth_user_id equals this value are included. ON DELETE CASCADE.",
("personal_exports","status"): "Processing status: pending, running, ready, failed or expired.",
("personal_exports","file_path"): "Server path of the resulting zip, under <dataset_root>/_exports/personal/; NULL once expired and cleaned.",
("personal_exports","size_bytes"): "Size of the resulting file.",
("personal_exports","sample_count"): "Number of sample rows written to the package's samples.csv (feature files may be fewer if no longer on disk).",
("personal_exports","error"): "Error message when the export failed; truncated to 500 characters.",
("personal_exports","created_at"): "Timestamp of the request.",
("personal_exports","completed_at"): "Timestamp of completion, successful or not.",
("personal_exports","expires_at"): "Timestamp after which the file is cleaned up; same TTL as organization exports.",

("tenant_purges","purge_id"): "Identifier of one organization purge.",
("tenant_purges","tenant_id"): "Identifier of the organization that was purged. Held as TEXT: it is a historical trace, not a link.",
("tenant_purges","display_name"): "Organization name as it stood at purge time.",
("tenant_purges","requested_by"): "Account that requested the purge. A trace; there is no foreign key.",
("tenant_purges","row_counts"): "Rows deleted per table, as JSON.",
("tenant_purges","files_removed"): "Number of files removed from storage.",
("tenant_purges","bytes_removed"): "Number of bytes released.",
("tenant_purges","export_id"): "Data export taken before the purge, if any.",
("tenant_purges","reason"): "Reason for the purge.",
("tenant_purges","created_at"): "Timestamp when the purge ran.",

("webhook_endpoints","endpoint_id"): "Endpoint identifier.",
("webhook_endpoints","tenant_id"): "Organization owning the endpoint.",
("webhook_endpoints","url"): "HTTP address receiving the events.",
("webhook_endpoints","secret"): "Webhook signing secret, stored UNENCRYPTED (whsec_ plus 32 random bytes).",
("webhook_endpoints","event_types"): "Event types this endpoint subscribes to.",
("webhook_endpoints","is_active"): "Whether the endpoint still receives events.",
("webhook_endpoints","description"): "Operator-supplied description of the endpoint.",
("webhook_endpoints","created_by"): "Account that created the endpoint.",
("webhook_endpoints","created_at"): "Timestamp when the endpoint was created.",
("webhook_endpoints","last_success_at"): "Timestamp of the most recent successful delivery.",
("webhook_endpoints","last_failure_at"): "Timestamp of the most recent failed delivery.",
("webhook_endpoints","failure_streak"): "Number of CONSECUTIVE failures; resets to 0 the moment one delivery succeeds.",
("webhook_endpoints","disabled_at"): "Timestamp when the endpoint was disabled.",
("webhook_endpoints","disabled_reason"): "Reason the endpoint was disabled.",

("webhook_deliveries","delivery_id"): "Identifier of one delivery attempt record.",
("webhook_deliveries","tenant_id"): "Organization owning the delivery.",
("webhook_deliveries","endpoint_id"): "Destination endpoint of the delivery.",
("webhook_deliveries","event_type"): "Business event type being delivered.",
("webhook_deliveries","payload"): "Request body to be sent to the endpoint, as JSON.",
("webhook_deliveries","status"): "Delivery status.",
("webhook_deliveries","attempts"): "Number of attempts made. 0 means nothing has been sent yet.",
("webhook_deliveries","last_status_code"): "HTTP status code of the most recent attempt; null on a network error or timeout.",
("webhook_deliveries","last_error"): "Error description from the most recent attempt, truncated to 500 characters.",
("webhook_deliveries","next_attempt_at"): "Earliest time a retry may be made.",
("webhook_deliveries","created_at"): "Timestamp when the delivery was queued.",
("webhook_deliveries","delivered_at"): "Timestamp when delivery succeeded; null while it has not.",

("support_tickets","ticket_id"): "Support-ticket identifier.",
("support_tickets","tenant_id"): "Organization holding the ticket.",
("support_tickets","user_id"): "Account that OPENED the ticket.",
("support_tickets","subject"): "Subject line of the ticket.",
("support_tickets","category"): "Category assigned to the ticket.",
("support_tickets","status"): "Current status of the ticket.",
("support_tickets","priority"): "Priority assigned to the ticket.",
("support_tickets","created_at"): "Timestamp when the ticket was opened.",
("support_tickets","updated_at"): "Timestamp of the most recent update.",
("support_tickets","resolved_at"): "Timestamp relating to completion of the ticket.",

("support_messages","message_id"): "Identifier of one message inside a ticket.",
("support_messages","tenant_id"): "Organization holding the message.",
("support_messages","ticket_id"): "Ticket containing this message.",
("support_messages","author_id"): "Account that wrote the message; null when the author is not a person.",
("support_messages","author_label"): "Author label, captured AT SEND TIME. It is historical evidence and is never rewritten.",
("support_messages","is_staff"): "Whether the SENDER was support staff at the moment of sending.",
("support_messages","body"): "Message body.",
("support_messages","created_at"): "Timestamp when the message was sent.",
("support_messages","author_kind"): "Category of the message author.",

("notifications","notification_id"): "Notification identifier.",
("notifications","tenant_id"): "Organization context of the notification.",
("notifications","user_id"): "Account RECEIVING the notification.",
("notifications","kind"): "Notification type.",
("notifications","title"): "Notification title.",
("notifications","body"): "Notification body.",
("notifications","link"): "In-application link the recipient follows to open the related item.",
("notifications","severity"): "Severity used to present the notification.",
("notifications","read_at"): "Timestamp when the recipient read it; null while unread.",
("notifications","created_at"): "Timestamp when the notification was raised.",

("event_outbox","event_id"): "Identifier of one event in the outbox.",
("event_outbox","tenant_id"): "Organization the event arose in; null for platform-level events.",
("event_outbox","event_type_code"): "Event type code.",
("event_outbox","payload"): "Data carried with the event, as JSON.",
("event_outbox","occurred_at"): "Timestamp when the event OCCURRED — the watermark each reader uses to know how far it has consumed.",
("event_outbox","created_at"): "Timestamp when the row was written.",
("event_outbox","dispatch_status"): "Dispatch state of the event.",
("event_outbox","attempts"): "Number of dispatch attempts.",
("event_outbox","available_at"): "Earliest time the event may be retried.",
("event_outbox","processed_at"): "Timestamp when the event finished processing.",
("event_outbox","last_error"): "Error from the most recent dispatch attempt.",

("google_sheets_sync_status","id"): "Identifier of the sync-cursor row.",
("google_sheets_sync_status","table_name"): "Source table this cursor tracks.",
("google_sheets_sync_status","current_spreadsheet_id"): "Identifier of the Google SPREADSHEET currently being written to — not a Drive folder.",
("google_sheets_sync_status","current_sheet_index"): "Index of the current worksheet, counted from 1.",
("google_sheets_sync_status","current_data_rows"): "Number of data rows already written into the current worksheet.",
("google_sheets_sync_status","max_rows_per_sheet"): "Row threshold per worksheet before rolling to the next; default 500,000.",
("google_sheets_sync_status","updated_at"): "Timestamp when the cursor was last updated.",

# ---- G. Legal, audit and platform ------------------------------------------
("legal_documents","doc_id"): "Identifier of one published legal document.",
("legal_documents","kind"): "Document type.",
("legal_documents","version"): "Document version.",
("legal_documents","effective_from"): "Timestamp from which the document takes effect.",
("legal_documents","content_hash"): "Content hash at publication time; the anchor a consent signature points at.",
("legal_documents","url"): "Public address of the document.",
("legal_documents","title"): "Document title.",
("legal_documents","requires_reconsent"): "Whether this version forces anyone who accepted an earlier version to accept again.",
("legal_documents","body"): "Document body stored directly in the database.",
("legal_documents","body_format"): "Format the body is stored and rendered in.",
("legal_documents","language"): "Language of this version of the document.",
("legal_documents","change_summary"): "Summary of the change against the previous version.",
("legal_documents","published_at"): "Timestamp of publication.",
("legal_documents","published_by"): "Account that published the document.",
("legal_documents","storage_backend"): "Where the body is held when it is not in the body column.",
("legal_documents","storage_key"): "Lookup key for the body in the content-addressed store.",
("legal_documents","byte_size"): "Size of the body, in bytes.",
("legal_documents","file_key"): "Lookup key for the attached file when body_format = 'file'.",
("legal_documents","file_name"): "Original filename of a file-form document.",
("legal_documents","file_mime"): "MIME type of the attached file.",
("legal_documents","file_size"): "Size of the attached file, in bytes.",

("legal_document_drafts","draft_id"): "Draft identifier.",
("legal_document_drafts","kind"): "Document type this draft targets.",
("legal_document_drafts","title"): "Intended title.",
("legal_document_drafts","language"): "Language of the draft.",
("legal_document_drafts","body"): "Draft body.",
("legal_document_drafts","body_format"): "Format of the draft body.",
("legal_document_drafts","change_summary"): "Summary of the intended change.",
("legal_document_drafts","target_version"): "Version number to assign when the draft is published.",
("legal_document_drafts","requires_reconsent"): "Whether publishing from this draft will force re-consent.",
("legal_document_drafts","effective_from"): "Intended effective timestamp.",
("legal_document_drafts","status"): "Lifecycle status of the draft.",
("legal_document_drafts","revision"): "Number of times the draft has been revised, starting at 1.",
("legal_document_drafts","based_on_version"): "Published version the draft is based on.",
("legal_document_drafts","published_version"): "Version actually published from this draft.",
("legal_document_drafts","storage_key"): "Lookup key for the draft body in the store.",
("legal_document_drafts","content_hash"): "Content hash of the draft.",
("legal_document_drafts","byte_size"): "Size of the draft body, in bytes.",
("legal_document_drafts","created_by"): "Account that created the draft.",
("legal_document_drafts","updated_by"): "Account that last edited the draft.",
("legal_document_drafts","created_at"): "Timestamp when the draft was created.",
("legal_document_drafts","updated_at"): "Timestamp of the most recent edit.",

("legal_document_events","event_id"): "Sequence number of the event in the ledger.",
("legal_document_events","occurred_at"): "Timestamp when the event occurred.",
("legal_document_events","actor_user_id"): "Account that acted. Kept as a trace; there is deliberately NO foreign key.",
("legal_document_events","actor_label"): "Actor label, filled in at write time.",
("legal_document_events","action"): "Action recorded.",
("legal_document_events","kind"): "Document type involved. A trace, not a link.",
("legal_document_events","version"): "Document version involved. A trace, not a link.",
("legal_document_events","draft_id"): "Draft involved. A trace, not a link.",
("legal_document_events","revision"): "Revision number of the draft at the time of the event.",
("legal_document_events","storage_key"): "Content lookup key at the time of the event.",
("legal_document_events","content_hash"): "Content hash at the time of the event.",
("legal_document_events","detail"): "Additional event data, as JSON.",

("user_consents","consent_id"): "Identifier of one account consent record.",
("user_consents","user_id"): "Account that IS THE SUBJECT of the consent.",
("user_consents","kind"): "Type of document consented to.",
("user_consents","version"): "Version of the document consented to.",
("user_consents","accepted_at"): "Timestamp of acceptance.",
("user_consents","ip_hash"): "Hash of the IP address at acceptance time; the column does NOT store the address itself.",
("user_consents","user_agent"): "User-agent string at acceptance time.",
("user_consents","withdrawn_at"): "Timestamp when consent was withdrawn.",
("user_consents","source"): "Origin of the record.",
("user_consents","note"): "Note attached to the consent record.",
("user_consents","recorded_by"): "Account that WROTE this record.",

("signer_consents","consent_id"): "Identifier of one signer consent record.",
("signer_consents","tenant_id"): "Organization that scopes the record.",
("signer_consents","signer_id"): "Signer who IS THE SUBJECT of the consent.",
("signer_consents","scope"): "Permitted use of the data. A release may not exceed the scope granted here.",
("signer_consents","kind"): "Type of document consented to.",
("signer_consents","version"): "Version of the document consented to.",
("signer_consents","granted_at"): "Timestamp when permission was granted.",
("signer_consents","withdrawn_at"): "Timestamp when permission was withdrawn. Withdrawal is withdrawal: the sample can no longer be released.",
("signer_consents","guardian_name"): "Name of the guardian where the signer is not old enough to consent alone.",
("signer_consents","evidence"): "Description of the evidence for the grant.",
("signer_consents","recorded_by"): "Account that wrote this record.",

("audit_log","audit_id"): "Sequence number of the audit row.",
("audit_log","tenant_id"): "Organization the action belongs to. Null for PLATFORM-level actions.",
("audit_log","actor_user_id"): "Account that performed the action.",
("audit_log","actor_label"): "Actor label, captured at write time.",
("audit_log","action"): "Action recorded.",
("audit_log","target_type"): "Type of the object acted upon.",
("audit_log","target_id"): "Identifier of the object acted upon.",
("audit_log","detail"): "Additional data, as JSON.",
("audit_log","ip_hash"): "Hash of the request's IP address; the column does NOT store the address itself.",
("audit_log","created_at"): "Timestamp when the audit row was written.",

("sot_authorized_keys","public_key"): "Public key of a machine authorized to write the source of truth.",
("sot_authorized_keys","name"): "Name of the writer machine.",
("sot_authorized_keys","fingerprint"): "Key fingerprint, used for quick comparison.",
("sot_authorized_keys","note"): "Operator note.",
("sot_authorized_keys","added_by"): "Who added the key, held as TEXT.",
("sot_authorized_keys","added_at"): "Timestamp when the key was added.",
("sot_authorized_keys","revoked_at"): "Timestamp when the key was revoked.",

("platform_settings","key"): "Platform-level configuration key.",
("platform_settings","value"): "Configuration value, stored as TEXT.",
("platform_settings","updated_by"): "Account that last changed the setting.",
("platform_settings","updated_at"): "Timestamp of the most recent change.",

("schema_migrations","version"): "Schema version this application brings the database to.",
("schema_migrations","applied_at"): "Timestamp of the application.",
("schema_migrations","applied_by"): "Database role that ran the application.",
("schema_migrations","applied_on"): "Identity of the MACHINE that ran the command.",
("schema_migrations","note"): "Operator note attached to the application.",
("schema_migrations","migration_checksum"): "SHA-256 hash of the migration payload in the FORWARD (up) direction for that version.",
}

# --------------------------------------------------------------------------
# Ket xuat
# --------------------------------------------------------------------------
theo_bang = collections.OrderedDict()
for c in cols:
    theo_bang.setdefault(c["table_name"], []).append(c)

# Cong may 1: moi bang cua catalog phai nam trong dung mot nhom.
da_nhom = [t for _, _, ts in GROUPS for t in ts]
assert len(da_nhom) == len(set(da_nhom)), "mot bang nam o hai nhom"
thieu = set(theo_bang) - set(da_nhom)
thua = set(da_nhom) - set(theo_bang)
assert not thieu, "bang cua catalog chua duoc xep nhom: %s" % sorted(thieu)
assert not thua, "nhom nhac toi bang khong co trong catalog: %s" % sorted(thua)

# Cong may 2: moi cot phai co mo ta tieng Anh.
ko_mota = [(c["table_name"], c["column_name"]) for c in cols
           if (c["table_name"], c["column_name"]) not in DESC]
if ko_mota:
    sys.exit("THIEU MO TA cho %d cot: %s" % (len(ko_mota), ko_mota[:20]))

o = []
w = o.append
w("# A.1. DATA DICTIONARY\n")
w("The data dictionary documents the physical structure and purpose of each")
w("relation in the CTU.SignBridge database. Tables are grouped according to the")
w("same functional domains used in the physical database model.\n")
w("Structure — data type, nullability, keys, defaults and permitted value sets —")
w("is read directly from the `signdb` catalog at schema version **v8**")
w("(%d tables, %d columns). Descriptions are authored and reviewed separately;" % (len(theo_bang), len(cols)))
w("the database itself carries no column comments.\n")

for ky, ten, ts in GROUPS:
    w("\n## %s. %s\n" % (ky, ten))
    for t in ts:
        w("### %s\n" % t)
        w("| Field Name | Data Type | Constraint | Description |")
        w("|---|---|---|---|")
        for c in theo_bang[t]:
            w("| %s | %s | %s | %s |" % (
                c["column_name"],
                TYPE[c["data_type"]],
                ve_constraint(c),
                DESC[(t, c["column_name"])]))
        w("")

out = HERE.parent.parent.parent / "00-thesis" / "quyen" / "PHU_LUC_A1_DATA_DICTIONARY_EN.md"
out.write_text("\n".join(o) + "\n", encoding="utf-8")
print("da ghi:", out)
print("bang:", len(theo_bang), "cot:", len(cols))

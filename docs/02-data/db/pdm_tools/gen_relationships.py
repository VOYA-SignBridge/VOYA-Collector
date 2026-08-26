# -*- coding: utf-8 -*-
"""Bảng vẽ ERD — bản 2, phân loại A/B/C và tên nhóm D do người đặt.

Đổi so với bản 1:
  * Bản 1 gộp `tenant_id`/`user_id`/`auth_user_id` vào nhóm "suy được từ tên
    cột". SAI: `tenant_id` không chứa động từ "owns", `auth_user_id` không chứa
    "operates". Đó là suy diễn ngữ nghĩa, chỉ khác là đầu vào có thật.
  * Ba loại nguồn tên bây giờ:
        A  tên cột CHỨA động từ  (created_by, reviewed_by, opened_by_user_id…)
        B  tham chiếu/sở hữu cấu trúc  (tenant_id, user_id, class_uid, …)
        C  quan hệ miền, khoá ghép  — bắt buộc đặt tay
  * B và C chỉ có tên khi người duyệt đã chốt, chứ không sinh máy.
"""
import collections
import csv
import io
import pathlib
import re


def doc(t):
    return list(csv.DictReader(io.StringIO(pathlib.Path(t).read_text(encoding="utf-8"))))


fks = doc("fk.csv")
TEN = {"A": "Tenant & Access Management", "B": "Authentication & User Security",
       "C": "VSL Vocabulary & Registry", "D": "VSL Collection & Dataset",
       "E": "Legal, Consent & Governance", "F": "Training & Evaluation",
       "G": "Plan, Billing & Storage", "H": "Integration & Operations"}
NHOM = {}
for d in pathlib.Path("nhom.txt").read_text().split("\n"):
    p = d.split()
    if p:
        for t in p[1:]:
            NHOM[t] = p[0]

# Loại A — tên cột TỰ CHỨA động từ. Đây là dữ liệu, không phải suy diễn.
LOAI_A = {
    "created_by": ("creates", "is created by"), "updated_by": ("updates", "is updated by"),
    "revoked_by": ("revokes", "is revoked by"), "approved_by": ("approves", "is approved by"),
    "reviewed_by": ("reviews", "is reviewed by"), "invited_by": ("invites", "is invited by"),
    "changed_by": ("changes", "is changed by"), "accepted_by": ("accepts", "is accepted by"),
    "opened_by_user_id": ("opens", "is opened by"), "closed_by": ("closes", "is closed by"),
    "requested_by": ("requests", "is requested by"), "assigned_by": ("assigns", "is assigned by"),
    "granted_by": ("grants", "is granted by"), "merged_by": ("merges", "is merged by"),
    "deleted_by": ("deletes", "is deleted by"), "signed_by": ("signs", "is signed by"),
}

# Ghi de theo TEN RANG BUOC. Can thiet khi hai khoa ngoai trung ca (cha, con,
# cot) — `project_allocations.tenant_id` co DUNG hai FK nhu vay, va chung khac
# nhau o ON DELETE. Cung mot Relationship Name, hai Code: khong bia hai ngu
# nghia chi de hop thuc hoa hai rang buoc vat ly.
THEO_CONSTRAINT = {
    "fk_project_allocations_tenant":
        ("Tenant scopes Project Allocation", "TENANT_SCOPES_PROJECT_ALLOCATION_RESTRICT", "scope"),
    "project_allocations_tenant_id_fkey":
        ("Tenant scopes Project Allocation", "TENANT_SCOPES_PROJECT_ALLOCATION_CASCADE", "scope"),
}

# Nhom F (Training & Evaluation), chot 26/08/2026.
NHOM_F = {
    # `class_uid` NULLABLE, va bang giu ca class_idx lan label rieng theo tung
    # job — nen "is referenced by" dung hon "belongs to".
    ("classes", "training_job_classes", "class_uid"):
        ("Class is referenced by Training Job Class",
         "CLASS_IS_REFERENCED_BY_TRAINING_JOB_CLASS", "class mapping"),
    ("tenants", "training_job_classes", "tenant_id"):
        ("Tenant scopes Training Job Class", "TENANT_SCOPES_TRAINING_JOB_CLASS", "scope"),
    ("training_jobs", "training_job_classes", "job_id"):
        ("Training Job contains Training Job Class",
         "TRAINING_JOB_CONTAINS_TRAINING_JOB_CLASS", "job composition"),
    # Provenance tu vung: cho biet anh chup tu vung NAO gan voi luot huan luyen,
    # thay vi chi biet model chay luc nao. Khoa ghep nen phien ban phai thuoc
    # dung to chuc ay.
    ("registry_versions", "training_jobs", "tenant_id+registry_version"):
        ("Registry Version anchors Training Job",
         "REGISTRY_VERSION_ANCHORS_TRAINING_JOB", "provenance"),
    ("tenants", "training_jobs", "tenant_id"):
        ("Tenant scopes Training Job", "TENANT_SCOPES_TRAINING_JOB", "scope"),
    # Khong dung "starts"/"requests"/"trains": catalog chua chung minh hanh dong
    # cu the nao.
    ("users", "training_jobs", "auth_user_id"):
        ("User is recorded as Actor for Training Job",
         "USER_IS_RECORDED_AS_ACTOR_FOR_TRAINING_JOB", "optional actor"),
    # Mot semantics, HAI rang buoc vat ly — giong cap doi o nhom D.
    ("training_jobs", "training_metrics", "job_id"):
        ("Training Job records Training Metric (legacy key)",
         "TRAINING_JOB_RECORDS_TRAINING_METRIC_LEGACY_KEY", "legacy key"),
    ("training_jobs", "training_metrics", "tenant_id+job_id"):
        ("Training Job records Training Metric",
         "TRAINING_JOB_RECORDS_TRAINING_METRIC", "tenant-aware"),
    ("tenants", "training_metrics", "tenant_id"):
        ("Tenant scopes Training Metric", "TENANT_SCOPES_TRAINING_METRIC", "scope"),
}

# Nhom B (Authentication & User Security), chot 26/08/2026.
# KHONG dung "owns" cho bat ky chung chi nao: day la hien vat bao mat gan voi
# tai khoan, khong phai mien so huu.
NHOM_B = {
    ("users", "password_reset_tokens", "user_id"):
        ("User has Password Reset Token", "USER_HAS_PASSWORD_RESET_TOKEN", "password recovery"),
    ("users", "refresh_tokens", "user_id"):
        ("User holds Refresh Token", "USER_HOLDS_REFRESH_TOKEN", "session credential"),
    # 1 - 0..1: `user_id` chinh la khoa chinh cua bang.
    ("users", "user_action_passcodes", "user_id"):
        ("User has Action Passcode", "USER_HAS_ACTION_PASSCODE", "privileged action credential"),
    ("users", "user_recovery_codes", "user_id"):
        ("User has Recovery Code", "USER_HAS_RECOVERY_CODE", "account recovery"),
    ("users", "user_totp", "user_id"):
        ("User has TOTP Credential", "USER_HAS_TOTP_CREDENTIAL", "MFA credential"),
    # `user_id` NULLABLE: mot thu thach xac minh ton tai duoc TRUOC khi co tai
    # khoan (xac minh email luc dang ky), va ban ghi van giu purpose, channel,
    # destination, code_hash. Nen "associated with" chu khong "has".
    ("users", "verification_codes", "user_id"):
        ("User is associated with Verification Code",
         "USER_IS_ASSOCIATED_WITH_VERIFICATION_CODE", "optional verification subject"),
}

# Nhom G (Plan, Billing & Storage), chot 26/08/2026.
NHOM_G = {
    ("tenants", "storage_reservations", "tenant_id"):
        ("Tenant has Storage Reservation", "TENANT_HAS_STORAGE_RESERVATION", "quota reservation"),
    # 1 - 0..1, va bang chi giu bytes_used/reconciled_at/updated_at: day la BO
    # DEM hien trang cho moi to chuc, khong phai lich su nhieu dong.
    ("tenants", "tenant_storage", "tenant_id"):
        ("Tenant maintains Storage Counter", "TENANT_MAINTAINS_STORAGE_COUNTER", "storage accounting"),
    # "Subscription Record" chu khong "current subscription": bang co
    # started_at/ended_at/grace/trial nen no la LICH SU. Goi hien hanh se lan
    # voi `tenants.plan_code`.
    ("tenants", "tenant_subscriptions", "tenant_id"):
        ("Tenant has Subscription Record", "TENANT_HAS_SUBSCRIPTION_RECORD", "subscription history"),
    ("plans", "tenant_subscriptions", "plan_code"):
        ("Plan is selected by Tenant Subscription",
         "PLAN_IS_SELECTED_BY_TENANT_SUBSCRIPTION", "entitlement history"),
    ("tenants", "tenant_usage_daily", "tenant_id"):
        ("Tenant records Daily Usage", "TENANT_RECORDS_DAILY_USAGE", "usage accounting"),
}

# Nhom H (Integration & Operations), chot 26/08/2026.
NHOM_H = {
    # "scopes" chu khong "owns": FK nullable nen co thong diep tich hop KHONG
    # thuoc to chuc nao — su kien cap nen tang. Cung hinh dang voi audit_log.
    ("tenants", "event_outbox", "tenant_id"):
        ("Tenant scopes Outbox Event", "TENANT_SCOPES_OUTBOX_EVENT", "optional scope"),
    ("tenants", "notifications", "tenant_id"):
        ("Tenant scopes Notification", "TENANT_SCOPES_NOTIFICATION", "scope"),
    ("users", "notifications", "user_id"):
        ("User receives Notification", "USER_RECEIVES_NOTIFICATION", "recipient"),
    # `support_messages.tenant_id` khong du thua du co the suy qua ticket: no la
    # pham vi TRUC TIEP ma RLS bam vao.
    ("tenants", "support_messages", "tenant_id"):
        ("Tenant scopes Support Message", "TENANT_SCOPES_SUPPORT_MESSAGE", "scope / RLS"),
    # "is recorded as Author" chu khong "authors": author_kind co the la `bot`
    # hoac `staff`, va khi ay author_id NULL. Ten nay chiu duoc truong hop do.
    ("users", "support_messages", "author_id"):
        ("User is recorded as Author of Support Message",
         "USER_IS_RECORDED_AS_AUTHOR_OF_SUPPORT_MESSAGE", "optional author"),
    ("support_tickets", "support_messages", "ticket_id"):
        ("Support Ticket contains Support Message",
         "SUPPORT_TICKET_CONTAINS_SUPPORT_MESSAGE", "support hierarchy"),
    ("tenants", "support_tickets", "tenant_id"):
        ("Tenant scopes Support Ticket", "TENANT_SCOPES_SUPPORT_TICKET", "scope"),
    # Nguoi mo ticket khong nhat thiet viet moi tin nhan trong ticket ay.
    ("users", "support_tickets", "user_id"):
        ("User opens Support Ticket", "USER_OPENS_SUPPORT_TICKET", "requester"),
    ("tenants", "webhook_deliveries", "tenant_id"):
        ("Tenant scopes Webhook Delivery", "TENANT_SCOPES_WEBHOOK_DELIVERY", "scope"),
    # Cau bi dong: van bat dau tu entity CHA (dung chieu khoa ngoai) nhung khong
    # dao nghia nghiep vu. "produces" se khien nguoi doc tuong endpoint ben
    # ngoai la thanh phan phat sinh thong diep; that ra no la CAU HINH DICH.
    ("webhook_endpoints", "webhook_deliveries", "endpoint_id"):
        ("Webhook Endpoint is target of Webhook Delivery",
         "WEBHOOK_ENDPOINT_IS_TARGET_OF_WEBHOOK_DELIVERY", "delivery lifecycle"),
    ("tenants", "webhook_endpoints", "tenant_id"):
        ("Tenant scopes Webhook Endpoint", "TENANT_SCOPES_WEBHOOK_ENDPOINT", "scope"),
}

# Nhom E (Legal, Consent & Governance), chot 26/08/2026.
NHOM_E = {
    ("users", "audit_log", "actor_user_id"):
        ("User is recorded as Actor in Audit Log",
         "USER_IS_RECORDED_AS_ACTOR_IN_AUDIT_LOG", "audit actor"),
    # Cardinality 0..1 tu noi rang ngu canh tenant KHONG bat buoc: so kiem toan
    # ghi duoc ca su kien cap nen tang, khong thuoc to chuc nao.
    ("tenants", "audit_log", "tenant_id"):
        ("Tenant scopes Audit Log Entry", "TENANT_SCOPES_AUDIT_LOG_ENTRY", "optional scope"),
    ("users", "legal_documents", "published_by"):
        ("User publishes Legal Document", "USER_PUBLISHES_LEGAL_DOCUMENT", "actor/action"),
    # "anchors" chu khong "grants"/"signs": khoa ngoai chi bao dam chap thuan
    # neo vao DUNG MOT phien ban van ban. No khong noi gi ve viec ai da ky —
    # ban ghi con den tu backfill va import.
    ("legal_documents", "signer_consents", "kind+version"):
        ("Legal Document Version anchors Signer Consent",
         "LEGAL_DOCUMENT_VERSION_ANCHORS_SIGNER_CONSENT", "legal evidence"),
    ("signers", "signer_consents", "tenant_id+signer_id"):
        ("Signer is subject of Signer Consent",
         "SIGNER_IS_SUBJECT_OF_SIGNER_CONSENT", "consent subject"),
    ("tenants", "signer_consents", "tenant_id"):
        ("Tenant scopes Signer Consent", "TENANT_SCOPES_SIGNER_CONSENT", "scope"),
    ("users", "signer_consents", "recorded_by"):
        ("User records Signer Consent", "USER_RECORDS_SIGNER_CONSENT", "recorder"),
    ("tenants", "tenant_exports", "tenant_id"):
        ("Tenant scopes Tenant Export", "TENANT_SCOPES_TENANT_EXPORT", "scope"),
    ("legal_documents", "user_consents", "kind+version"):
        ("Legal Document Version anchors User Consent",
         "LEGAL_DOCUMENT_VERSION_ANCHORS_USER_CONSENT", "legal evidence"),
    # Nguoi GHI bang chung khong nhat thiet la nguoi duoc ghi nhan chap thuan.
    ("users", "user_consents", "recorded_by"):
        ("User records User Consent", "USER_RECORDS_USER_CONSENT", "recorder"),
    ("users", "user_consents", "user_id"):
        ("User is subject of User Consent",
         "USER_IS_SUBJECT_OF_USER_CONSENT", "consent subject"),
}

# Nhom A, chot 26/08/2026. Gia tri: (ten, code, nhan).
NHOM_A = {
    ("tenants", "api_keys", "tenant_id"):
        ("Tenant scopes API Key", "TENANT_SCOPES_API_KEY", "scope"),
    # FK la (parent_membership_id, user_id) -> (membership_id, user_id), nen cay
    # membership bi rang phai thuoc CUNG MOT nguoi. Ten dai nhung giu duoc dieu do.
    ("memberships", "memberships", "parent_membership_id+user_id"):
        ("Membership is parent of Membership for Same User",
         "MEMBERSHIP_IS_PARENT_OF_MEMBERSHIP_FOR_SAME_USER", "hierarchy"),
    # Ba cot: tenant-aware VA workspace-aware. Mot membership cap Project khong
    # tro duoc sang project cua workspace khac hay to chuc khac.
    ("projects", "memberships", "tenant_id+workspace_id+project_id"):
        ("Project scopes Membership", "PROJECT_SCOPES_MEMBERSHIP", "scope"),
    ("workspaces", "memberships", "tenant_id+workspace_id"):
        ("Workspace scopes Membership", "WORKSPACE_SCOPES_MEMBERSHIP", "scope"),
    ("projects", "project_allocations", "tenant_id+project_id"):
        ("Project has Project Allocation", "PROJECT_HAS_PROJECT_ALLOCATION", "allocation"),
    ("tenants", "projects", "tenant_id"):
        ("Tenant scopes Project", "TENANT_SCOPES_PROJECT", "scope"),
    ("memberships", "role_assignments", "membership_id+user_id"):
        ("Membership carries Role Assignment", "MEMBERSHIP_CARRIES_ROLE_ASSIGNMENT", "RBAC scope"),
    # Ba vai nghiep vu KHAC NHAU tren cung mot bang. Luoc do tu phan biet chung:
    # user_id NOT NULL/CASCADE, assigned_by NOT NULL/RESTRICT, revoked_by NULL/SET NULL.
    ("users", "role_assignments", "assigned_by_user_id"):
        ("User grants Role through Role Assignment",
         "USER_GRANTS_ROLE_THROUGH_ROLE_ASSIGNMENT", "actor/action"),
    ("users", "role_assignments", "revoked_by_user_id"):
        ("User revokes Role Assignment", "USER_REVOKES_ROLE_ASSIGNMENT", "actor/action"),
    ("users", "role_assignments", "user_id"):
        ("User receives Role Assignment", "USER_RECEIVES_ROLE_ASSIGNMENT", "subject"),
    ("permissions", "role_permissions", "permission_code"):
        ("Permission is granted through Role Permission",
         "PERMISSION_IS_GRANTED_THROUGH_ROLE_PERMISSION", "RBAC"),
    ("roles", "role_permissions", "role_id"):
        ("Role contains Role Permission", "ROLE_CONTAINS_ROLE_PERMISSION", "RBAC"),
    ("users", "roles", "created_by_user_id"):
        ("User creates Role", "USER_CREATES_ROLE", "actor/action"),
    ("tenants", "roles", "tenant_id"):
        ("Tenant scopes Custom Role", "TENANT_SCOPES_CUSTOM_ROLE", "scope"),
    ("tenants", "tenant_invitations", "tenant_id"):
        ("Tenant scopes Tenant Invitation", "TENANT_SCOPES_TENANT_INVITATION", "scope"),
    ("community_versions", "tenants", "cloned_from_community_version"):
        ("Community Version seeds Tenant", "COMMUNITY_VERSION_SEEDS_TENANT", "provenance"),
    ("users", "tenants", "owner_user_id"):
        ("User owns Tenant", "USER_OWNS_TENANT", "ownership"),
    ("plans", "tenants", "plan_code"):
        ("Plan defines Tenant Entitlements", "PLAN_DEFINES_TENANT_ENTITLEMENTS", "entitlement"),
    # CO Y khong dung "belongs to": quan he thanh vien co tham quyen la
    # Membership. Goi cot nay "belongs to" se lam hai co che trong ngang hang.
    ("tenants", "users", "tenant_id"):
        ("Tenant provides Default Context for User",
         "TENANT_PROVIDES_DEFAULT_CONTEXT_FOR_USER", "context"),
    # Chu "Legacy" nam TRONG ten. Khong co no, nguoi doc tuong day la co che
    # phan quyen chinh, trong khi that su la User -> Membership -> Role
    # Assignment -> Role -> Role Permission -> Permission.
    ("roles", "users", "role_id"):
        ("Legacy Role is referenced by User", "LEGACY_ROLE_IS_REFERENCED_BY_USER", "legacy"),
}

# Tên do NGƯỜI chốt. Khoá: (bảng cha, bảng con, cột con) — phải có cột con vì
# `users -> samples` là HAI quan hệ khác nhau (auth_user_id và reviewed_by).
DA_CHOT = {
    ("tenants", "workspaces", "tenant_id"): "Tenant contains Workspace",
    ("workspaces", "projects", "tenant_id+workspace_id"): "Workspace contains Project",
    ("users", "memberships", "user_id"): "User holds Membership",
    ("tenants", "memberships", "tenant_id"): "Tenant scopes Membership",
    ("roles", "role_assignments", "role_id"): "Role is granted through Role Assignment",
    ("tenants", "classes", "tenant_id"): "Tenant owns Class",
    ("dialects", "classes", "tenant_id+dialect"): "Dialect varies Class",
    ("regions", "classes", "region"): "Region localizes Class",
    ("recognition_profiles", "classes", "tenant_id+recognition_profile"): "Recognition Profile profiles Class",
    ("vocabulary_groups", "classes", "tenant_id+vocabulary_group"): "Vocabulary Group groups Class",
    # --- nhom C (Vocabulary), chot 26/08/2026 ---
    ("languages", "classes", "language"): "Language categorizes Class",
    ("dialects", "dialect_aliases", "tenant_id+new_dialect_id"):
        "Dialect is target of Dialect Alias",
    ("tenants", "dialect_aliases", "tenant_id"): "Tenant scopes Dialect Alias",
    # "includes" chu khong "owns": phuong ngu la BIEN THE thuoc mot ngon ngu.
    ("languages", "dialects", "language"): "Language includes Dialect",
    # Huong cua `merged_into`: hang CHA la dich, hang CON la cai bi gop.
    ("dialects", "dialects", "tenant_id+merged_into"):
        "Dialect is merge target of Dialect",
    ("tenants", "dialects", "tenant_id"): "Tenant scopes Dialect",
    ("tenants", "recognition_profiles", "tenant_id"): "Tenant scopes Recognition Profile",
    ("tenants", "registry_versions", "tenant_id"): "Tenant scopes Registry Version",
    ("tenants", "vocabulary_groups", "tenant_id"): "Tenant scopes Vocabulary Group",
    # "maintains": bang nay giu CON TRO registry hien hanh, khong chi thuoc ve.
    ("tenants", "vocabulary_registry_meta", "tenant_id"):
        "Tenant maintains Vocabulary Registry Metadata",
    # "is selected by": `version` co the NULL theo bat bien v7, nen khong ham y
    # moi metadata deu bat buoc co mot phien ban.
    ("registry_versions", "vocabulary_registry_meta", "tenant_id+version"):
        "Registry Version is selected by Vocabulary Registry Metadata",
    # --- nhóm D, chốt 26/08/2026 ---
    # Bốn quan hệ language/dialect là TRỰC TIẾP, không suy qua Class: cả
    # `samples` lẫn `raw_uploads` giữ riêng hai trường ấy kèm khoá ngoại. Vẽ
    # thành `Dialect -> Class -> Sample` sẽ che mất phần phi chuẩn hoá có chủ ý.
    ("dialects", "raw_uploads", "tenant_id+dialect"): "Dialect categorizes Raw Upload",
    ("languages", "raw_uploads", "language"): "Language categorizes Raw Upload",
    ("dialects", "samples", "tenant_id+dialect"): "Dialect categorizes Sample",
    ("languages", "samples", "language"): "Language categorizes Sample",
    # "scopes" chứ không "owns": một alias chỉ có nghĩa trong phạm vi một tổ chức.
    ("tenants", "signer_aliases", "tenant_id"): "Tenant scopes Signer Alias",
    # "corresponds to" chứ không "owns"/"is": `external_user_id` NULL khi người
    # ký không có tài khoản, nên tài khoản và danh tính người ký là HAI khái
    # niệm nối với nhau, không phải một.
    ("users", "signers", "external_user_id"): "User Account corresponds to Signer",
    ("tenants", "signers", "tenant_id"): "Tenant manages Signer",
    ("tenants", "collection_sessions", "tenant_id"): "Tenant owns Collection Session",
    ("collection_sessions", "capture_sessions", "tenant_id+collection_session_id"):
        "Collection Session contains Capture Session",
    ("classes", "capture_sessions", "tenant_id+class_uid"): "Class is captured in Capture Session",
    ("signers", "capture_sessions", "tenant_id+signer_id"):
        "Capture Session references summarized Signer",
    ("tenants", "capture_sessions", "tenant_id"): "Tenant owns Capture Session",
    ("users", "capture_sessions", "auth_user_id"): "User operates Capture Session",
    ("capture_sessions", "samples", "tenant_id+capture_session_id"): "Capture Session contains Sample",
    ("capture_sessions", "samples", "capture_session_id"): "Capture Session contains Sample (legacy key)",
    ("classes", "samples", "tenant_id+class_uid"): "Class labels Sample",
    ("classes", "samples", "class_uid"): "Class labels Sample (legacy key)",
    ("signers", "samples", "tenant_id+signer_id"): "Signer performs Sample",
    ("users", "samples", "auth_user_id"): "User records Sample",
    ("tenants", "samples", "tenant_id"): "Tenant owns Sample",
    ("classes", "raw_uploads", "tenant_id+class_uid"): "Class classifies Raw Upload",
    ("tenants", "raw_uploads", "tenant_id"): "Tenant owns Raw Upload",
    ("users", "raw_uploads", "auth_user_id"): "User uploads Raw Upload",
    ("signers", "signer_aliases", "tenant_id+new_signer_id"): "Signer is target of Signer Alias",
}


def so_it(t):
    """Số nhiều -> số ít cho ĐÚNG tập 62 tên bảng đang có.

    Tiếng Anh không có luật tổng quát, nên đây là luật đủ dùng cho tập này chứ
    không phải một bộ số ít hoá. Hai lỗi đã gặp và cách chặn:

      `rstrip("s")`  ăn cả hai chữ s của `classes` -> "Classe"
      bỏ một "s"     `aliases` -> "aliase"   (đuôi -es sau phụ âm xuýt)

    Luật: bỏ "es" khi phần còn lại kết thúc bằng âm xuýt (s, x, z, ch, sh);
    ngược lại bỏ "s". `aliases` -> `alias` (còn "s": đúng), `roles` -> `rol`
    không còn âm xuýt nên rơi xuống nhánh sau -> `role`.

    Toàn bộ 62 tên được in ra khi chạy, để một lỗi còn sót là thấy được chứ
    không nằm im trong một bảng 131 dòng.
    """
    if t.endswith("ies"):
        return t[:-3] + "y"
    if t.endswith("es"):
        goc = t[:-2]
        if goc.endswith(("s", "x", "z", "ch", "sh")):
            return goc
    if t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


#: Tu viet tat giu nguyen chu hoa. Day la chuan hoa TRINH BAY — no khong suy ra
#: y nghia nao, chi sua cach hien thi — nen dat trong generator la dung cho.
VIET_TAT = {"api": "API", "totp": "TOTP", "sot": "SOT", "vsl": "VSL",
            "pdm": "PDM", "uid": "UID", "url": "URL", "id": "ID",
            "csv": "CSV", "otp": "OTP", "sms": "SMS", "ttl": "TTL"}


def tach(s):
    tu = []
    for w in so_it(s).split("_"):
        tu.append(VIET_TAT.get(w.lower(), w.capitalize()))
    return " ".join(tu) or s


ra = []
for r in fks:
    con, cha, cot = r["child_table"], r["parent_table"], r["child_cols"]
    ghep = int(r["n_cols"]) > 1
    rieng = [c for c in cot.split("+") if c != "tenant_id"] or [cot]
    khoa = rieng[0]

    # Thu tu tra: ten rang buoc (hep nhat) -> nhom A -> DA_CHOT chung.
    bo = (THEO_CONSTRAINT.get(r["conname"]) or NHOM_A.get((cha, con, cot))
          or NHOM_E.get((cha, con, cot))
          or NHOM_H.get((cha, con, cot))
          or NHOM_F.get((cha, con, cot))
          or NHOM_B.get((cha, con, cot))
          or NHOM_G.get((cha, con, cot)))
    if bo:
        ten, ma_chot, nhan = bo
    else:
        ten, ma_chot, nhan = DA_CHOT.get((cha, con, cot)), None, ""

    if khoa in LOAI_A:
        loai, v1, v2 = "A", *LOAI_A[khoa]
        ten = ten or "%s %s %s" % (tach(cha), v1, tach(con))
    else:
        loai = "C" if ghep else "B"
        v1 = v2 = ""
        ten = ten or ""

    ma = ma_chot or (re.sub(r"[^A-Z0-9]+", "_", ten.upper()).strip("_") if ten
                     else re.sub(r"[^A-Z0-9]+", "_",
                                 ("%s__%s__%s" % (cha, con, cot)).upper()).strip("_"))
    ra.append({**r, "nhom": NHOM.get(con, "?"), "ten": ten, "ma": ma, "loai": loai,
               "v1": v1, "v2": v2, "ghep": ghep, "da_chot": bool(ten), "nhan": nhan})

o = []
w = o.append
w("# Bảng vẽ ERD theo nhóm A–H\n")
w("Sinh từ catalog `signdb` v8 ngày 26/08/2026. **Entity, cột khoá ngoại,")
w("cardinality, ON DELETE là dữ liệu hệ thống.** Tên quan hệ thì không —")
w("đặt tên là việc mô hình hoá.\n")
w("## Ba loại nguồn tên\n")
w("| Loại | Nghĩa | Có tên tự động không |")
w("|---|---|---|")
w("| **A** | Tên cột TỰ CHỨA động từ: `created_by`, `reviewed_by`, `opened_by_user_id`… | có — tên cột là dữ liệu |")
w("| **B** | Tham chiếu/sở hữu cấu trúc: `tenant_id`, `user_id`, `class_uid`, `language`… | **không** |")
w("| **C** | Quan hệ miền qua khoá GHÉP `(tenant_id, …)` | **không** |")
w("")
w("Bản trước xếp `tenant_id` → *owns* và `auth_user_id` → *operates* vào loại A.")
w("Sai: hai cột đó không chứa động từ nào; đó là suy diễn ngữ nghĩa của công cụ.")
w("Loại B và C chỉ có tên khi người duyệt đã chốt — cột **Đã chốt** đánh dấu.\n")
dem = collections.Counter(x["loai"] for x in ra)
n_chot = sum(1 for x in ra if x["da_chot"])
n_co_ten = sum(1 for x in ra if x["ten"])
w("| | số |")
w("|---|---:|")
w("| tổng quan hệ | %d |" % len(ra))
w("| loại A (tên cột có động từ) | %d |" % dem["A"])
w("| loại B (tham chiếu cấu trúc) | %d |" % dem["B"])
w("| loại C (khoá ghép) | %d |" % dem["C"])
w("| **đã có tên** | **%d** |" % n_co_ten)
w("| **còn phải đặt tay** | **%d** |" % (len(ra) - n_co_ten))
w("")
for k in "ABCDEFGH":
    rs = [x for x in ra if x["nhom"] == k]
    if not rs:
        continue
    con_lai = sum(1 for x in rs if not x["ten"])
    w("## %s. %s — %d quan hệ, còn %d phải đặt tay\n" % (k, TEN[k], len(rs), con_lai))
    w("| Entity 1 (cha) | Entity 2 (con) | Relationship Name | Code | Cột khoá ngoại | Ghép | Cardinality | ON DELETE | Nhãn | Loại |")
    w("|---|---|---|---|---|:--:|---|---|---|:--:|")
    for x in sorted(rs, key=lambda y: (y["child_table"], y["conname"])):
        ten = x["ten"] if x["ten"] else "_(chưa đặt)_"
        cot = "`%s` → `%s`" % (x["child_cols"].replace("+", ", "),
                               x["parent_cols"].replace("+", ", "))
        w("| `%s` | `%s` | %s | `%s` | %s | %s | %s — %s | %s | %s | %s |" % (
            x["parent_table"], x["child_table"], ten, x["ma"], cot,
            "✓" if x["ghep"] else "—", x["parent_card"], x["child_card"],
            x["on_delete"], x.get("nhan") or "—", x["loai"]))
    w("")

pathlib.Path("PDM_V8_RELATIONSHIPS.md").write_text("\n".join(o), encoding="utf-8")
with open("rel.csv", "w", newline="", encoding="utf-8") as f:
    wr = csv.writer(f)
    wr.writerow(["group", "entity1_parent", "entity2_child", "relationship_name", "code", "label",
                 "child_cols", "parent_cols", "is_composite", "parent_card", "child_card",
                 "on_delete", "verb1", "verb2", "name_class", "human_confirmed",
                 "constraint_name"])
    for x in ra:
        wr.writerow([x["nhom"], x["parent_table"], x["child_table"], x["ten"], x["ma"], x.get("nhan", ""),
                     x["child_cols"], x["parent_cols"], "Y" if x["ghep"] else "N",
                     x["parent_card"], x["child_card"], x["on_delete"], x["v1"], x["v2"],
                     x["loai"], "Y" if x["da_chot"] else "N", x["conname"]])

bang = sorted({x["child_table"] for x in ra} | {x["parent_table"] for x in ra})
print("--- so it hoa %d ten bang ---" % len(bang))
for i in range(0, len(bang), 3):
    print("   " + " | ".join("%-22s -> %-20s" % (b, tach(b)) for b in bang[i:i+3]))
print()
print("tong %d | A=%d B=%d C=%d | da co ten %d | con phai dat tay %d"
      % (len(ra), dem["A"], dem["B"], dem["C"], n_co_ten, len(ra) - n_co_ten))
d = [x for x in ra if x["nhom"] == "D" and not x["ten"]]
print("nhom D con thieu ten: %d" % len(d))
for x in d:
    print("   %s -> %s (%s)" % (x["parent_table"], x["child_table"], x["child_cols"]))

"""Xoá vĩnh viễn các tài khoản THỬ NGHIỆM và tổ chức tự tạo của chúng.

Chủ dự án yêu cầu 15/09/2026: Minh123, Minh1234, minh12345, "Minh Huy".
Không hoàn tác được — chạy dump trước (scripts/pg_backup hoặc pg_dump).

Chạy TRONG container backend (có `app`, DSN, và hệ tệp dataset):

    docker cp scripts/xoa_tai_khoan_thu.py voya_backend:/tmp/x.py
    docker exec -e MSYS_NO_PATHCONV=1 voya_backend python /tmp/x.py            # xem trước
    docker exec -e MSYS_NO_PATHCONV=1 voya_backend python /tmp/x.py --apply    # xoá thật

Thứ tự (vì khoá ngoại):
  1. XOÁ MỀM tổ chức tự tạo của họ (`tenant_admin.delete_tenant`). Xoá vĩnh
     viễn bị lifecycle giữ 30 ngày ân hạn — cố ý, không lách; sau mốc đó bấm
     "Xoá vĩnh viễn" ở trang quản trị tổ chức.
  2. Gỡ các tham chiếu KHÔNG cascade (mẫu, phiên thu, phiếu hỗ trợ, nhật ký...):
     đặt NULL — dữ liệu ở lại, chỉ mất người đứng tên.
  3. Xoá `role_assignments` (RESTRICT trên assigned_by) rồi `DELETE FROM users`;
     phần còn lại (membership, consent, token...) cascade theo lược đồ.
"""
import sys

sys.path.insert(0, "/app")
from app.storage.metadata_db import _execute, _fetch_all  # noqa: E402
from app.tenant_context import system_scope  # noqa: E402

USERNAMES = ["Minh123", "Minh1234", "minh12345", "Minh Huy"]
APPLY = "--apply" in sys.argv
ADMIN_ID = "eeeaeb8b-a832-4d1d-bac7-ebdd819fc644"  # Minh (admin) — người đứng tên lệnh purge

NULLIFY = [  # (bảng, cột) — FK sang users không cascade
    ("samples", "auth_user_id"), ("samples", "reviewed_by"),
    ("raw_uploads", "auth_user_id"), ("capture_sessions", "auth_user_id"),
    ("training_jobs", "auth_user_id"), ("collection_sessions", "opened_by_user_id"),
    ("support_tickets", "user_id"), ("support_messages", "author_id"),
    ("audit_log", "actor_user_id"), ("signers", "external_user_id"),
    ("signer_consents", "recorded_by"), ("user_consents", "recorded_by"),
    ("tenant_invitations", "invited_by"), ("tenant_invitations", "accepted_by"),
    ("tenant_subscriptions", "changed_by"), ("registry_versions", "created_by"),
    ("community_versions", "created_by"), ("community_dialects", "updated_by"),
    ("community_profiles", "updated_by"), ("dialects", "created_by"), ("dialects", "approved_by"),
    ("dialect_aliases", "merged_by"), ("signer_aliases", "merged_by"),
    ("api_keys", "created_by"), ("api_keys", "revoked_by"), ("roles", "created_by_user_id"),
    ("role_assignments", "revoked_by_user_id"), ("tenants", "owner_user_id"),
    ("tenant_exports", "requested_by"), ("webhook_endpoints", "created_by"),
    ("legal_documents", "published_by"), ("legal_document_drafts", "created_by"),
    ("legal_document_drafts", "updated_by"), ("platform_settings", "updated_by"),
    ("project_allocations", "updated_by"),
]

with system_scope("xoa tai khoan thu nghiem"):
    users = _fetch_all(
        "SELECT id::text AS id, username, tenant_id FROM users WHERE username = ANY(%s)", (USERNAMES,))
    print("Tài khoản:", [(u["username"], u["tenant_id"]) for u in users])
    ids = [u["id"] for u in users]
    tenants = _fetch_all(
        "SELECT tenant_id, is_self_serve FROM tenants WHERE owner_user_id::text = ANY(%s) AND tenant_id <> 'default'",
        (ids,))
    print("Tổ chức tự tạo sẽ xoá:", [t["tenant_id"] for t in tenants if t["is_self_serve"]])
    for table, col in NULLIFY:
        n = _fetch_all(f"SELECT count(*) AS n FROM {table} WHERE {col}::text = ANY(%s)", (ids,))
        if n and n[0]["n"]:
            print(f"  gỡ tham chiếu {table}.{col}: {n[0]['n']} dòng")

if not APPLY:
    print("(xem trước; thêm --apply để xoá)")
    sys.exit(0)

from app import tenant_admin as ta  # noqa: E402

# Tổ chức thử: XOÁ MỀM (mất chủ, không đăng nhập vào được). Xoá vĩnh viễn phải
# chờ hết ân hạn 30 ngày của lifecycle (mốc in ra bên dưới) — lúc đó bấm "Xoá
# vĩnh viễn" ở trang quản trị tổ chức, hoặc gọi tenant_lifecycle.purge_tenant.
for t in tenants:
    if not t["is_self_serve"]:
        continue
    with system_scope("xoa tai khoan thu nghiem: xoa mem to chuc"):
        row = _fetch_all("SELECT deleted_at FROM tenants WHERE tenant_id = %s", (t["tenant_id"],))
    if row and not row[0]["deleted_at"]:
        ta.delete_tenant(t["tenant_id"])
        print("đã xoá mềm tổ chức", t["tenant_id"])
    else:
        print("tổ chức đã xoá mềm từ trước:", t["tenant_id"])
    from app.tenant_lifecycle import purge_preview
    print("   xoá vĩnh viễn được từ:", (purge_preview(t["tenant_id"]).get("blockers") or ["ngay bây giờ"])[0])

with system_scope("xoa tai khoan thu nghiem: go tham chieu va xoa"):
    for table, col in NULLIFY:
        _execute(f"UPDATE {table} SET {col} = NULL WHERE {col}::text = ANY(%s)", (ids,))
    _execute("DELETE FROM role_assignments WHERE user_id::text = ANY(%s) OR assigned_by_user_id::text = ANY(%s)", (ids, ids))
    _execute("DELETE FROM users WHERE id::text = ANY(%s)", (ids,))
    left = _fetch_all("SELECT count(*) AS n FROM users WHERE username = ANY(%s)", (USERNAMES,))
    print("còn lại:", left[0]["n"], "— XONG")

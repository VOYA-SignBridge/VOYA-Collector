#!/usr/bin/env python3
"""Sinh ERD ĐÚNG CHUẨN cho draw.io, đọc thẳng từ cơ sở dữ liệu đang chạy.

Hai ký pháp, hai mục đích khác nhau
------------------------------------
**Chen** (trang 1) — mức KHÁI NIỆM. Thực thể là hình chữ nhật, quan hệ là hình
thoi có TÊN, thuộc tính là hình elip, khoá chính gạch chân, lực lượng ghi 1/N/M
trên cạnh. Đây là ký pháp các giáo trình CSDL tiếng Việt dạy, và là thứ một
chương "Phân tích thiết kế" của luận văn cần.

**Chân chim / IE** (trang 2–4) — mức LOGIC và VẬT LÝ. Thực thể là bảng thuộc
tính, lực lượng vẽ ở CẢ HAI đầu bằng ký hiệu chân chim. Đây là ký pháp dùng để
làm việc, và là thứ khớp một-một với lược đồ thật.

Vì sao mô hình khái niệm KHÔNG sinh tự động được
--------------------------------------------------
Mức khái niệm là một **diễn giải**, không phải một sự kiện của cơ sở dữ liệu.
Không truy vấn nào cho biết `recognition_profile` là "thuộc tính phân loại của
lớp" còn `dialect` là "một thực thể riêng" — cả hai đều là khoá ngoại như nhau.
Chọn cái nào lên mô hình khái niệm là việc của người thiết kế.

Nên mô hình khái niệm ở đây được VIẾT TAY (xem `CONCEPTUAL_*`), và bù lại nó
được **máy kiểm chứng**: mỗi quan hệ khai báo kèm khoá ngoại thật của nó, và bộ
sinh DỪNG với lỗi nếu khoá đó không tồn tại trong CSDL. Một mô hình khái niệm vẽ
tay thường sai lặng lẽ khi lược đồ đổi; cái này không sai lặng lẽ được.

Những gì mức khái niệm CỐ Ý bỏ, và vì sao
-------------------------------------------
13 thực thể trên tổng số 44 bảng. Bị bỏ:

* **Bảng kỹ thuật** — `refresh_tokens`, `verification_codes`, `audit_log`,
  `google_sheets_sync_status`, `tenant_usage_daily`… Chúng là cơ chế, không phải
  khái niệm nghiệp vụ.
* **`recognition_profiles`, `vocabulary_groups`** — ở mức khái niệm chúng là
  thuộc tính phân loại của LỚP. `dialects` được giữ vì phương ngữ đi theo cả
  MẪU chứ không chỉ theo lớp.
* **`capture_sessions`** — một cách gom mẫu, không phải một khái niệm độc lập.
* **`samples.auth_user_id`** (ai tải lên) — ở mức khái niệm, mẫu do NGƯỜI KÝ
  tạo ra trong một TỔ CHỨC; tài khoản nào bấm nút là siêu dữ liệu xuất xứ. Sự
  thật đo được ủng hộ cách nhìn này: 166 mẫu có cột đó rỗng.
* **21 khoá ngoại `tenant_id` còn lại** — mẫu hình y hệt 4 quan hệ "sở hữu" đã
  vẽ. Vẽ đủ 25 hình thoi thì hình vẽ không đọc được mà không nói thêm được gì.

Mọi thứ bị bỏ đều CÓ MẶT ĐẦY ĐỦ trên trang 2 (ERD logic). Đó là lý do có hai
trang chứ không phải một.

Cách chạy
---------
    python docs/02-data/db/gen_erd.py                 # ghi docs/02-data/db/voya_erd.drawio
    python docs/02-data/db/gen_erd.py --sql           # kèm DDL cho đường nhập SQL
    python docs/02-data/db/gen_erd.py --stats         # chỉ in số liệu lược đồ
    python docs/02-data/db/gen_erd.py --dsn postgres://…   # không cần Docker
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from xml.sax.saxutils import escape

# =========================================================================== SQL

Q_TABLES = """
SELECT c.relname, c.relrowsecurity,
       (xpath('/row/cnt/text()',
              query_to_xml(format('SELECT count(*) AS cnt FROM public.%I', c.relname),
                           false, true, '')))[1]::text::bigint
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'r'
ORDER BY c.relname
"""

Q_COLUMNS = """
SELECT c.table_name, c.column_name,
       CASE c.data_type
         WHEN 'character varying' THEN 'varchar'
         WHEN 'timestamp with time zone' THEN 'timestamptz'
         WHEN 'double precision' THEN 'float8'
         WHEN 'character' THEN 'char'
         ELSE c.data_type END,
       (c.is_nullable = 'NO')
FROM information_schema.columns c
JOIN pg_class pc ON pc.relname = c.table_name
JOIN pg_namespace pn ON pn.oid = pc.relnamespace AND pn.nspname = 'public'
WHERE c.table_schema = 'public' AND pc.relkind = 'r'
ORDER BY c.table_name, c.ordinal_position
"""

Q_CONSTRAINTS = """
SELECT conrelid::regclass::text, contype, pg_get_constraintdef(oid)
FROM pg_constraint
WHERE connamespace = 'public'::regnamespace AND contype IN ('p', 'u', 'f')
ORDER BY conrelid::regclass::text, conname
"""


def _psql(sql: str, container: str, user: str, db: str) -> List[List[str]]:
    """Chạy truy vấn qua `docker exec`, phân tách bằng ký tự đơn vị (0x1f).

    Không dùng `|`: `pg_get_constraintdef` trả về văn bản có thể chứa dấu đó, và
    một dấu phân tách nằm trong dữ liệu sẽ làm lệch cột mà không báo lỗi.
    """
    cmd = ["docker", "exec", container, "psql", "-U", user, "-d", db,
           "-t", "-A", "-F", "\x1f", "-c", sql]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if out.returncode != 0:
        raise SystemExit(f"psql thất bại:\n{out.stderr.strip()}")
    return [ln.split("\x1f") for ln in out.stdout.splitlines() if ln.strip()]


def _psycopg(sql: str, dsn: str) -> List[List[str]]:
    import psycopg2

    with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(sql)
        return [["" if v is None else str(v) for v in r] for r in cur.fetchall()]


def _truthy(v: str) -> bool:
    return v in ("t", "true", "True", "1")


# =========================================================================== mô hình


class Schema:
    """Lược đồ đã đọc, cộng những suy luận mà một ERD cần.

    Ba đại lượng dưới đây là toàn bộ phần "hiểu" của bộ sinh, và cả ba đều suy
    ra được từ lược đồ chứ không phải khai báo tay:

    * **thực thể yếu** — khoá chính có chứa một cột khoá ngoại. Nghĩa là hàng
      con không tự định danh được nếu thiếu cha. `dialects(tenant_id,
      dialect_id)` là ví dụ: `dialect_id` chỉ duy nhất TRONG một tenant.
    * **thực thể kết hợp** — khoá chính gồm TOÀN khoá ngoại của ≥2 bảng cha.
      Đó là hiện thân của một quan hệ nhiều-nhiều. Ở đây chỉ có `tenant_members`.
    * **quan hệ định danh** — khoá ngoại nằm trong khoá chính của bảng con. Vẽ
      nét liền; không định danh thì vẽ nét đứt. Đây là quy ước IE, không phải
      lựa chọn thẩm mỹ.
    """

    def __init__(self, rows_tables, rows_columns, rows_constraints):
        self.tables: Dict[str, Dict[str, Any]] = {
            r[0]: {"rls": _truthy(r[1]), "rows": int(r[2] or 0)} for r in rows_tables}

        self.columns: Dict[str, List[Tuple[str, str, bool]]] = {}
        for t, col, typ, notnull in rows_columns:
            self.columns.setdefault(t, []).append((col, typ, _truthy(notnull)))

        self.pk: Dict[str, List[str]] = {}
        self.unique: Dict[str, List[Tuple[str, ...]]] = {}
        self.fks: List[Dict[str, Any]] = []
        self._parse_constraints(rows_constraints)

        self.notnull = {(t, c): nn for t, cols in self.columns.items()
                        for c, _typ, nn in cols}

    def _parse_constraints(self, rows) -> None:
        for table, contype, definition in rows:
            table = table.strip('"')
            if contype == "p":
                inner = definition[definition.index("(") + 1: definition.rindex(")")]
                self.pk[table] = [c.strip() for c in inner.split(",")]
            elif contype == "u":
                inner = definition[definition.index("(") + 1: definition.index(")")]
                self.unique.setdefault(table, []).append(
                    tuple(c.strip() for c in inner.split(",")))
            elif contype == "f":
                head, _, tail = definition.partition(" REFERENCES ")
                cols = [c.strip() for c in
                        head[head.index("(") + 1: head.rindex(")")].split(",")]
                ref_table = tail[: tail.index("(")].strip().strip('"')
                ref_cols = [c.strip() for c in
                            tail[tail.index("(") + 1: tail.index(")")].split(",")]
                self.fks.append({
                    "table": table, "columns": cols,
                    "ref_table": ref_table, "ref_columns": ref_cols,
                    "composite": len(cols) > 1,
                    "on_delete": ("CASCADE" if "ON DELETE CASCADE" in definition
                                  else "SET NULL" if "ON DELETE SET NULL" in definition
                                  else "RESTRICT" if "ON DELETE RESTRICT" in definition
                                  else ""),
                    # Cột NEO cạnh. Với khoá ghép `(tenant_id, x)` thì neo vào `x`:
                    # neo vào `tenant_id` sẽ khiến mọi cạnh của bảng chụm vào một
                    # dòng và hình vẽ không đọc được.
                    "anchor": next((c for c in cols if c != "tenant_id"), cols[0]),
                })

    # ---------------------------------------------------------------- suy luận

    def fks_of(self, table: str) -> List[Dict[str, Any]]:
        return [f for f in self.fks if f["table"] == table]

    def fk_columns(self, table: str) -> set:
        return {c for f in self.fks_of(table) for c in f["columns"]}

    def is_identifying(self, fk: Dict[str, Any]) -> bool:
        """Khoá ngoại có nằm trong khoá chính của bảng con không."""
        return set(fk["columns"]) <= set(self.pk.get(fk["table"], []))

    def is_unique(self, table: str, cols: Sequence[str]) -> bool:
        """Bộ cột này có bị một ràng buộc duy nhất phủ không → quan hệ 1:1."""
        want = tuple(cols)
        if tuple(self.pk.get(table, [])) == want:
            return True
        return any(u == want for u in self.unique.get(table, []))

    def entity_kind(self, table: str) -> str:
        """'strong' · 'weak' · 'associative'."""
        pk = set(self.pk.get(table, []))
        if not pk:
            return "strong"
        fk_in_pk = {c for f in self.fks_of(table) for c in f["columns"] if c in pk}
        if not fk_in_pk:
            return "strong"
        parents = {f["ref_table"] for f in self.fks_of(table)
                   if set(f["columns"]) <= pk}
        if pk <= fk_in_pk and len(parents) >= 2:
            return "associative"
        return "weak"

    def cardinality(self, fk: Dict[str, Any]) -> Tuple[str, str]:
        """(đầu con, đầu cha) theo ký hiệu chân chim của draw.io.

        Đầu **cha** đọc được chắc chắn từ lược đồ: khoá ngoại NOT NULL nghĩa là
        *đúng một* (`ERmandOne`); cho phép NULL nghĩa là *không hoặc một*
        (`ERzeroToOne`).

        Đầu **con** thì lược đồ chỉ nói được cận trên. Một hàng cha luôn có thể
        chưa có con nào, nên mặc định là *không hoặc nhiều* (`ERzeroToMany`) —
        KHÔNG phải `ERoneToMany`. Viết "một hoặc nhiều" ở đây là khẳng định một
        ràng buộc mà cơ sở dữ liệu không hề ép, tức là vẽ sai.

        Ngoại lệ duy nhất: nếu bộ cột khoá ngoại bị một ràng buộc duy nhất phủ
        thì quan hệ là 1:1 và đầu con thành `ERzeroToOne`.
        """
        all_notnull = all(self.notnull.get((fk["table"], c), False)
                          for c in fk["columns"])
        parent_end = "ERmandOne" if all_notnull else "ERzeroToOne"
        child_end = ("ERzeroToOne" if self.is_unique(fk["table"], fk["columns"])
                     else "ERzeroToMany")
        return child_end, parent_end


#: Động từ đặt tên quan hệ, tra theo tên cột khoá ngoại.
#:
#: Một ERD không có tên quan hệ thì chỉ là bản đồ khoá ngoại. Tên phải là ĐỘNG
#: TỪ đọc được theo chiều con → cha ("mẫu **thuộc lớp** lớp").
RELATION_VERBS: Dict[str, str] = {
    "tenant_id": "belongs to",
    "plan_code": "subscribes to",
    "user_id": "of",
    "auth_user_id": "collected by",
    "actor_user_id": "acted by",
    "owner_user_id": "owned by",
    "external_user_id": "maps to",
    "created_by": "created by",
    "updated_by": "updated by",
    "approved_by": "approved by",
    "published_by": "published by",
    "recorded_by": "recorded by",
    "merged_by": "merged by",
    "revoked_by": "revoked by",
    "requested_by": "requested by",
    "invited_by": "invited by",
    "accepted_by": "accepted by",
    "changed_by": "changed by",
    "class_uid": "classified as",
    "signer_id": "performed by",
    "dialect": "in dialect",
    "language": "in language",
    "recognition_profile": "uses profile",
    "vocabulary_group": "in group",
    "merged_into": "merged into",
    "new_dialect_id": "redirects to",
    "new_signer_id": "redirects to",
    "capture_session_id": "in session",
    "job_id": "of training job",
    "registry_version": "pins version",
    "endpoint_id": "delivered to",
    "role_id": "holds role",
    "kind": "bound to",
    "cloned_from_community_version": "cloned from",
}


def relation_name(fk: Dict[str, Any]) -> str:
    """Tên quan hệ, đọc theo chiều con → cha."""
    return RELATION_VERBS.get(fk["anchor"], "references")


# =========================================================================== mặt phẳng

PLANES: "OrderedDict[str, Dict[str, Any]]" = OrderedDict([
    # ---- MODULE A — Tenant and Authorization (18 bảng) ----------------------
    ("tenancy", {"label": "CORE — Tenant, Workspace, Project",
                 "color": "#0B4DA2", "fill": "#E7EEF9", "module": "A",
                 "tables": ["tenants", "workspaces", "projects",
                            "project_allocations"]}),
    ("authz", {"label": "SCOPED AUTHORIZATION", "color": "#1F4E9C",
               "fill": "#E3EBF7", "module": "A",
               "tables": ["memberships", "roles", "permissions",
                          "role_permissions", "role_assignments",
                          "tenant_invitations"]}),
    ("identity", {"label": "IDENTITY AND ACCESS", "color": "#6B4FA8",
                  "fill": "#EFEAF8", "module": "A",
                  "tables": ["users", "refresh_tokens", "password_reset_tokens",
                             "verification_codes", "user_totp",
                             "user_recovery_codes", "user_action_passcodes",
                             "api_keys"]}),

    # ---- MODULE B — Vocabulary and Registry (11 bảng) -----------------------
    ("catalogue", {"label": "PLATFORM CATALOGUE", "color": "#2F6E5A",
                   "fill": "#E6F1EC", "module": "B",
                   "tables": ["languages", "regions"]}),
    ("vocab", {"label": "VOCABULARY AND REGISTRY (tenant-scoped)", "color": "#0E6E7A",
               "fill": "#E2F1F3", "module": "B",
               "tables": ["dialects", "dialect_aliases", "recognition_profiles",
                          "vocabulary_groups", "vocabulary_registry_meta",
                          "registry_versions"]}),
    # Ba bảng `community_*` là DANH MỤC HỆ THỐNG, không phải mặt phẳng Cộng
    # đồng. Cộng đồng là một HÀNG của `tenants` (`tenant_type='COMMUNITY'`).
    # Nhãn ở đây phải nói đúng điều đó, vì tên bảng là di sản và gây hiểu nhầm.
    ("syscat", {"label": "SYSTEM CATALOGUE (community_* table names are legacy)",
                "color": "#7A6410", "fill": "#F5F0DC", "module": "B",
                "tables": ["community_dialects", "community_profiles",
                           "community_versions"]}),

    # ---- MODULE C — Collection and Sample (9 bảng) --------------------------
    ("corpus", {"label": "CORPUS — Collected data", "color": "#1B6E4A",
                "fill": "#E4F1EA", "module": "C",
                "tables": ["samples", "classes", "raw_uploads",
                           "capture_sessions", "signers", "signer_aliases"]}),
    ("training", {"label": "TRAINING (downstream)", "color": "#8A4B12",
                  "fill": "#F7EBE0", "module": "C",
                  "tables": ["training_jobs", "training_job_classes",
                             "training_metrics"]}),

    # ---- MODULE D — Governance and Platform (21 bảng) -----------------------
    ("legal", {"label": "LEGAL, CONSENT AND AUDIT", "color": "#8E1F5E",
               "fill": "#F7E5EF", "module": "D",
               "tables": ["legal_documents", "legal_document_drafts",
                          "legal_document_events", "user_consents",
                          "signer_consents", "audit_log"]}),
    ("commerce", {"label": "TENANT SERVICES AND INTEGRATION", "color": "#A3311F",
                  "fill": "#F8E7E3", "module": "D",
                  "tables": ["plans", "tenant_subscriptions", "tenant_usage_daily",
                             "tenant_exports", "tenant_purges",
                             "webhook_endpoints", "webhook_deliveries",
                             "support_tickets", "support_messages",
                             "notifications", "event_outbox"]}),
    ("platform", {"label": "PLATFORM AND INFRASTRUCTURE", "color": "#4A5560",
                  "fill": "#ECEEF1", "module": "D",
                  "tables": ["platform_settings", "sot_authorized_keys",
                             "schema_migrations", "google_sheets_sync_status"]}),
])

#: Bốn mô-đun của Chương 3 §3.4.2, mỗi mô-đun một trang PDM (Figure 3.15–3.18).
#: Thứ tự khoá trong PLANES quyết định thứ tự khối trên trang.
MODULES: "OrderedDict[str, str]" = OrderedDict([
    ("A", "Module A: Tenant and Authorization"),
    ("B", "Module B: Vocabulary and Registry"),
    ("C", "Module C: Collection and Sample"),
    ("D", "Module D: Governance and Platform"),
])


def planes_of_module(module: str) -> List[str]:
    return [k for k, p in PLANES.items() if p.get("module") == module]


PLANE_OF: Dict[str, str] = {t: k for k, p in PLANES.items() for t in p["tables"]}


def color_of(table: str) -> Tuple[str, str]:
    p = PLANES.get(PLANE_OF.get(table, ""), None)
    return (p["color"], p["fill"]) if p else ("#4A5560", "#ECEEF1")


# =========================================================================== Chen

#: Thực thể của mô hình khái niệm: tên bảng -> (nhãn, cột toạ độ, hàng toạ độ,
#: danh sách thuộc tính hiển thị). Thuộc tính đầu tiên là khoá — nó được gạch
#: chân theo đúng quy ước Chen.
CONCEPTUAL_ENTITIES: "OrderedDict[str, Dict[str, Any]]" = OrderedDict([
    # Hàng 0 — danh mục nền tảng
    ("plans",             {"label": "SERVICE PLAN", "i": 3, "j": 0,
                           "attrs": ["plan_code", "display_name", "price_cents"]}),

    # Hàng 2 — hai gốc: tổ chức và tài khoản
    ("tenants",           {"label": "TENANT", "i": 3, "j": 2,
                           "attrs": ["tenant_id", "display_name", "billing_status"]}),
    ("users",             {"label": "USER", "i": 11, "j": 2,
                           "attrs": ["id", "username", "email"]}),

    # Hàng 4 — thực thể thuộc tổ chức, trải đều để cạnh từ TENANT không chồng
    ("dialects",          {"label": "DIALECT", "i": 0, "j": 4,
                           "attrs": ["dialect_id", "display_name", "is_alphabet"]}),
    ("classes",           {"label": "SIGN CLASS", "i": 3, "j": 4,
                           "attrs": ["class_uid", "label_original", "hands_required"]}),
    ("signers",           {"label": "SIGNER", "i": 6, "j": 4,
                           "attrs": ["signer_id", "display_name", "regional_group"]}),
    ("registry_versions", {"label": "REGISTRY\nVERSION", "i": 9, "j": 4,
                           "attrs": ["version", "content_hash"]}),
    ("user_consents",     {"label": "USER\nCONSENT", "i": 11, "j": 4,
                           "attrs": ["consent_id", "accepted_at", "withdrawn_at"]}),

    # Hàng 6 — lượt huấn luyện nằm giữa REGISTRY VERSION và USER
    ("training_jobs",     {"label": "TRAINING\nJOB", "i": 9, "j": 6,
                           "attrs": ["job_id", "status", "test_acc"]}),

    # Hàng 8 — dữ liệu thu được và bằng chứng pháp lý
    ("raw_uploads",       {"label": "RAW\nUPLOAD", "i": 0, "j": 8,
                           "attrs": ["upload_uid", "original_filename", "status"]}),
    ("samples",           {"label": "SAMPLE", "i": 3, "j": 8,
                           "attrs": ["sample_uid", "file_path", "completeness"]}),
    ("signer_consents",   {"label": "SIGNER\nCONSENT", "i": 6, "j": 8,
                           "attrs": ["consent_id", "scope", "withdrawn_at"]}),
    ("legal_documents",   {"label": "LEGAL\nDOCUMENT", "i": 11, "j": 8,
                           "attrs": ["kind", "version", "content_hash"]}),
])

#: Quan hệ của mô hình khái niệm.
#:
#: `via` là (bảng con, cột khoá ngoại) — nó KHÔNG dùng để vẽ, nó dùng để **kiểm
#: chứng**: bộ sinh dừng với lỗi nếu khoá ngoại đó không có thật. Đó là thứ giữ
#: cho một hình vẽ tay không âm thầm nói sai khi lược đồ đổi.
CONCEPTUAL_RELATIONS: Tuple[Dict[str, Any], ...] = (
    # --- gốc: gói dịch vụ và tư cách thành viên ---------------------------
    {"name": "SUBSCRIBES TO", "i": 3, "j": 1, "a": "tenants", "b": "plans",
     "ca": "N", "cb": "1", "via": ("tenants", "plan_code")},

    # `tenant_members` là KHUNG NHÌN trên lát cắt `scope_level='TENANT'` của
    # `memberships`; khung nhìn không mang khoá ngoại, nên quan hệ phải khai qua
    # bảng gốc. Khai qua khung nhìn là lỗi đã làm bộ sinh dừng ở lần chạy 18/08.
    {"name": "PARTICIPATES IN", "i": 7, "j": 2, "a": "users", "b": "tenants",
     "ca": "M", "cb": "N", "via": ("memberships", "user_id"),
     "attrs": ["scope_level"], "assoc": True},

    # --- TENANT sở hữu bốn nhóm tài nguyên, mỗi cạnh một cột riêng --------
    {"name": "OWNS", "i": 0, "j": 3, "a": "tenants", "b": "dialects",
     "ca": "1", "cb": "N", "via": ("dialects", "tenant_id"), "identifying": True},
    {"name": "OWNS", "i": 3, "j": 3, "a": "tenants", "b": "classes",
     "ca": "1", "cb": "N", "via": ("classes", "tenant_id")},
    {"name": "OWNS", "i": 6, "j": 3, "a": "tenants", "b": "signers",
     "ca": "1", "cb": "N", "via": ("signers", "tenant_id")},
    {"name": "PUBLISHES", "i": 9, "j": 3, "a": "tenants", "b": "registry_versions",
     "ca": "1", "cb": "N", "via": ("registry_versions", "tenant_id"),
     "identifying": True},

    # --- USER và bằng chứng chấp thuận -----------------------------------
    {"name": "ACCEPTS", "i": 11, "j": 3, "a": "users", "b": "user_consents",
     "ca": "1", "cb": "N", "via": ("user_consents", "user_id")},

    # --- từ vựng ---------------------------------------------------------
    {"name": "CLASSIFIES", "i": 1.5, "j": 4, "a": "dialects", "b": "classes",
     "ca": "1", "cb": "N", "via": ("classes", "dialect")},

    # --- huấn luyện: ghim KHÔNG GIAN NHÃN, không ghim nội dung bộ dữ liệu -
    {"name": "PINS", "i": 9, "j": 5, "a": "registry_versions", "b": "training_jobs",
     "ca": "1", "cb": "N", "via": ("training_jobs", "registry_version")},
    {"name": "SUBMITS", "i": 10.4, "j": 5, "a": "users", "b": "training_jobs",
     "ca": "1", "cb": "N", "via": ("training_jobs", "auth_user_id")},

    # --- dữ liệu thu được ------------------------------------------------
    {"name": "SOURCE OF", "i": 0, "j": 6, "a": "classes", "b": "raw_uploads",
     "ca": "1", "cb": "N", "via": ("raw_uploads", "class_uid")},
    {"name": "GROUPS", "i": 3, "j": 6, "a": "classes", "b": "samples",
     "ca": "1", "cb": "N", "via": ("samples", "class_uid")},
    {"name": "PERFORMS", "i": 4.5, "j": 7, "a": "signers", "b": "samples",
     "ca": "1", "cb": "N", "via": ("samples", "signer_id")},

    # --- đồng thuận của chủ thể dữ liệu ----------------------------------
    {"name": "GRANTS", "i": 6, "j": 6, "a": "signers", "b": "signer_consents",
     "ca": "1", "cb": "N", "via": ("signer_consents", "signer_id")},

    # Hai quan hệ GHIM VÀO khác nhau ở CHỦ THỂ: một là tài khoản chấp thuận
    # điều khoản dịch vụ, một là CHỦ THỂ DỮ LIỆU cho phép dùng dữ liệu của
    # mình. Chỉ vế thứ hai chi phối đường phát hành dữ liệu.
    {"name": "BOUND TO", "i": 11, "j": 6, "a": "user_consents", "b": "legal_documents",
     "ca": "N", "cb": "1", "via": ("user_consents", "kind")},
    {"name": "BOUND TO", "i": 8.5, "j": 8, "a": "signer_consents", "b": "legal_documents",
     "ca": "N", "cb": "1", "via": ("signer_consents", "kind")},
)


def validate_conceptual(schema: Schema) -> List[str]:
    """Đối chiếu mô hình khái niệm với lược đồ thật. Trả về danh sách sai lệch."""
    problems: List[str] = []
    for name in CONCEPTUAL_ENTITIES:
        if name not in schema.tables:
            problems.append(f"thực thể {name!r} không có bảng tương ứng")
            continue
        cols = {c for c, _t, _n in schema.columns.get(name, [])}
        for a in CONCEPTUAL_ENTITIES[name]["attrs"]:
            if a not in cols:
                problems.append(f"{name}.{a} không tồn tại")
    for rel in CONCEPTUAL_RELATIONS:
        child, column = rel["via"]
        if not any(f["table"] == child and column in f["columns"] for f in schema.fks):
            problems.append(
                f"quan hệ {rel['name']!r} khai qua {child}.{column} nhưng "
                f"không có khoá ngoại nào như vậy")
    return problems


# =========================================================================== dựng XML

CHEN_X, CHEN_Y = 300, 240
CHEN_X0, CHEN_Y0 = 300, 190
E_W, E_H = 210, 66
D_W, D_H = 180, 84
A_W, A_H = 132, 44


def _cell(cid, value, style, parent, x=None, y=None, w=None, h=None,
          vertex=True, source=None, target=None, relative=False, extra_geo="") -> str:
    """Một `mxCell`. `value` được thoát XML, và `\\n` thành ngắt dòng THẬT.

    Chi tiết đáng ghi: mọi kiểu ở đây đều có `html=1`, nên draw.io hiểu nhãn là
    HTML. Một ký tự xuống dòng thật trong giá trị thuộc tính XML bị bộ phân tích
    chuẩn hoá thành DẤU CÁCH (attribute-value normalization), nên nhãn hai dòng
    sẽ lặng lẽ bị dồn thành một dòng. Cách đúng là ghi `&lt;br&gt;` — draw.io đọc
    ra chuỗi `<br>` rồi render nó thành ngắt dòng.
    """
    geo = "<mxGeometry"
    if relative:
        geo += ' relative="1"'
    for k, v in (("x", x), ("y", y), ("width", w), ("height", h)):
        if v is not None:
            geo += f' {k}="{round(v)}"'
    geo += f' as="geometry">{extra_geo}</mxGeometry>' if extra_geo else ' as="geometry"/>'
    if vertex:
        kind = 'vertex="1"'
    else:
        kind = 'edge="1"'
        if source:
            kind += f' source="{source}"'
        if target:
            kind += f' target="{target}"'
    label = escape(value).replace("\n", "&lt;br&gt;")
    return (f'<mxCell id="{cid}" value="{label}" style="{escape(style)}" '
            f'{kind} parent="{parent}">{geo}</mxCell>')


def _edge_label(eid: str, text: str, pos: float) -> str:
    """Nhãn lực lượng đặt gần một đầu cạnh (Chen: 1 / N / M)."""
    style = ("edgeLabel;html=1;align=center;verticalAlign=middle;resizable=0;"
             "points=[];fontSize=15;fontStyle=1;labelBackgroundColor=none;")
    return (f'<mxCell id="{eid}" value="{escape(text)}" style="{escape(style)}" '
            f'vertex="1" connectable="0" parent="{eid.rsplit("_", 1)[0]}">'
            f'<mxGeometry x="{pos}" relative="1" as="geometry">'
            f'<mxPoint as="offset"/></mxGeometry></mxCell>')


def build_chen(schema: Schema) -> str:
    """Trang mức khái niệm, ký pháp Chen."""
    out: List[str] = []
    node_boxes: List[Tuple[float, float, float, float, str]] = []

    def centre(i: float, j: float) -> Tuple[float, float]:
        return CHEN_X0 + i * CHEN_X, CHEN_Y0 + j * CHEN_Y

    # --- thực thể + thuộc tính
    for name, spec in CONCEPTUAL_ENTITIES.items():
        cx, cy = centre(spec["i"], spec["j"])
        color, fill = color_of(name)
        kind = schema.entity_kind(name)
        eid = f"ce_{name}"

        # Thực thể YẾU vẽ viền đôi. draw.io không có kiểu viền đôi cho hình chữ
        # nhật, nên vẽ một khung lớn hơn 7px phía sau — kết quả giống hệt quy ước
        # Chen và vẫn là một hình vẽ bình thường, không phải ảnh.
        if kind in ("weak", "associative"):
            out.append(_cell(
                f"{eid}_outer", "",
                f"rounded=0;html=1;fillColor=none;strokeColor={color};strokeWidth=1.5;",
                "1", cx - E_W / 2 - 7, cy - E_H / 2 - 7, E_W + 14, E_H + 14))

        out.append(_cell(
            eid, spec["label"],
            f"rounded=0;html=1;whiteSpace=wrap;fillColor={fill};strokeColor={color};"
            f"strokeWidth=1.5;fontSize=14;fontStyle=1;fontColor=#111111;verticalAlign=middle;",
            "1", cx - E_W / 2, cy - E_H / 2, E_W, E_H))
        node_boxes.append((cx - E_W / 2 - 7, cy - E_H / 2 - 7, E_W + 14, E_H + 14, name))

        # Thuộc tính: quạt phía trên thực thể. Cái đầu tiên là khoá → gạch chân
        # (fontStyle=4), đúng quy ước Chen.
        attrs = spec["attrs"]
        offsets = [-185, 0, 185][: len(attrs)] if len(attrs) > 1 else [0]
        if len(attrs) == 2:
            offsets = [-100, 100]
        for k, attr in enumerate(attrs):
            ax = cx + offsets[k]
            ay = cy - E_H / 2 - 62
            aid = f"ca_{name}_{k}"
            is_key = k == 0
            out.append(_cell(
                aid, attr,
                f"ellipse;html=1;whiteSpace=wrap;fillColor=#FFFFFF;strokeColor={color};"
                f"fontSize=11;fontColor=#111111;"
                f"{'fontStyle=4;' if is_key else ''}",
                "1", ax - A_W / 2, ay - A_H / 2, A_W, A_H))
            node_boxes.append((ax - A_W / 2, ay - A_H / 2, A_W, A_H, f"{name}.{attr}"))
            out.append(_cell(
                f"cae_{name}_{k}", "",
                f"endArrow=none;html=1;strokeColor={color};rounded=0;",
                "1", vertex=False, source=aid, target=eid))

    # --- quan hệ (hình thoi) + cạnh mang lực lượng
    for n, rel in enumerate(CONCEPTUAL_RELATIONS):
        cx, cy = centre(rel["i"], rel["j"])
        color, fill = color_of(rel["b"])
        rid = f"cr_{n}"

        # Quan hệ ĐỊNH DANH (nối một thực thể yếu với cha của nó) vẽ hình thoi
        # đôi — cùng quy ước, cùng cách dựng như thực thể yếu.
        if rel.get("identifying"):
            out.append(_cell(
                f"{rid}_outer", "",
                f"rhombus;html=1;fillColor=none;strokeColor={color};strokeWidth=1.5;",
                "1", cx - D_W / 2 - 8, cy - D_H / 2 - 8, D_W + 16, D_H + 16))

        out.append(_cell(
            rid, rel["name"],
            f"rhombus;html=1;whiteSpace=wrap;fillColor=#FFFFFF;strokeColor={color};"
            f"strokeWidth=1.5;fontSize=11;fontStyle=1;fontColor=#111111;",
            "1", cx - D_W / 2, cy - D_H / 2, D_W, D_H))
        node_boxes.append((cx - D_W / 2 - 8, cy - D_H / 2 - 8, D_W + 16, D_H + 16,
                           rel["name"]))

        # Thuộc tính CỦA quan hệ — chỉ có ở quan hệ nhiều-nhiều (`role` của
        # THAM GIA). Đây chính là lý do Chen cần hình thoi: một thuộc tính không
        # thuộc về thực thể nào mà thuộc về sự kết hợp của hai thực thể.
        for k, attr in enumerate(rel.get("attrs", [])):
            ax, ay = cx, cy + D_H / 2 + 58
            aid = f"cra_{n}_{k}"
            out.append(_cell(
                aid, attr,
                f"ellipse;html=1;whiteSpace=wrap;fillColor=#FFFFFF;strokeColor={color};"
                f"fontSize=11;fontColor=#111111;",
                "1", ax - A_W / 2, ay - A_H / 2, A_W, A_H))
            node_boxes.append((ax - A_W / 2, ay - A_H / 2, A_W, A_H, f"{rel['name']}.{attr}"))
            out.append(_cell(
                f"crae_{n}_{k}", "",
                f"endArrow=none;html=1;strokeColor={color};rounded=0;",
                "1", vertex=False, source=rid, target=aid))

        for side, ent, card, pos in (("a", rel["a"], rel["ca"], -0.72),
                                     ("b", rel["b"], rel["cb"], 0.72)):
            eid = f"cre_{n}_{side}"
            out.append(_cell(
                eid, "",
                f"endArrow=none;html=1;rounded=0;strokeColor={color};strokeWidth=1.5;"
                f"edgeStyle=orthogonalEdgeStyle;",
                "1", vertex=False, source=rid, target=f"ce_{ent}"))
            out.append(_edge_label(f"{eid}_lbl", card, pos))

    _warn_overlaps(node_boxes, "Chen")
    return _page("1 · Conceptual Data Model — Chen notation", "".join(out))


def _warn_overlaps(boxes, page: str) -> None:
    """Báo khi hai hộp đè lên nhau.

    Toạ độ của trang Chen là viết tay, nên đây là lưới an toàn duy nhất: một
    hình vẽ có hai hộp chồng nhau vẫn mở được, vẫn xuất được PNG, và chỉ lộ ra
    khi có người nhìn kỹ — thường là người chấm.
    """
    for a in range(len(boxes)):
        xa, ya, wa, ha, na = boxes[a]
        for b in range(a + 1, len(boxes)):
            xb, yb, wb, hb, nb = boxes[b]
            if xa < xb + wb and xb < xa + wa and ya < yb + hb and yb < ya + ha:
                print(f"[CẢNH BÁO] trang {page}: {na!r} đè lên {nb!r}", file=sys.stderr)


# --------------------------------------------------------------------------- IE

ROW_H, TITLE_H, COL_W, GAP_X, GAP_Y, PAD = 20, 30, 268, 48, 40, 24

#: Bề rộng máng bên trái, nơi in `PK`. Tách khỏi tên thuộc tính bằng một
#: đường kẻ dọc — cùng bố cục với ký pháp bảng mà draw.io và các công cụ
#: ERD thương mại dùng: dấu khoá không chen vào giữa danh sách tên.
KEY_W = 38


def build_ie(schema: Schema, name: str, planes: Optional[List[str]], mode: str) -> str:
    """Trang ký pháp chân chim (IE).

    `mode` quyết định hiện bao nhiêu thuộc tính:

    * ``'none'`` — chỉ tên thực thể. Đây là **bản đồ quan hệ**: nó trả lời "cái
      gì nối với cái gì" mà không bắt người đọc lướt qua 475 thuộc tính để tìm
      ra. Với 44 thực thể thì đây là trang duy nhất in vừa một tờ và vẫn đọc
      được tên quan hệ trên cạnh.
    * ``'keys'`` — khoá chính, khoá ngoại và ``tenant_id``.
    * ``'all'``  — mọi thuộc tính.
    """
    keys = planes or list(PLANES)
    visible = {t for k in keys for t in PLANES[k]["tables"] if t in schema.tables}

    out: List[str] = []
    edges: List[str] = []
    row_id: Dict[Tuple[str, str], str] = {}
    table_id: Dict[str, str] = {}

    def cols_for(t: str):
        if mode == "none":
            return []
        fkc = schema.fk_columns(t)
        pkc = set(schema.pk.get(t, []))
        uqc = {c for u in schema.unique.get(t, []) for c in u}
        res = []
        for col, typ, notnull in schema.columns.get(t, []):
            # HAI vai trò khác nhau, cố ý tách rời:
            #
            #   `role`  quyết định cột có được HIỆN ở chế độ rút gọn không
            #   `mark`  quyết định in nhãn gì trước tên cột
            #
            # Gộp chúng làm một là lỗi đã mắc: khi bỏ nhãn FK/U đi cho gọn, mọi
            # cột khoá ngoại biến mất khỏi các trang PDM — vì phép lọc đang đọc
            # chính cái nhãn vừa bị xoá.
            role = ("PK,FK" if col in pkc and col in fkc else
                    "PK" if col in pkc else "FK" if col in fkc else
                    "U" if col in uqc else "")
            if mode != "all" and not role and col != "tenant_id":
                continue
            # CHỈ khoá chính được đánh dấu.
            #
            # Chuẩn chân chim đặt lực lượng và hướng phụ thuộc lên ĐƯỜNG NỐI,
            # không lên hộp. Một nhãn `FK` trong hộp lặp lại điều mà đường nối
            # đã nói, và lặp thì có ngày lệch: cột đổi tên hay khoá ngoại bị gỡ
            # sẽ để lại một nhãn `FK` nói dối. `U` cũng vậy — ràng buộc duy nhất
            # đã hiện ra ở đầu mút `ERzeroToOne` của quan hệ 1:1.
            mark = "PK" if col in pkc else ""
            res.append((col, typ, notnull, mark))
        return res

    cursor_x, cursor_y, band_h = PAD, PAD, 0
    per_row_max = 4 if planes else 5

    for key in keys:
        plane = PLANES[key]
        members = [t for t in plane["tables"] if t in visible]
        if not members:
            continue

        per_row = min(per_row_max, max(1, len(members)))
        boxes = [(t, (TITLE_H + 12) if mode == "none"
                 else TITLE_H + ROW_H * max(1, len(cols_for(t))))
                 for t in members]
        rows_needed = (len(boxes) + per_row - 1) // per_row
        heights = [max(h for _t, h in boxes[r * per_row:(r + 1) * per_row])
                   for r in range(rows_needed)]
        gw = per_row * COL_W + (per_row - 1) * GAP_X + 2 * PAD
        gh = sum(heights) + (len(heights) - 1) * GAP_Y + TITLE_H + 2 * PAD

        if cursor_x > PAD and cursor_x + gw > 2500:
            cursor_x, cursor_y, band_h = PAD, cursor_y + band_h + GAP_Y * 2, 0

        gid = f"g_{key}"
        out.append(_cell(
            gid, f'{plane["label"]}  ({len(members)})',
            f'rounded=1;arcSize=3;html=1;fillColor=none;strokeColor={plane["color"]};'
            f'dashed=1;dashPattern=6 4;verticalAlign=top;align=left;spacingLeft=10;'
            f'spacingTop=4;fontSize=13;fontStyle=1;fontColor={plane["color"]};strokeWidth=2;',
            "1", cursor_x, cursor_y, gw, gh))

        ty = TITLE_H + PAD
        for r in range(rows_needed):
            chunk = boxes[r * per_row:(r + 1) * per_row]
            for idx, (t, h) in enumerate(chunk):
                tid = f"t_{t}"
                table_id[t] = tid
                tx = PAD + idx * (COL_W + GAP_X)
                kind = schema.entity_kind(t)

                # Thực thể yếu / kết hợp: viền đôi, cùng quy ước với trang Chen.
                if kind in ("weak", "associative"):
                    out.append(_cell(
                        f"{tid}_outer", "",
                        f'rounded=1;arcSize=6;html=1;fillColor=none;'
                        f'strokeColor={plane["color"]};strokeWidth=1.2;',
                        gid, tx - 6, ty - 6, COL_W + 12, h + 12))

                mark = " 🔒" if schema.tables[t]["rls"] else ""
                if kind == "associative":
                    mark += "  ⋈"
                # Trên bản đồ, số hàng thay cho danh sách thuộc tính: đó là thứ
                # duy nhất phân biệt được thực thể đang dùng thật với thực thể
                # mới tạo mà chưa ai ghi vào — câu hỏi hay được hỏi nhất khi
                # nhìn một lược đồ 44 bảng lần đầu.
                title = (f'{t}{mark}  ·  {schema.tables[t]["rows"]}' if mode == "none"
                         else f"{t}{mark}")
                out.append(_cell(
                    tid, title,
                    f'swimlane;fontStyle=0;childLayout=stackLayout;horizontal=1;'
                    f'align=center;verticalAlign=middle;'
                    f'startSize={TITLE_H};horizontalStack=0;resizeParent=1;'
                    f'resizeParentMax=0;html=1;collapsible=0;marginBottom=0;'
                    f'swimlaneFillColor={plane["fill"]};strokeColor={plane["color"]};'
                    f'fillColor={plane["color"]};fontColor=#FFFFFF;fontSize=12;'
                    f'rounded=1;arcSize=6;',
                    gid, tx, ty, COL_W, h))

                # Đường kẻ dọc tách máng khoá khỏi tên thuộc tính. Vẽ MỘT lần
                # cho cả hộp chứ không kẻ từng hàng: một đường liền chạy hết
                # thân bảng đọc ra là một cột, còn 46 đoạn kẻ rời thì không.
                #
                # Nằm ngoài `childLayout=stackLayout` (cha là nhóm, không phải
                # bảng) vì stackLayout sẽ xếp nó thành một hàng nữa.
                so_hang = len(cols_for(t))
                if so_hang:
                    out.append(_cell(
                        f"{tid}_kegach", "",
                        f'line;direction=north;strokeColor={plane["color"]};'
                        f'strokeWidth=1;html=1;',
                        gid, tx + KEY_W, ty + TITLE_H, 1, so_hang * ROW_H))

                cy = TITLE_H
                for col, typ, notnull, tag in cols_for(t):
                    # HAI ô cho một hàng: máng khoá bên trái, tên bên phải.
                    #
                    # Kiểu dữ liệu KHÔNG in ra. Ký pháp bảng này đọc theo chiều
                    # dọc — mắt lướt một cột tên; chèn `· text` sau mỗi tên biến
                    # cột ấy thành văn xuôi và mất luôn cái lợi đó. Kiểu đầy đủ
                    # nằm ở `SCHEMA_TABLES.md`, nơi nó là thứ người ta đến tìm.
                    out.append(_cell(
                        f"r_{t}__{col}__k", tag,
                        f'text;strokeColor=none;fillColor=none;align=center;'
                        f'verticalAlign=middle;overflow=hidden;rotatable=0;'
                        f'html=1;fontSize=9;fontStyle=1;fontColor=#1A1A1A;',
                        tid, 0, cy, KEY_W, ROW_H))

                    # Ô TÊN mới là đầu neo của đường nối — `row_id` trỏ vào nó.
                    # Neo vào ô máng sẽ làm đường nối đâm vào giữa hộp.
                    rid = f"r_{t}__{col}"
                    row_id[(t, col)] = rid
                    out.append(_cell(
                        rid, col,
                        f'text;strokeColor=none;fillColor=none;align=left;'
                        f'verticalAlign=middle;spacingLeft=8;spacingRight=6;'
                        f'overflow=hidden;points=[[0,0.5],[1,0.5]];'
                        f'portConstraint=eastwest;rotatable=0;whiteSpace=wrap;html=1;'
                        f'fontSize=10;fontColor=#1A1A1A;'
                        f'{"fontStyle=1;" if tag else ""}',
                        tid, KEY_W, cy, COL_W - KEY_W, ROW_H))
                    cy += ROW_H
            ty += max(h for _t, h in chunk) + GAP_Y

        cursor_x += gw + GAP_X * 2
        band_h = max(band_h, gh)

    seen = set()
    for n, fk in enumerate(schema.fks):
        child, parent = fk["table"], fk["ref_table"]
        if child not in visible or parent not in visible:
            continue
        src = row_id.get((child, fk["anchor"])) or table_id.get(child)
        dst = table_id.get(parent)
        if not src or not dst or (src, dst) in seen:
            continue
        seen.add((src, dst))

        child_end, parent_end = schema.cardinality(fk)
        color, _ = color_of(parent)
        label = relation_name(fk)
        if fk["composite"]:
            label += f'\n({", ".join(fk["columns"])})'

        # Nét LIỀN cho quan hệ định danh (khoá ngoại nằm trong khoá chính của
        # con), nét ĐỨT cho quan hệ không định danh. Đây là quy ước IE, không
        # phải lựa chọn thẩm mỹ — nó cho biết hàng con có tự định danh được khi
        # thiếu cha hay không.
        style = (f'edgeStyle=entityRelationEdgeStyle;rounded=1;html=1;'
                 f'exitX=1;exitY=0.5;entryX=0;entryY=0.5;'
                 f'strokeColor={color};strokeWidth=1.3;'
                 f'startArrow={child_end};startFill=0;endArrow={parent_end};endFill=0;'
                 f'fontSize=9;fontColor={color};labelBackgroundColor=none;'
                 f'{"" if schema.is_identifying(fk) else "dashed=1;dashPattern=6 4;"}')
        edges.append(_cell(f"e{n}", label, style, "1", vertex=False,
                           source=src, target=dst, relative=True,
                           extra_geo='<mxPoint as="offset" y="-8"/>'))

    return _page(name, "".join(out + edges))


def _page(name: str, body: str) -> str:
    # `id` là BẮT BUỘC trong định dạng .drawio, dù draw.io mở được tệp thiếu nó.
    #
    # Trình xuất chính thức thì không: `drawio-export` dừng với
    # "missing field `@id`" và không ra được tệp ảnh nào. Tệp mở xem thì bình
    # thường, mà tự động hoá lại hỏng — kiểu lệch chỉ lộ ra khi có người thử
    # xuất hàng loạt.
    #
    # Sinh từ chính TÊN trang: ổn định qua các lượt sinh lại, nên khác biệt giữa
    # hai bản tệp là khác biệt về NỘI DUNG. Một `uuid4()` ở đây sẽ biến mọi lượt
    # chạy thành một lượt sửa trong git.
    import hashlib as _h
    pid = _h.sha1(name.encode("utf-8")).hexdigest()[:20]
    return (f'<diagram id="{pid}" name="{escape(name)}">'
            f'<mxGraphModel dx="1400" dy="900" grid="0" gridSize="10" guides="1" '
            f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
            f'pageWidth="1169" pageHeight="826" math="0" shadow="0">'
            f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root>'
            f'</mxGraphModel></diagram>')


# =========================================================================== SQL out


def build_sql(schema: Schema) -> str:
    """DDL rút gọn — bản văn lược đồ, KHÔNG phải đường dựng ERD.

    Đã thử trên draw.io 10/08/2026 (Arrange → Insert → Advanced → SQL): nó dựng
    được các bảng nhưng **không dựng một cạnh nào**. Những dòng
    ``FOREIGN KEY (x) REFERENCES y(z)`` bị bộ phân tích coi là một CỘT và hiện
    thành một hàng chữ bên trong hộp; ngoài ra cột được tham chiếu còn bị gắn
    nhãn ``PK`` nhầm. Kết quả là 44 hộp xếp thành một hàng, không đường nối.

    Nên đừng dùng tệp này để vẽ quan hệ — ``voya_erd.drawio`` mới là bản có đủ
    88 cạnh kèm lực lượng. Cái này giữ lại vì nó vẫn có ích cho việc khác: nạp
    lược đồ vào một công cụ ERD khác, dán vào phụ lục tài liệu, hoặc dựng một
    CSDL rỗng cùng hình dạng để thử nghiệm.

    Hai phép rút gọn còn lại, ghi ra để bản DDL không bị hiểu là bản sao trung
    thành của lược đồ:

    * 17 khoá ngoại **ghép** không diễn đạt được ở dạng một cột nên nằm dưới
      dạng chú thích ``-- FK GHÉP:``.
    * ``timestamptz`` và ``jsonb`` là kiểu riêng của Postgres; chúng được hạ về
      tập ANSI để các bộ phân tích khác không bỏ qua cả dòng.
    """
    simple = {"timestamptz": "TIMESTAMP", "jsonb": "TEXT", "uuid": "VARCHAR(36)",
              "text": "VARCHAR(255)", "varchar": "VARCHAR(255)", "bigint": "BIGINT",
              "integer": "INT", "boolean": "BOOLEAN", "real": "FLOAT",
              "float8": "FLOAT", "date": "DATE", "char": "CHAR(1)"}
    composite = sum(1 for f in schema.fks if f["composite"])
    lines = [
        "-- Lược đồ VOYA Collector — sinh tự động từ CSDL đang chạy.",
        f"-- {len(schema.tables)} bảng · {len(schema.fks)} khoá ngoại "
        f"({composite} ghép → chỉ là chú thích) · "
        f"{sum(1 for t in schema.tables.values() if t['rls'])} bảng có RLS.",
        "--",
        "-- ĐỪNG dùng tệp này để vẽ ERD trong draw.io.",
        "-- Đã thử 10/08/2026: draw.io dựng được bảng nhưng KHÔNG dựng cạnh nào —",
        "-- nó coi mỗi dòng FOREIGN KEY là một CỘT và hiện thành hàng chữ trong hộp.",
        "-- Bản có đủ 88 quan hệ kèm lực lượng: docs/02-data/db/voya_erd.drawio",
    ]
    for key, plane in PLANES.items():
        members = [t for t in plane["tables"] if t in schema.tables]
        if not members:
            continue
        lines += ["", f"-- ===== {plane['label']} " + "=" * max(0, 46 - len(plane['label'])), ""]
        for t in members:
            kind = schema.entity_kind(t)
            note = {"weak": " · THỰC THỂ YẾU", "associative": " · THỰC THỂ KẾT HỢP"}.get(kind, "")
            lines.append(f"-- {t}{note}{'  [RLS]' if schema.tables[t]['rls'] else ''}"
                         f" · {schema.tables[t]['rows']} hàng")
            body = [f"  {c} {simple.get(ty, 'VARCHAR(255)')}"
                    f"{' NOT NULL' if nn else ''}"
                    for c, ty, nn in schema.columns.get(t, [])]
            if schema.pk.get(t):
                body.append(f"  PRIMARY KEY ({', '.join(schema.pk[t])})")
            for f in schema.fks_of(t):
                if not f["composite"]:
                    body.append(f"  FOREIGN KEY ({f['columns'][0]}) "
                                f"REFERENCES {f['ref_table']}({f['ref_columns'][0]})")
            lines.append(f"CREATE TABLE {t} (")
            lines.append(",\n".join(body))
            lines.append(");")
            for f in schema.fks_of(t):
                if f["composite"]:
                    lines.append(f"-- FK GHÉP: ({', '.join(f['columns'])}) -> "
                                 f"{f['ref_table']}({', '.join(f['ref_columns'])})")
            lines.append("")
    return "\n".join(lines)


# =========================================================================== main


def _show(path: str) -> str:
    """Đường dẫn ngắn nhất mà người đọc vẫn mở được từ chỗ họ đang đứng.

    Mặc định giờ là đường tuyệt đối (neo vào `__file__`), và in nguyên nó ra thì
    dòng thông báo dài gấp ba mà không thêm thông tin gì cho người đang đứng ở
    gốc repo. `relative_to` ném ValueError khi tệp nằm ngoài thư mục hiện hành —
    ổ đĩa khác trên Windows chẳng hạn — và khi đó đường tuyệt đối mới là câu trả
    lời đúng.
    """
    try:
        return str(Path(path).resolve().relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(path)


def main() -> int:
    # Console Windows mặc định cp1252 và mọi thông điệp ở đây đều có dấu. Không
    # có dòng này thì script GHI XONG tệp rồi chết ở câu `print` cuối với mã
    # thoát khác 0 — trông y hệt một lượt sinh thất bại.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    # Đường ra mặc định neo vào VỊ TRÍ CỦA TỆP NÀY, không vào thư mục hiện hành.
    #
    # Bản đầu để `"docs/02-data/db/voya_erd.drawio"` và nó hỏng theo kiểu khó chịu nhất:
    # chạy từ gốc repo thì đúng, chạy từ chính `docs/02-data/db` thì đường dẫn nhân đôi
    # thành `docs/02-data/db/docs/02-data/db/…` và Python báo "no such file" về ĐÚNG tệp script
    # vừa gõ tên — thông điệp lỗi chỉ vào một thứ hoàn toàn không phải nguyên
    # nhân. Neo vào `__file__` thì lệnh chạy được từ bất kỳ đâu.
    here = Path(__file__).resolve().parent

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-o", "--out", default=str(here / "voya_erd.drawio"))
    ap.add_argument("--dsn")
    ap.add_argument("--container", default="voya_postgres")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--db", default="signdb")
    ap.add_argument("--sql", metavar="PATH", nargs="?",
                    const=str(here / "schema_erd.sql"))
    ap.add_argument("--stats", action="store_true")
    args = ap.parse_args()

    run = ((lambda q: _psycopg(q, args.dsn)) if args.dsn else
           (lambda q: _psql(q, args.container, args.user, args.db)))
    schema = Schema(run(Q_TABLES), run(Q_COLUMNS), run(Q_CONSTRAINTS))

    orphans = sorted(set(schema.tables) - set(PLANE_OF))
    if orphans:
        print(f"[CẢNH BÁO] {len(orphans)} bảng chưa gán mặt phẳng, KHÔNG lên hình: "
              f"{', '.join(orphans)}", file=sys.stderr)

    # Mô hình khái niệm là diễn giải viết tay; đây là chỗ nó bị đối chiếu với
    # sự thật. Dừng hẳn chứ không cảnh báo: một ERD khái niệm nói sai về khoá
    # ngoại còn tệ hơn không có ERD nào.
    problems = validate_conceptual(schema)
    if problems:
        print("[LỖI] mô hình khái niệm không khớp lược đồ:", file=sys.stderr)
        for p in problems:
            print(f"  · {p}", file=sys.stderr)
        return 2

    kinds = {k: sum(1 for t in schema.tables if schema.entity_kind(t) == k)
             for k in ("strong", "weak", "associative")}

    if args.stats:
        print(json.dumps({
            "tables": len(schema.tables),
            "columns": sum(len(v) for v in schema.columns.values()),
            "foreign_keys": len(schema.fks),
            "composite_fks": sum(1 for f in schema.fks if f["composite"]),
            "identifying_fks": sum(1 for f in schema.fks if schema.is_identifying(f)),
            "one_to_one": sum(1 for f in schema.fks
                              if schema.cardinality(f)[0] == "ERzeroToOne"),
            "mandatory_parent": sum(1 for f in schema.fks
                                    if schema.cardinality(f)[1] == "ERmandOne"),
            "entities": kinds,
            "rls_tables": sum(1 for t in schema.tables.values() if t["rls"]),
            "conceptual": {"entities": len(CONCEPTUAL_ENTITIES),
                           "relations": len(CONCEPTUAL_RELATIONS)},
        }, ensure_ascii=False, indent=2))
        return 0

    # Bố cục trang khớp một-một với hình của Chương 3:
    #   trang 1     — tham chiếu cho Figure 3.13 (CDM), vẽ tay ở PowerDesigner
    #   trang 2     — tham chiếu cho Figure 3.14 (LDM Overview)
    #   trang 3     — LDM đủ khoá, dùng để đối chiếu
    #   trang 4–7   — Figure 3.15–3.18, mỗi mô-đun một trang PDM
    pages = [
        build_chen(schema),
        build_ie(schema, "2 · Relationship Map — entities and links only",
                 None, "none"),
        build_ie(schema, "3 · Logical Data Model — crow's foot with keys", None, "keys"),
    ]
    for idx, (mod, title) in enumerate(MODULES.items(), start=4):
        pages.append(build_ie(schema, f"{idx} · PDM {title}",
                              planes_of_module(mod), "all"))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>'
           f'<mxfile host="app.diagrams.net" type="device">{"".join(pages)}</mxfile>')
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(xml)

    print(f"Đã ghi {_show(args.out)}")
    print(f"  · trang 1 (Chen):      {len(CONCEPTUAL_ENTITIES)} thực thể, "
          f"{len(CONCEPTUAL_RELATIONS)} quan hệ — đã đối chiếu với lược đồ, khớp")
    print(f"  · trang 2 (bản đồ):    {len(schema.tables)} thực thể, chỉ đường nối")
    print(f"  · trang 3 (LDM):       {len(schema.tables)} thực thể "
          f"({kinds['strong']} mạnh / {kinds['weak']} yếu / "
          f"{kinds['associative']} kết hợp), {len(schema.fks)} quan hệ")
    for idx, (mod, title) in enumerate(MODULES.items(), start=4):
        n = sum(1 for k in planes_of_module(mod)
                for t in PLANES[k]["tables"] if t in schema.tables)
        print(f"  · trang {idx} (PDM {mod}):     {n} bảng — {title}")

    if args.sql:
        with open(args.sql, "w", encoding="utf-8") as fh:
            fh.write(build_sql(schema))
        comp = sum(1 for f in schema.fks if f["composite"])
        print(f"Đã ghi {_show(args.sql)} — bản văn lược đồ "
              f"({len(schema.fks) - comp} khoá ngoại đơn, {comp} khoá ghép thành chú thích). "
              f"KHÔNG dùng để vẽ: draw.io không dựng cạnh từ tệp này.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

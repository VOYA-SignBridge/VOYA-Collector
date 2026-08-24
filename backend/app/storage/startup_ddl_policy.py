"""Tập thao tác DDL được phép chạy lúc KHỞI ĐỘNG — allowlist, không phải denylist.

Bản vá ngày 12/08/2026 lấy phần phá huỷ ra khỏi `ensure_tables()` bằng một cái
lưới quét từ khoá: `DROP TABLE|DROP COLUMN|DROP INDEX|TRUNCATE|DELETE FROM`.
Cái lưới đó đúng với những gì nó biết, và chỉ mạnh bằng danh sách từ khoá.
Đo lại ngày 13/08/2026 trên chính tập câu lệnh đang chạy mỗi lần backend lên:

    21 câu UPDATE   — đổi dữ liệu đã có, gồm đổi tên role và tắt role
    10 câu INSERT   — 5 câu seed hằng, 5 câu chép từ bảng khác sang
     1 câu ALTER COLUMN ... TYPE uuid, kèm một UPDATE ghi vào cột note
     2 câu RENAME COLUMN
     1 câu SET NOT NULL
     2 câu DROP CONSTRAINT không có câu tạo lại

Không câu nào trong số đó chứa một từ khoá của cái lưới. Đó là lý do tệp này
đảo chiều câu hỏi:

    lưới cũ   "câu này có giống thứ ta biết là nguy hiểm không?"
    tệp này   "câu này có CHỨNG MINH được thuộc tập an toàn không?"

Ba lớp, và lớp thứ ba mới là thứ mua được nhiều nhất:

    A. AN TOÀN LÚC KHỞI ĐỘNG   khớp một hình dạng trong `_SAFE_SHAPES`
    B. CHỈ ĐI MIGRATION         chứa một động từ đột biến chưa được biện minh
    C. CHƯA PHÂN LOẠI           không rơi vào đâu cả -> test ĐỎ

Một câu DDL mới mà bộ phân loại chưa hiểu KHÔNG được mặc nhiên coi là an toàn.
Nó rơi xuống B (bị loại khỏi đường khởi động, chỉ `app.cli.migrate` chạy được)
và làm `test_no_startup_statement_is_unclassified` đỏ, nên người thêm nó phải
nói ra nó là loại gì trước khi merge.

Quan hệ với checksum
--------------------
`migration_payload()` băm đúng phần một chiều. Vì tệp này QUYẾT ĐỊNH phần một
chiều gồm những gì, mỗi lần phân loại lại là một lần payload đổi — tức là một
lần checksum đổi, tức là phải lên phiên bản mới. Đó là hành vi mong muốn: "câu
nào chỉ được chạy có người ra lệnh" là một phần của hợp đồng lược đồ, không
phải chi tiết cài đặt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Sequence

from app.storage.schema_version import canonical_sql

__all__ = [
    "StartupException",
    "Verdict",
    "STARTUP_EXCEPTIONS",
    "classify_corpus",
    "migration_only_statements",
    "startup_corpus",
]


# ---------------------------------------------------------------------------
# Ngoại lệ có tên và có lý do
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StartupException:
    """Một câu chứa động từ đột biến nhưng VẪN được chạy lúc khởi động.

    Mỗi mục phải nói ra ba thứ, và cả ba đều bị test kiểm:

      * `label`       tên gọi được, để nhắc tới trong nhật ký và trong tranh luận
      * `reason`      vì sao nó an toàn — không phải "vì nó vẫn chạy xưa nay"
      * `guard`       cơ chế làm nó chạy lại được mà không đổi gì thêm

    `fingerprint` là đoạn văn bản nhận diện. Nó cố tình KHÔNG phải toàn văn câu
    lệnh: chép toàn văn vào đây thì mỗi lần sửa một dấu phẩy lại phải sửa hai
    chỗ, và cái chép tay sẽ trôi khỏi bản gốc trong im lặng. Đổi lại, một dấu
    vân tay lỏng có thể vẫn khớp sau khi thân câu đã bị sửa thành thứ khác —
    nên `guard` vẫn được kiểm trên câu ĐANG chạy, chứ không phải trên bản chép.
    """

    label: str
    reason: str
    fingerprint: str
    guard: str


#: Năm câu seed hằng. Chúng chỉ ĐIỀN dòng còn thiếu, và nội dung dòng nằm ngay
#: trong câu lệnh chứ không đọc từ bảng nào — nên chạy lần thứ hai không đổi gì.
#: Năm câu INSERT còn lại của hệ thống KHÔNG có mặt ở đây, vì chúng dựng dòng
#: mới TỪ dữ liệu đang có (`SELECT DISTINCT ... FROM samples`); kết quả của
#: chúng phụ thuộc vào trạng thái cơ sở dữ liệu lúc chạy, và một lượt khởi động
#: lại lúc 3 giờ sáng không phải chỗ để chuyện đó xảy ra.
STARTUP_EXCEPTIONS: tuple[StartupException, ...] = (
    StartupException(
        label="seed_two_interface_languages",
        reason="Hai ngôn ngữ giao diện là hằng số của sản phẩm, không phải dữ "
               "liệu người dùng. Máy cài mới cần chúng trước request đầu tiên.",
        fingerprint="INSERT INTO languages (code, name) VALUES",
        guard="ON CONFLICT DO NOTHING",
    ),
    StartupException(
        label="seed_default_tenant",
        reason="Mọi dòng dữ liệu cũ đều mang tenant_id='default'. Thiếu dòng "
               "này thì mọi khoá ngoại tenant hỏng và backend lên nhưng vô dụng.",
        fingerprint="INSERT INTO tenants(tenant_id, display_name, slug) SELECT 'default'",
        guard="WHERE NOT EXISTS",
    ),
    StartupException(
        label="seed_community_tenant",
        reason="Tenant cộng đồng là mặt phẳng dùng chung của registry ba mặt "
               "phẳng; nó do MÃ định nghĩa, không do người vận hành tạo.",
        # Dấu vân tay KHÔNG chứa mã tenant nữa. Ngày 22/08/2026
        # `COMMUNITY_TENANT_ID` chuyển từ `'community'` sang tenant đang giữ
        # corpus, và một dấu vân tay viết cứng mã cũ sẽ lặng lẽ thôi khớp — câu
        # seed rơi xuống "chưa phân loại" và bị loại khỏi đường khởi động.
        # Ba giá trị còn lại đủ nhận dạng: chỉ câu này gieo một tenant COMMUNITY
        # dự trữ trên gói enterprise.
        fingerprint="'Cộng đồng',",
        guard="WHERE NOT EXISTS",
    ),
    StartupException(
        label="backfill_community_membership",
        reason="Mọi tài khoản đang hoạt động đều thuộc Cộng đồng. Chỉ THÊM "
               "dòng cho người chưa có, nhờ `NOT EXISTS` — không sửa, không "
               "xoá tư cách thành viên nào đã tồn tại.",
        fingerprint="SELECT u.id, 'TENANT'",
        guard="NOT EXISTS",
    ),
    StartupException(
        label="backfill_community_role",
        reason="Tư cách thành viên mà thiếu vai thì tài khoản không ghi được "
               "gì — `access_gate` từ chối người không có grant nào. Câu này "
               "gắn `community_member` cho những dòng còn thiếu.",
        fingerprint="JOIN roles r ON r.role_code = 'community_member'",
        guard="NOT EXISTS",
    ),
    StartupException(
        label="fix_retired_community_plan",
        reason="Một câu từ thời v4 gán `plan_code='internal'` cho tenant khởi "
               "tạo, nhưng `internal` không còn trong bảng `plans`. Mệnh đề "
               "`NOT EXISTS` giữ phạm vi hẹp: không đụng tenant đang mang gói "
               "hợp lệ, nên nó không ghi đè một quyết định thương mại.",
        # Dấu vân tay phải DUY NHẤT. Bản đầu dùng `SET plan_code = 'enterprise'`
        # và nó trùng với chính câu backfill v4 ngay bên dưới — câu ấy không có
        # chốt chặn `NOT EXISTS`, nên bộ phân loại báo "ngoại lệ khai chốt chặn
        # mà câu lệnh không còn có". Mệnh đề tương quan dưới đây chỉ xuất hiện ở
        # câu vá này.
        fingerprint="p.plan_code = tenants.plan_code",
        guard="NOT EXISTS (SELECT 1 FROM plans",
    ),
    StartupException(
        label="retire_legacy_community_row",
        reason="Máy đã chạy bản trước có một hàng `community` RỖNG mang "
               "`tenant_type='COMMUNITY'`. Chỉ mục duy nhất chỉ cho phép MỘT "
               "hàng như vậy, nên hàng cũ phải nghỉ trước khi tenant giữ corpus "
               "được nâng lên — nếu không cả lượt migration dừng vì trùng khoá. "
               "Xoá MỀM, vì hàng ấy còn dòng phụ thuộc với khoá ngoại RESTRICT.",
        # Dấu vân tay CỐ Ý không nhắc tên cột `is_system_reserved`.
        #
        # `test_is_system_reserved_is_never_read_by_authorisation` quét cây cú
        # pháp và bắt mọi chuỗi chứa tên ấy — nó không phân biệt được "khớp một
        # câu DDL" với "đọc để quyết định quyền", và blanket rule đó là thứ làm
        # bài kiểm có giá trị. Vế còn lại đủ nhận dạng: đây là câu DUY NHẤT đặt
        # `tenant_type` về ORGANIZATION.
        fingerprint="SET tenant_type = 'ORGANIZATION'",
        guard="WHERE tenant_id = 'community'",
    ),
    StartupException(
        label="revoke_legacy_community_invitations",
        reason="Lời mời còn treo trỏ vào hàng vừa cho nghỉ. Không thu hồi thì "
               "người nhận bấm liên kết và gia nhập một tổ chức đã ngừng hoạt "
               "động — một ngõ cụt không có thông báo nào giải thích.",
        fingerprint="UPDATE tenant_invitations SET revoked_at = COALESCE",
        guard="WHERE tenant_id = 'community'",
    ),
    StartupException(
        label="seed_vocabulary_registry_meta_row",
        reason="Một dòng meta cho mỗi tenant, khoá chính là tenant_id. Không "
               "mang dữ liệu, chỉ mở chỗ cho registry ghi vào. Từ v7 nó trỏ "
               "vào phiên bản CAO NHẤT có thật — hoặc NULL khi chưa công bố "
               "gì — thay vì để cột rơi vào DEFAULT 1 và tạo con trỏ treo.",
        fingerprint="INSERT INTO vocabulary_registry_meta(tenant_id, version)",
        guard="ON CONFLICT DO NOTHING",
    ),
    StartupException(
        label="seed_builtin_plans",
        reason="Danh mục gói dịch vụ là hằng số của sản phẩm và được mã đọc "
               "theo `plan_code`. Một cơ sở dữ liệu không có nó thì mọi phép "
               "kiểm hạn mức trả về 'không có gói'.",
        fingerprint="INSERT INTO plans (",
        guard="ON CONFLICT",
    ),
)


# ---------------------------------------------------------------------------
# Hình dạng được phép
# ---------------------------------------------------------------------------

#: Thứ tự có ý nghĩa: mục khớp ĐẦU TIÊN thắng, nên hình dạng hẹp phải đứng
#: trước hình dạng rộng.
_SAFE_SHAPES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("create_table_if_not_exists",
     re.compile(r"\ACREATE TABLE IF NOT EXISTS \w", re.IGNORECASE)),
    ("create_index_if_not_exists",
     re.compile(r"\ACREATE (UNIQUE )?INDEX IF NOT EXISTS \w", re.IGNORECASE)),
    ("create_extension_if_not_exists",
     re.compile(r"\ACREATE EXTENSION IF NOT EXISTS \w", re.IGNORECASE)),
    ("add_column_if_not_exists",
     re.compile(r"\AALTER TABLE \w+ ADD COLUMN IF NOT EXISTS \w", re.IGNORECASE)),
    ("add_constraint",
     re.compile(r"\AALTER TABLE \w+ ADD CONSTRAINT \w", re.IGNORECASE)),
    # Nới lỏng thì thêm được, siết lại thì không: `SET DEFAULT` / `DROP DEFAULT`
    # / `DROP NOT NULL` không thể hỏng vì dữ liệu đang có, và giá trị mặc định
    # đi theo MÃ. Chiều ngược lại (`SET NOT NULL`, `... TYPE ...`) nằm trong
    # `_MUTATING_VERBS` bên dưới.
    ("relax_column_constraint",
     re.compile(r"\AALTER TABLE \w+ ALTER COLUMN \w+ "
                r"(SET DEFAULT .+|DROP DEFAULT|DROP NOT NULL)\Z", re.IGNORECASE)),
    ("enable_row_level_security",
     re.compile(r"\AALTER TABLE \w+ ENABLE ROW LEVEL SECURITY\Z", re.IGNORECASE)),
    ("force_row_level_security",
     re.compile(r"\AALTER TABLE \w+ FORCE ROW LEVEL SECURITY\Z", re.IGNORECASE)),
    ("create_policy",
     re.compile(r"\ACREATE POLICY \w", re.IGNORECASE)),
    ("create_trigger",
     re.compile(r"\ACREATE TRIGGER \w", re.IGNORECASE)),
    ("create_or_replace_view",
     re.compile(r"\ACREATE OR REPLACE VIEW \w", re.IGNORECASE)),
    ("create_or_replace_function",
     re.compile(r"\ACREATE OR REPLACE FUNCTION \w", re.IGNORECASE)),
    ("comment_on",
     re.compile(r"\ACOMMENT ON \w", re.IGNORECASE)),
    # Ba hình dạng "bỏ rồi dựng lại". Chúng chỉ an toàn khi có câu dựng lại —
    # xem `_paired_drop_is_safe`.
    ("drop_policy_before_recreate",
     re.compile(r"\ADROP POLICY IF EXISTS (?P<name>\w+) ON \w+\Z", re.IGNORECASE)),
    ("drop_trigger_before_recreate",
     re.compile(r"\ADROP TRIGGER IF EXISTS (?P<name>\w+) ON \w+\Z", re.IGNORECASE)),
    ("drop_constraint_before_recreate",
     re.compile(r"\AALTER TABLE \w+ DROP CONSTRAINT (IF EXISTS )?(?P<name>\w+)\Z",
                re.IGNORECASE)),
    # Khối `DO $$`: hình dạng không nói được gì, nên nó được xét bằng động từ
    # bên trong. Xem `_classify_do_block`.
    ("do_block_additive",
     re.compile(r"\ADO \$\$", re.IGNORECASE)),
)

_PAIRED_DROP_SHAPES = {
    "drop_policy_before_recreate": ("policy", "chính sách"),
    "drop_trigger_before_recreate": ("trigger", "trigger"),
    "drop_constraint_before_recreate": ("constraint", "ràng buộc"),
}


# ---------------------------------------------------------------------------
# Động từ đột biến
# ---------------------------------------------------------------------------

#: Những gì KHÔNG được phép, ở bất kỳ đâu trong câu — kể cả sâu trong thân một
#: khối `DO $$` mà hình dạng bên ngoài trông vô hại.
#:
#: `UPDATE` bắt buộc phải kèm `SET` mới tính, nếu không thì `ON UPDATE CASCADE`
#: của mọi khoá ngoại và `BEFORE INSERT OR UPDATE` của mọi trigger đều bị bắt
#: nhầm — 30 báo động giả, và báo động giả thì người ta tắt cả cái cổng đi.
_MUTATING_VERBS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("DROP TABLE", re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE)),
    ("DROP COLUMN", re.compile(r"\bDROP\s+COLUMN\b", re.IGNORECASE)),
    ("DROP INDEX", re.compile(r"\bDROP\s+INDEX\b", re.IGNORECASE)),
    ("DROP VIEW", re.compile(r"\bDROP\s+VIEW\b", re.IGNORECASE)),
    ("DROP SCHEMA", re.compile(r"\bDROP\s+SCHEMA\b", re.IGNORECASE)),
    ("TRUNCATE", re.compile(r"\bTRUNCATE\b", re.IGNORECASE)),
    ("DELETE FROM", re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)),
    ("UPDATE ... SET", re.compile(
        r"\bUPDATE\s+[\w.\"]+(\s+(?:AS\s+)?\w+)?\s+SET\b", re.IGNORECASE)),
    ("INSERT INTO", re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE)),
    ("ALTER COLUMN ... TYPE", re.compile(
        r"\bALTER\s+COLUMN\s+\w+\s+(SET\s+DATA\s+)?TYPE\b", re.IGNORECASE)),
    ("SET NOT NULL", re.compile(r"\bSET\s+NOT\s+NULL\b", re.IGNORECASE)),
    # Hai chiều NGƯỢC lại của `SET NOT NULL`, bổ sung 24/08/2026. Chúng trông
    # hiền hơn vì không thể ngã trên dữ liệu đang có, nhưng đó chính là lý do
    # phải bắt: một câu NỚI ràng buộc chạy im lặng ở mọi lần khởi động sẽ gỡ
    # mất phép kiểm mà không lần triển khai nào ghi lại. `DROP DEFAULT` còn đổi
    # ngữ nghĩa của MỌI câu INSERT sau đó — đúng thứ vừa gây ra v7, nơi một
    # DEFAULT 1 lặng lẽ dựng con trỏ trỏ vào phiên bản chưa tồn tại.
    ("DROP NOT NULL", re.compile(r"\bDROP\s+NOT\s+NULL\b", re.IGNORECASE)),
    ("DROP DEFAULT", re.compile(r"\bDROP\s+DEFAULT\b", re.IGNORECASE)),
    ("RENAME", re.compile(r"\bRENAME\b", re.IGNORECASE)),
    ("ALTER TYPE", re.compile(r"\bALTER\s+TYPE\b", re.IGNORECASE)),
    ("GRANT", re.compile(r"\bGRANT\b", re.IGNORECASE)),
    ("REVOKE", re.compile(r"\bREVOKE\b", re.IGNORECASE)),
)

_DROP_CONSTRAINT_IN_BODY = re.compile(
    r"\bDROP\s+CONSTRAINT\s+(?:IF\s+EXISTS\s+)?(\w+)", re.IGNORECASE)
_ADD_CONSTRAINT_IN_BODY = re.compile(r"\bADD\s+CONSTRAINT\s+(\w+)", re.IGNORECASE)

_RECREATED_PATTERNS = {
    "policy": re.compile(r"\bCREATE\s+POLICY\s+(\w+)", re.IGNORECASE),
    "trigger": re.compile(r"\bCREATE\s+TRIGGER\s+(\w+)", re.IGNORECASE),
    "constraint": _ADD_CONSTRAINT_IN_BODY,
}


# ---------------------------------------------------------------------------
# Phán quyết
# ---------------------------------------------------------------------------

#: Bốn mặt phẳng. Ba cái đầu là kết luận; cái thứ tư là "chưa ai kết luận".
STARTUP_SAFE = "startup-safe"
HISTORICAL_ONLY = "historical-only"
MIGRATION_ONLY = "migration-only"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Verdict:
    """Kết luận cho MỘT câu lệnh, kèm lý do đọc được."""

    statement: str
    group: str
    shape: str | None
    detail: str
    plane: str = MIGRATION_ONLY

    @property
    def is_startup_safe(self) -> bool:
        return self.plane == STARTUP_SAFE

    def describe(self, width: int = 150) -> str:
        head = " ".join(canonical_sql(self.statement).split())[:width]
        return f"[{self.group}] {self.detail}\n    {head}"


@dataclass(frozen=True)
class HistoricalMigration:
    """Một lượt biến đổi ĐÃ hoàn thành nhiệm vụ và sẽ không thuộc phiên bản nào nữa.

    Khai một câu là "lịch sử" là một khẳng định mạnh: nó nói rằng mọi cơ sở dữ
    liệu còn sống đã đi qua lượt biến đổi này rồi, nên nó không cần chạy lúc
    khởi động VÀ cũng không cần có mặt trong payload của bất kỳ phiên bản mới
    nào. Sai ở vế đầu thì vô hại (câu vẫn chạy được qua migration); sai ở vế
    sau thì một máy cài mới sẽ thiếu lượt biến đổi đó.

    Vì thế mặt phẳng này phải KHAI TƯỜNG MINH, còn `migration-only` là mặc
    định — "nguy hiểm, và chưa ai nhận nó thuộc phiên bản nào".
    """

    label: str
    reason: str
    pattern: re.Pattern[str]


def _historical(label: str, reason: str, pattern: str) -> HistoricalMigration:
    return HistoricalMigration(label, reason, re.compile(pattern, re.IGNORECASE))


#: Bốn mươi ba câu, gom theo lượt biến đổi. Mỗi nhóm là một chuyện đã xảy ra.
HISTORICAL_MIGRATIONS: tuple[HistoricalMigration, ...] = (
    _historical(
        "retire_pre_registry_dialects",
        "Phương ngữ trước khi có registry dùng cột `code`; registry v3 thay "
        "bằng `dialect_id`. Bảng cũ đã bỏ, không cơ sở dữ liệu nào còn cột đó.",
        r"table_name = 'dialects' AND column_name = 'code'"),
    _historical(
        "backfill_support_message_author_kind",
        "`author_kind` thêm vào sau khi bảng đã có dữ liệu; câu này suy nó ra "
        "từ `is_staff` cho các dòng cũ. Dòng mới luôn ghi thẳng cột này.",
        r"UPDATE support_messages SET author_kind"),
    _historical(
        "backfill_refresh_token_families",
        "Phát hiện tái dùng token cần `family_id`; token cũ chưa có. Token "
        "phát hành sau đó đều mang sẵn.",
        r"UPDATE refresh_tokens SET family_id"),
    _historical(
        "retire_tenant_members_role_column",
        "`tenant_members` đã thành VIEW ở v5. Khối này chỉ chạy khi nó còn là "
        "BẢNG, tức trên một cơ sở dữ liệu chưa qua v5.",
        r"ALTER TABLE tenant_members ALTER COLUMN role"),
    _historical(
        "retire_the_viewer_role_value",
        "Vai `viewer` bị bỏ khỏi mô hình phân quyền (13 role, không có "
        "tenant_viewer). Hai câu này gỡ giá trị còn sót ở lời mời và ở "
        "`memberships.legacy_role`.",
        r"SET (legacy_)?role = NULL WHERE (legacy_)?role = 'viewer'"),
    _historical(
        "drop_global_class_uniques",
        "Hai chỉ mục duy nhất TOÀN CỤC trên `classes` chặn hai tenant dùng "
        "cùng một slug. v3 thay bằng khoá ghép có `tenant_id`.",
        r"DROP INDEX IF EXISTS uq_classes_"),
    _historical(
        "normalise_empty_strings_to_null",
        "Sáu cột từng nhận chuỗi rỗng thay cho NULL, làm mọi phép `IS NULL` "
        "sai. Đường ghi đã sửa; sáu câu này dọn dữ liệu cũ.",
        r"UPDATE (classes|dialects|samples) SET \w+ = NULL WHERE \w+ = ''"),
    _historical(
        "seed_language_registry_from_data",
        "Bảng `languages` ra đời sau khi `classes.language` đã có dữ liệu tự "
        "do; câu này dựng danh mục từ chính các giá trị đang dùng.",
        r"INSERT INTO languages \(code, name\) SELECT DISTINCT"),
    _historical(
        "seed_vocabulary_groups_from_classes",
        "Cùng hình dạng với `languages`: nhóm từ vựng vốn là chuỗi tự do trên "
        "`classes`, được nâng thành bảng riêng.",
        r"INSERT INTO vocabulary_groups .* SELECT DISTINCT"),
    # `seed_signers_from_samples` ĐÃ GỠ 24/08/2026, cùng lượt với câu nó phân
    # loại. Giữ lại một nhóm lịch sử cho câu đã biến mất chính là thứ
    # `test_every_historical_group_matches_a_real_statement` gọi là "cửa mở sẵn
    # không ai còn đi qua": nếu sau này ai dựng lại một câu
    # `INSERT INTO signers … SELECT DISTINCT`, bộ phân loại sẽ vẫy nó qua với
    # nhãn "lịch sử" thay vì bắt người viết giải trình.
    #
    # Câu bị gỡ là câu tự sinh `signers` để khoá ngoại chịu đi qua — nó đã gộp
    # sáu người thật thành `S010`. Xem chú thích ở chỗ nó từng đứng trong
    # `metadata_db.MIGRATION_STATEMENTS`, và `tests/test_no_synthetic_signer.py`.
    _historical(
        "build_capture_sessions_from_samples",
        "Phiên thu ra đời ở v4 và được dựng lại từ mẫu đã có, rồi gắn ngược "
        "vào `samples.capture_session_id`. Mẫu mới tạo phiên ngay khi thu.",
        r"INSERT INTO capture_sessions .* SELECT gen_random_uuid|"
        r"UPDATE samples s SET capture_session_id"),
    _historical(
        "convert_signer_external_id_to_uuid",
        "`signers.external_user_id` từng là TEXT; đổi sang UUID để khoá ngoại "
        "sang `users` dựng được. Giá trị không parse nổi được ghi vào `note`.",
        r"column_name = 'external_user_id' AND data_type"),
    _historical(
        "replace_single_column_class_foreign_key",
        "`samples_class_uid_fkey` chỉ một cột nên cho mẫu của tenant A trỏ "
        "sang lớp của tenant B. Thay bằng khoá ghép `fk_samples_class_tenant`.",
        r"conname = 'fk_samples_class_tenant'"),
    _historical(
        "drop_dead_user_profiles",
        "`user_profiles` chưa từng có dòng nào và không mã nào đọc. Chỉ bỏ khi "
        "đếm được 0 dòng.",
        r"to_regclass\('public\.user_profiles'\)"),
    _historical(
        "backfill_tenant_plan_codes",
        "Gói dịch vụ ra đời ở v4.3; tenant có trước đó chưa có `plan_code`. "
        "Tenant khởi tạo từng lấy `internal`, nhưng gói đó đã bị gỡ khỏi bảng "
        "`plans` ở v6 — trên máy cài mới nó làm `fk_tenants_plan` đổ. Nay lấy "
        "`enterprise`; regex nhận cả ba giá trị để máy đã chạy vẫn khớp.",
        r"UPDATE tenants SET plan_code = '(internal|school|enterprise)' "
        r"WHERE plan_code IS NULL"),
    _historical(
        "tighten_tenant_plan_code_to_not_null",
        "Siết `NOT NULL` sau khi backfill ở trên đã lấp hết. Chỉ chạy khi cột "
        "còn nullable và không còn dòng nào NULL.",
        r"column_name = 'plan_code' AND is_nullable"),
    _historical(
        "open_first_subscription_row",
        "Mỗi tenant cần một dòng đăng ký đang mở; v4.3 sinh nó từ gói đang có "
        "hiệu lực. Tenant mới tạo dòng này ngay khi đăng ký.",
        r"INSERT INTO tenant_subscriptions .* SELECT gen_random_uuid"),
    _historical(
        "drop_legacy_actor_foreign_key",
        "`legal_document_events.actor_user_id` từng khoá ngoại sang `users`, "
        "nhưng nhật ký pháp lý phải sống lâu hơn tài khoản đã xoá.",
        r"conname = 'legal_document_events_actor_user_id_fkey'"),
    _historical(
        "reserve_the_community_tenant_type",
        "Tenant `community` là mặt phẳng dùng chung của registry ba mặt "
        "phẳng; câu này gắn cờ hệ thống cho dòng đã tạo trước khi có cột.",
        r"UPDATE tenants SET tenant_type = 'COMMUNITY'"),
    _historical(
        "rename_roles_primary_key",
        "`roles.id` -> `roles.role_id` khi bảng được đổi hình tại chỗ ở v5.",
        r"column_name = 'id' \) AND NOT EXISTS[\s\S]*column_name = 'role_id'"),
    _historical(
        "rename_roles_name_to_role_code",
        "`roles.name` -> `roles.role_code` trong cùng lượt đổi hình v5. Đổi "
        "tại chỗ chứ không tạo bảng `roles_v2`, vì một bảng mới bên cạnh một "
        "bảng chết là thứ sẽ còn đó ba năm nữa.",
        r"column_name = 'name' \) AND NOT EXISTS[\s\S]*column_name = 'role_code'"),
    _historical(
        "drop_vestigial_roles_name",
        "Bỏ cột `roles.name` sau khi `role_code` đã lấp đủ. Chỉ bỏ khi không "
        "còn dòng nào có `name` mà thiếu `role_code`.",
        r"ALTER TABLE roles DROP COLUMN name"),
    _historical(
        "backfill_role_display_name",
        "`role_name` thêm sau; dòng cũ lấy tạm `role_code` làm tên hiển thị.",
        r"UPDATE roles SET role_name = role_code WHERE role_name IS NULL"),
    _historical(
        "rename_builtin_role_codes",
        "Năm mã role dựng sẵn đổi tên ở v5 (`platform_admin` -> "
        "`platform_administrator`, ...). Chỉ đổi khi mã mới chưa tồn tại.",
        r"UPDATE roles SET role_code = '\w+' WHERE role_code = '\w+'"),
    _historical(
        "adopt_stray_global_roles",
        "Role phạm vi toàn cục do hệ cũ để lại được NHẬN NUÔI (đánh dấu dựng "
        "sẵn, tắt đi) chứ không xoá — xoá thì mất dấu vết ai từng có quyền gì.",
        r"UPDATE roles SET is_builtin = TRUE, is_active = FALSE"),
    _historical(
        "drop_roles_name_unique",
        "`roles_name_key` là ràng buộc duy nhất trên cột `name` đã bỏ. Không "
        "dựng lại: khoá duy nhất mới là `(tenant_id, role_code)`.",
        r"DROP CONSTRAINT IF EXISTS roles_name_key"),
    _historical(
        "close_system_permissions_to_custom_roles",
        "Quyền phạm vi SYSTEM không được gán cho role tự tạo. Câu này sửa các "
        "dòng danh mục đã seed trước khi luật đó có.",
        r"UPDATE permissions SET is_custom_role_allowed = FALSE"),
    _historical(
        "migrate_tenant_members_to_memberships",
        "Tám bảng phân quyền gộp còn hai ở v5; đây là lượt chép dữ liệu từ "
        "`tenant_members` sang `memberships`.",
        r"tablename = 'tenant_members'\) THEN INSERT INTO memberships"),
    _historical(
        "migrate_system_roles_to_assignments",
        "Cùng lượt gộp v5: `system_user_roles` -> `role_assignments`.",
        # Phải kèm `INSERT INTO role_assignments`. Bản đầu chỉ khớp
        # `to_regclass('system_user_roles')` và nuốt luôn câu BỎ bảng cũ — câu
        # đó cũng nhắc tên bảng này. Hai câu vẫn cùng mặt phẳng nên không có
        # hậu quả về hành vi, nhưng câu bỏ bảng bị dán nhãn sai và nhóm
        # `drop_legacy_membership_tables` thành nhóm chết.
        r"to_regclass\('system_user_roles'\)[\s\S]*INSERT INTO role_assignments"),
    _historical(
        "drop_legacy_membership_tables",
        "Bỏ các bảng của hệ cũ, và chỉ bỏ khi đã đếm được số dòng đích khớp "
        "số dòng nguồn.",
        r"to_regclass\('workspace_member_roles'\)"),
)


def _matching_historical(canonical: str) -> HistoricalMigration | None:
    for entry in HISTORICAL_MIGRATIONS:
        if entry.pattern.search(canonical):
            return entry
    return None


def _matching_exception(canonical: str) -> StartupException | None:
    for exc in STARTUP_EXCEPTIONS:
        if exc.fingerprint in canonical:
            return exc
    return None


def _mutating_verbs_in(canonical: str) -> list[str]:
    return [name for name, rx in _MUTATING_VERBS if rx.search(canonical)]


def _classify_do_block(canonical: str) -> tuple[str | None, str]:
    """Khối `DO $$` được xét bằng những gì nó LÀM, không bằng những gì nó trông.

    Trong tập hiện tại có 42 khối. Phần lớn là mẫu "thêm ràng buộc nếu chưa có"
    — thuần cộng thêm. Nhưng cùng hình dạng đó cũng chứa một câu đổi kiểu cột
    sang `uuid`, hai câu đổi tên cột, một câu `SET NOT NULL`. Nếu xét theo hình
    dạng ngoài thì cả bốn được coi là an toàn.
    """
    verbs = _mutating_verbs_in(canonical)
    if verbs:
        return None, f"khối DO chứa {', '.join(verbs)}"

    # `DROP CONSTRAINT` bên trong một khối chỉ an toàn khi chính khối đó dựng
    # lại đúng cái tên vừa bỏ. Khối là MỘT giao dịch, nên bỏ-rồi-dựng ở đây
    # không để lại khe hở nào; còn bỏ mà không dựng thì là xoá vĩnh viễn, chỉ
    # khác ở chỗ nó nấp sau một câu `IF EXISTS`.
    dropped = set(_DROP_CONSTRAINT_IN_BODY.findall(canonical))
    if dropped:
        added = set(_ADD_CONSTRAINT_IN_BODY.findall(canonical))
        orphan = sorted(dropped - added)
        if orphan:
            return None, ("khối DO bỏ ràng buộc mà không dựng lại: "
                          + ", ".join(orphan))

    return "do_block_additive", "khối DO chỉ cộng thêm"


def _classify_one(statement: str, group: str,
                  recreated: Mapping[str, set[str]]) -> Verdict:
    canonical = canonical_sql(statement)

    # LỊCH SỬ xét trước mọi thứ: đó là một quyết định của con người, và nó nói
    # nhiều hơn bất kỳ suy luận nào từ hình dạng câu lệnh.
    historical = _matching_historical(canonical)
    if historical is not None:
        return Verdict(statement, group, f"historical:{historical.label}",
                       historical.reason, HISTORICAL_ONLY)

    exc = _matching_exception(canonical)
    if exc is not None:
        if exc.guard.upper() not in canonical.upper():
            return Verdict(statement, group, None,
                           f"ngoại lệ `{exc.label}` khai chốt chặn "
                           f"`{exc.guard}` nhưng câu lệnh không còn chốt đó",
                           MIGRATION_ONLY)
        return Verdict(statement, group, f"exception:{exc.label}", exc.reason,
                       STARTUP_SAFE)

    for name, rx in _SAFE_SHAPES:
        match = rx.match(canonical)
        if not match:
            continue

        if name == "do_block_additive":
            shape, detail = _classify_do_block(canonical)
            plane = STARTUP_SAFE if shape else MIGRATION_ONLY
            return Verdict(statement, group, shape, detail, plane)

        if name in _PAIRED_DROP_SHAPES:
            kind, label_vi = _PAIRED_DROP_SHAPES[name]
            dropped = match.group("name")
            if dropped not in recreated[kind]:
                return Verdict(
                    statement, group, None,
                    f"bỏ {label_vi} `{dropped}` mà không có câu nào dựng lại — "
                    f"đây là XOÁ, không phải mẫu bỏ-rồi-dựng", MIGRATION_ONLY)
            return Verdict(statement, group, name,
                           f"bỏ {label_vi} `{dropped}`, dựng lại ngay trong cùng "
                           f"lượt chạy", STARTUP_SAFE)

        verbs = _mutating_verbs_in(canonical)
        if verbs:
            return Verdict(statement, group, None,
                           f"hình dạng `{name}` nhưng chứa {', '.join(verbs)}",
                           MIGRATION_ONLY)
        return Verdict(statement, group, name, f"hình dạng `{name}`", STARTUP_SAFE)

    # Hai kết cục cuối, và chúng KHÁC nhau. "Biết là nguy hiểm" thì đã có tên
    # gọi và chỉ cần người quyết nó thuộc phiên bản nào. "Chưa biết là gì" thì
    # chưa ai từng nhìn câu này — và đó là trạng thái phải làm test đỏ, vì im
    # lặng cho qua chính là mô hình cũ: "không thấy nguy hiểm thì cho chạy".
    verbs = _mutating_verbs_in(canonical)
    if verbs:
        return Verdict(statement, group, None,
                       f"chứa {', '.join(verbs)}; chưa ai nhận nó thuộc phiên "
                       f"bản migration nào", MIGRATION_ONLY)
    return Verdict(statement, group, None, "không khớp hình dạng nào", UNKNOWN)


# ---------------------------------------------------------------------------
# Tập câu lệnh và bộ nhớ đệm
# ---------------------------------------------------------------------------

def startup_corpus() -> dict[str, tuple[str, ...]]:
    """Mọi danh sách mà `_apply_schema` chạy, KHÔNG lọc gì.

    Nạp muộn vì `metadata_db` gọi ngược lại tệp này từ `one_way_statements()`;
    nhập ở tầng module sẽ thành vòng.
    """
    from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS
    from app.storage.metadata_db import (
        DDL_STATEMENTS, INDEX_STATEMENTS, MIGRATION_STATEMENTS, TENANT_FK_LOOP_SQL,
    )
    from app.storage.rls import rls_ddl
    from app.storage.schema_version import SCHEMA_VERSION_DDL

    return {
        "SCHEMA_VERSION_DDL": tuple(SCHEMA_VERSION_DDL),
        "DDL_STATEMENTS": tuple(DDL_STATEMENTS),
        "MIGRATION_STATEMENTS": tuple(MIGRATION_STATEMENTS),
        "AUTHZ_DDL_STATEMENTS": tuple(AUTHZ_DDL_STATEMENTS),
        "TENANT_FK_LOOP_SQL": (TENANT_FK_LOOP_SQL,),
        "INDEX_STATEMENTS": tuple(INDEX_STATEMENTS),
        "rls_ddl": tuple(rls_ddl()),
    }


#: Ba danh sách còn lại chạy KHÔNG qua bộ lọc `startup_safe()`:
#:
#:   SCHEMA_VERSION_DDL   cổng phiên bản phải đọc được sổ đăng bạ trước đã
#:   TENANT_FK_LOOP_SQL   vòng lặp khoá ngoại, phát lần thứ ba
#:   rls_ddl              cài chính sách cách ly tenant
#:
#: Với chúng, bộ phân loại chỉ KIỂM được chứ không LỌC được — nên
#: `test_the_unfilterable_lists_are_all_startup_safe` phải luôn xanh.
UNFILTERABLE_GROUPS = frozenset({
    "SCHEMA_VERSION_DDL", "TENANT_FK_LOOP_SQL", "rls_ddl",
})


def classify_corpus(corpus: Mapping[str, Sequence[str]] | None = None
                    ) -> tuple[Verdict, ...]:
    """Phán quyết cho mọi câu trong tập, giữ nguyên thứ tự."""
    if corpus is None:
        corpus = startup_corpus()
    frozen = tuple((name, tuple(stmts)) for name, stmts in corpus.items())
    return _classify_cached(frozen)


@lru_cache(maxsize=8)
def _classify_cached(frozen: tuple[tuple[str, tuple[str, ...]], ...]
                     ) -> tuple[Verdict, ...]:
    # Khoá của bộ nhớ đệm là NỘI DUNG tập câu lệnh, không phải một cờ "đã chạy
    # chưa". Bộ test sửa các danh sách tại chỗ để đo độ nhạy của checksum; một
    # bộ đệm khoá theo cờ sẽ trả lại kết quả cũ và làm phép đo đó vô nghĩa.
    everything = "\n".join(
        canonical_sql(s) for _, stmts in frozen for s in stmts)
    recreated = {kind: set(rx.findall(everything))
                 for kind, rx in _RECREATED_PATTERNS.items()}

    return tuple(
        _classify_one(stmt, group, recreated)
        for group, stmts in frozen
        for stmt in stmts
    )


def migration_only_statements(corpus: Mapping[str, Sequence[str]] | None = None
                              ) -> frozenset[str]:
    """Mọi câu KHÔNG chứng minh được là an toàn lúc khởi động.

    Đây là nửa "khoá tương lai" của cặp khoá. Nửa kia — checksum — khoá quá
    khứ: nội dung một migration đã áp dụng không đổi được nữa. Ghép lại,
    một câu DDL mới hoặc phải nói được nó thuộc hình dạng an toàn nào, hoặc
    phải đi qua một lượt migration có người ra lệnh và có phiên bản mới.

    `corpus` chỉ để bộ test dựng tập giả. Đường sản xuất luôn để None.

    Tên hàm giữ nguyên vì `metadata_db.one_way_statements()` gọi nó, nhưng
    nghĩa rộng hơn tên: nó trả về CẢ BA mặt phẳng không được chạy lúc khởi
    động — `historical-only`, `migration-only`, và `unknown`. Xem
    `statements_by_plane()` khi cần phân biệt.
    """
    return frozenset(
        v.statement for v in classify_corpus(corpus)
        if not v.is_startup_safe and v.group not in UNFILTERABLE_GROUPS
    )


def statements_by_plane(corpus: Mapping[str, Sequence[str]] | None = None
                        ) -> dict[str, list[Verdict]]:
    """Phán quyết gom theo mặt phẳng — dùng cho báo cáo và cho test."""
    planes: dict[str, list[Verdict]] = {
        STARTUP_SAFE: [], HISTORICAL_ONLY: [], MIGRATION_ONLY: [], UNKNOWN: [],
    }
    for verdict in classify_corpus(corpus):
        planes[verdict.plane].append(verdict)
    return planes

"""Pull + apply the latest SOT version — READER path (server/VPS, read-only).

Runs at deploy time BEFORE any worker, and NEVER writes to the store. Order:

  1. Read LATEST.json + LATEST.sig, VERIFY the signature against the committed
     authorized keys. Unsigned/forged => REJECT, touch nothing.
  2. Read that version's manifest + signature, VERIFY it too, and confirm
     LATEST actually points at this manifest (sha256 match).
  3. Download each catalog CSV and check its sha256 against the signed manifest.
     Any mismatch (tamper / truncated) => REJECT, touch nothing.
  4. Apply the schema idempotently, then confirm every required column exists
     (schema must be a SUPERSET of SOT — extra columns are fine, missing is not).
  5. Upsert every SOT row (superset data sync): add/update, NEVER delete rows the
     server has beyond SOT.

All DB operations are injected so this is unit-testable without Postgres; the
production wiring lives in `run_sync()`.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from app.sot import keys, manifest as m
from app.sot.store import SotStore, read_text

logger = logging.getLogger(__name__)


class SotSyncRejected(RuntimeError):
    """Raised when SOT content fails verification; the DB is left untouched."""


@dataclass
class SyncResult:
    status: str
    version: Optional[str] = None
    signed_by: Optional[str] = None
    schema_applied: bool = False
    schema_gaps: List[str] = field(default_factory=list)
    #: Câu bị bỏ THEO CHÍNH SÁCH vì dựng lại đối tượng đã retire — bình thường.
    schema_skipped_retired: List[str] = field(default_factory=list)
    #: Câu thất bại NGOÀI DỰ KIẾN. Có phần tử ở đây thì `status` phải nói ra.
    schema_failed: List[str] = field(default_factory=list)
    rows_upserted: Dict[str, int] = field(default_factory=dict)
    rows_failed: Dict[str, int] = field(default_factory=dict)
    server_extras: Dict[str, int] = field(default_factory=dict)
    reason: Optional[str] = None


# Injected DB surface — bound to metadata_db in run_sync(), faked in tests.
@dataclass
class CatalogSink:
    apply_schema: Callable[[str], None]
    column_exists: Callable[[str, str], bool]
    count_rows: Callable[[str], int]
    upsert_class: Callable[[dict], None]
    upsert_sample: Callable[[dict], None]
    upsert_raw_upload: Callable[[dict], None]


# Which CSV feeds which table + upsert.
_CSV_TABLE = {
    "labels.csv": "classes",
    "samples.csv": "samples",
    "raw_uploads.csv": "raw_uploads",
}


def _parse_csv(data: bytes) -> List[dict]:
    return list(csv.DictReader(io.StringIO(data.decode("utf-8"))))


def _read_or_reject(store: SotStore, rel_path: str, what: str) -> bytes:
    """Read a file the version/manifest promises exists.

    A missing file means the publish is INCOMPLETE (not every file uploaded) or a
    file was renamed/removed on the store. Turn that into a clean SotSyncRejected
    so `_cmd_sync` reports "REJECTED (DB untouched)" and exits 4 — instead of the
    raw FileNotFoundError bubbling up as an uncaught traceback + exit 1, which
    hides the real cause (exactly the confusing failure a renamed labels.csv gave).
    """
    try:
        return store.read_bytes(rel_path)
    except FileNotFoundError as exc:
        raise SotSyncRejected(
            f"incomplete SOT version: missing {what} ({rel_path}) — the publish did "
            "not upload every file, or a file was renamed/removed on the store"
        ) from exc


def sync_from_sot(store: SotStore, sink: CatalogSink, *, authorized_keys: List[dict]) -> SyncResult:
    # --- 1. LATEST + signature ------------------------------------------------
    if not store.exists(m.LATEST_NAME):
        return SyncResult(status="empty", reason="no LATEST.json in SOT (nothing published yet)")

    latest_bytes = store.read_bytes(m.LATEST_NAME)
    try:
        latest_sig = read_text(store, m.LATEST_SIG_NAME)
    except Exception as exc:
        raise SotSyncRejected(f"LATEST.sig missing/unreadable: {exc}") from exc

    if keys.verify_with_authorized(latest_bytes, latest_sig, authorized_keys) is None:
        raise SotSyncRejected("LATEST.json signature not from any registered machine — rejected")

    import json

    latest = json.loads(latest_bytes.decode("utf-8"))
    version = latest.get("version")
    parsed = m.parse_version_name(str(version or ""))
    if not parsed:
        raise SotSyncRejected(f"LATEST points at invalid version name: {version!r}")

    # --- 2. Manifest + signature ---------------------------------------------
    manifest_bytes = _read_or_reject(store, f"{version}/{m.MANIFEST_NAME}", "manifest.json")
    manifest_sig = _read_or_reject(store, f"{version}/{m.MANIFEST_SIG_NAME}", "manifest.sig").decode("utf-8")
    signed_by = keys.verify_with_authorized(manifest_bytes, manifest_sig, authorized_keys)
    if signed_by is None:
        raise SotSyncRejected(f"{version} manifest signature invalid — rejected")

    if latest.get("manifest_sha256") != m.sha256_bytes(manifest_bytes):
        raise SotSyncRejected("LATEST.manifest_sha256 does not match the version's manifest")

    manifest = json.loads(manifest_bytes.decode("utf-8"))
    m.validate_manifest_shape(manifest)
    if manifest.get("version") != version:
        raise SotSyncRejected("manifest.version disagrees with LATEST.version")

    # --- 3. Download + checksum every catalog file ---------------------------
    file_hashes = manifest["files"]
    csv_bytes: Dict[str, bytes] = {}
    for name in m.CATALOG_FILES:
        data = _read_or_reject(store, f"{version}/{name}", name)
        expected = file_hashes.get(name)
        if expected != m.sha256_bytes(data):
            raise SotSyncRejected(f"{name} checksum mismatch (tampered/truncated) — rejected")
        csv_bytes[name] = data

    schema_sql = _read_or_reject(store, f"{version}/schema/schema.sql", "schema/schema.sql")
    if file_hashes.get("schema/schema.sql") != m.sha256_bytes(schema_sql):
        raise SotSyncRejected("schema.sql checksum mismatch — rejected")

    result = SyncResult(status="applied", version=version, signed_by=signed_by)

    # --- 4. Schema: apply idempotently, then verify SUPERSET coverage --------
    # `apply_schema` trả về `SchemaApplyReport`; các hàm giả trong bộ kiểm vẫn
    # trả `None`, nên đọc phòng thủ thay vì bắt mọi nơi phải đổi cùng lúc.
    bao_cao = sink.apply_schema(schema_sql.decode("utf-8"))
    result.schema_applied = True
    if bao_cao is not None:
        result.schema_skipped_retired = list(getattr(bao_cao, "skipped_retired", []))
        result.schema_failed = list(getattr(bao_cao, "failed", []))
    for table, cols in manifest.get("required_columns", {}).items():
        for col in cols:
            if not sink.column_exists(table, col):
                result.schema_gaps.append(f"{table}.{col}")
    if result.schema_gaps:
        # Schema is NOT a superset — do not import data against an incomplete schema.
        raise SotSyncRejected(
            f"schema missing required columns after apply: {result.schema_gaps}"
        )

    # --- 5. Data: superset upsert (add/update, never delete server extras) ----
    upsert_by_table = {
        "classes": sink.upsert_class,
        "samples": sink.upsert_sample,
        "raw_uploads": sink.upsert_raw_upload,
    }
    for name in m.CATALOG_FILES:
        table = _CSV_TABLE[name]
        rows = _parse_csv(csv_bytes[name])
        upsert = upsert_by_table[table]
        # Per-row isolation: the content is already signature+checksum verified,
        # so a row that fails here is an operational hiccup (e.g. a stray bad
        # row / constraint), NOT tampering. Skip it and keep going rather than
        # aborting the whole sync — a single row must not block the deploy.
        # Each upsert() is its own DB transaction, so a failure rolls back only
        # that row and never poisons the ones after it.
        ok = 0
        failed = 0
        for row in rows:
            try:
                upsert(row)
                ok += 1
            except Exception as exc:
                failed += 1
                logger.warning("[SOT] %s: skipped a row that failed to upsert: %s", table, exc)
        result.rows_upserted[table] = ok
        if failed:
            result.rows_failed[table] = failed
        # Superset visibility: how many rows the server has beyond SOT.
        try:
            extra = sink.count_rows(table) - len(rows)
            result.server_extras[table] = max(0, extra)
        except Exception:
            pass

    # Một lượt phát lại lược đồ hỏng nửa chừng KHÔNG được mang nhãn "applied".
    #
    # Bản trước ghi mọi thất bại ở mức warning rồi trả về "applied", nên một
    # lượt sync hỏng và một lượt sync sạch đọc lên giống hệt nhau. Trạng thái
    # phải nói ra sự thật, kể cả khi mã thoát vì lý do vận hành vẫn là 0 —
    # xem chú thích ở `app/sot/cli.py`.
    #
    # Bỏ theo chính sách thì KHÔNG đổi trạng thái: đó là kết quả đúng.
    if result.schema_failed:
        result.status = "applied_degraded"

    logger.info(
        "[SOT] synced %s signed_by=%s upserted=%s failed=%s extras=%s "
        "schema_bo_qua_retire=%s schema_that_bai=%s",
        version, signed_by, result.rows_upserted, result.rows_failed,
        result.server_extras, result.schema_skipped_retired, len(result.schema_failed),
    )
    return result


# ---------------------------------------------------------------------------
# Production wiring
# ---------------------------------------------------------------------------

def effective_authorized_keys() -> List[dict]:
    """Committed baseline (authorized_keys.json) UNION the DB-managed registry.

    The DB registry lets an admin register/revoke writer machines at runtime (via
    the SOT admin page) and have THIS deployment's reader trust them immediately,
    with no git commit + redeploy. The committed file stays the always-on baseline;
    if the DB is unreachable we fall back to it alone — fail-safe, since an outage
    then NARROWS trust (fewer accepted signers), never widens it.
    """
    merged = {
        e.get("public_key"): e
        for e in keys.load_authorized_keys()
        if e.get("public_key")
    }
    try:
        from app.storage import metadata_db as db

        for row in db.sot_list_authorized_keys(include_revoked=False):
            pk = row.get("public_key")
            if pk and pk not in merged:  # committed baseline wins on conflict
                merged[pk] = {
                    "name": row.get("name"),
                    "public_key": pk,
                    "fingerprint": row.get("fingerprint"),
                }
    except Exception as exc:
        logger.warning(
            "[SOT] DB authorized-key lookup failed; using committed baseline only: %s", exc
        )
    return list(merged.values())


def run_sync() -> SyncResult:
    """Entry point for the `sot-init` container / CLI `sync`.

    Binds the injected DB surface to metadata_db + the real Drive store, then
    runs sync_from_sot. Returns a SyncResult; raises SotSyncRejected on bad SOT.
    """
    from app.sot.store import GDriveSotStore
    from app.storage import metadata_db as db

    store = GDriveSotStore(read_only=True)
    sink = CatalogSink(
        apply_schema=_apply_schema_sql,
        column_exists=db._column_exists,
        count_rows=lambda t: db._fetch_all(f"SELECT COUNT(*) AS c FROM {t}")[0]["c"],
        upsert_class=db.upsert_class,
        upsert_sample=db.upsert_sample,
        upsert_raw_upload=db.upsert_raw_upload,
    )
    authorized = effective_authorized_keys()
    return sync_from_sot(store, sink, authorized_keys=authorized)


_DOLLAR_TAG_RE = re.compile(r"\$[A-Za-z0-9_]*\$")


def _split_sql_statements(sql: str) -> List[str]:
    """Split SQL on top-level ';' only.

    A naive ``sql.split(';')`` breaks the moment a statement legitimately
    contains a ';' — e.g. a future trigger / PL-pgSQL function body wrapped in
    ``$$ ... ; ... $$`` — silently dropping half a CREATE and leaving the table
    unbuilt. This respects single-quoted strings, ``$tag$``-dollar-quoted blocks
    and SQL comments so the whole body stays one statement.

    Comments were the gap. `--` and `/* */` were passed straight through, so a
    prose sentence inside a schema comment split the statement in two the moment
    it contained a semicolon — which ordinary English does, in the exact place a
    comment is most likely to be explaining a trade-off. The failure is not a
    syntax error at review time: the export looks fine, and the deploy applies
    half a CREATE TABLE. Found when a comment added to `tenant_invitations` made
    the schema round-trip to 108 statements instead of 107.
    """
    stmts: List[str] = []
    buf: List[str] = []
    i, n = 0, len(sql)
    in_squote = False
    in_line_comment = False
    in_block_comment = False
    dollar_tag: Optional[str] = None
    while i < n:
        ch = sql[i]
        if in_line_comment:
            buf.append(ch)
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue
        if in_block_comment:
            buf.append(ch)
            if ch == "*" and sql.startswith("*/", i):
                buf.append("/")
                i += 2
                in_block_comment = False
            else:
                i += 1
            continue
        if dollar_tag is None and not in_squote:
            # Only outside a string: `--` inside '...' is data, not a comment.
            if sql.startswith("--", i):
                in_line_comment = True
                buf.append(ch)
                i += 1
                continue
            if sql.startswith("/*", i):
                in_block_comment = True
                buf.append(ch)
                i += 1
                continue
        if dollar_tag is not None:
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buf.append(ch)
                i += 1
            continue
        if in_squote:
            buf.append(ch)
            if ch == "'":
                in_squote = False
            i += 1
            continue
        if ch == "'":
            in_squote = True
            buf.append(ch)
            i += 1
            continue
        if ch == "$":
            mt = _DOLLAR_TAG_RE.match(sql, i)
            if mt:
                tag = mt.group(0)
                dollar_tag = tag
                buf.append(tag)
                i += len(tag)
                continue
        if ch == ";":
            stmts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf)
    if tail.strip():
        stmts.append(tail)
    return [s.strip() for s in stmts if s.strip()]


@dataclass
class SchemaApplyReport:
    """Chuyện gì đã xảy ra với từng câu trong bản chụp lược đồ của gói SOT."""

    applied: int = 0
    #: Bỏ qua THEO CHÍNH SÁCH — câu này định dựng lại một đối tượng đã retire.
    #: Đây là kết quả ĐÚNG, không phải lỗi.
    skipped_retired: List[str] = field(default_factory=list)
    #: Câu thất bại NHƯNG hậu điều kiện của nó ĐÃ ĐÚNG SẴN, và điều đó được
    #: CHỨNG MINH bằng truy vấn catalog — không phải suy từ chuỗi lỗi.
    already_satisfied: List[str] = field(default_factory=list)
    #: Thất bại NGOÀI DỰ KIẾN. Không được lẫn với hai loại trên, và không được im.
    failed: List[str] = field(default_factory=list)


def _apply_schema_sql(schema_sql: str) -> SchemaApplyReport:
    """Áp bản chụp lược đồ của gói SOT — nhưng KHÔNG cho nó vượt quyền migration.

    Uses the migration role: this is DDL arriving from a signed snapshot, and
    the application role is deliberately unable to alter tables (see
    `storage/rls.py`). Before the role split this went through the shared
    application pool, which would now log every statement as skipped and leave a
    reader machine silently one schema version behind.

    Chốt chặn đối tượng đã retire (15/08/2026)
    ------------------------------------------
    Gói SOT mang một bản chụp ĐÔNG LẠNH của lược đồ tại thời điểm publish. Gói
    `Ver5_06082026` — ký hợp lệ, chữ ký đúng, không hề bị sửa — ra đời TRƯỚC khi
    `region` bước vào định danh lớp, nên nó chứa:

        CREATE UNIQUE INDEX IF NOT EXISTS uq_classes_tenant_slug_lang_dialect …

    và KHÔNG chứa bản có `region`. Phát lại nguyên văn ở mỗi lượt sync nghĩa là
    `migrate` gỡ chỉ mục rồi `sot_init` dựng lại nó ngay trong cùng lượt triển
    khai. Đo được ngày 15/08: `migrate --status` xanh trước `up -d`, đỏ sau.

    Chữ ký hợp lệ chứng minh gói KHÔNG BỊ SỬA. Nó không chứng minh nội dung còn
    ĐÚNG với hệ thống hôm nay. Đó là hai câu hỏi khác nhau, và trước hôm nay chỉ
    câu thứ nhất được hỏi.

    Danh sách retire lấy từ `metadata_db.creates_retired_object()` — cùng nguồn
    mà `migrate --status` dùng. Một danh sách riêng cho SOT sẽ trôi khỏi nó.

    Vì sao KHÔNG còn nuốt lỗi im lặng
    ---------------------------------
    Bản trước ghi mọi thất bại ở mức `warning` rồi đi tiếp, và `sync` vẫn báo
    "applied". Một lượt phát lại hỏng nửa chừng trông y hệt một lượt thành công.
    Nay hai loại được tách bạch và cùng được trả về cho người gọi: bỏ theo chính
    sách là bình thường, còn thất bại ngoài dự kiến thì ghi mức `error` và làm
    trạng thái sync đổi.
    """
    from app.storage.metadata_db import _migration_cursor, creates_retired_object

    report = SchemaApplyReport()
    with _migration_cursor() as cur:
        for stmt in _split_sql_statements(schema_sql):
            da_retire = creates_retired_object(stmt)
            if da_retire:
                report.skipped_retired.append(da_retire)
                logger.warning(
                    "[SOT] BO QUA theo chinh sach: goi nay dung lai doi tuong DA "
                    "RETIRE '%s'. Goi duoc ky truoc khi doi tuong bi go; migration "
                    "hien hanh moi la nguon su that ve luoc do. Cau: %s",
                    da_retire, " ".join(stmt.split())[:120],
                )
                continue
            try:
                cur.execute(stmt)
                report.applied += 1
                continue
            except Exception as exc:
                loi_goc = exc

            # Câu hỏi DUY NHẤT được phép cứu một câu thất bại:
            # "trạng thái mà câu này muốn tạo ra, hiện đã đúng chưa?"
            #
            # KHÔNG bắt chuỗi "already exists" rồi coi là xong. Cùng một tên
            # ràng buộc nhưng ĐỊNH NGHĨA khác nhau cũng cho đúng câu lỗi ấy, và
            # nuốt nó là che một lược đồ đã trôi — tệ hơn hẳn việc báo lỗi.
            ten = _postcondition_da_dung(cur, stmt)
            if ten:
                report.already_satisfied.append(ten)
                logger.info(
                    "[SOT] '%s' da o trang thai dich (dinh nghia KHOP) — bo qua "
                    "cau tao lai", ten)
                continue

            loi = f"{' '.join(stmt.split())[:100]} -> {loi_goc}"
            report.failed.append(loi)
            logger.error("[SOT] schema stmt THAT BAI (ngoai du kien): %s", loi)
    return report


_RE_ADD_CONSTRAINT = re.compile(
    r"^\s*ALTER\s+TABLE\s+(?:ONLY\s+)?([A-Za-z_][\w]*)\s+ADD\s+CONSTRAINT\s+"
    r"([A-Za-z_][\w]*)\s+(.+)$",
    re.IGNORECASE | re.DOTALL)


def _chuan_hoa_sql(s: str) -> str:
    """Gộp khoảng trắng + bỏ hoa/thường, để so hai định nghĩa cho công bằng."""
    return " ".join(s.split()).rstrip(";").strip().lower()


#: Câu GIEO DỮ LIỆU đời cũ nằm trong bản chụp lược đồ mà sổ đăng ký bước dữ
#: liệu của migration KHÔNG sở hữu — hiện còn đúng MỘT câu.
#:
#: Mỗi mục là (tên định danh, dấu vân tay, mệnh đề chứng minh hậu điều kiện).
#: Mệnh đề phải trả về đúng một giá trị boolean.
#:
#: Vì sao chỉ còn một
#: ------------------
#: Ba câu khác từng phải nằm ở đây — gieo `vocabulary_registry_meta`, bootstrap
#: tenant `default`, gieo tenant `community` — nay đều là bước đã đăng ký ở
#: `metadata_db._data_steps()`, nên nhánh (1) của `_postcondition_da_dung` hỏi
#: thẳng hậu điều kiện GỐC của chúng. Chép mệnh đề chứng minh sang đây lần nữa
#: sẽ tạo hai authority cho cùng một câu hỏi, và cái sai lệch sẽ im lặng.
#:
#: `tenant_subscriptions` ở lại vì nó KHÔNG phải bước migration: nó gieo dựa
#: trên trạng thái đang có (`SELECT ... FROM tenants`), nên không có một "trạng
#: thái đích" cố định để đăng ký.
#:
#: Vì sao là danh sách hẹp chứ không phải luật tổng quát
#: -----------------------------------------------------
#: Luật "INSERT nào hỏng thì đi kiểm hậu điều kiện" biến reader thành công cụ
#: ĐOÁN Ý ĐỊNH của SQL. Một câu INSERT lạ xuất hiện — trong `Ver5` hay gói khác
#: — phải là `schema_failed` cho tới khi có người phân tích nó, chứ không được
#: hưởng ké một cơ chế viết cho những câu đã biết.
#:
#: Các câu này đều là DỮ LIỆU, không phải lược đồ, và đều bị RLS chặn — RLS
#: đang làm đúng việc. Hướng đi lâu dài là gỡ chúng khỏi `export_schema_sql()`
#: cho các gói tương lai; xem
#: docs/10-issues/ISSUE_sot_reader_as_schema_migrator.md. Nhưng `Ver5_06082026`
#: bất biến vẫn mang chúng, nên reader vẫn phải biết cách đối xử.
_LEGACY_SEEDS = (
    (
        "legacy_seed_open_tenant_subscriptions",
        re.compile(r"^\s*INSERT\s+INTO\s+tenant_subscriptions\b", re.IGNORECASE),
        # Hai nửa: phủ đủ (không tenant nào thiếu) VÀ không trùng (không tenant
        # nào có hai đăng ký cùng mở). Chỉ nửa đầu thì một tenant có hai dòng mở
        # vẫn được chấm là "đã đúng".
        # `deleted_at IS NULL` — thêm 16/08/2026. Vế phủ đủ trước đây quét CẢ
        # tenant đã xoá mềm, và một tenant đã xoá thì theo định nghĩa không cần
        # đăng ký đang mở: lượt xoá chính là thứ đóng đăng ký lại.
        #
        # Hậu quả không nằm ở bộ test. Hậu điều kiện này quyết định việc bộ đọc
        # SOT có chấp nhận câu gieo đời cũ là "đã đúng" hay không; sai một lần
        # là câu ấy rơi vào `schema_failed`, và lượt đồng bộ SOT hỏng. Nghĩa là
        # bất kỳ bản cài nào TỪNG xoá mềm một tenant đều không đồng bộ SOT được
        # nữa — một quả mìn hẹn giờ, chỉ nổ sau lần xoá tenant đầu tiên.
        #
        # Đo được trên `signdb_test`: 8 tenant vi phạm, và cả 8 đều đã xoá mềm;
        # tập tenant đang sống sạch hoàn toàn. Bất biến ở `test_schema_v4` vốn
        # đã lọc `deleted_at IS NULL`, nên hai nơi nói về cùng một điều mà lệch
        # nhau đúng ở mệnh đề này.
        "SELECT NOT EXISTS ("
        "  SELECT 1 FROM tenants t WHERE t.plan_code IS NOT NULL"
        "    AND t.deleted_at IS NULL"
        "    AND NOT EXISTS (SELECT 1 FROM tenant_subscriptions s"
        "                    WHERE s.tenant_id = t.tenant_id AND s.ended_at IS NULL)"
        ") AND NOT EXISTS ("
        "  SELECT 1 FROM tenant_subscriptions WHERE ended_at IS NULL"
        "  GROUP BY tenant_id HAVING count(*) > 1"
        ")",
    ),
)


def _chung_minh(cur, ten_luat: str, menh_de: str) -> bool:
    """Chạy một mệnh đề chứng minh trong phạm vi hệ thống HẸP, rồi tắt lại.

    Phạm vi là bắt buộc, không phải tiện tay. Mệnh đề chứng minh hỏi về TOÀN BỘ
    tenant ("không tenant nào thiếu đăng ký đang mở"). Từ 15/08/2026 `tenants`
    bật RLS + FORCE nên vai migration cũng chịu chính sách, và `_migration_cursor`
    KHÔNG tự đặt phạm vi.

    Không có nó thì `NOT EXISTS (SELECT 1 FROM tenants …)` thấy 0 tenant và trả
    TRUE một cách RỖNG TUẾCH: hậu điều kiện được chấm "đã thoả" chính xác vì
    không nhìn thấy gì. Đó là xanh-giả do phép kiểm tự tạo ra cho mình — tệ hơn
    không kiểm, vì nó có vẻ nghiêm.

    Bật rồi TẮT thay vì để nguyên: các câu lược đồ chạy sau trên cùng kết nối
    không có lý do gì được thừa hưởng quyền xuyên tenant.
    """
    from app.storage.rls import SYSTEM_SCOPE_GUC, SYSTEM_SCOPE_ON

    try:
        cur.execute("SELECT set_config(%s, %s, false)",
                    (SYSTEM_SCOPE_GUC, SYSTEM_SCOPE_ON))
        try:
            cur.execute(menh_de)
            return bool(cur.fetchone()[0])
        finally:
            cur.execute("SELECT set_config(%s, %s, false)",
                        (SYSTEM_SCOPE_GUC, ""))
    except Exception as exc:
        logger.error("[SOT] khong kiem duoc hau dieu kien '%s': %s", ten_luat, exc)
        return False


def _postcondition_da_dung(cur, stmt: str) -> Optional[str]:
    """Tên đối tượng/luật nếu trạng thái câu này muốn tạo ĐÃ đúng — hoặc None.

    Ba nhánh, cả ba đều CHỨNG MINH bằng truy vấn chứ không đọc thông điệp lỗi:

      1. Câu này là một BƯỚC ĐỊNH HÌNH DỮ LIỆU của migration — hỏi lại đúng hậu
         điều kiện đã đăng ký ở `metadata_db._data_steps()`.
      2. `ALTER TABLE … ADD CONSTRAINT` — dạng câu duy nhất trong bản chụp mà
         SQL không diễn đạt được `IF NOT EXISTS`. So ĐỊNH NGHĨA lấy từ
         `pg_constraint`; trùng tên mà khác định nghĩa là lược đồ đã trôi, và
         đó là việc phải BÁO chứ không phải việc được bỏ qua.
      3. Câu gieo dữ liệu đời cũ ở `_LEGACY_SEEDS` — phần còn lại, không nằm
         trong sổ đăng ký bước dữ liệu.

    Mọi thứ khác trả None và đi thẳng vào `schema_failed`.

    Vì sao nhánh 1 chỉ KIỂM chứ không CHẠY
    --------------------------------------
    `_run_data_step` của migration mở phạm vi hệ thống rồi CHẠY câu. Reader thì
    không được: hướng đi đã chốt là SOT thôi làm bộ migration lược đồ độc lập
    (docs/10-issues/ISSUE_sot_reader_as_schema_migrator.md). Nên ở đây câu trả
    lời chỉ có hai vế — trạng thái đã đúng thì bỏ qua sạch sẽ, chưa đúng thì
    `schema_failed` và để `app.cli.migrate` sửa. Reader không tự vá dữ liệu.
    """
    # Giao dịch đã hỏng vì câu lỗi ở trên; phải gỡ trước khi truy vấn tiếp.
    try:
        cur.execute("ROLLBACK")
    except Exception:
        pass

    # (1) Sổ đăng ký bước dữ liệu — MỘT nguồn cho cả migration lẫn reader.
    #
    # Khớp theo văn bản đã chuẩn hoá chứ không theo dấu vân tay riêng: hai bên
    # phải nói về ĐÚNG một câu. Chép mệnh đề chứng minh sang đây lần thứ hai là
    # dựng sẵn hai authority cho cùng một câu hỏi, và cái sai lệch sẽ im lặng.
    try:
        from app.storage.metadata_db import _data_steps

        chuan = _chuan_hoa_sql(stmt)
        for ly_do, cac_cau, hau_dieu_kien in _data_steps().values():
            if _chuan_hoa_sql(cac_cau[0]) != chuan:
                continue
            if _chung_minh(cur, ly_do, hau_dieu_kien):
                return ly_do
            logger.error(
                "[SOT] '%s': buoc du lieu that bai VA hau dieu kien CHUA dat. "
                "Reader KHONG tu va — chay `app.cli.migrate` de sua.", ly_do)
            return None
    except ImportError:  # pragma: no cover — chỉ khi cây nhập bị cắt
        logger.error("[SOT] khong doc duoc so dang ky buoc du lieu")

    # (3) Phần còn lại của các câu gieo đời cũ.
    for ten_luat, van_tay, menh_de in _LEGACY_SEEDS:
        if not van_tay.match(stmt.strip()):
            continue
        if _chung_minh(cur, ten_luat, menh_de):
            return ten_luat
        logger.error(
            "[SOT] '%s': cau gieo du lieu doi cu that bai VA hau dieu kien CHUA "
            "dung — day la loi that, khong phai tuong thich nguoc.", ten_luat)
        return None

    m = _RE_ADD_CONSTRAINT.match(stmt.strip())
    if not m:
        return None
    bang, ten, dinh_nghia = m.group(1), m.group(2), m.group(3)

    cur.execute(
        "SELECT pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "WHERE c.conname = %s AND t.relname = %s", (ten, bang))
    hang = cur.fetchone()
    if not hang:
        return None

    hien_tai = _chuan_hoa_sql(hang[0])
    yeu_cau = _chuan_hoa_sql(dinh_nghia)
    if hien_tai == yeu_cau:
        return ten

    # Cùng tên, khác định nghĩa. KHÔNG bỏ qua — đây là lược đồ đã trôi.
    logger.error(
        "[SOT] rang buoc '%s' tren '%s' TRUNG TEN nhung KHAC dinh nghia.\n"
        "      goi yeu cau: %s\n      hien co    : %s",
        ten, bang, yeu_cau[:200], hien_tai[:200])
    return None

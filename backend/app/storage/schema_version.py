"""Phiên bản lược đồ: ai được chạy trên cái gì, và ai được đổi nó.

Vì sao tệp này tồn tại
======================
Ngày 12/08/2026, `ensure_tables()` chạy nhầm lên `signdb` của sản xuất và đưa
sản xuất vào trạng thái **lược đồ v5 / mã v4**. Không mất dữ liệu, nhưng không
ai chọn trạng thái đó, và không bước nào phát hiện ra nó.

Bản vá đầu tiên (`_assert_expected_database`) chặn được lỗi *nhắm sai đích*.
Nó KHÔNG chặn được thứ đã gây ra thiệt hại thật: một lần **khởi động ứng dụng**
tự ý đổi cấu trúc cơ sở dữ liệu. Chừng nào migration phá huỷ còn nằm trên
đường khởi động, mọi `docker compose up` đều là một lượt migration không công
bố.

Nên hợp đồng đổi thành:

    lệnh migration rõ ràng
        -> đổi lược đồ / dữ liệu
        -> đóng dấu phiên bản
        -> kiểm chứng
        -> khởi động ứng dụng
        -> ensure_tables() chỉ THÊM, không phá

và ứng dụng **từ chối khởi động** khi phiên bản không khớp.

Vì sao kiểm HAI CHIỀU
=====================
Chặn "cơ sở dữ liệu quá cũ" là phản xạ tự nhiên, và nó chỉ bắt được một nửa.
Sự cố 12/08 có hình dạng ngược lại::

    lược đồ v5  +  ảnh ứng dụng cũ  ->  mã đọc bảng không còn như nó tưởng

Một ảnh cũ chạy trên lược đồ mới hơn không "thiếu tính năng" — nó đọc và ghi
theo một hình dạng đã đổi. Cho nên khoảng chấp nhận là một **đoạn**::

    MIN_SUPPORTED_SCHEMA_VERSION <= phiên_bản_DB <= APP_SCHEMA_VERSION

Ngoài đoạn đó, ở cả hai đầu, là từ chối khởi động.

Vì sao `MAX(version)` chứ không phải một dòng duy nhất
======================================================
Bảng giữ **lịch sử**, mỗi lần migration một dòng. Một dòng bị ghi đè trả lời
được "bây giờ ở đâu" nhưng không trả lời được "đã đi qua đâu, lúc nào, do ai" —
mà đó chính là câu hỏi của lượt điều tra sự cố vừa rồi.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


#: Phiên bản lược đồ mà ẢNH NÀY viết ra và hiểu được.
#:
#: Tăng con số này khi một lượt thay đổi làm mã CŨ không còn đọc đúng cơ sở dữ
#: liệu MỚI. Thêm một bảng rời thì không cần tăng — mã cũ vẫn đúng, chỉ là
#: không biết bảng đó. Đổi tên cột, gộp bảng, biến bảng thành view thì CÓ.
#:
#: **Con số này KHÔNG được tăng vì lý do phân loại lại DDL.** Ngày 13/08/2026
#: tôi đã định làm vậy — bộ phân loại `startup_ddl_policy` tìm ra 43 câu không
#: chứng minh được là an toàn lúc khởi động, đưa chúng vào tập một chiều thì
#: payload đổi, nên "phải lên phiên bản mới".
#:
#: Lập luận đó lộn ngược nhân quả. Việc phân loại DDL khởi động là *kiến trúc
#: triển khai*, không phải một phiên bản nghiệp vụ của lược đồ. Nếu phân loại
#: lại làm checksum đổi thì lỗi nằm ở chỗ `migration_payload()` được dựng từ
#: một tập DẪN XUẤT — xem chú thích ở đó.
#:
#: v6 KHÔNG còn dành cho Billing (24/08/2026)
#: ------------------------------------------
#: Số này từng được giữ chỗ cho mô hình gói Free/Plus/Pro/Enterprise
#: (`docs/07-business/BILLING_MODEL_V6.md`). Đổi ý có lý do, không phải tiện tay:
#:
#:   Billing v6   chưa hoàn tất, chưa phát hành, chưa có gì trên sản xuất
#:   v6 hiện tại  gỡ một BẤT BIẾN SAI đã được áp lên `signdb` và đang có khả
#:                năng TỪ CHỐI dữ liệu hợp lệ
#:
#: Một lỗi lược đồ đang sống trên sản xuất được ưu tiên hơn việc giữ một con số
#: cho tính năng chưa ra đời.
#:
#: v7 cũng KHÔNG phải Billing (24/08/2026)
#: ---------------------------------------
#: Cùng lý do, lần thứ hai trong một ngày. Khoá ngoại ghép thêm ngày 23/08 làm
#: lộ ra hai giá trị mốc bịa trong `vocabulary_registry_meta.version` (0 lúc
#: clone, DEFAULT 1 lúc gieo), và hậu quả là **tạo tenant mới hỏng**. v7 đổi
#: mốc ấy sang NULL.
#:
#: v8 — Billing, và nó KHÔNG đổi hình dạng gì (25/08/2026)
#: -------------------------------------------------------
#: Mô hình bốn gói đã chạy trên sản xuất từ 13/08 nhưng vào bằng cửa sau: các
#: câu nằm trong `MIGRATION_STATEMENTS` mà không thuộc payload nào, nên chạy
#: lại mỗi lượt migrate và không con số nào ghim được chúng. v8 đặt tên và đóng
#: dấu cho thứ đã tồn tại — no-op trên sản xuất, chạy thật trên bản cài mới, và
#: hai đường phải hội tụ.
APP_SCHEMA_VERSION = 8

#: Lược đồ CŨ NHẤT mà ảnh này còn chạy đúng trên đó.
#:
#: Bằng `APP_SCHEMA_VERSION` nghĩa là: không tương thích ngược. Đó là trạng
#: thái đúng ở đây, vì v5 gộp tám bảng phân quyền thành hai và biến
#: `tenant_members` thành VIEW — mã v4 ghi vào tám bảng đã không còn.
#:
#: Khi nào nới: nếu một lượt tăng phiên bản chỉ THÊM thứ mới và mã mới vẫn đọc
#: được lược đồ cũ, để hằng số này ở lại con số cũ. Khi đó một ảnh mới triển
#: khai được TRƯỚC lượt migration — thứ tự đảo ngược đó là cách duy nhất để
#: triển khai không có thời gian chết.
#:
#: v6 ở lại 5 theo đúng luật đó, dù nó GỠ chứ không thêm: ba câu của v6 chỉ bỏ
#: những thứ mã v6 không còn nhắc tới, nên ảnh v6 chạy đúng trên lược đồ v5.
MIN_SUPPORTED_SCHEMA_VERSION = 5

#: Tên bảng sổ đăng bạ. Số ít chủ ý: nó ghi các lượt ĐÃ ÁP DỤNG, không phải
#: các tệp migration đang chờ.
SCHEMA_VERSION_TABLE = "schema_migrations"


class SchemaVersionError(RuntimeError):
    """Lược đồ và ảnh ứng dụng không dùng được với nhau."""


class SchemaNotMigrated(SchemaVersionError):
    """Cơ sở dữ liệu chưa từng được đóng dấu phiên bản nào."""


class SchemaTooOld(SchemaVersionError):
    """Lược đồ cũ hơn mức ảnh này chạy được."""


class SchemaTooNew(SchemaVersionError):
    """Lược đồ mới hơn mức ảnh này hiểu được — ảnh cũ trên lược đồ mới."""


#: DDL của chính sổ đăng bạ. Nằm ở danh sách THÊM (chạy được lúc khởi động):
#: một bảng trống, không khoá ngoại, không ai đọc ngoài chỗ này. Nếu nó nằm ở
#: danh sách migration thì cổng phiên bản sẽ phải xử lý trường hợp "bảng chưa
#: tồn tại" bằng cách đoán, và đoán là thứ cổng này sinh ra để loại bỏ.
SCHEMA_VERSION_DDL: tuple[str, ...] = (
    f"""
    CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} (
        version     INTEGER NOT NULL,
        applied_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        applied_by  TEXT NOT NULL,
        applied_on  TEXT,
        note        TEXT,
        PRIMARY KEY (version, applied_at)
    )
    """,
    f"CREATE INDEX IF NOT EXISTS ix_{SCHEMA_VERSION_TABLE}_version "
    f"ON {SCHEMA_VERSION_TABLE} (version DESC)",
    # Thêm sau, nên phải là ALTER: bảng đã tồn tại trên sản xuất từ 12/08/2026
    # với bốn cột đầu. Cột này KHÔNG có DEFAULT và cố ý để NULL trên dòng cũ —
    # NULL nghĩa là "chưa ai xác nhận", và nó phải khác với "đã xác nhận".
    f"ALTER TABLE {SCHEMA_VERSION_TABLE} "
    f"ADD COLUMN IF NOT EXISTS migration_checksum TEXT",
)


# ---------------------------------------------------------------------------
# Checksum: nội dung một migration ĐÃ ÁP DỤNG là bất biến
# ---------------------------------------------------------------------------
#
# Vì sao chỉ tính trên PHẦN MỘT CHIỀU
# ===================================
# Không phải trên toàn bộ DDL. `ensure_tables()` được phép thêm bảng, thêm cột,
# cài lại chính sách RLS ở mỗi lần khởi động — đó là hợp đồng hiện tại. Nếu
# checksum phủ cả phần đó thì thêm một bảng mới sẽ làm gate đỏ và buộc bump
# phiên bản cho một thay đổi thuần cộng thêm. Cổng sẽ kêu quá nhiều, và một cổng
# kêu quá nhiều thì bị gỡ.
#
# Phần MỘT CHIỀU thì khác hẳn: nó bỏ bảng, chép dữ liệu lịch sử sang hình dạng
# mới, ghi đè giá trị cũ. Sau khi đã chạy trên một cơ sở dữ liệu, sửa nội dung
# của nó nghĩa là hai máy mang cùng nhãn "v5" nhưng đã đi qua hai lượt biến đổi
# khác nhau — và không có cách nào phát hiện bằng cách nhìn lược đồ.
#
# Vì sao phải CHUẨN HOÁ trước khi băm
# ===================================
# Băm thẳng chuỗi Python thì một lần sửa chính tả trong chú thích SQL cũng làm
# sản xuất từ chối khởi động. Cái giá của việc đó không phải là phiền: nó dạy
# người vận hành rằng gate hay báo nhầm, và lần báo THẬT sẽ bị bỏ qua.
#
# Nên chuẩn hoá bỏ chú thích `--` và gộp khoảng trắng — nhưng CHỈ ngoài chuỗi
# nháy đơn. Trong chuỗi thì mọi ký tự đều có nghĩa: `RAISE EXCEPTION 'a--b'`
# không được biến thành `RAISE EXCEPTION 'a`.


class MigrationChecksumMismatch(SchemaVersionError):
    """Nội dung migration đã đổi sau khi phiên bản đó được áp dụng."""


class MigrationChecksumMissing(SchemaVersionError):
    """Phiên bản đã đóng dấu nhưng chưa có checksum, và chưa qua adoption."""


def canonical_sql(statement: str) -> str:
    """Dạng chuẩn của một câu lệnh, để băm.

    Bỏ chú thích `--` và gộp khoảng trắng ở phần MÃ; giữ nguyên từng ký tự bên
    trong chuỗi nháy đơn. Thân `$$ ... $$` được coi là mã chứ không phải chuỗi,
    vì đó chính là mã plpgsql và chú thích trong đó cũng chỉ là chú thích.
    """
    out: list[str] = []
    i, n = 0, len(statement)
    in_single = False
    pending_space = False

    def emit(ch: str) -> None:
        nonlocal pending_space
        if pending_space and out:
            out.append(" ")
        pending_space = False
        out.append(ch)

    while i < n:
        ch = statement[i]

        if in_single:
            out.append(ch)
            if ch == "'":
                if i + 1 < n and statement[i + 1] == "'":
                    out.append("'")      # '' escape ben trong chuoi
                    i += 2
                    continue
                in_single = False
            i += 1
            continue

        if ch == "'":
            emit(ch)
            in_single = True
            i += 1
            continue

        if ch == "-" and i + 1 < n and statement[i + 1] == "-":
            nl = statement.find("\n", i)
            i = n if nl == -1 else nl
            pending_space = True
            continue

        if ch.isspace():
            pending_space = True
            i += 1
            continue

        emit(ch)
        i += 1

    return "".join(out).strip()


def migration_payload(version: int = APP_SCHEMA_VERSION) -> list[str]:
    """Các câu thuộc migration `version`, ĐÚNG thứ tự thực thi.

    Bản đầu của hàm này lọc bốn danh sách DDL theo `one_way_statements()`. Nó
    chạy đúng đúng một ngày. Vấn đề: `one_way_statements()` là một phép PHÂN
    LOẠI, và phân loại thì tiến hoá — khi `startup_ddl_policy` bắt thêm 43 câu
    nguy hiểm, payload "v5" nhảy từ 11 lên 63 câu. Tức là *quá khứ* tự viết
    lại theo hiểu biết của hiện tại, và checksum — thứ sinh ra để chứng minh
    quá khứ không đổi — mất sạch ý nghĩa.

    Nay payload đến từ `migration_history`, nơi mỗi phiên bản là một dãy tường
    minh viết tay. Bộ phân loại có bắt thêm bao nhiêu câu cũng không chạm được
    vào con số của v5.
    """
    from app.storage.migration_history import migration_payload as historical

    return historical(version)


def migration_checksum(version: int = APP_SCHEMA_VERSION) -> str:
    """SHA-256 của payload đã chuẩn hoá, kèm số câu.

    Số câu nằm trong phần được băm để việc GỘP hai câu thành một — hoặc tách
    một câu làm hai — cũng đổi checksum, dù chuỗi nối lại có thể giống nhau.
    """
    import hashlib

    payload = [canonical_sql(s) for s in migration_payload(version)]
    blob = f"{len(payload)}\n" + "\n".join(payload)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def read_schema_version(cur) -> int | None:
    """Phiên bản hiện tại, hoặc None nếu chưa từng đóng dấu.

    Trả về None cho CẢ HAI trường hợp "bảng chưa có" và "bảng rỗng". Người gọi
    không cần phân biệt: cả hai đều có nghĩa là chưa ai chạy migration nào, và
    cách xử lý giống hệt nhau.
    """
    cur.execute("SELECT to_regclass(%s)", (f"public.{SCHEMA_VERSION_TABLE}",))
    row = cur.fetchone()
    if not row or row[0] is None:
        return None

    cur.execute(f"SELECT max(version) FROM {SCHEMA_VERSION_TABLE}")
    row = cur.fetchone()
    return row[0] if row else None


def read_recorded_checksum(cur) -> tuple[int | None, str | None, bool]:
    """`(version, checksum_da_ghi, cot_ton_tai)` của lần đóng dấu MỚI NHẤT.

    Trả về cả cờ "cột có tồn tại không" vì trên một cơ sở dữ liệu chưa chạy
    `ensure_tables()` của ảnh này, cột `migration_checksum` chưa có — và đó khác
    hẳn với "cột có nhưng để NULL". Cái đầu là chưa nâng cấp; cái sau là đã nâng
    cấp nhưng chưa ai xác nhận nội dung migration.
    """
    cur.execute("SELECT to_regclass(%s)", (f"public.{SCHEMA_VERSION_TABLE}",))
    row = cur.fetchone()
    if not row or row[0] is None:
        return (None, None, False)

    cur.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = 'migration_checksum'",
        (SCHEMA_VERSION_TABLE,))
    has_column = cur.fetchone() is not None
    if not has_column:
        return (read_schema_version(cur), None, False)

    cur.execute(
        f"SELECT version, migration_checksum FROM {SCHEMA_VERSION_TABLE} "
        f"ORDER BY version DESC, applied_at DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        return (None, None, True)
    return (row[0], row[1], True)


def checksum_problem(cur) -> SchemaVersionError | None:
    """Lý do KHÔNG được chạy tiếp vì lý do checksum, hoặc None.

    Ba trạng thái, và chúng phải khác nhau:

      * chưa đóng dấu phiên bản nào  -> không phải việc của hàm này (None)
      * đã ghi checksum, khớp        -> None
      * đã ghi checksum, LỆCH        -> `MigrationChecksumMismatch`
      * đã đóng dấu, checksum NULL   -> `MigrationChecksumMissing`

    Trạng thái cuối là trạng thái của sản xuất ngay sau khi ảnh này lên: dòng
    v5 được ghi ngày 12/08/2026, trước khi cột checksum tồn tại. Nó KHÔNG được
    tự điền. Một cơ chế "nếu NULL thì điền giá trị hiện tại" sẽ khiến một
    migration ĐÃ BỊ SỬA tự hợp thức hoá ở lần khởi động kế tiếp — đúng thứ mà
    checksum sinh ra để ngăn. Phải đi qua `--adopt-checksum`, nơi có kiểm chứng.
    """
    version, recorded, has_column = read_recorded_checksum(cur)
    if version is None:
        return None

    # Checksum chỉ so được với payload của CHÍNH phiên bản đã ghi. Ảnh này chỉ
    # dựng được payload của `APP_SCHEMA_VERSION`, nên trên một cơ sở dữ liệu
    # đóng dấu phiên bản khác, so sánh sẽ luôn lệch — và lệch vì một lý do
    # không liên quan gì tới "migration đã bị sửa".
    #
    # Chuyện lệch phiên bản đã có cổng riêng (`compatibility_error`) với thông
    # điệp đúng việc. Trả về None ở đây KHÔNG nới lỏng gì: `assert_startup_
    # compatible` chạy cổng phiên bản TRƯỚC và đã ném lỗi rồi.
    if version != APP_SCHEMA_VERSION:
        return None

    current = migration_checksum()

    if not has_column:
        return MigrationChecksumMissing(
            f"So dang ba chua co cot `migration_checksum` (co so du lieu cu hon "
            f"anh nay). Chay `ensure_tables()` mot lan roi:\n"
            f"    python -m app.cli.migrate --adopt-checksum")

    if recorded is None:
        return MigrationChecksumMissing(
            f"v{version} da duoc dong dau nhung CHUA co checksum. Khong tu dien: "
            f"lam vay thi mot migration da bi sua se tu hop thuc hoa.\n"
            f"Xac nhan mot lan, co kiem chung:\n"
            f"    EXPECTED_DATABASE=<ten_db> python -m app.cli.migrate --adopt-checksum")

    if recorded != current:
        return MigrationChecksumMismatch(
            f"NOI DUNG MIGRATION v{version} DA DOI sau khi no duoc ap dung.\n"
            f"    da ghi   : {recorded}\n"
            f"    hien tai : {current}\n"
            f"Mot phien ban da ap dung la BAT BIEN. Neu can sua, tao phien ban "
            f"v{version + 1} chu khong sua lai v{version}. Neu ban tin rang thay "
            f"doi nay vo hai va co chu y, xem docs/03-security/AUTHORIZATION.md muc migration.")

    return None


def stamp_schema_version(cur, version: int = APP_SCHEMA_VERSION,
                         note: str | None = None) -> None:
    """Ghi lại rằng lược đồ đã đạt `version`, và ai đưa nó tới đó.

    `applied_on` là danh tính của MÁY chạy lệnh, không phải của cơ sở dữ liệu.
    Hệ này có hai máy publisher và một máy triển khai; khi một lượt migration
    chạy từ chỗ không ai ngờ, cột này là thứ nói ra điều đó.
    """
    cur.execute("SELECT current_user")
    applied_by = cur.fetchone()[0]

    applied_on = (
        os.getenv("VOYA_MACHINE_ID")
        or os.getenv("HOSTNAME")
        or os.getenv("COMPUTERNAME")
        or None
    )

    checksum = migration_checksum()
    cur.execute(
        f"INSERT INTO {SCHEMA_VERSION_TABLE} "
        f"(version, applied_by, applied_on, note, migration_checksum) "
        f"VALUES (%s, %s, %s, %s, %s)",
        (version, applied_by, applied_on, note, checksum),
    )
    logger.warning(
        "[SCHEMA-VERSION] da dong dau version=%s applied_by=%s applied_on=%s "
        "checksum=%s note=%s",
        version, applied_by, applied_on or "(khong biet)", checksum[:16], note or "-",
    )


def compatibility_error(db_version: int | None) -> SchemaVersionError | None:
    """Lý do ảnh này KHÔNG chạy được trên `db_version`, hoặc None nếu chạy được.

    Tách khỏi `assert_startup_compatible` vì `verify_deployment` cần hỏi cùng
    câu hỏi mà không được phép ném lỗi — nó là công cụ chẩn đoán, và một công
    cụ chẩn đoán ngã trước khi in ra kết quả thì vô dụng đúng lúc cần nhất.
    """
    if db_version is None:
        return SchemaNotMigrated(
            f"Co so du lieu chua duoc migrate (bang {SCHEMA_VERSION_TABLE} trong "
            f"hoac chua ton tai). Anh nay can lieu do v{APP_SCHEMA_VERSION}.\n"
            f"    Chay:  python -m app.cli.migrate --to {APP_SCHEMA_VERSION}\n"
            f"Neu co so du lieu NAY da o v{APP_SCHEMA_VERSION} tu truoc khi so "
            f"dang ba ra doi, dung:  python -m app.cli.migrate --adopt"
        )

    if db_version < MIN_SUPPORTED_SCHEMA_VERSION:
        return SchemaTooOld(
            f"Luoc do dang o v{db_version}, anh nay chi chay tu "
            f"v{MIN_SUPPORTED_SCHEMA_VERSION} tro len.\n"
            f"    Chay migration truoc:  python -m app.cli.migrate "
            f"--to {APP_SCHEMA_VERSION}"
        )

    if db_version > APP_SCHEMA_VERSION:
        return SchemaTooNew(
            f"Luoc do dang o v{db_version} nhung anh nay chi hieu toi "
            f"v{APP_SCHEMA_VERSION} — day la ANH CU tren LUOC DO MOI, dung hinh "
            f"dang da gay ra su co 12/08/2026.\n"
            f"Khong tu migration nguoc. Trien khai anh ho tro v{db_version}, "
            f"hoac khoi phuc co so du lieu ve moc truoc migration."
        )

    return None


def assert_startup_compatible(cur) -> int:
    """Cổng khởi động, fail-closed cả hai chiều. Trả về phiên bản của DB.

    Gọi TRƯỚC khi ứng dụng phục vụ request đầu tiên. Ném lỗi thay vì ghi log
    rồi đi tiếp là chủ ý: một backend chạy trên lược đồ sai vẫn trả 200 cho
    phần lớn đường đi và chỉ hỏng ở những đường ít người đi nhất — tức là hỏng
    ở nơi lâu nhất mới bị phát hiện.
    """
    db_version = read_schema_version(cur)
    error = compatibility_error(db_version)

    logger.warning(
        "[SCHEMA-VERSION] db=%s anh ho tro=[%s..%s] -> %s",
        db_version if db_version is not None else "(chua dong dau)",
        MIN_SUPPORTED_SCHEMA_VERSION, APP_SCHEMA_VERSION,
        "TU CHOI KHOI DONG" if error else "khop",
    )

    if error:
        raise error

    # Checksum, sau khi phiên bản đã khớp. Hai mức, cố ý khác nhau:
    #
    #   LỆCH   -> ném. Nội dung migration đã đổi sau khi áp dụng, nên cái nhãn
    #             "v5" trên cơ sở dữ liệu này và cái "v5" trong mã không còn
    #             chỉ cùng một lượt biến đổi. Không nhìn lược đồ mà phát hiện
    #             được, nên đây là chỗ duy nhất bắt được.
    #
    #   THIẾU  -> chỉ cảnh báo. Sản xuất mang một dòng v5 ghi ngày 12/08/2026,
    #             trước khi cột checksum tồn tại. Nếu chặn khởi động ở đây thì
    #             chính lượt triển khai mang cột này lên sẽ làm sập sản xuất
    #             trước khi có ảnh nào chạy được `--adopt-checksum`. Đường chặn
    #             nằm ở `app.cli.migrate`, chạy TRƯỚC khi stack lên và dừng hẳn
    #             lượt triển khai — không có gì lọt qua.
    problem = checksum_problem(cur)
    if isinstance(problem, MigrationChecksumMismatch):
        logger.error("[SCHEMA-VERSION] %s", " ".join(str(problem).split()))
        raise problem
    if isinstance(problem, MigrationChecksumMissing):
        logger.warning(
            "[SCHEMA-VERSION] v%s CHUA co checksum — chay "
            "`python -m app.cli.migrate --adopt-checksum` de xac nhan mot lan.",
            db_version)

    return db_version

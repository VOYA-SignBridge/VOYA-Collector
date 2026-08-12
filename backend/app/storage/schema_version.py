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
APP_SCHEMA_VERSION = 5

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
)


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

    cur.execute(
        f"INSERT INTO {SCHEMA_VERSION_TABLE} "
        f"(version, applied_by, applied_on, note) VALUES (%s, %s, %s, %s)",
        (version, applied_by, applied_on, note),
    )
    logger.warning(
        "[SCHEMA-VERSION] da dong dau version=%s applied_by=%s applied_on=%s note=%s",
        version, applied_by, applied_on or "(khong biet)", note or "-",
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
    return db_version

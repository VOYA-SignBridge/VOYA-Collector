"""Lịch sử migration: phiên bản N gồm ĐÚNG những câu nào, theo ĐÚNG thứ tự nào.

Vì sao tệp này tách khỏi `schema_version.py`
============================================
Hai khái niệm nghe giống nhau và tuyệt đối không được dẫn xuất từ nhau:

    one_way_statements()      PHÂN LOẠI — "câu nào không được chạy lúc khởi động"
    migration_payload(N)      LỊCH SỬ  — "migration N thực sự gồm những câu nào"

Phân loại được phép tiến hoá. Ngày 13/08/2026 bộ phân loại `startup_ddl_policy`
tìm thêm 43 câu không chứng minh được là an toàn lúc khởi động, và ngày mai nó
có thể tìm ra 80. Đó là tiến bộ.

Lịch sử KHÔNG được phép tiến hoá. Nhưng bản đầu của `migration_payload()` lọc
danh sách theo `one_way_statements()`, nên payload "v5" trôi theo bộ phân loại:
11 câu -> 45 -> 63. Cổng checksum báo `NOI DUNG MIGRATION v5 DA DOI` và nó nói
đúng — chỉ có điều thứ đã đổi là *định nghĩa* của v5, chứ không phải v5.

Nên ở đây không có một phép lọc nào. Mỗi phiên bản là một dãy tường minh, viết
tay, có tên cho từng câu.

Vì sao có NHÃN chứ không chỉ là hằng số
=======================================
Checksum phụ thuộc ba thứ: câu nào (identity), nội dung câu, và thứ tự. Một
dãy trần chỉ giữ được hai thứ sau. Vài câu phải tham chiếu qua chỉ số
(`_DROP_GLOBAL_CLASS_UNIQUES[0]`), và một lần đảo thứ tự trong tuple gốc sẽ
lặng lẽ đổi payload. Nhãn làm cho lượt hỏng đó nói được nó hỏng ở đâu, thay vì
chỉ nói "checksum khác".
"""

from __future__ import annotations

__all__ = [
    "MIGRATION_HISTORY",
    "V5_CHECKSUM",
    "UnknownMigrationVersion",
    "labelled_payload",
    "migration_payload",
]


class UnknownMigrationVersion(LookupError):
    """Hỏi payload của một phiên bản chưa được đóng gói."""


#: Checksum mà SẢN XUẤT đã ghi lúc 2026-08-12 19:57:50 UTC, chép nguyên văn từ
#: `schema_migrations`. Đây là con số đối chứng ĐỘC LẬP: nó không được tính ra
#: từ mã trong kho này, nên nếu payload bên dưới lệch đi một byte thì
#: `test_the_v5_checksum_is_still_the_one_production_recorded` đỏ.
V5_CHECKSUM = "373023b55ec4b3ec64e118389ec7b14fee0a9f377a09af810c8fe6f48cc93f30"


def _v5() -> tuple[tuple[str, str], ...]:
    """Mười một câu của v5, theo đúng thứ tự đã chạy trên sản xuất 12/08/2026.

    Thứ tự này KHÔNG phải do ai chọn hôm nay — nó là thứ tự mà bản
    `migration_payload()` cũ sinh ra khi quét bốn danh sách DDL, và nó đã được
    dựng lại rồi đối chiếu: checksum của đúng dãy này bằng `V5_CHECKSUM`.

    Nạp muộn vì hai mô-đun kia nhập ngược lại tệp này qua `schema_version`.
    """
    from app.storage import authz_schema as authz
    from app.storage import metadata_db as mdb

    return (
        # --- từ DDL_STATEMENTS ---
        ("drop_pre_registry_dialects", mdb._DROP_PRE_REGISTRY_DIALECTS),
        # --- từ MIGRATION_STATEMENTS ---
        ("drop_global_class_unique_first", mdb._DROP_GLOBAL_CLASS_UNIQUES[0]),
        ("drop_global_class_unique_second", mdb._DROP_GLOBAL_CLASS_UNIQUES[1]),
        ("drop_dead_user_profiles", mdb._DROP_DEAD_USER_PROFILES),
        # --- từ AUTHZ_DDL_STATEMENTS ---
        ("drop_vestigial_role_name", authz._DROP_VESTIGIAL_ROLE_NAME),
        ("migrate_memberships", authz._MIGRATE_MEMBERSHIPS),
        ("migrate_assignments", authz._MIGRATE_ASSIGNMENTS),
        ("drop_legacy_membership_tables", authz._DROP_LEGACY_MEMBERSHIP_TABLES),
        ("retire_legacy_role_first", authz._LEGACY_ROLE_RETIREMENT_DDL[0]),
        ("retire_legacy_role_second", authz._LEGACY_ROLE_RETIREMENT_DDL[1]),
        ("retire_legacy_role_third", authz._LEGACY_ROLE_RETIREMENT_DDL[2]),
    )


#: Phiên bản -> hàm dựng dãy có nhãn.
#:
#: v6 CỐ Ý vắng mặt. Mô hình gói Free/Plus/Pro/Enterprise còn dang dở
#: (`docs/07-business/BILLING_MODEL_V6.md`), và một payload chưa hoàn chỉnh mà đã có mục ở
#: đây thì lần `--to 6` đầu tiên sẽ đóng dấu một checksum của bản nửa vời —
#: rồi bất biến vĩnh viễn. Thêm mục v6 là việc CUỐI CÙNG của lượt Billing v6,
#: không phải việc đầu tiên.
MIGRATION_HISTORY = {
    5: _v5,
}


def labelled_payload(version: int) -> tuple[tuple[str, str], ...]:
    """`((nhãn, câu lệnh), ...)` của một phiên bản, theo thứ tự thực thi."""
    try:
        build = MIGRATION_HISTORY[version]
    except KeyError:
        known = ", ".join(f"v{v}" for v in sorted(MIGRATION_HISTORY))
        raise UnknownMigrationVersion(
            f"chua dong goi payload cho v{version}. Da co: {known}. "
            f"Mot phien ban khong co payload thi khong dong dau duoc, va do la "
            f"co y: checksum khoa noi dung migration vinh vien ngay lan apply "
            f"dau tien."
        ) from None
    return build()


def migration_payload(version: int) -> list[str]:
    """Các câu của một phiên bản, theo đúng thứ tự thực thi."""
    return [statement for _, statement in labelled_payload(version)]

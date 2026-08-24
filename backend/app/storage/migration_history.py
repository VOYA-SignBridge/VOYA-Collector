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

Kỷ luật versioning — thêm một câu MỘT CHIỀU thì phải có phiên bản MỚI
====================================================================
Ngày 15/08/2026 lộ ra một lỗ mà chính sự tách bạch ở trên tạo ra, và nó là cái
giá phải trả chứ không phải lỗi thiết kế.

Việc `region` vào định danh lớp thêm một câu một chiều —
`DROP INDEX IF EXISTS uq_classes_tenant_slug_lang_dialect` — vào lược đồ,
nhưng KHÔNG tăng `APP_SCHEMA_VERSION`. Hệ quả:

    payload v5      : 11 câu, không có câu DROP ấy
    checksum v5     : KHÔNG đổi
    lược đồ sản xuất: đã đổi thật

Tức là một thay đổi lược đồ có thật đi qua mà cổng bất biến không hề thấy. Thứ
bắt được nó là `retired_objects` trong `migrate --status` — nhưng phép kiểm ấy
chỉ trả lời *"trạng thái cuối có đúng không"*, không trả lời được
*"thay đổi này thuộc phiên bản nào"*.

Luật, áp dụng từ thay đổi lược đồ KẾ TIẾP trở đi:

    Thêm hoặc bớt một câu DDL một chiều có ảnh hưởng tới lược đồ sản xuất
    ⇒ BẮT BUỘC một phiên bản migration mới.
    KHÔNG sửa payload của một phiên bản đã tồn tại.

Payload v5 **không** được sửa hồi tố. Sửa nó là viết lại quá khứ — đúng thứ
tệp này sinh ra để ngăn — và sẽ làm checksum lệch khỏi con số sản xuất đã ghi
lúc 2026-08-12 19:57:50 UTC (xem `V5_CHECKSUM`).

Cách đóng lịch sử cho sạch, khi khung migration sẵn sàng: phiên bản kế tiếp
chứa câu tương ứng ở dạng luỹ đẳng, ví dụ

    v6: DROP INDEX IF EXISTS uq_classes_tenant_slug_lang_dialect

Trên sản xuất hôm nay nó là no-op (chỉ mục đã gỡ lúc 04:07 ngày 15/08). Trên
một cơ sở dữ liệu nâng cấp từ trạng thái cũ, nó tạo ra một bước chuyển **có
phiên bản và có checksum** thay vì một thay đổi không ai quy được về đâu.

Đừng tạo v6 chỉ để cho đẹp nếu khung chưa sẵn sàng — một phiên bản rỗng nghĩa
cũng là một loại nói dối.
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


def _v6() -> tuple[tuple[str, str], ...]:
    """Ba câu của v6: gỡ bất biến "buổi thu có đúng một người ký".

    Vì sao v6 KHÔNG còn là Billing
    -------------------------------
    Số này từng được giữ chỗ cho mô hình gói Free/Plus/Pro/Enterprise, và chú
    thích cũ ở đây dặn "thêm mục v6 là việc CUỐI CÙNG của lượt Billing". Lời
    dặn ấy vẫn đúng VỚI BILLING — điều đổi là ai được dùng con số này.

        Billing v6      chưa hoàn tất, chưa phát hành, chưa có gì trên sản xuất
        bất biến dưới   đã áp lên `signdb` ngày 23/08/2026, và sẽ TỪ CHỐI dữ
                        liệu hợp lệ ngay khi danh tính người ký được gỡ đúng

    Một lỗi lược đồ đang sống được ưu tiên hơn một con số giữ chỗ cho tính năng
    chưa ra đời. Billing chuyển sang v7.

    Vì sao chỉ có ba câu
    --------------------
    `users.role_id`, `samples_class_uid_fkey` và vài khoản dọn dẹp khác cũng
    đang chờ DROP, nhưng KHÔNG đi cùng chuyến này. Một migration sửa lỗi ngắn,
    một lý do duy nhất, hậu điều kiện đọc hết trong một hơi — thứ ấy audit
    được. Gộp thêm ba việc không liên quan thì lần sau không ai trả lời nổi
    "v6 đã sửa cái gì".

    Thứ tự BẮT BUỘC: khoá ngoại trước, rồi khoá ứng viên nó trỏ tới, rồi cột.
    Đảo lại thì Postgres từ chối vì còn phụ thuộc.

    Cả ba đều `IF EXISTS`, nên trên một bản cài mới — nơi cột chưa từng ra đời
    — v6 là ba no-op. Đó là điều kiện để `--to 6` chạy được ở mọi xuất phát
    điểm, không chỉ trên máy đã đi qua ngày 23/08.
    """
    from app.storage import metadata_db as mdb

    return (
        ("drop_collection_signer_fk", mdb._V6_DROP_COLLECTION_SIGNER_FK),
        ("drop_collection_signer_unique", mdb._V6_DROP_COLLECTION_SIGNER_UNIQUE),
        ("drop_collection_signer_column", mdb._V6_DROP_COLLECTION_SIGNER_COLUMN),
    )


def _v7() -> tuple[tuple[str, str], ...]:
    """Ba câu của v7: "chưa công bố registry" là NULL, không phải 0 hay 1.

    Vì sao có v7 ngay sau v6
    ------------------------
    Cùng một lỗi, hai lần trong một ngày: gắn khoá ngoại lên một cột ĐÃ CÓ mà
    chỉ kiểm dữ liệu hiện có, không kiểm đường GHI. Khoá ngoại ghép
    `(tenant_id, version) -> registry_versions` thêm ngày 23/08/2026 đúng về
    nguyên tắc, nhưng cột ấy đang mang hai giá trị mốc bịa:

        clone_catalog_to_tenant  ghi 0   phiên bản 0 KHÔNG BAO GIỜ tồn tại
        DEFAULT của cột           là 1   phiên bản 1 chưa chắc tồn tại

    Hậu quả đo được: `INSERT INTO vocabulary_registry_meta(tenant_id, version)
    VALUES('probe-fk', 0)` bị từ chối, và `tenant_admin.py` không bọc lỗi ấy —
    **tạo tenant mới hỏng**. Chưa nổ trên sản xuất chỉ vì stack đang tắt.

    Vì sao KHÔNG gỡ khoá ngoại cho xong
    -----------------------------------
    Gỡ là quay về trạng thái yếu hơn rồi vẫn phải làm việc này. Cột vốn đã có
    sẵn cách nói "chưa có gì" mà không cần bịa số: NULL. Khoá ngoại MATCH
    SIMPLE cho NULL đi qua, nên giữ được phép kiểm mà vẫn biểu diễn được trạng
    thái rỗng.

    Thứ tự BẮT BUỘC: bỏ DEFAULT, bỏ NOT NULL, rồi mới đặt được NULL.

    Đi kèm ở tầng mã, và thiếu một trong ba thì v7 vô nghĩa:
      * `clone_catalog_to_tenant` ghi NULL thay cho 0;
      * `_bump()` TẠO `registry_versions` trước rồi mới dời con trỏ — bản cũ
        làm ngược và cũng bị chính khoá ngoại ấy chặn;
      * bước gieo trỏ vào `max(version)` có thật thay vì để rơi vào DEFAULT.
    """
    from app.storage import metadata_db as mdb

    return (
        ("registry_pointer_drop_default", mdb._SQL_V7_REGISTRY_POINTER_DROP_DEFAULT),
        ("registry_pointer_drop_not_null", mdb._SQL_V7_REGISTRY_POINTER_DROP_NOT_NULL),
        ("registry_pointer_empty_is_null", mdb._SQL_V7_REGISTRY_POINTER_NULL_SENTINEL),
    )


#: Phiên bản -> hàm dựng dãy có nhãn.
MIGRATION_HISTORY = {
    5: _v5,
    6: _v6,
    7: _v7,
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

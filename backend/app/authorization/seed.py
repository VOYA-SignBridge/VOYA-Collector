"""Đưa danh mục quyền và role dựng sẵn từ mã nguồn vào cơ sở dữ liệu.

Vì sao ĐỐI CHIẾU chứ không chỉ chèn
------------------------------------
`INSERT ... ON CONFLICT DO NOTHING` là đủ cho lần chạy đầu và sai từ lần thứ
hai. Ba thay đổi thường gặp mà nó bỏ sót:

  * Sửa mô tả hoặc bật `requires_passcode` cho một quyền đã có → không có hiệu
    lực, và cơ sở dữ liệu giữ giá trị cũ trong khi mã nguồn nói khác. Với
    `requires_passcode`, đó là một bước xác thực nâng cấp đã được viết ra
    nhưng không bao giờ chạy.
  * Gỡ một quyền khỏi role dựng sẵn → dòng `role_permissions` cũ ở lại, nên
    người dùng GIỮ NGUYÊN quyền đã bị gỡ. Đây là kiểu hở nguy hiểm nhất trong
    tệp này: mã nguồn nói đã thu hồi, hệ thống nói chưa.
  * Xoá hẳn một quyền khỏi danh mục → dòng mồ côi trong `permissions` vẫn
    chiếu vào Casbin.

Nên hàm ở đây đối chiếu cả hai chiều: THÊM cái thiếu, GỠ cái thừa. Chỉ với
role `is_builtin = TRUE` — role do tenant tự tạo không thuộc quyền quản lý của
tệp này và không bị đụng tới.

Vì sao quyền bị gỡ được VÔ HIỆU HOÁ chứ không XOÁ
--------------------------------------------------
`DELETE FROM permissions` sẽ vướng `ON DELETE RESTRICT` từ `role_permissions`
của các role tự tạo — đúng như thiết kế, vì xoá một quyền khỏi danh mục trong
khi tenant vẫn đang gán nó là làm hỏng cấu hình của họ mà không báo. `is_active
= FALSE` cho cùng hiệu quả lúc chạy (adapter lọc theo cột này, nên quyền không
còn chiếu vào Casbin) mà vẫn giữ được dấu vết để trả lời "role này từng chứa
gì".

Phạm vi khi chạy
----------------
Ghi vào `roles` với `tenant_id IS NULL`. Bảng đó chịu chính sách danh mục dùng
chung, và vế WITH CHECK của chính sách ấy đòi `tenant_id = current_setting(
'app.tenant_id')` — một dòng NULL không thoả. Nên seed PHẢI chạy trong system
scope, và hàm này khẳng định điều đó thay vì phó mặc cho người gọi nhớ.
"""

from __future__ import annotations

import logging
from typing import Any

from app.authorization.catalog import (
    BUILTIN_ROLES,
    PERMISSIONS,
    RETIRED_BUILTIN_ROLES,
    custom_role_allowed,
)

logger = logging.getLogger(__name__)


def _sync_permissions(cur) -> dict[str, int]:
    """Đưa bảng `permissions` khớp với danh mục trong mã nguồn."""
    # `is_custom_role_allowed` PHẢI được ghi tường minh, không được để mặc định.
    #
    # Cột đó mặc định TRUE ở cơ sở dữ liệu, và `ck_permissions_system_not_custom_role`
    # cấm TRUE với quyền phạm vi SYSTEM. Bản trước không nêu cột này, nên câu
    # INSERT đầu tiên của một lượt seed — `platform.user.read`, một quyền SYSTEM
    # — vi phạm CHECK và ném `CheckViolation`. `_seed_authorization` bắt và hạ
    # xuống một dòng log, nên hệ vẫn khởi động; nhưng TOÀN BỘ lượt seed dừng ở
    # câu đó. Không quyền nào được đồng bộ, không role nào được dựng, và bước
    # vô hiệu hoá role đã nghỉ không bao giờ chạy tới.
    #
    # `catalog.custom_role_allowed()` là nguồn: nó đã ép quyền SYSTEM về FALSE
    # bất kể cờ trong danh mục, đúng cùng bất biến mà CHECK cưỡng chế. Hai lớp
    # cho một quy tắc, và giờ chúng nói cùng một điều.
    rows = [
        (p.code, p.description, p.scope, p.risk, p.requires_passcode,
         p.api_assignable, custom_role_allowed(p.code))
        for p in PERMISSIONS
    ]
    # `DO UPDATE` chứ không `DO NOTHING`: xem docstring module. Mọi cột siêu dữ
    # liệu đều được ghi đè, kể cả `is_active` — một quyền quay lại danh mục
    # sau khi từng bị gỡ phải sống lại, không thì nó im lặng vẫn tắt.
    cur.executemany(
        """
        INSERT INTO permissions (
            permission_code, description, applicable_scope, risk_level,
            requires_passcode, is_api_assignable, is_custom_role_allowed, is_active
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (permission_code) DO UPDATE SET
            description            = EXCLUDED.description,
            applicable_scope       = EXCLUDED.applicable_scope,
            risk_level             = EXCLUDED.risk_level,
            requires_passcode      = EXCLUDED.requires_passcode,
            is_api_assignable      = EXCLUDED.is_api_assignable,
            is_custom_role_allowed = EXCLUDED.is_custom_role_allowed,
            is_active              = TRUE
        """,
        rows,
    )

    known = [p.code for p in PERMISSIONS]
    cur.execute(
        "UPDATE permissions SET is_active = FALSE "
        "WHERE permission_code <> ALL(%s) AND is_active",
        (known,),
    )
    retired = cur.rowcount or 0
    if retired:
        logger.warning(
            "[AUTHZ-SEED] %d quyen khong con trong danh muc da bi vo hieu hoa", retired
        )
    return {"permissions": len(rows), "retired": retired}


def _sync_builtin_roles(cur) -> dict[str, Any]:
    """Tạo/cập nhật role dựng sẵn và đối chiếu tập quyền của chúng."""
    added = removed = 0

    for role in BUILTIN_ROLES:
        # HAI cột, hai vai, và trộn chúng là một lỗi im lặng.
        #
        # v5 tách `roles.name` cũ thành:
        #
        #     role_code   định danh ỔN ĐỊNH — xuất hiện nguyên văn trong policy
        #                 Casbin và trong nhật ký kiểm toán, và là thứ mà
        #                 `LEGACY_TENANT_ROLE_MAP`, `RETIRED_BUILTIN_ROLES`,
        #                 `backfill_authz` và `_BUILTIN_PERMISSIONS` tra theo
        #     role_name   NHÃN hiển thị — người dùng đọc, tenant sửa được
        #
        # Ghi nhãn hiển thị vào `role_code` làm cả bốn nơi kia tra không ra:
        # backfill dừng với "thiếu role dựng sẵn", `_legacy_decision` ném
        # `KeyError`, và lượt vô hiệu hoá role đã nghỉ khớp 0 dòng — im lặng.
        #
        # Tra theo `role_code` MỘT MÌNH, không kèm `scope_level`:
        # `uq_roles_builtin_code` làm mã role dựng sẵn duy nhất TOÀN CỤC chứ
        # không theo phạm vi. Thêm `scope_level` vào vị từ sẽ làm một role ĐỔI
        # PHẠM VI không tìm thấy chính nó, rồi câu INSERT ngay sau đó va vào
        # chỉ mục.
        #
        # Đọc-rồi-ghi KHÔNG tự nó an toàn — bản đầu của chú thích này khẳng
        # định ngược lại và sản xuất bác bỏ ngay lượt triển khai đầu tiên. Cái
        # làm nó an toàn là `SEED_LOCK_KEY` mà `seed_authorization_catalogue`
        # giữ; đừng gọi thẳng hàm này mà không có khoá đó.
        cur.execute(
            "SELECT role_id FROM roles WHERE tenant_id IS NULL AND role_code = %s",
            (role.code,),
        )
        found = cur.fetchone()
        if found:
            role_id = found[0]
            cur.execute(
                "UPDATE roles SET role_name = %s, description = %s, scope_level = %s, "
                "       is_builtin = TRUE, is_active = TRUE "
                " WHERE role_id = %s",
                (role.name, role.description, role.scope, role_id),
            )
        else:
            cur.execute(
                "INSERT INTO roles (tenant_id, role_code, role_name, description, "
                "scope_level, is_builtin, is_active) "
                "VALUES (NULL, %s, %s, %s, %s, TRUE, TRUE) "
                "RETURNING role_id",
                (role.code, role.name, role.description, role.scope),
            )
            role_id = cur.fetchone()[0]

        wanted = list(role.permissions)

        # Gỡ trước, thêm sau. Thứ tự này quan trọng nếu một quyền vừa đổi phạm
        # vi: gỡ dòng cũ rồi thêm lại sẽ đi qua trigger dominance với giá trị
        # MỚI, còn thứ tự ngược lại có thể để dòng cũ chặn.
        cur.execute(
            "DELETE FROM role_permissions "
            "WHERE role_id = %s AND permission_code <> ALL(%s)",
            (role_id, wanted),
        )
        removed += cur.rowcount or 0

        cur.executemany(
            "INSERT INTO role_permissions (role_id, permission_code) VALUES (%s, %s) "
            "ON CONFLICT (role_id, permission_code) DO NOTHING",
            [(role_id, code) for code in wanted],
        )
        added += cur.rowcount or 0

    return {"roles": len(BUILTIN_ROLES), "grants_added": added, "grants_removed": removed}


def _retire_builtin_roles(cur) -> dict[str, Any]:
    """Vô hiệu hoá những role dựng sẵn đã bị gỡ khỏi danh mục. KHÔNG xoá.

    Vì sao đọc `RETIRED_BUILTIN_ROLES` chứ không "mọi role không có trong
    `BUILTIN_ROLES`"
    ---------------------------------------------------------------------
    Xem chú thích dài ở hằng số đó: vắng mặt trong danh mục có thể là GỠ HẲN
    hoặc mới chỉ ĐỔI TÊN, và một bước suy diễn tự động sẽ tắt nhầm cái thứ hai
    cùng toàn bộ assignment đang sống của nó. Danh sách viết tay là chỗ người
    ta phải nói rõ ý định.

    Vì sao `is_active = FALSE` là ĐỦ để vai đó hết hiệu lực
    -------------------------------------------------------
    `adapter.py` lọc `r.is_active` ở cả bốn truy vấn chiếu policy, nên một role
    đã tắt không sinh dòng policy nào — kể cả khi `role_permissions` của nó còn
    nguyên. Giữ lại các dòng đó là chủ ý: chúng là câu trả lời duy nhất cho
    "vai này từng cấp những gì", và một sổ kiểm toán không đọc được lịch sử thì
    không phải sổ kiểm toán.

    Vì sao ĐẾM assignment rồi kêu, thay vì lặng lẽ tắt
    --------------------------------------------------
    Tắt một role đang có người mang là THU HỒI QUYỀN CỦA NGƯỜI THẬT, và nó xảy
    ra lúc khởi động container — nơi không ai đang nhìn. Nếu con số khác 0, dòng
    log này là thứ duy nhất giải thích vì sao sáng hôm sau có người mất quyền.
    """
    if not RETIRED_BUILTIN_ROLES:
        return {"retired_roles": 0}

    names = list(RETIRED_BUILTIN_ROLES)

    # Bảng assignment nào TỒN TẠI, hỏi bảng đó — và đừng cho rằng bảng nào cũng
    # có mặt.
    #
    # Hai thế hệ lược đồ cùng sống trong kho này: v1.0 có bốn bảng theo phạm vi
    # (`tenant_member_roles`, ...), v5 gộp lại thành một `role_assignments`. Một
    # câu truy vấn nêu thẳng tên bảng của thế hệ kia là `UndefinedTable` —
    # PostgreSQL phân giải tên lúc PHÂN TÍCH CÚ PHÁP, nên `to_regclass` trong
    # mệnh đề WHERE không cứu được, và lỗi đó sẽ kéo đổ cả lượt seed.
    #
    # Việc đếm ở đây là một CẢNH BÁO, không phải một quyết định — nên nó dựng
    # câu hỏi từ những bảng thật sự có, và im lặng bỏ qua những bảng vắng mặt.
    cur.execute(
        "SELECT tablename FROM pg_tables "
        " WHERE schemaname = current_schema() AND tablename = ANY(%s)",
        (["role_assignments", "tenant_member_roles", "workspace_member_roles",
          "project_member_roles", "system_user_roles"],),
    )
    present = [row[0] for row in cur.fetchall()]

    live_expr = " + ".join(
        f"(SELECT count(*) FROM {t} a "
        f"  WHERE a.role_id = r.role_id AND a.revoked_at IS NULL)"
        for t in present
    ) or "0"

    # Đếm TRƯỚC khi tắt. Sau khi tắt, con số vẫn đọc được nhưng câu hỏi "lượt
    # seed này đã thu hồi của bao nhiêu người" thì không.
    cur.execute(
        f"""
        SELECT r.role_code, ({live_expr}) AS live
          FROM roles r
         WHERE r.tenant_id IS NULL AND r.is_builtin AND r.role_code = ANY(%s)
        """,  # noqa: S608 - `present` chỉ chứa tên lấy từ pg_tables, không phải đầu vào
        (names,),
    )
    for name, live in cur.fetchall():
        if live:
            logger.error(
                "[AUTHZ-SEED] role %r da bi go khoi danh muc nhung con %d "
                "assignment dang song — vo hieu hoa no THU HOI quyen cua tung "
                "do nguoi. Kiem tra truoc khi trien khai tiep.",
                name, live,
            )

    cur.execute(
        "UPDATE roles SET is_active = FALSE "
        " WHERE tenant_id IS NULL AND is_builtin AND role_code = ANY(%s) AND is_active",
        (names,),
    )
    turned_off = cur.rowcount or 0
    if turned_off:
        logger.warning(
            "[AUTHZ-SEED] %d role dung san da nghi da bi vo hieu hoa: %s",
            turned_off, ", ".join(names),
        )
    return {"retired_roles": turned_off}


#: Khoá tư vấn bao cả khối phân quyền — seed VÀ khối DDL trong
#: `metadata_db.ensure_tables()`, vốn cũng chạy 4 lần song song.
#: Công khai (không gạch dưới) chính vì `metadata_db` nhập nó. Con số tuỳ ý nhưng phải CỐ ĐỊNH và không
#: trùng với khoá tư vấn nào khác trong hệ.
SEED_LOCK_KEY = 0x5106_B12D  # "SIGB" + 1D, chỉ để dễ nhận ra trong pg_locks


def seed_authorization_catalogue(cur) -> dict[str, Any]:
    """Đồng bộ danh mục quyền + role dựng sẵn. Idempotent VÀ an toàn khi đồng thời.

    Nhận một cursor thay vì tự mở kết nối, để chạy được CẢ trong
    `ensure_tables()` (vai migration, autocommit) LẪN trong một test đang giữ
    giao dịch riêng của nó. Người gọi chịu trách nhiệm về phạm vi và commit.

    Vì sao có khoá tư vấn
    ---------------------
    Bản đầu của hàm này mang một câu khẳng định trong chú thích: *"an toàn vì
    seed chạy một lần lúc khởi động, không đồng thời"*. Câu đó SAI, và sản xuất
    chứng minh ngay ở lượt triển khai đầu tiên:

        [AUTHZ-SEED] that bai: UniqueViolation:
        duplicate key ... (scope_level, name)=(TENANT, tenant_admin) already exists

    gunicorn chạy **4 worker**, cả bốn gọi `ensure_tables()` gần như cùng một
    mili giây. `_sync_builtin_roles` đọc-rồi-ghi: hai worker cùng SELECT không
    thấy gì, cùng INSERT, một thắng và ba thua.

    Ở lần đó hậu quả vô hại — worker thắng seed xong, ba worker thua ném lỗi và
    `_seed_authorization` nuốt. Nhưng trên một cơ sở dữ liệu TRỐNG, worker thua
    có thể chết sau khi đã ghi `permissions` và trước khi ghi xong `roles`, để
    lại danh mục dở dang mà dấu hiệu duy nhất là một dòng log.

    `pg_advisory_lock` ở mức PHIÊN chứ không mức giao dịch: `_migration_cursor`
    chạy autocommit, nên `pg_advisory_xact_lock` sẽ nhả ra ngay lập tức và
    không khoá được gì. Kết nối đó không thuộc pool và đóng ngay sau đó, nên
    khoá mức phiên không rò sang ai.

    Ba worker thua KHÔNG bị bỏ qua — chúng chờ, rồi chạy lại toàn bộ lượt seed.
    Vì mọi bước đều đối chiếu, chúng báo 0 thay đổi thay vì ném lỗi.
    """
    cur.execute("SELECT pg_advisory_lock(%s)", (SEED_LOCK_KEY,))
    try:
        return _seed_locked(cur)
    finally:
        # `finally`, vì một lỗi giữa chừng mà không nhả khoá sẽ làm mọi lần
        # khởi động sau treo ở đây cho tới khi kết nối đóng.
        cur.execute("SELECT pg_advisory_unlock(%s)", (SEED_LOCK_KEY,))


def _seed_locked(cur) -> dict[str, Any]:
    stats: dict[str, Any] = {}
    stats.update(_sync_permissions(cur))
    stats.update(_sync_builtin_roles(cur))
    # SAU `_sync_builtin_roles`, không trước: hàm đó đặt `is_active = TRUE` cho
    # mọi role nó chạm tới. Chạy trước thì một role đã nghỉ mà vẫn còn tên
    # trong `BUILTIN_ROLES` sẽ được bật lại ngay sau đó — chốt tự kiểm lúc
    # import chặn tình huống ấy, và thứ tự ở đây là lớp thứ hai.
    stats.update(_retire_builtin_roles(cur))
    logger.info(
        "[AUTHZ-SEED] %d quyen, %d role dung san, +%d/-%d lien ket quyen, "
        "%d role da nghi",
        stats["permissions"], stats["roles"],
        stats["grants_added"], stats["grants_removed"],
        stats["retired_roles"],
    )
    return stats

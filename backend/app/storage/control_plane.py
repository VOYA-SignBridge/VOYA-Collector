"""Mặt phẳng ĐIỀU KHIỂN: bảng nào, vai nào, đúng quyền nào.

Vì sao có tệp này
=================
Tới 15/08/2026 `voya_app` là một credential gánh hai loại quyền: thao tác
nghiệp vụ của tenant, và thao tác điều khiển nền tảng. `tenant_purges` là ví dụ
rõ nhất — sổ cái ghi việc một tổ chức đã bị xoá vĩnh viễn, và vai ứng dụng có
đủ bốn quyền trên nó:

    voya_app   SELECT INSERT UPDATE DELETE     (đo 15/08/2026)

Nghĩa là một đường ghi bất kỳ chạy dưới vai ứng dụng — hoặc một lỗ SQL — vừa
**xoá được lịch sử purge**, vừa **ghi được "đã purge"** cho một tổ chức chưa hề
bị xoá. Đó là lỗ TOÀN VẸN sổ cái, không phải lỗ cách ly tenant, nên RLS không
phải công cụ đúng.

Hai kiểu bảo vệ, không phải một
===============================
Lưới phủ (`test_rls_covers_every_tenant_table.py`) chấp nhận HAI cách, và mỗi
bảng mang `tenant_id` phải thuộc đúng một:

    A. Dữ liệu của tenant   -> RLS + FORCE + policy + kiểm hành vi
    B. Dữ liệu điều khiển   -> vai ứng dụng KHÔNG có quyền trực tiếp
                               + vai điều khiển có ĐÚNG quyền tối thiểu

Vì sao `tenant_purges` thuộc B, chứng minh bằng THỨ TỰ THỰC THI
==============================================================
`tenant_lifecycle.purge_tenant` xoá dòng `tenants` TRƯỚC khi ghi sổ:

    tenant_lifecycle.py:521   DELETE FROM tenants WHERE tenant_id = %s
    tenant_lifecycle.py:528   INSERT INTO tenant_purges(...)

Tại thời điểm dòng sổ ra đời, tenant ấy KHÔNG CÒN TỒN TẠI. Một chính sách RLS
"chỉ thấy dòng của tenant mình" không có gì để so, và `WITH CHECK` sẽ chặn
chính câu ghi trừ khi mở phạm vi hệ thống. Bật RLS ở đây rồi lại mở
`system_scope` để vượt qua nó là một vòng tròn: nó làm con số phủ đẹp lên mà
không thêm một chút bảo vệ nào.

Cùng lý do, `tenant_id` ở bảng này là CHỦ THỂ được ghi lại, không phải quyền sở
hữu — bảng cố ý không có khoá ngoại tới `tenants`.

Vì sao ĐÚNG `INSERT`, không phải CRUD cho tiện
==============================================
Đo trên lược đồ thật ngày 15/08/2026:

    trigger                    0     -> không cần quyền nào thêm
    khoá ngoại đi ra           0     -> không cần SELECT trên bảng được trỏ tới
    DEFAULT dùng sequence      0     -> không cần USAGE trên sequence
    RLS policy                 0
    câu ghi có RETURNING?      KHÔNG -> không cần SELECT

Nên tập quyền tối thiểu thật sự là `{INSERT}`. Nếu một ngày câu ghi cần
`RETURNING`, cấp thêm SELECT SAU KHI chứng minh cần, đừng mở trước.

Hàng rào phải trả lời được trước khi dùng vai điều khiển
========================================================
Vai này KHÔNG phải "vai mạnh hơn `voya_app`, gặp chỗ nào RLS chặn thì lấy ra
dùng". Mỗi lần thêm một mục vào đây phải trả lời được cả bốn câu:

    1. Đây có thật sự là thao tác MẶT PHẲNG ĐIỀU KHIỂN không?
    2. Vì sao `voya_app` KHÔNG nên có quyền này?
    3. Quyền tối thiểu thật sự là gì?
    4. Phép phân quyền nào xảy ra TRƯỚC khi lấy kết nối điều khiển?

Không trả lời được cả bốn thì không dùng vai điều khiển.

Điều tệp này KHÔNG đạt được
===========================
Đây là tách biệt ở tầng **DB principal**, chưa phải tầng **tiến trình**. Tiến
trình API vẫn giữ cả `DATABASE_URL` lẫn `CONTROL_DATABASE_URL`, nên kẻ chiếm
được toàn quyền thực thi mã trong tiến trình vẫn đọc được biến môi trường và
lấy được credential điều khiển.

Nó chống tốt: SQL injection dưới vai ứng dụng, truy vấn nhầm nhóm kết nối,
quyền nở dần, và mọi DML trực tiếp từ vai ứng dụng. Nó KHÔNG chống: chiếm toàn
bộ tiến trình. Muốn chống nốt thì credential điều khiển phải rời khỏi tiến
trình API (hàng đợi + worker điều khiển riêng) — đó là Mức II và cố ý ngoài
phạm vi lượt này. Xem docs/TENANT_ISOLATION_AND_AUTHZ.md §4.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

#: Vai điều khiển ở sản xuất, và vai tương ứng của bộ test.
#:
#: Bộ test dùng vai THẬT chứ không giả lập bằng `admin`: một phép kiểm chạy
#: dưới superuser sẽ xanh dù mọi GRANT đều sai.
CONTROL_ROLE = "voya_control"
TEST_CONTROL_ROLE = "voya_test_control"

#: Biến môi trường mang DSN điều khiển. Rỗng nghĩa là "chưa tách vai" — đường
#: gọi sẽ nói ra điều đó chứ không lặng lẽ rơi về `voya_app`.
CONTROL_DSN_ENV = "CONTROL_DATABASE_URL"

#: Bảng ĐIỀU KHIỂN -> tập quyền CHÍNH XÁC của vai điều khiển trên bảng đó.
#:
#: "Chính xác" theo cả hai chiều: thiếu một quyền thì đường ghi thật hỏng, thừa
#: một quyền thì `test_control_plane_privileges.py` ĐỎ. Cấp thêm cho tiện sẽ bị
#: bắt, và đó là chủ ý — đây là chỗ quyền hay nở ra âm thầm nhất.
#:
#: Vai ỨNG DỤNG không có quyền nào trên các bảng này, không có ngoại lệ.
CONTROL_PLANE_TABLES: dict[str, frozenset[str]] = {
    "tenant_purges": frozenset({"INSERT"}),
}

#: Bốn quyền bảng mà vai ứng dụng có ở mọi nơi khác — dùng để THU LẠI trên các
#: bảng điều khiển. Phải khớp `provision_db_roles.TABLE_PRIVILEGES`; phép kiểm
#: cấu trúc canh hai hằng số này không lệch nhau.
APP_TABLE_PRIVILEGES: tuple[str, ...] = ("SELECT", "INSERT", "UPDATE", "DELETE")


@contextmanager
def control_cursor():
    """Con trỏ chạy dưới vai ĐIỀU KHIỂN. Đọc tên hàm là biết đang bước qua ranh giới.

    Tên dài và khác hẳn `_cursor()` là chủ ý: một người đọc `tenant_lifecycle.py`
    phải thấy ngay rằng dòng đó không chạy bằng danh tính phục vụ request.

    Điều KHÔNG được làm ở đây
    -------------------------
    Không đặt `app.system_scope`, không đặt `app.tenant_id`. Năng lực của kết
    nối này đến từ QUYỀN của vai trên bảng, không từ một sentinel mà vai ứng
    dụng cũng tự đặt được. Trộn hai cơ chế sẽ làm mất đúng điều vừa đạt được:
    một thao tác điều khiển sẽ lại phụ thuộc vào một biến mà `voya_app` bật lên
    được.

    Không phải chỗ phân quyền. Kết nối này chỉ trả lời "đường mã này có năng lực
    điều khiển ở tầng SQL không". Câu "người dùng có được phép làm việc này
    không" phải đã được trả lời TRƯỚC, ở tầng ứng dụng.
    """
    from app.storage.postgres_connection import connect_control

    conn = connect_control()
    try:
        with conn:
            with conn.cursor() as cur:
                yield cur
    finally:
        conn.close()


def control_plane_tables() -> tuple[str, ...]:
    """Tên bảng điều khiển, thứ tự ổn định để câu lệnh sinh ra lặp lại được."""
    return tuple(sorted(CONTROL_PLANE_TABLES))


def revoke_from_app_statements(app_role: str) -> list[str]:
    """Thu lại MỌI quyền của vai ứng dụng trên các bảng điều khiển.

    Phải chạy SAU `GRANT ... ON ALL TABLES`, vì câu đó quét cả những bảng này —
    cùng lý do và cùng vị trí với `REFERENCE_TABLES`.
    """
    quoted = f'"{app_role}"'
    return [
        f"REVOKE {', '.join(APP_TABLE_PRIVILEGES)} ON {bang} FROM {quoted}"
        for bang in control_plane_tables()
    ]


def grant_to_control_statements(control_role: str) -> list[str]:
    """Cấp cho vai điều khiển ĐÚNG tập quyền đã khai báo, không hơn.

    `REVOKE ALL` trước rồi `GRANT` lại: nếu ai đó từng cấp tay `UPDATE` cho vai
    điều khiển, một câu `GRANT INSERT` không lấy nó đi, và bảng quyền sẽ trôi
    khỏi khai báo mà không ai thấy. Lượt cấp phát này là ĐỊNH NGHĨA trạng thái,
    không phải một lời đề nghị bổ sung.
    """
    quoted = f'"{control_role}"'
    cau: list[str] = []
    for bang in control_plane_tables():
        cau.append(f"REVOKE ALL ON {bang} FROM {quoted}")
        quyen = ", ".join(sorted(CONTROL_PLANE_TABLES[bang]))
        cau.append(f"GRANT {quyen} ON {bang} TO {quoted}")
    return cau

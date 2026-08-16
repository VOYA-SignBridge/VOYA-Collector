#!/usr/bin/env python3
"""Gieo fixture đối kháng tối thiểu cho phép đo cách ly tenant.

    docker cp scripts/seed_isolation_fixture.py voya_backend_iso:/tmp/
    docker exec voya_backend_iso python /tmp/seed_isolation_fixture.py

CHỈ CHẠY TRÊN CƠ SỞ DỮ LIỆU TEST. Script tự từ chối nếu `current_database()`
là `signdb` — không dựa vào người gọi nhớ đúng.

Vì sao phải gieo dữ liệu THẬT ở CẢ HAI tenant
=============================================
Phép thử "A đọc tài nguyên của B" chỉ có giá trị khi tài nguyên của B TỒN TẠI.
Nếu nó không tồn tại, máy chủ trả 404 và bộ đo chấm là "đã chặn" — một điểm
tuyệt đối kiếm được từ hư không. Đây đúng là lỗi mà chốt OpenAPI vừa bắt ở
mức đường dẫn; ở mức dữ liệu thì không có sơ đồ nào bắt hộ, chỉ có fixture.

Nói cách khác: fixture phải làm cho phép thử CÓ KHẢ NĂNG THÀNH CÔNG SAI. Một
bộ đo không thể thất bại thì không đo gì cả.

Vì sao dùng `create_tenant()` chứ không INSERT thẳng
====================================================
`classes` trỏ tới `dialects` bằng khoá ngoại TỔ HỢP `(tenant_id, dialect)`, nên
một tenant không có danh mục riêng thì không giữ nổi một lớp nào. `create_tenant`
nhân bản danh mục như một phần của thao tác. INSERT tay vào `tenants` tạo ra một
tenant trông bình thường trong danh sách và từ chối mọi lượt ghi.
"""

from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path


def _nap_duong_dan_app() -> None:
    """Tìm gốc mã `app/` ở CẢ HAI kiểu container.

    `voya_backend_iso` nướng mã vào `/app`; container test gắn cây làm việc ở
    `/src` nên mã nằm ở `/src/backend`. Bản đầu ghi cứng `/app`, nên kịch bản này
    không nạp được ở container test — và helper tenant/user/membership trong đây
    lại đúng là thứ `seed_cross_store.py` phải tái dùng thay vì viết lại SQL lần
    thứ hai.
    """
    ung_vien = ["/app", "/src/backend",
                str(Path(__file__).resolve().parents[1] / "backend")]
    for goc in ung_vien:
        if (Path(goc) / "app" / "__init__.py").exists():
            sys.path.insert(0, goc)
            return
    raise SystemExit(f"khong tim thay goc ma 'app/' trong: {ung_vien}")


_nap_duong_dan_app()

from app.auth import get_password_hash                    # noqa: E402
from app.storage.metadata_db import _cursor               # noqa: E402
from app.tenant_admin import create_tenant                # noqa: E402
from app.tenant_context import system_scope, tenant_scope  # noqa: E402

MAT_KHAU = "IsoProbe!2026"

BEN = [
    {"tenant": "iso_a", "ten": "ISO Tenant A", "user": "iso_user_a"},
    {"tenant": "iso_b", "ten": "ISO Tenant B", "user": "iso_user_b"},
]

#: Quản trị viên nền tảng THUỘC tenant A. Xem `_tao_user` cho lý do đầy đủ: nếu
#: không có tài khoản vượt được cổng quyền sở hữu thì cổng phạm vi tenant ở phía
#: sau nó chưa từng được kiểm, và một loạt 403 sẽ được ghi nhầm thành "cách ly
#: hoạt động". Đây KHÔNG phải một ngoại lệ được cấp để lấy kết quả đẹp — nó là
#: đối tượng khiến kết quả trở nên khắt khe hơn.
QUAN_TRI = {"tenant": "iso_a", "user": "iso_admin_a"}

#: Quản trị viên CỦA TENANT — khác hẳn `QUAN_TRI` ở trên.
#:
#: Hai loại chủ thể này bị lẫn rất dễ, và lẫn thì phép đo vô nghĩa:
#:
#:     users.is_admin = TRUE        -> platform_administrator   (phạm vi NỀN TẢNG)
#:     tenant_members.role='admin'  -> tenant_administrator      (phạm vi MỘT TENANT)
#:
#: Nguồn: docs/03-security/AUTHORIZATION.md §247. Ngày 16/08/2026 một lượt đo
#: dùng `iso_admin_a` (is_admin=TRUE) rồi kỳ vọng nó bị chặn ở ranh giới tenant.
#: Nó KHÔNG bị chặn — và đó là đúng thiết kế, vì tài khoản ấy là quản trị viên
#: nền tảng. Phép đo khi đó đang kiểm sai loại chủ thể, chứ hệ thống không sai.
#:
#: Tài khoản này có `is_admin=FALSE` và vai `admin` TRONG `iso_a`. Nó là chủ thể
#: đúng để hỏi "quyền cao trong tenant có nới được ranh giới tenant không".
QUAN_TRI_TENANT = {"tenant": "iso_a", "user": "iso_tadmin_a", "role": "admin"}


def _chan_neu_san_xuat() -> str:
    with _cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        db, who = cur.fetchone()
    if db == "signdb":
        raise SystemExit(f"TU CHOI: dang tro vao san xuat ({db}). Dung lai.")
    print(f"  csdl={db}  vai={who}")
    return db


def _co_tenant(tenant_id: str) -> bool:
    with system_scope("kiem tra fixture do luong"):
        with _cursor() as cur:
            cur.execute("SELECT 1 FROM tenants WHERE tenant_id = %s", (tenant_id,))
            return cur.fetchone() is not None


def _dialect_cua(tenant_id: str) -> str:
    """Một dialect THUỘC tenant này — khoá ngoại tổ hợp không nhận của tenant khác."""
    with tenant_scope(tenant_id):
        with _cursor() as cur:
            cur.execute(
                "SELECT dialect_id FROM dialects WHERE tenant_id = %s "
                "ORDER BY dialect_id LIMIT 1",
                (tenant_id,),
            )
            row = cur.fetchone()
    if not row:
        raise SystemExit(f"tenant {tenant_id} khong co dialect nao — danh muc chua nhan ban")
    return row[0]


def _tao_user(tenant_id: str, username: str, is_admin: bool = False) -> str:
    """`is_admin` là cờ QUẢN TRỊ NỀN TẢNG, không phải vai trong tenant.

    Vì sao phép đo cần một tài khoản như vậy
    ----------------------------------------
    `POST /classes/{uid}/sessions/{sid}/reassign` hỏi hai câu, theo thứ tự:

        1. người gọi có SỞ HỮU mẫu này không   (`auth_user_id`, hoặc `is_admin`)
        2. lớp đích có nằm trong PHẠM VI của người gọi không

    Lượt đo 15/08/2026 không bao giờ chạm được câu 2: mọi lượt thử xuyên tenant
    dừng ở câu 1 với 403, và kết quả được ghi là "đã chặn". Nhưng nó bị chặn bởi
    QUYỀN SỞ HỮU — một tính chất hoàn toàn khác, và một tính chất mà `is_admin`
    vô hiệu hoá hoàn toàn.

    Nói cách khác: bộ đo cũ không thể phân biệt "cách ly tenant hoạt động" với
    "chưa có ai đi tới chỗ cách ly tenant được kiểm". Tài khoản này tồn tại để
    vượt qua câu 1 một cách hợp lệ, để câu 2 lần đầu tiên bị kiểm thật.

    Bất biến cần chứng minh là: cách ly tenant ĐỘC LẬP với phân quyền sở hữu.
    Một quản trị viên nền tảng của tenant A vẫn KHÔNG được phân giải tài nguyên
    của tenant B — và phải nhận đúng câu trả lời như với một UID không tồn tại.
    """
    with system_scope("gieo tai khoan do luong"):
        with _cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
            if row:
                # Đặt lại mật khẩu để lượt chạy sau vẫn đăng nhập được bằng
                # hằng số ở trên, kể cả khi ai đó đã đổi. `is_admin` cũng đặt
                # lại: một lượt gieo phải cho ra CÙNG một trạng thái dù tài
                # khoản đã có sẵn hay không, nếu không thì hai lượt chạy đo hai
                # hệ thống khác nhau.
                cur.execute(
                    "UPDATE users SET password_hash = %s, is_active = TRUE, "
                    "email_verified_at = COALESCE(email_verified_at, now()), "
                    "is_admin = %s, tenant_id = %s WHERE id = %s",
                    (get_password_hash(MAT_KHAU), is_admin, tenant_id, row[0]),
                )
                return str(row[0])
            uid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO users (id, username, email, password_hash, is_active, "
                "is_admin, tenant_id, email_verified_at) "
                "VALUES (%s, %s, %s, %s, TRUE, %s, %s, now())",
                (uid, username, f"{username}@iso.local",
                 get_password_hash(MAT_KHAU), is_admin, tenant_id),
            )
            return uid


def _gan_tu_cach_thanh_vien(tenant_id: str, user_id: str,
                            role: str = "editor") -> None:
    """Một tài khoản sống PHẢI là thành viên của tenant nhà mình.

    Vì sao đây không phải chi tiết vụn
    ----------------------------------
    Ngày 15/08/2026, `test_every_live_user_is_a_member_of_their_tenant` đỏ vì ba
    tài khoản do CHÍNH kịch bản này gieo: `iso_user_a`, `iso_user_b`, `perf_user`
    — tất cả đều có `users.tenant_id` nhưng không có dòng `memberships` nào.

    Bất biến bị vi phạm là bất biến THẬT: đường phân quyền của sản xuất đi

        User -> TenantMembership -> EffectiveScope -> AccessDecision

    nên một tài khoản thiếu vế thứ hai bị hệ thống coi là "không phải thành
    viên" ở mọi phép kiểm quyền, kể cả với chủ tổ chức.

    Hậu quả với chính phép đo mà kịch bản này phục vụ
    ------------------------------------------------
    Nó tạo ra một BIẾN GÂY NHIỄU. Kết quả "iso_user_a không đọc được dữ liệu của
    iso_b" có thể đến từ hai nguyên nhân hoàn toàn khác nhau:

        * cô lập tenant hoạt động đúng, HOẶC
        * tài khoản ấy vốn đã không có tư cách thành viên hợp lệ

    Phép đo cũ chưa chắc sai về KẾT QUẢ, nhưng nó không phân định được hai khả
    năng đó. Đối chứng DƯƠNG — "A đọc/ghi được dữ liệu của chính A" — mới là thứ
    loại bỏ nhiễu, và nó chỉ có nghĩa khi tài khoản ở trạng thái hợp lệ.

    Vì sao gọi đường nghiệp vụ chứ không `INSERT` thẳng
    ---------------------------------------------------
    `tenant_members` là VIEW trên `memberships`, và bảng nền có chỉ mục duy nhất
    TỪNG PHẦN (`WHERE scope_level = 'TENANT'`) mà `ON CONFLICT` phải nêu lại.
    Chép logic ấy sang đây là dựng một đường gieo thứ hai sẽ trôi khỏi đường
    thật. `add_member` cũng là nơi kiểm hạn mức ghế — fixture đi qua đúng cổng
    mà người dùng thật đi qua.

    Vì sao PHẢI cấp vai, dù `add_member` mặc định `NO_ROLE`
    -------------------------------------------------------
    Lập luận ban đầu — "gắn người vào tổ chức và cấp vai là hai hành động khác
    nhau; phép đo cô lập hỏi về tenant, không hỏi về vai" — đúng về mặt mô hình
    và SAI về mặt phép đo. Đối chứng dương bác bỏ nó bằng số:

        A đọc danh tính của chính mình        ĐẠT
        A đọc phiên thu của lớp CỦA CHÍNH A   TRƯỢT (404)
        A đọc dữ liệu mẫu CỦA CHÍNH A         TRƯỢT (404)

    Thành viên không vai không đọc được gì trong chính tenant của mình. Khi đó
    mọi ca "đã chặn" ở nhóm đối kháng không còn phân định được giữa "cô lập
    đúng" và "tài khoản này vốn không đọc được gì" — tức phép đo mất khả năng
    thất bại, và một phép đo không thể thất bại thì không đo gì cả.

    `editor` là vai làm việc bình thường (`ROLES = ("admin", "editor")`). Cố ý
    KHÔNG dùng `admin`: đường quản trị đi nhánh mã khác và nới một phần lọc theo
    tenant, tức sẽ đo một đoạn mã không phải đoạn người dùng thường đi qua — và
    với một phép đo CÔ LẬP thì dùng vai mạnh nhất là tự làm yếu kết luận.

    Mặc định của `add_member` KHÔNG đổi. Chỗ cần vai là fixture này, không phải
    cả hệ thống.
    """
    from app import tenant_admin

    tenant_admin.add_member(tenant_id, user_id, role=role)


def _khang_dinh_user_ton_tai(username: str) -> str:
    """Đọc lại SAU KHI giao dịch đã đóng. Thiếu thì dừng, không đi tiếp.

    Ngày 15/08/2026, `_tao_user` in ra là đã tạo `perf_user` với một UUID cụ
    thể, và hàng đó không có trong cơ sở dữ liệu — kể cả khi đọc bằng `admin`,
    tức không phải RLS che. Chèn lại bằng đúng đoạn mã ấy thì thành công.
    NGUYÊN NHÂN CHƯA XÁC ĐỊNH.

    Không biết vì sao thì chưa sửa được, nhưng biến một lượt mất im lặng thành
    một lượt hỏng ồn ào thì làm được ngay — và đó là phần nguy hiểm. Không có
    khẳng định này, bước sau (đăng nhập lấy token) trả 401, và 401 trông y hệt
    "sai mật khẩu"; đường truy vết dẫn đi hoàn toàn sai hướng.

    Đọc ở một giao dịch KHÁC, không phải cùng giao dịch với lượt ghi: đọc lại
    trong cùng giao dịch chỉ xác nhận rằng câu lệnh đã chạy, không xác nhận
    rằng nó đã được commit.
    """
    with system_scope("khang dinh tai khoan da ton tai that"):
        with _cursor() as cur:
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            row = cur.fetchone()
    if not row:
        raise SystemExit(
            f"GIEO HONG: '{username}' bao la da tao nhung doc lai khong thay.\n"
            f"Dung lai o day. Chay tiep se cho mot loi 401 luc dang nhap va\n"
            f"loi do trong y het 'sai mat khau'."
        )
    return str(row[0])


def _khang_dinh_la_thanh_vien(username: str, tenant_id: str, user_id: str) -> None:
    """Đọc lại tư cách thành viên ở một giao dịch KHÁC, y như với tài khoản.

    Cùng lý do đã ghi ở `_khang_dinh_user_ton_tai`: đọc lại trong cùng giao dịch
    chỉ xác nhận câu lệnh đã chạy, không xác nhận nó đã được commit. Và một
    fixture thiếu tư cách thành viên KHÔNG hỏng ồn ào — nó chỉ làm phép đo cô
    lập mất đối chứng dương, rồi mọi ca âm vẫn xanh.
    """
    with system_scope("khang dinh tu cach thanh vien da ton tai that"):
        with _cursor() as cur:
            cur.execute(
                "SELECT 1 FROM tenant_members WHERE user_id = %s AND tenant_id = %s",
                (user_id, tenant_id))
            co = cur.fetchone() is not None
    if not co:
        raise SystemExit(
            f"GIEO HONG: '{username}' khong co tu cach thanh vien trong "
            f"'{tenant_id}'.\nDung lai o day: phep do co lap se mat doi chung "
            f"DUONG, va ket qua 'khong doc duoc tenant kia' se khong phan dinh\n"
            f"duoc giua 'co lap dung' va 'tai khoan von da khong co quyen'."
        )


def _tao_workspace_project(tenant_id: str) -> tuple[str, str]:
    with tenant_scope(tenant_id):
        with _cursor() as cur:
            cur.execute(
                "SELECT workspace_id FROM workspaces WHERE tenant_id = %s "
                "ORDER BY created_at LIMIT 1", (tenant_id,))
            row = cur.fetchone()
            if row:
                ws = str(row[0])
            else:
                ws = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO workspaces (workspace_id, tenant_id, name, is_default) "
                    "VALUES (%s, %s, %s, TRUE)", (ws, tenant_id, f"ws-{tenant_id}"))

            cur.execute(
                "SELECT project_id FROM projects WHERE tenant_id = %s "
                "ORDER BY created_at LIMIT 1", (tenant_id,))
            row = cur.fetchone()
            if row:
                return ws, str(row[0])
            pr = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO projects (project_id, tenant_id, workspace_id, name, is_default) "
                "VALUES (%s, %s, %s, %s, TRUE)", (pr, tenant_id, ws, f"pj-{tenant_id}"))
            return ws, pr


def _tao_lop_va_mau(tenant_id: str, dialect: str) -> tuple[str, str]:
    slug = f"iso-{tenant_id}"
    with tenant_scope(tenant_id):
        with _cursor() as cur:
            cur.execute(
                "SELECT class_uid FROM classes WHERE tenant_id = %s AND slug = %s",
                (tenant_id, slug))
            row = cur.fetchone()
            if row:
                cuid = str(row[0])
            else:
                cuid = uuid.uuid4().hex[:16]
                cur.execute(
                    "INSERT INTO classes (class_uid, slug, label_original, language, "
                    "dialect, tenant_id, is_active) "
                    "VALUES (%s, %s, %s, 'vn', %s, %s, TRUE)",
                    (cuid, slug, f"lop do luong {tenant_id}", dialect, tenant_id))

            cur.execute(
                "SELECT sample_uid FROM samples WHERE tenant_id = %s AND class_uid = %s "
                "LIMIT 1", (tenant_id, cuid))
            row = cur.fetchone()
            if row:
                return cuid, str(row[0])
            # `samples_uid_is_hex10`: CHECK (sample_uid ~ '^[0-9a-f]{10}$').
            # Đúng mười, không phải "tối đa mười".
            suid = uuid.uuid4().hex[:10]
            cur.execute(
                "INSERT INTO samples (sample_uid, class_uid, slug, label_original, "
                "language, dialect, tenant_id, source_type, status) "
                "VALUES (%s, %s, %s, %s, 'vn', %s, %s, 'camera', 'ready')",
                (suid, cuid, slug, f"mau do luong {tenant_id}", dialect, tenant_id))
            return cuid, suid


def _tai_khoan_do_hieu_nang() -> dict:
    """Một người dùng THƯỜNG trong tenant giữ khối dữ liệu lớn.

    `iso_a` và `iso_b` mỗi bên đúng một lớp và một mẫu — vừa đủ để phép thử đối
    kháng có thể thành công sai, nhưng KHÔNG đại diện cho chi phí truy vấn. Đo
    độ trễ đường tenant-scoped bằng một tenant một dòng sẽ ra một bảng số đẹp
    của một hệ thống không tồn tại.

    Dùng vai THƯỜNG chứ không phải quản trị: đường quản trị đi qua nhánh khác
    và thường bỏ qua một phần lọc theo tenant, tức đo một đường mã khác với
    đường mà người dùng thật đi.
    """
    # PHẢI có `system_scope`. Không có ngữ cảnh tenant thì RLS khớp 0 dòng, và
    # `GROUP BY` trên 0 dòng trả về KHÔNG dòng nào — code đọc thành "hệ thống
    # không có mẫu nào" rồi lặng lẽ bỏ qua bước này. Bản đầu của hàm đúng như
    # vậy: nó trả `{}` trên một cơ sở dữ liệu có 3.862 mẫu.
    with system_scope("do kich thuoc du lieu tung tenant"):
        with _cursor() as cur:
            cur.execute(
                "SELECT tenant_id, count(*) FROM samples GROUP BY tenant_id "
                "ORDER BY 2 DESC LIMIT 1")
            row = cur.fetchone()
    if not row:
        raise SystemExit("khong tenant nao co mau — kiem tra lai pham vi truy van")
    tenant, so_mau = row[0], row[1]
    _tao_user(tenant, "perf_user")
    uid = _khang_dinh_user_ton_tai("perf_user")
    # `perf_user` KHÔNG được đặc cách chỉ vì nó phục vụ phép đo hiệu năng. Nó là
    # một tài khoản ứng dụng sống theo đúng lược đồ hiện tại, nên nó chịu đúng
    # bất biến của mọi tài khoản sống. Nếu một ngày có tải thật cần một chủ thể
    # KHÔNG phải thành viên tenant, thì đó phải là một loại chủ thể được mô hình
    # hoá tường minh — không phải một `users` thường được fixture cho phép vi
    # phạm ràng buộc nghiệp vụ.
    _gan_tu_cach_thanh_vien(tenant, uid)
    _khang_dinh_la_thanh_vien("perf_user", tenant, uid)
    print(f"\n== tai khoan do hieu nang ==")
    print(f"  perf_user trong '{tenant}' ({so_mau} mau)  id={uid[:8]}…")
    return {"username": "perf_user", "user_id": uid, "tenant_id": tenant,
            "so_mau_tenant": so_mau}


def main() -> int:
    print("== kiem tra dich ==")
    db = _chan_neu_san_xuat()

    ket = {"database": db, "mat_khau": MAT_KHAU, "ben": {}}

    for b in BEN:
        tid = b["tenant"]
        print(f"\n== {tid} ==")
        if _co_tenant(tid):
            print("  tenant da co, dung lai")
        else:
            with system_scope("gieo tenant do luong"):
                create_tenant(tid, display_name=b["ten"], slug=tid, clone_catalog=True)
            print("  tao tenant + nhan ban danh muc")

        dialect = _dialect_cua(tid)
        _tao_user(tid, b["user"])
        uid = _khang_dinh_user_ton_tai(b["user"])
        _gan_tu_cach_thanh_vien(tid, uid)
        _khang_dinh_la_thanh_vien(b["user"], tid, uid)
        ws, pr = _tao_workspace_project(tid)
        cuid, suid = _tao_lop_va_mau(tid, dialect)

        print(f"  user={b['user']} ({uid[:8]}…)  ws={ws[:8]}…  project={pr[:8]}…")
        print(f"  class={cuid}  sample={suid}")

        ket["ben"][tid] = {
            "tenant_id": tid, "username": b["user"], "user_id": uid,
            "workspace_id": ws, "project_id": pr,
            "class_uid": cuid, "sample_uid": suid, "dialect": dialect,
        }

    # Khẳng định cuối: mỗi bên phải THẬT SỰ đọc được tài nguyên của chính mình.
    # Nếu bước này hỏng thì mọi kết quả "đã chặn" ở bộ đo sau đều vô nghĩa — sẽ
    # không phân biệt được "cách ly chặn" với "dữ liệu không tồn tại".
    print("\n== khang dinh: moi ben doc duoc do cua chinh minh ==")
    for tid, v in ket["ben"].items():
        with tenant_scope(tid):
            with _cursor() as cur:
                cur.execute("SELECT count(*) FROM classes WHERE class_uid = %s",
                            (v["class_uid"],))
                nc = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM samples WHERE sample_uid = %s",
                            (v["sample_uid"],))
                ns = cur.fetchone()[0]
        print(f"  {tid}: class={nc} sample={ns}")
        if nc != 1 or ns != 1:
            raise SystemExit(f"{tid} khong doc duoc tai nguyen cua chinh no — fixture hong")

    # Quản trị viên nền tảng của tenant A. Chịu ĐÚNG bất biến tư cách thành viên
    # như mọi tài khoản sống — `is_admin` mở quyền, không miễn ràng buộc.
    print(f"\n== quan tri vien nen tang ==")
    _tao_user(QUAN_TRI["tenant"], QUAN_TRI["user"], is_admin=True)
    admin_id = _khang_dinh_user_ton_tai(QUAN_TRI["user"])
    _gan_tu_cach_thanh_vien(QUAN_TRI["tenant"], admin_id)
    _khang_dinh_la_thanh_vien(QUAN_TRI["user"], QUAN_TRI["tenant"], admin_id)
    print(f"  {QUAN_TRI['user']} trong '{QUAN_TRI['tenant']}'  id={admin_id[:8]}… "
          f"is_admin=True")
    ket["quan_tri"] = {"username": QUAN_TRI["user"], "user_id": admin_id,
                       "tenant_id": QUAN_TRI["tenant"], "is_admin": True,
                       "loai": "platform_administrator"}

    # Quản trị viên CỦA TENANT: is_admin=FALSE, vai `admin` trong iso_a.
    print("\n== quan tri vien TENANT ==")
    _tao_user(QUAN_TRI_TENANT["tenant"], QUAN_TRI_TENANT["user"], is_admin=False)
    tadmin_id = _khang_dinh_user_ton_tai(QUAN_TRI_TENANT["user"])
    _gan_tu_cach_thanh_vien(QUAN_TRI_TENANT["tenant"], tadmin_id,
                            role=QUAN_TRI_TENANT["role"])
    _khang_dinh_la_thanh_vien(QUAN_TRI_TENANT["user"], QUAN_TRI_TENANT["tenant"],
                              tadmin_id)
    print(f"  {QUAN_TRI_TENANT['user']} trong '{QUAN_TRI_TENANT['tenant']}'  "
          f"id={tadmin_id[:8]}… is_admin=False role={QUAN_TRI_TENANT['role']}")
    ket["quan_tri_tenant"] = {
        "username": QUAN_TRI_TENANT["user"], "user_id": tadmin_id,
        "tenant_id": QUAN_TRI_TENANT["tenant"], "is_admin": False,
        "role": QUAN_TRI_TENANT["role"], "loai": "tenant_administrator"}

    ket["do_hieu_nang"] = _tai_khoan_do_hieu_nang()

    with open("/tmp/iso_fixture.json", "w", encoding="utf-8") as fh:
        json.dump(ket, fh, ensure_ascii=False, indent=2)
    print("\nda ghi /tmp/iso_fixture.json")
    print(json.dumps(ket, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

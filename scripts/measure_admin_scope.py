#!/usr/bin/env python3
"""B6 — quyền quản trị KHÔNG được nới ranh giới tenant.

    python scripts/measure_admin_scope.py --base http://voya_backend_iso:8000 \
        --fixture /src/.measurement/repro-.../fixture.json --dsn "$DSN"

Bất biến cần chứng minh
=======================
```
Admin(A)  ->  có thể làm điều được cấp TRONG A
Admin(A)  -X-> Data(B)
Admin(A)  -X-> Data(default)
Admin(A)  -X-> hành động ở phạm vi HỆ THỐNG
```

Hai khái niệm phải tách, và chúng bị lẫn ở đúng chỗ này:

```
quyền SỞ HỮU (ownership authorization)   is_admin vượt qua được — theo thiết kế
cách ly TENANT (tenant isolation)        is_admin KHÔNG được vượt qua
```

Ca S của lượt đo 15/08/2026 đã cho bằng chứng về chính điểm này: một lượt thử
xuyên tenant bị chặn bởi `auth_user_id` chứ không phải bởi phạm vi, nên kết quả
"đã chặn" khi ấy không nói gì về cách ly.

Vì sao chạy ca ÂM TRƯỚC
=======================
Ca dương xanh không phân biệt được "phân quyền đúng" với "phân quyền không tồn
tại" — cả hai đều cho ALLOW. Ca âm thì phân biệt được: fail-open lộ ra ngay.
Chạy ca âm trước cũng tránh việc một lượt ghi thành công ở ca dương làm thay đổi
trạng thái mà ca âm sau đó dựa vào.

`default` được kiểm RIÊNG
=========================
Sau khi bỏ `DEFAULT 'default'` khỏi `users.tenant_id` (16/08/2026), `default`
vẫn là một tenant hợp lệ — nó là nguồn bootstrap/seed. Điều phải chứng minh là
nó KHÔNG có ngữ nghĩa "tenant mà admin nào cũng vào được".
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_reassign_gate import _goi, dang_nhap          # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--fixture", required=True)
    ap.add_argument("--dsn", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    import os
    os.environ.setdefault("DATABASE_URL", args.dsn)

    fx = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    b_class = next(d["class_uid"] for d in fx["doi_tuong"]
                   if d["tenant_id"] == "iso_b" and d["vai_tro"] == "target")
    b_sample = next(d["sample_uid"] for d in fx["doi_tuong"]
                    if d["tenant_id"] == "iso_b" and d["vai_tro"] == "target")

    # HAI chủ thể, HAI kỳ vọng khác nhau. Lẫn chúng là lỗi của lượt đo đầu
    # (16/08/2026): nó dùng `iso_admin_a` rồi kỳ vọng bị chặn ở ranh giới
    # tenant, trong khi tài khoản ấy là QUẢN TRỊ VIÊN NỀN TẢNG.
    #
    #     users.is_admin = TRUE        -> platform_administrator
    #     tenant_members.role='admin'  -> tenant_administrator
    #
    # Nguồn: docs/03-security/AUTHORIZATION.md §247.
    op_tadmin = dang_nhap(args.base, "iso_tadmin_a")   # quản trị TENANT
    op_padmin = dang_nhap(args.base, "iso_admin_a")    # quản trị NỀN TẢNG
    ket = []

    def ca(nhan: str, pt: str, duong: str, mong: str, than_gui=None, op=None):
        ma, than = _goi(op or op_tadmin, args.base, pt, duong, than_gui)
        # "Chặn" gồm cả 404: tài nguyên ngoài phạm vi phải KHÔNG PHÂN BIỆT được
        # với tài nguyên không tồn tại. 403 kèm thông điệp "thuộc tenant khác"
        # sẽ là một phép thử tồn tại, nên nó KHÔNG được tính là đạt.
        chan = ma in (401, 403, 404)
        dat = chan if mong == "DENY" else (ma == 200)
        ket.append({"ca": nhan, "http": ma, "mong": mong, "dat": dat,
                    "than": than[:160]})
        print(f"  {'DAT ' if dat else 'TRUOT'} {nhan:44} http={ma:3} mong={mong}")
        if not dat:
            print(f"        {than[:200]}")

    print("=== CA AM (chay TRUOC) ===")
    # B6-1 — quản trị A chạm tài nguyên của B
    ca("B6-1 tadmin(A) -> lop cua B (sessions)", "GET",
       f"/api/v1/classes/{b_class}/sessions", "DENY")
    ca("B6-1 tadmin(A) -> mau cua B (data)", "GET",
       f"/api/v1/dataset/samples/{b_sample}/data", "DENY")
    # B6-2 — quản trị A chạm tenant seed
    ca("B6-2 tadmin(A) -> ho so tenant default", "GET",
       "/api/v1/tenants/default", "DENY")
    # B6-3 — quản trị A làm hành động phạm vi HỆ THỐNG
    ca("B6-3 tadmin(A) -> liet ke MOI tenant", "GET",
       "/api/v1/tenants", "DENY")
    # KHÔNG bắn DELETE thật ở ca âm. Lượt đo đầu đã xoá mềm `iso_b` thật và
    # phải khôi phục tay. Một ca âm chỉ có nghĩa khi nó ĐƯỢC chặn; nếu nó
    # KHÔNG bị chặn thì nó vừa phá fixture. Dùng thao tác ĐỌC tương đương ở
    # phạm vi hệ thống thay thế — nó trả lời cùng câu hỏi mà không phá gì.
    ca("B6-3 tadmin(A) -> doc ho so tenant B", "GET",
       "/api/v1/tenants/iso_b", "DENY")

    print("\n=== CA DUONG ===")
    # Ca DƯƠNG then chốt của B: quản trị TENANT phải xem được bảng điều khiển
    # của CHÍNH tổ chức mình.
    #
    #   403 -> cổng phân quyền sai (vẫn đang đòi cờ nền tảng `is_admin`)
    #   200 kèm dữ liệu của B -> phạm vi sai
    #
    # Phải đạt CẢ HAI mới có nghĩa. Trước 16/08/2026 endpoint gác bằng
    # `require_admin` (= platform_administrator) trong khi dữ liệu đã thu về
    # phạm vi tenant — nên nó không phục vụ đúng ai: quản trị tenant bị 403 ở
    # chính bảng của mình, còn quản trị nền tảng qua được nhưng chỉ thấy tenant
    # nhà của họ.
    ma, than = _goi(op_tadmin, args.base, "GET", "/api/v1/admin/data-report")
    lo_b = sorted({u for u in (b_class, b_sample) if u in than})
    dat = (ma == 200 and not lo_b)
    ket.append({"ca": "B+-1 tadmin(A) -> data-report cua A", "http": ma,
                "mong": "ALLOW+scoped", "dat": dat,
                "dinh_danh_B_lo": lo_b, "than": than[:200]})
    print(f"  {'DAT ' if dat else 'TRUOT'} "
          f"{'B+-1 tadmin(A) -> data-report cua A':44} http={ma:3} "
          f"dinh_danh_B_lo={lo_b or '-'}")
    if not dat:
        print(f"        {than[:220]}")
    # Quản trị NỀN TẢNG được phép ở phạm vi hệ thống — theo thiết kế, và hàng
    # rào là `audit_log` chứ không phải phân quyền (COMMUNITY_DATA_COMMONS §10).
    ca("padmin -> liet ke MOI tenant (dung thiet ke)", "GET",
       "/api/v1/tenants", "ALLOW", op=op_padmin)
    ca("padmin -> bang dieu khien du lieu", "GET",
       "/api/v1/admin/data-report", "ALLOW", op=op_padmin)

    ok = all(r["dat"] for r in ket)
    print(f"\n=== TONG: {'DAT' if ok else 'TRUOT'} ===")
    if args.out:
        Path(args.out).write_text(json.dumps(ket, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"da ghi {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

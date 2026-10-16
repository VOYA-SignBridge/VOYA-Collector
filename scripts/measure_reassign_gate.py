#!/usr/bin/env python3
"""Bốn ca nghiệm thu cho `POST /classes/{uid}/sessions/{sid}/reassign`.

    python scripts/measure_reassign_gate.py \
        --base http://127.0.0.1:8020 \
        --fixture .measurement/iso-.../fixture.json \
        --tenant-users iso_a=iso_user_a,iso_b=iso_user_b \
        --admin iso_admin_a

Vì sao có tệp này thay vì thêm ca vào `adversarial_isolation.py`
================================================================
Bộ đối kháng chấm theo MÃ TRẠNG THÁI HTTP. Sự cố 15/08/2026 cho thấy mã trạng
thái là một bộ đo không đủ cho đường ghi này:

    HTTP 400          người gọi thấy "thất bại"
    PostgreSQL        không đổi
    samples.csv       ĐÃ ĐỔI                  <- không mã trạng thái nào nói ra
    tệp .npz          đã hoàn nguyên          <- `file_path` treo

Một lượt bị từ chối vẫn thay đổi hệ thống. Nên bốn ca dưới đây chụp BỐN MẶT
PHẲNG trước và sau mỗi lượt gọi, và một ca chỉ ĐẠT khi cả bốn khớp kỳ vọng:

    1. hàng PostgreSQL   (`samples`, đọc dưới phạm vi tenant SỞ HỮU)
    2. hàng samples.csv  (đọc thô, không lọc — phải thấy cả rò rỉ nếu có)
    3. tệp .npz          (tồn tại ở đâu)
    4. `file_path`       (CSV trỏ tới đâu — treo hay không)

Bốn ca
======
    T4  A, chủ sở hữu, mẫu của A -> lớp KHÁC của A      phải THÀNH CÔNG
    T1  A, chủ sở hữu, mẫu của A -> lớp của B           phải bị chặn bởi PHẠM VI
    T2  quản trị A, mẫu của B    -> lớp của A           phải bị chặn bởi PHẠM VI
    T0  A, chủ sở hữu, mẫu của A -> lớp KHÔNG TỒN TẠI   mốc so sánh cho T1

T4 chạy TRƯỚC. Nó trả lời câu hỏi tiên quyết "phạm vi tenant có thực sự được
truyền vào đường này không" — nếu T4 đỏ vì thiếu phạm vi thì mọi ca an ninh sau
đó chỉ là 404 vô nghĩa, đúng loại điểm-kiếm-từ-hư-không đã hai lần làm hỏng
phép đo này.

T0 tồn tại để T1 nói được điều gì. Một mình "T1 trả 404" không phân biệt được
"cách ly chặn" với "lỗi ở đâu đó". Chỉ khi T0 và T1 cho ra CÙNG mã trạng thái và
CÙNG thân phản hồi thì mới kết luận được: tài nguyên của tenant khác không phân
biệt được với tài nguyên không tồn tại.

T2 dùng quản trị viên nền tảng CÓ CHỦ Ý. Cổng quyền sở hữu (`auth_user_id`) đứng
TRƯỚC cổng phạm vi trong endpoint, nên một tài khoản thường luôn dừng ở 403 và
cổng phạm vi không bao giờ bị kiểm. `is_admin` vô hiệu hoá cổng thứ nhất — và
bất biến cần chứng minh là cổng thứ hai vẫn giữ. Cách ly tenant phải ĐỘC LẬP với
phân quyền sở hữu.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

MAT_KHAU = "IsoProbe!2026"


# ---------------------------------------------------------------- HTTP -----

#: Cookie CSRF, echo lại trong header này (double-submit). Xem `main.csrf_protect`.
CSRF_COOKIE = "voya_csrf"


def _goi(opener, base: str, method: str, path: str,
         body: Optional[dict] = None, timeout: float = 30.0) -> tuple[int, str]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(base.rstrip("/") + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    # Không có header này thì MỌI lượt POST dừng ở 403 CSRF — trước khi chạm tới
    # quyền sở hữu hay phạm vi tenant. Nguy hiểm ở chỗ nó trông giống hệt một kết
    # quả tốt: bốn ca cùng 403, T0 và T1 "không phân biệt được", không mặt phẳng
    # nào đổi. Đó là lý do T4 (ca PHẢI thành công) là cổng của cả họ: chỉ nó phát
    # hiện được rằng chưa có lượt gọi nào thực sự tới được đường mã cần đo.
    for ck in getattr(opener, "_ho_cookie", []):
        if ck.name == CSRF_COOKIE:
            req.add_header("X-CSRF-Token", ck.value)
            break
    try:
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:                                   # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def dang_nhap(base: str, username: str):
    """Trả về một `opener` MANG SẴN phiên của tài khoản này.

    Xác thực ở hệ này đi bằng COOKIE, không phải `Authorization: Bearer` —
    `/auth/login` trả hồ sơ người dùng và đặt cookie phiên. Mỗi danh tính phải
    có hũ cookie RIÊNG: một hũ dùng chung thì lượt đăng nhập sau ghi đè lượt
    trước, và mọi ca "quản trị A" sẽ lặng lẽ chạy dưới danh tính vừa đăng nhập
    gần nhất. Bộ đo khi đó vẫn cho ra kết quả — chỉ là của một ca khác.
    """
    import http.cookiejar
    ho = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(ho))
    opener._ho_cookie = ho          # để `_goi` lấy được token CSRF ra echo lại
    ma, than = _goi(opener, base, "POST", "/api/v1/auth/login",
                    # `identifier`, không phải `username`: nhận cả tên lẫn email.
                    {"identifier": username, "password": MAT_KHAU})
    if ma != 200:
        raise SystemExit(f"dang nhap that bai cho {username}: {ma} {than[:400]}")
    # Khẳng định phiên thuộc ĐÚNG tài khoản vừa yêu cầu. Nếu không, mọi ca sau
    # đó đo nhầm chủ thể và kết quả vô nghĩa dù trông vẫn hợp lý.
    ma, than = _goi(opener, base, "GET", "/api/v1/auth/me")
    if ma != 200 or json.loads(than).get("username") != username:
        raise SystemExit(f"phien khong thuoc {username}: {ma} {than[:400]}")
    return opener


# ------------------------------------------------- ảnh chụp bốn mặt phẳng --

def _bam(p: Path) -> Optional[str]:
    if not p.exists():
        return None
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def _hang_csv(csv_path: Path, sample_uid: str) -> Optional[dict]:
    """Đọc THÔ, không lọc tenant.

    Cố ý: bộ đo phải nhìn thấy được một hàng bị ghi sai tenant. Lọc ở đây thì
    một lượt rò rỉ sẽ trông y hệt "không có gì xảy ra".
    """
    if not csv_path.exists():
        return None
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if (r.get("sample_uid") or "") == sample_uid:
                return r
    return None


def _hang_db(dsn: str, sample_uid: str) -> Optional[dict]:
    """Đọc dưới sentinel hệ thống, KHÔNG dưới phạm vi một tenant.

    Bộ đo cần biết hàng THỰC SỰ mang giá trị gì, kể cả khi nó vừa bị ghi sang
    tenant khác. Đọc dưới `tenant_scope('iso_a')` sẽ trả 0 dòng cho đúng cái
    trường hợp cần phát hiện, và 0 dòng đọc thành "không có gì thay đổi".
    """
    import psycopg2
    with psycopg2.connect(dsn) as c:
        with c.cursor() as cur:
            cur.execute("SELECT set_config('app.system_scope','on',false)")
            cur.execute(
                "SELECT class_uid, tenant_id, file_path, storage_key, auth_user_id "
                "FROM samples WHERE sample_uid = %s", (sample_uid,))
            row = cur.fetchone()
    if not row:
        return None
    return dict(zip(("class_uid", "tenant_id", "file_path",
                     "storage_key", "auth_user_id"), (str(x) for x in row)))


def chup(goc: Path, dsn: str, sample_uid: str) -> dict:
    csv_row = _hang_csv(goc / "samples.csv", sample_uid)
    db_row = _hang_db(dsn, sample_uid)
    duong = (csv_row or {}).get("file_path") or ""
    tep = (goc / duong) if duong else None
    # Quét cả cây: một tệp bị DI CHUYỂN mà `file_path` không đổi thì so sánh
    # `file_path` một mình sẽ báo "không đổi". Vị trí thật mới là bằng chứng.
    o_dau = sorted(str(p.relative_to(goc)) for p in goc.rglob(f"{sample_uid}.npz"))
    return {
        "csv": csv_row,
        "db": db_row,
        "file_path_csv": duong,
        "file_ton_tai_o_file_path": bool(tep and tep.exists()),
        "npz_thuc_te_o": o_dau,
        "npz_bam": _bam(tep) if tep else None,
    }


def khac_biet(truoc: dict, sau: dict) -> list[str]:
    ra = []
    for k in ("file_path_csv", "file_ton_tai_o_file_path", "npz_thuc_te_o", "npz_bam"):
        if truoc[k] != sau[k]:
            ra.append(f"{k}: {truoc[k]!r} -> {sau[k]!r}")
    for mp in ("csv", "db"):
        a, b = truoc[mp] or {}, sau[mp] or {}
        for col in sorted(set(a) | set(b)):
            if a.get(col) != b.get(col):
                ra.append(f"{mp}.{col}: {a.get(col)!r} -> {b.get(col)!r}")
    return ra


# ------------------------------------------------------------------ ca ----

def chay_ca(ten: str, mo_ta: str, base: str, goc: Path, dsn: str, *,
            opener, class_uid: str, session_id: str, sample_uid: str,
            target_ref: str) -> dict:
    truoc = chup(goc, dsn, sample_uid)
    ma, than = _goi(opener, base, "POST",
                    f"/api/v1/classes/{class_uid}/sessions/{session_id}/reassign",
                    {"target_class_ref": target_ref})
    sau = chup(goc, dsn, sample_uid)
    return {
        "ca": ten, "mo_ta": mo_ta,
        "http": ma, "than": than[:600],
        "target_ref": target_ref, "sample_uid": sample_uid,
        "truoc": truoc, "sau": sau, "thay_doi": khac_biet(truoc, sau),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8020")
    ap.add_argument("--fixture", required=True, help="fixture.json cua cay do")
    ap.add_argument("--dsn", default=os.environ.get("VOYA_MEASURE_DSN", ""),
                    help="DSN toi CSDL test (mac dinh $VOYA_MEASURE_DSN)")
    ap.add_argument("--admin", default="iso_admin_a")
    ap.add_argument("--out", default="", help="ghi ket qua JSON vao day")
    args = ap.parse_args()

    if not args.dsn:
        raise SystemExit("thieu --dsn (hoac $VOYA_MEASURE_DSN)")

    fx = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    # Gốc cây suy từ VỊ TRÍ của fixture.json, không đọc từ trường "root" bên
    # trong nó: cây được mount vào container ở một đường dẫn khác đường dẫn lúc
    # gieo, nên một trường "root" tuyệt đối sẽ trỏ ra ngoài.
    goc = Path(args.fixture).resolve().parent
    if not goc.exists():
        raise SystemExit(f"cay do khong con: {goc}")

    def lay(tenant: str, vai: str) -> dict:
        for d in fx["doi_tuong"]:
            if d["tenant_id"] == tenant and d["vai_tro"] == vai:
                return d
        raise SystemExit(f"fixture thieu {tenant}/{vai}")

    a_upd, a_targ = lay("iso_a", "control_update"), lay("iso_a", "target")
    b_targ = lay("iso_b", "target")

    op_a = dang_nhap(args.base, "iso_user_a")
    op_admin = dang_nhap(args.base, args.admin)

    ket = [
        # T4 TRƯỚC: nếu phạm vi tenant không tới được đường này, ca này đỏ và
        # mọi ca an ninh phía sau chỉ là 404 vô nghĩa.
        chay_ca("T4", "A chu so huu: mau cua A -> lop KHAC cua A (phai THANH CONG)",
                args.base, goc, args.dsn, opener=op_a,
                class_uid=a_upd["class_uid"], session_id=a_upd["session_id"],
                sample_uid=a_upd["sample_uid"], target_ref=a_targ["class_uid"]),
        # T0 là MỐC SO SÁNH của T1, không phải một ca an ninh.
        chay_ca("T0", "A chu so huu: mau cua A -> lop KHONG TON TAI (moc so sanh)",
                args.base, goc, args.dsn, opener=op_a,
                class_uid=a_targ["class_uid"], session_id=a_targ["session_id"],
                sample_uid=a_targ["sample_uid"],
                target_ref="khongtontai0000"),
        chay_ca("T1", "A chu so huu: mau cua A -> lop cua B (phai chan boi PHAM VI)",
                args.base, goc, args.dsn, opener=op_a,
                class_uid=a_targ["class_uid"], session_id=a_targ["session_id"],
                sample_uid=a_targ["sample_uid"], target_ref=b_targ["class_uid"]),
        # T2: quản trị viên vượt cổng quyền sở hữu một cách hợp lệ, để cổng
        # phạm vi lần đầu bị kiểm thật.
        chay_ca("T2", "quan tri A (bypass so huu): mau cua B -> lop cua A",
                args.base, goc, args.dsn, opener=op_admin,
                class_uid=b_targ["class_uid"], session_id=b_targ["session_id"],
                sample_uid=b_targ["sample_uid"], target_ref=a_targ["class_uid"]),
    ]

    for r in ket:
        print(f"\n=== {r['ca']} — {r['mo_ta']}")
        print(f"    HTTP {r['http']}  {r['than'][:200]}")
        if r["thay_doi"]:
            print("    THAY DOI:")
            for d in r["thay_doi"]:
                print(f"      {d}")
        else:
            print("    khong mat phang nao doi")

    t0 = next(r for r in ket if r["ca"] == "T0")
    t1 = next(r for r in ket if r["ca"] == "T1")
    print(f"\n=== khong phan biet duoc T0/T1 ===")
    print(f"    T0 http={t0['http']}  T1 http={t1['http']}   "
          f"{'GIONG' if t0['http'] == t1['http'] else 'KHAC'}")
    print(f"    than giong nhau: {t0['than'] == t1['than']}")

    if args.out:
        Path(args.out).write_text(json.dumps(ket, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"\nda ghi {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

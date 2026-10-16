#!/usr/bin/env python3
"""Ma trận READ-1..7 — cách ly ở ĐƯỜNG ĐỌC.

    python scripts/measure_read_isolation.py --base http://voya_backend_iso:8000 \
        --fixture /src/.measurement/repro-.../fixture.json --dsn "$DSN"

Vì sao đường đọc cần một bộ đo riêng
====================================
Nhóm ghi hỏng thì mất dữ liệu — dễ thấy. Nhóm đọc hỏng thì KHÔNG có dấu vết
nào: không hàng nào đổi, không tệp nào chuyển, log sạch. Thứ rò ra là thông tin,
và thông tin thì không để lại vết.

Bốn kiểu rò, và ba kiểu sau KHÔNG bắt được bằng cách so danh sách hàng
=====================================================================
    1. rò HÀNG          A thấy hàng của B
    2. rò TỒN TẠI       A phân biệt được "của B" với "không có"
    3. rò TỔNG HỢP      A không thấy hàng nào của B, nhưng `count` có B
    4. rò ĐỆM/ĐƯỜNG DẪN A làm nóng đệm hoặc phân giải đường dẫn của B

Kiểu 3 là kiểu nguy hiểm nhất vì nó trông vô hại nhất: giao diện không hiển thị
một hàng nào của tenant khác, nhưng con số tổng vẫn kể lại quy mô của họ.

Phép đo trung tâm: ĐỔI B, QUAN SÁT A
====================================
Không thể chứng minh "A không thấy B" bằng cách nhìn phản hồi của A một lần. Một
con số đúng ở một thời điểm không nói được nó được tính từ đâu.

Nên bộ đo này chụp phản hồi của A, rồi THÊM DỮ LIỆU VÀO B, rồi chụp lại. Bất
biến là:

    phản hồi của A trước == phản hồi của A sau

Nếu bất kỳ trường nào đổi — kể cả một con số đếm — thì trường đó được tính từ dữ
liệu của B, dù không hàng nào của B xuất hiện.

Ngoại lệ công khai
==================
`/classes/community-stats` là bảng số của trang công khai. Nó ĐƯỢC PHÉP không
đổi theo tenant người gọi, nhưng phạm vi của nó là TENANT CÔNG KHAI, không phải
"cộng mọi tenant". Nên nó cũng phải bất biến khi thêm dữ liệu vào một tenant
riêng — chỉ khác lý do. Xem READ-7.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from measure_reassign_gate import _goi, dang_nhap        # noqa: E402


#: `(nhãn, phương thức, đường dẫn)` — mọi điểm đọc của nhóm A2.
DIEM_DOC = [
    ("classes.list",       "GET",  "/api/v1/classes/list"),
    ("classes.suggest",    "GET",  "/api/v1/classes/suggest?q="),
    ("classes.collectors", "GET",  "/api/v1/classes/collectors?q="),
    ("classes.stats",      "GET",  "/api/v1/classes/stats"),
    ("dataset.labels",     "GET",  "/api/v1/dataset/labels"),
    ("community-stats",    "GET",  "/api/v1/classes/community-stats"),
]

#: Điểm CÔNG KHAI có chủ ý: bất biến vì phạm vi của nó là tenant công khai, chứ
#: không phải vì nó theo phạm vi người gọi. Bất biến giống nhau, lý do khác nhau.
CONG_KHAI = {"community-stats"}


def chup(op, base: str) -> dict:
    ra = {}
    for ten, pt, duong in DIEM_DOC:
        ma, than = _goi(op, base, pt, duong)
        ra[ten] = {"http": ma, "than": than}
    return ra


def _chuoi(than: str) -> str:
    """Chuẩn hoá để so sánh: thứ tự khoá không được tính là khác biệt."""
    try:
        return json.dumps(json.loads(than), sort_keys=True, ensure_ascii=False)
    except Exception:                                        # noqa: BLE001
        return than


def _duong_dan_khac(a, b, goc: str = "") -> list[str]:
    """Liệt kê ĐƯỜNG DẪN TỚI TRƯỜNG đã đổi, không phải "hai chuỗi khác nhau".

    Vì sao chi tiết này quan trọng
    ------------------------------
    Lượt chạy đầu ngày 16/08/2026 báo `classes.list` trượt READ-3. Bản ghi chỉ
    giữ 200 ký tự đầu của thân phản hồi, nên không thể biết cái gì đã đổi —
    `count` (rò tổng hợp thật) hay một dấu thời gian (nhiễu của bộ đo). Hai
    kết luận trái ngược nhau, và dụng cụ không phân biệt được.

    Một bộ đo trả lời "khác" mà không trả lời "khác ở đâu" thì mọi lần trượt đều
    phải điều tra tay, và áp lực khi ấy là nới phép kiểm cho hết đỏ — tức là gỡ
    đúng cái bẫy vừa giăng.
    """
    ra: list[str] = []
    if type(a) is not type(b):
        return [f"{goc or '<goc>'}: {type(a).__name__} -> {type(b).__name__}"]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                ra.append(f"{goc}.{k}: THEM {b[k]!r}")
            elif k not in b:
                ra.append(f"{goc}.{k}: MAT {a[k]!r}")
            else:
                ra += _duong_dan_khac(a[k], b[k], f"{goc}.{k}")
    elif isinstance(a, list):
        if len(a) != len(b):
            ra.append(f"{goc}: do dai {len(a)} -> {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)):
                ra += _duong_dan_khac(x, y, f"{goc}[{i}]")
    elif a != b:
        ra.append(f"{goc}: {a!r} -> {b!r}")
    return ra


#: Trường ĐỔI Ở MỌI LƯỢT ĐỌC, độc lập với dữ liệu — loại trừ CÓ LÝ DO.
#:
#: `ClassMetadata.to_label_row()` gán `now_str()` cho hai trường này. Nó là hàm
#: DỰNG HÀNG MỚI, và ở đó `now()` đúng là thời điểm tạo. Nhưng
#: `routers/classes.py` dùng nó để HIỂN THỊ, nên mỗi lượt `GET /classes/list`
#: đóng lại dấu thời gian mới cho mọi lớp.
#:
#: Loại trừ ở đây là hợp lệ vì hai trường ấy đổi kể cả khi KHÔNG ai chạm vào
#: tenant B — tức chúng không mang thông tin về B. Đã kiểm bằng cách quan sát
#: chúng đổi giữa hai lượt đọc liên tiếp không có thao tác ghi nào xen giữa.
#:
#: Đây KHÔNG phải cách làm cho phép thử hết đỏ. Bản thân sự bất định ấy là một
#: lỗi riêng — xem docs/10-issues/P3_label_row_timestamps.md — và nó được ghi
#: lại chứ không bị nuốt.
TRUONG_BIEN_DONG = {"created_at", "migrated_at"}


def khac_biet_truong(truoc: str, sau: str) -> list[str]:
    try:
        khac = _duong_dan_khac(json.loads(truoc), json.loads(sau))
    except Exception:                                        # noqa: BLE001
        return ["<khong phai JSON>"] if truoc != sau else []
    # Tách ở dấu hai chấm ĐẦU TIÊN: giá trị là dấu thời gian và tự nó chứa dấu
    # hai chấm, nên `rsplit(":")` cắt vào giữa giá trị và phép loại trừ không
    # bao giờ khớp — im lặng, trong khi trông như đã có tác dụng.
    return [d for d in khac
            if d.split(":", 1)[0].rsplit(".", 1)[-1] not in TRUONG_BIEN_DONG]


def them_du_lieu_cho_B(dsn: str, tenant_b: str, dialect: str) -> dict:
    """Thêm 1 lớp + 3 mẫu + 1 người đóng góp MỚI vào B, dưới phạm vi của B.

    Ghi dưới `tenant_scope(B)` chứ không `system_scope`: dữ liệu phải đi đúng
    đường ghi của ứng dụng, nếu không thì một chính sách RLS phần ghi bị hỏng sẽ
    không lộ ra ở đây mà lộ ra giữa phép đo.
    """
    sys.path.insert(0, "/app")
    sys.path.insert(0, "/src/backend")
    from app.storage.metadata_db import _cursor
    from app.tenant_context import tenant_scope

    hs = uuid.uuid4().hex[:6]
    cls = f"read{hs}"
    nguoi = f"nguoi-doc-{hs}"
    maus = [f"9{uuid.uuid4().hex[:9]}" for _ in range(3)]
    with tenant_scope(tenant_b):
        with _cursor() as cur:
            cur.execute(
                "INSERT INTO classes (class_uid, slug, label_original, language, "
                "dialect, tenant_id, is_active) VALUES (%s,%s,%s,'vn',%s,%s,TRUE)",
                (cls, f"{tenant_b}-read-{hs}", f"lop do doc {hs}", dialect, tenant_b))
            for m in maus:
                cur.execute(
                    "INSERT INTO samples (sample_uid, class_uid, slug, label_original, "
                    "language, dialect, tenant_id, source_type, status, user_id) "
                    "VALUES (%s,%s,%s,%s,'vn',%s,%s,'camera','ready',%s)",
                    (m, cls, f"{tenant_b}-read-{hs}", f"mau {hs}",
                     dialect, tenant_b, nguoi))
    return {"class_uid": cls, "samples": maus, "contributor": nguoi}


def _read4(op_a, base: str, goc: Path, a_class: dict, dialect: str) -> dict:
    """Tiêm một hàng CỦA B mang `class_uid` CỦA A vào `samples.csv`, rồi đọc.

    Trả về danh sách quan hệ bị rò. Rỗng nghĩa là đạt.

    Hàng tiêm mang định danh riêng biệt ở MỌI trường quan hệ — `sample_uid`,
    `session_id`, `user_id`, `file_path` — để nếu nó lọt ra thì thấy được nó lọt
    qua đường nào, chứ không chỉ biết "có rò".
    """
    import csv as _csv
    csv_path = goc / "samples.csv"
    with open(csv_path, newline="", encoding="utf-8") as fh:
        doc = _csv.DictReader(fh)
        cot = list(doc.fieldnames or [])
        hang = list(doc)

    hs = uuid.uuid4().hex[:6]
    xam_nhap = {c: "" for c in cot}
    xam_nhap.update({
        "sample_uid": f"8{uuid.uuid4().hex[:9]}",
        "class_uid": a_class["class_uid"],          # <- class_uid CỦA A
        "slug": a_class["slug"],
        "label_original": f"XAM-NHAP-{hs}",
        "language": "vn", "dialect": dialect,
        "source_type": "camera", "status": "ready",
        "session_id": f"sess-XAMNHAP-{hs}",
        "user_id": f"nguoi-XAMNHAP-{hs}",
        "file_path": f"vn/{dialect}/XAMNHAP-{hs}/x.npz",
        "created_at": "2026-08-16T00:00:00+00:00",
        "tenant_id": "iso_b",                        # <- nhưng THUỘC B
    })
    # Lọc theo header THẬT của tệp: `_write_samples_csv` cũng làm vậy, và một
    # cột thừa ở đây sẽ làm `DictWriter` ném lỗi giữa phép đo.
    xam_nhap = {c: xam_nhap.get(c, "") for c in cot}
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=cot)
        w.writeheader()
        for r in hang:
            w.writerow({c: r.get(c, "") for c in cot})
        w.writerow(xam_nhap)

    dau_vet = {k: xam_nhap[k] for k in
               ("sample_uid", "session_id", "user_id", "label_original", "file_path")}
    ro = []
    try:
        for nhan, duong in (
            ("sessions", f"/api/v1/classes/{a_class['class_uid']}/sessions"),
            ("list",     "/api/v1/classes/list"),
            ("stats",    "/api/v1/classes/stats"),
            ("collectors", "/api/v1/classes/collectors?q="),
        ):
            ma, than = _goi(op_a, base, "GET", duong)
            for truong, gt in dau_vet.items():
                if gt and gt in than:
                    ro.append(f"{nhan}: lo {truong}={gt}")
    finally:
        # Trả cây về nguyên trạng: hàng xâm nhập là dụng cụ, không phải dữ liệu.
        with open(csv_path, "w", newline="", encoding="utf-8") as fh:
            w = _csv.DictWriter(fh, fieldnames=cot)
            w.writeheader()
            for r in hang:
                w.writerow({c: r.get(c, "") for c in cot})
    return {"class_uid_cua_A": a_class["class_uid"], "hang_tiem": dau_vet,
            "ro": ro, "dat": not ro}


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
    dialect_b = fx["ben"]["iso_b"]["dialect"]
    b_only = {d["class_uid"] for d in fx["doi_tuong"] if d["tenant_id"] == "iso_b"}
    b_mau = {d["sample_uid"] for d in fx["doi_tuong"] if d["tenant_id"] == "iso_b"}

    op_a = dang_nhap(args.base, "iso_user_a")
    ket = {"READ-1": [], "READ-2": [], "READ-3": [], "READ-5": [], "READ-7": []}

    # ---------------------------------------------------- READ-1 rò hàng --
    truoc = chup(op_a, args.base)
    for ten, r in truoc.items():
        lo = sorted({u for u in (b_only | b_mau) if u in r["than"]})
        ket["READ-1"].append({"diem": ten, "http": r["http"],
                              "dinh_danh_cua_B_xuat_hien": lo,
                              "dat": not lo or ten in CONG_KHAI})

    # ------------------------------------------- READ-2 phép thử tồn tại --
    that = next(iter(b_only))
    khong = "khongtontai000000"
    for nhan, uid in (("B_co_that", that), ("khong_ton_tai", khong)):
        ma, than = _goi(op_a, args.base, "GET", f"/api/v1/classes/{uid}/sessions")
        ket["READ-2"].append({"nhan": nhan, "uid": uid, "http": ma, "than": than[:200]})
    a, b = ket["READ-2"]
    ket["READ-2_giong_nhau"] = (a["http"] == b["http"] and a["than"] == b["than"])

    # ----------------------------------------------- READ-3 rò tổng hợp --
    them = them_du_lieu_cho_B(args.dsn, "iso_b", dialect_b)
    sau = chup(op_a, args.base)
    for ten in truoc:
        khac = khac_biet_truong(truoc[ten]["than"], sau[ten]["than"])
        ket["READ-3"].append({
            "diem": ten, "bat_bien": not khac,
            "cong_khai": ten in CONG_KHAI,
            "truong_doi": khac,
        })
    ket["da_them_vao_B"] = them

    # ------------------------------- READ-4 quan hệ phụ cũng theo phạm vi --
    #
    # Phép thử NGHIỆT NHẤT có thể dựng cho quan hệ: một hàng của B mang ĐÚNG
    # `class_uid` của A.
    #
    # PostgreSQL không giữ nổi trạng thái này — `classes.class_uid` là PRIMARY
    # KEY toàn cục. Nhưng `samples.csv` KHÔNG có ràng buộc nào như vậy, và
    # đường đọc lớp/lần quay lấy dữ liệu TỪ CSV. Đó đúng là mặt phẳng nơi lỗ
    # P0 từng sống.
    #
    # Nếu `list_session_rows` lọc theo `class_uid` mà quên `tenant_id`, hàng
    # của B sẽ hiện ra trong trang chi tiết lớp của A — và không truy vấn
    # PostgreSQL nào phát hiện được, vì hàng ấy chưa từng vào cơ sở dữ liệu.
    a_class = next(d for d in fx["doi_tuong"]
                   if d["tenant_id"] == "iso_a" and d["vai_tro"] == "target")
    goc_cay = Path(args.fixture).resolve().parent
    ket["READ-4"] = _read4(op_a, args.base, goc_cay, a_class,
                           fx["ben"]["iso_a"]["dialect"])

    # ------------------------------------------ READ-6 nguồn liệt kê TTS --
    #
    # Bộ đệm khoá theo `(voice, text)` nên CHIA SẺ được một cách hợp lệ: hai
    # tenant có cùng một nhãn thì cùng nhận bản tổng hợp của chính chuỗi ấy.
    # Vì thế "khoá đệm có tồn tại" KHÔNG phải bằng chứng rò — nó có thể đã nóng
    # từ lượt gọi của B trước đó.
    #
    # Thứ phải đo là NGUỒN LIỆT KÊ: prewarm của A gửi xuống TTS đúng những nhãn
    # nào. Endpoint trả `labels` = số nhãn nó xếp lịch, nên con số ấy phải bất
    # biến khi B có thêm một nhãn mới hoàn toàn.
    ma, than = _goi(op_a, args.base, "POST", "/api/v1/tts/prewarm", {})
    truoc_tts = json.loads(than) if ma == 200 else {"loi": than[:200]}
    them2 = them_du_lieu_cho_B(args.dsn, "iso_b", dialect_b)
    ma2, than2 = _goi(op_a, args.base, "POST", "/api/v1/tts/prewarm", {})
    sau_tts = json.loads(than2) if ma2 == 200 else {"loi": than2[:200]}
    ket["READ-6"] = {
        "http": [ma, ma2], "truoc": truoc_tts, "sau": sau_tts,
        "da_them_nhan_moi_cho_B": them2["class_uid"],
        "dat": ma == 200 and ma2 == 200
               and truoc_tts.get("labels") == sau_tts.get("labels"),
    }

    # ------------------------------------- READ-5 không rơi về "default" --
    from app.dataset_samples import TenantScopeRequired, list_samples
    from app.dataset_manager import load_labels
    for ten, fn in (("list_samples", list_samples), ("load_labels", load_labels)):
        for gt in (None, "", "   "):
            try:
                fn(gt)
                ket["READ-5"].append({"ham": ten, "gia_tri": repr(gt),
                                      "dat": False, "ghi_chu": "KHONG nem loi"})
            except TenantScopeRequired:
                ket["READ-5"].append({"ham": ten, "gia_tri": repr(gt), "dat": True})
            except Exception as e:                           # noqa: BLE001
                ket["READ-5"].append({"ham": ten, "gia_tri": repr(gt),
                                      "dat": False, "ghi_chu": type(e).__name__})

    # ------------------------------------------------ in ra --------------
    print("\n=== READ-1  ro HANG ===")
    for r in ket["READ-1"]:
        print(f"  {'DAT ' if r['dat'] else 'TRUOT'} {r['diem']:20} http={r['http']} "
              f"dinh_danh_B={r['dinh_danh_cua_B_xuat_hien'] or '-'}")

    print("\n=== READ-2  phep thu ton tai ===")
    for r in ket["READ-2"]:
        print(f"  {r['nhan']:16} http={r['http']}  {r['than'][:90]}")
    print(f"  -> khong phan biet duoc: {ket['READ-2_giong_nhau']}")

    print("\n=== READ-3  ro TONG HOP (them du lieu vao B, quan sat A) ===")
    print(f"  da them vao iso_b: class={them['class_uid']} "
          f"samples={len(them['samples'])} contributor={them['contributor']}")
    for r in ket["READ-3"]:
        nhan = "DAT " if r["bat_bien"] else "TRUOT"
        ck = " (cong khai)" if r["cong_khai"] else ""
        print(f"  {nhan} {r['diem']:20} bat_bien={r['bat_bien']}{ck}")
        for d in r.get("truong_doi", [])[:12]:
            print(f"        {d}")

    # Hai khối dưới đây từng bị THIẾU trong khi vẫn được tính vào kết luận
    # (16/08/2026): bộ đo in "TONG: DAT" mà không nói gì về READ-4/READ-6. Kết
    # quả tính ra vẫn đúng, nhưng một kết luận không in ra thứ nó chấm thì người
    # đọc không phân biệt được "đã kiểm và đạt" với "chưa kiểm".
    print("\n=== READ-4  quan he phu (hang cua B mang class_uid cua A) ===")
    r4 = ket["READ-4"]
    print(f"  class_uid cua A : {r4['class_uid_cua_A']}")
    print(f"  hang tiem (thuoc iso_b): {r4['hang_tiem']['sample_uid']} "
          f"/ {r4['hang_tiem']['session_id']}")
    print(f"  {'DAT ' if r4['dat'] else 'TRUOT'} so quan he bi ro: {len(r4['ro'])}")
    for d in r4["ro"]:
        print(f"        {d}")

    print("\n=== READ-6  nguon liet ke TTS ===")
    r6 = ket["READ-6"]
    print(f"  da them nhan moi cho B: {r6['da_them_nhan_moi_cho_B']}")
    print(f"  {'DAT ' if r6['dat'] else 'TRUOT'} labels A: "
          f"truoc={r6['truoc'].get('labels')} sau={r6['sau'].get('labels')} "
          f"http={r6['http']}")

    print("\n=== READ-5  khong roi ve 'default' ===")
    for r in ket["READ-5"]:
        print(f"  {'DAT ' if r['dat'] else 'TRUOT'} {r['ham']:14} {r['gia_tri']:8} "
              f"{r.get('ghi_chu','')}")

    ok = (all(r["dat"] for r in ket["READ-1"])
          and ket["READ-2_giong_nhau"]
          and all(r["bat_bien"] for r in ket["READ-3"])
          and ket["READ-4"]["dat"]
          and ket["READ-6"]["dat"]
          and all(r["dat"] for r in ket["READ-5"]))
    print(f"\n=== TONG: {'DAT' if ok else 'TRUOT'} ===")

    if args.out:
        Path(args.out).write_text(json.dumps(ket, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
        print(f"da ghi {args.out}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

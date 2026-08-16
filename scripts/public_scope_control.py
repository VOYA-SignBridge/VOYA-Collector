#!/usr/bin/env python3
"""Đối chứng HAI CHIỀU cho PHẠM VI CÔNG BỐ ĐÃ CẤU HÌNH — lớp 3 của P0-B.

    python scripts/public_scope_control.py \
        --base http://voya_backend_iso:8000 --fixture /src/.measurement/p0b-... \
        --json ket_qua.json

Tên gọi: đây KHÔNG phải "đối chứng Community"
=============================================
Kịch bản này đo phạm vi mà điểm cuối THẬT SỰ đọc — giá trị của `public_tenant_id`
trong cấu hình, hiện là tenant khởi tạo. Nó KHÔNG đo tenant dự trữ mang tên
`community`.

Gọi nó là "đối chứng Community" sẽ là một khẳng định về một mặt phẳng chưa được
kiểm: chừng nào nguồn dữ liệu thật của điểm cuối chưa phải `tenant_id='community'`
thì không được viết "ngoại lệ Community đã được kiểm chứng" từ kết quả ở đây.

Điều kịch bản này chứng minh, phát biểu đúng phạm vi: **số liệu tổng hợp công
khai được cách ly khỏi thay đổi trong các phạm vi tổ chức riêng, và chỉ phản ứng
với thay đổi bên trong chính phạm vi nguồn đã được cấu hình tường minh của nó.**

Vì sao một chiều là chưa đủ
===========================
Điểm cuối thống kê công khai là một NGOẠI LỆ tường minh: nó trả dữ liệu tổng hợp
cho người gọi bất kỳ. Ngoại lệ nào cũng phải trả lời được hai câu, không phải
một:

    (1) nó có PHÁ cách ly không?   dữ liệu riêng của A hay B đổi
                                   -> con số công khai phải ĐỨNG YÊN
    (2) nó có SỐNG không?          dữ liệu thuộc phạm vi công bố đổi
                                   -> con số công khai phải ĐỔI

Chỉ hỏi câu (1) thì một điểm cuối hỏng trả hằng số `0` cũng "đạt" hoàn hảo. Đó
đúng là họ lỗi đã hai lần làm hỏng phép đo này: một cây fixture chỉ ghi vào cơ sở
dữ liệu khiến mọi lượt thử đối kháng trả 404, và bảng kết quả trông rất đẹp.

Câu (2) là thứ phân biệt "cách ly đúng" với "điểm cuối chết".

So sánh TRẠNG THÁI TRƯỚC/SAU, không so bốn con số một lần
=========================================================
Bốn con số đọc một lần chỉ nói lên hiện trạng. Điều cần chứng minh là một QUAN HỆ
NHÂN QUẢ: thay đổi này KHÔNG kéo theo thay đổi kia, còn thay đổi kia thì CÓ. Chỉ
phép so trước/sau quanh một can thiệp có kiểm soát mới nói được điều đó.

Phạm vi công bố KHÔNG phải tenant `community`
=============================================
Điểm cuối đọc `settings.public_tenant_id`, mặc định là tenant khởi tạo — một
tenant TỔ CHỨC bình thường. Tenant `community` là một tenant khác, và mặt phẳng
Community Data Commons hiện là 0 dòng mã. Kịch bản này vì thế can thiệp vào ĐÚNG
tenant mà điểm cuối thật sự đọc, chứ không vào tenant mang cái tên nghe hợp lý
hơn. Đo cái đang chạy, không đo cái đáng lẽ phải chạy.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
import uuid
from pathlib import Path

DUONG_CONG_KHAI = "/api/v1/classes/community-stats"


def _doc_thong_ke(base: str, timeout: float = 30.0) -> dict:
    """Bốn con số công khai, không kèm chứng thực — đúng như người ngoài thấy."""
    req = urllib.request.Request(base.rstrip("/") + DUONG_CONG_KHAI)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _them_lop_va_mau(goc: Path, tenant: str, dialect: str, nhan: str) -> dict:
    """Thêm MỘT lớp và MỘT mẫu vào cả ba kho, dưới phạm vi của `tenant`.

    Ghi qua đúng đường mà ứng dụng đọc: hàng PostgreSQL dưới phạm vi tenant, dòng
    CSV trong cây fixture, và tệp đặc trưng trên đĩa. Thiếu một trong ba thì phép
    đo chỉ chứng minh được về kho còn lại.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import tenant_scope

    uid_lop = f"ctl{uuid.uuid4().hex[:9]}"
    uid_mau = uuid.uuid4().hex[:10]
    slug = f"{tenant}-{nhan}-{uuid.uuid4().hex[:6]}"
    rel = f"vn/{dialect}/{slug}/{uid_mau}.npz"

    (goc / rel).parent.mkdir(parents=True, exist_ok=True)
    (goc / rel).write_bytes(b"PK\x03\x04doi-chung-cong-khai")

    for ten_tep, hang in (
        ("labels.csv", {"class_uid": uid_lop, "slug": slug,
                        "label_original": f"doi chung {nhan}", "language": "vn",
                        "dialect": dialect, "region": "unclassified",
                        "is_active": "true", "hands_required": "2",
                        "folder_name": slug, "tenant_id": tenant}),
        ("samples.csv", {"sample_uid": uid_mau, "class_uid": uid_lop, "slug": slug,
                         "label_original": f"doi chung {nhan}", "language": "vn",
                         "dialect": dialect, "source_type": "camera",
                         "session_id": f"sess-{nhan}", "seq_len": "16",
                         "completeness": "1.0",
                         "file_path": f"/isodata/{rel}", "tenant_id": tenant,
                         # NGƯỜI ĐÓNG GÓP mới. Con số `contributors_count` đếm
                         # theo cột này, nên dùng lại một người có sẵn sẽ làm
                         # đối chứng dương im lặng ở một trong bốn con số.
                         "user_id": f"nguoi-{nhan}-{uuid.uuid4().hex[:6]}"}),
    ):
        p = goc / ten_tep
        with io.open(p, encoding="utf-8", newline="") as fh:
            fields = next(csv.reader(fh))
        with io.open(p, "a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore").writerow(hang)

    with tenant_scope(tenant):
        with _cursor() as cur:
            cur.execute(
                "INSERT INTO classes (class_uid, slug, label_original, language, "
                "dialect, tenant_id, is_active) VALUES (%s,%s,%s,'vn',%s,%s,TRUE) "
                "ON CONFLICT (class_uid) DO NOTHING",
                (uid_lop, slug, f"doi chung {nhan}", dialect, tenant))
            cur.execute(
                "INSERT INTO samples (sample_uid, class_uid, slug, label_original, "
                "language, dialect, tenant_id, source_type, status, session_id) "
                "VALUES (%s,%s,%s,%s,'vn',%s,%s,'camera','ready',%s) "
                "ON CONFLICT (sample_uid) DO NOTHING",
                (uid_mau, uid_lop, slug, f"doi chung {nhan}", dialect, tenant,
                 f"sess-{nhan}"))

    return {"tenant_id": tenant, "class_uid": uid_lop, "sample_uid": uid_mau,
            "slug": slug, "file_path": rel}


def _don(dt: list[dict], goc: Path) -> None:
    """Gỡ mọi can thiệp. Chạy kể cả khi phép kiểm đã trượt."""
    from app.storage.metadata_db import _cursor
    from app.tenant_context import tenant_scope

    for d in reversed(dt):
        try:
            with tenant_scope(d["tenant_id"]):
                with _cursor() as cur:
                    cur.execute("DELETE FROM samples WHERE sample_uid = %s",
                                (d["sample_uid"],))
                    cur.execute("DELETE FROM classes WHERE class_uid = %s",
                                (d["class_uid"],))
        except Exception as e:                                   # noqa: BLE001
            print(f"  [warn] khong xoa duoc {d['class_uid']}: {e}")
        (goc / d["file_path"]).unlink(missing_ok=True)

    # CSV: viết lại, bỏ đúng các dòng đã thêm.
    bo_lop = {d["class_uid"] for d in dt}
    bo_mau = {d["sample_uid"] for d in dt}
    for ten_tep, khoa, bo in (("labels.csv", "class_uid", bo_lop),
                              ("samples.csv", "sample_uid", bo_mau)):
        p = goc / ten_tep
        with io.open(p, encoding="utf-8", newline="") as fh:
            r = list(csv.DictReader(fh))
            fields = list(r[0].keys()) if r else []
        with io.open(p, "w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            for row in r:
                if row.get(khoa) not in bo:
                    w.writerow(row)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--fixture", required=True, help="cây fixture dùng-một-lần")
    ap.add_argument("--tenant-a", default="iso_a")
    ap.add_argument("--tenant-b", default="iso_b")
    ap.add_argument("--json")
    a = ap.parse_args()

    sys.path.insert(0, "/app")
    from app.config import settings

    cong_bo = (settings.public_tenant_id or "").strip()
    goc = Path(a.fixture)
    print(f"pham vi cong bo that su cua diem cuoi: {cong_bo!r}")

    da_them: list[dict] = []
    ket: dict = {"public_tenant_id": cong_bo, "buoc": []}
    try:
        s0 = _doc_thong_ke(a.base)
        print(f"\nTRUOC BAT KY CAN THIEP NAO: {s0}")
        ket["truoc"] = s0

        # --- Chiều 1: dữ liệu RIÊNG đổi -> công khai phải ĐỨNG YÊN ----------
        for tenant in (a.tenant_a, a.tenant_b):
            da_them.append(_them_lop_va_mau(goc, tenant, "bac", "rieng"))
            s = _doc_thong_ke(a.base)
            dung_yen = s == s0
            print(f"  them 1 lop + 1 mau vao {tenant:<8} -> {s}  "
                  f"{'DUNG YEN (dat)' if dung_yen else 'DA DOI (TRUOT)'}")
            ket["buoc"].append({"can_thiep": f"tenant rieng {tenant}",
                                "ky_vong": "khong doi", "quan_sat": s,
                                "dat": dung_yen})

        # --- Chiều 2: dữ liệu CÔNG BỐ đổi -> công khai phải ĐỔI -------------
        # Không có vế này thì một điểm cuối trả hằng 0 cũng qua được chiều 1.
        da_them.append(_them_lop_va_mau(goc, cong_bo, "bac", "congbo"))
        s_sau = _doc_thong_ke(a.base)
        da_doi = s_sau != s0
        print(f"\n  them 1 lop + 1 mau vao {cong_bo:<8} -> {s_sau}  "
              f"{'DA DOI (dat)' if da_doi else 'DUNG YEN (TRUOT)'}")
        ket["buoc"].append({"can_thiep": f"tenant cong bo {cong_bo}",
                            "ky_vong": "phai doi", "quan_sat": s_sau,
                            "dat": da_doi})
        ket["sau"] = s_sau

        dat_het = all(b["dat"] for b in ket["buoc"])
        ket["dat"] = dat_het
        print("\n" + ("=" * 66))
        print("  LOP 3 DAT — ngoai le khong pha cach ly, VA no thuc su song"
              if dat_het else
              "  LOP 3 TRUOT — doc tung buoc o tren truoc khi cong bo bat cu so nao")
        print("=" * 66)
        return 0 if dat_het else 1
    finally:
        print("\ndon can thiep...")
        _don(da_them, goc)
        s_cuoi = _doc_thong_ke(a.base)
        ket["sau_khi_don"] = s_cuoi
        # Dọn xong phải trở về đúng trạng thái đầu. Không trở về nghĩa là kịch
        # bản này vừa để lại dấu vết trong cây fixture, và mọi phép đo chạy sau
        # nó trên cùng cây đều đang đứng trên một nền đã bị dịch.
        ket["don_sach"] = s_cuoi == ket.get("truoc")
        print(f"  sau khi don: {s_cuoi}  "
              f"{'khop trang thai dau' if ket['don_sach'] else 'KHONG KHOP — cay da bi dich'}")
        if a.json:
            with open(a.json, "w", encoding="utf-8") as fh:
                json.dump(ket, fh, ensure_ascii=False, indent=2)
            print(f"  da ghi {a.json}")


if __name__ == "__main__":
    sys.exit(main())

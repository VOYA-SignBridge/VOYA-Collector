#!/usr/bin/env python3
"""Gieo fixture đo cách ly NHẤT QUÁN trên cả ba kho: PostgreSQL + CSV + hệ tệp.

    sh scripts/seed_cross_store.sh

Vì sao phải là MỘT kịch bản chứ không phải hai
==============================================
Đường đọc lớp/mẫu của ứng dụng không thuần PostgreSQL: `list_classes()` gọi
`load_labels()` và hàm đó đọc `labels.csv` trên đĩa. Trước tệp này có hai bộ gieo,
mỗi bộ phủ đúng một kho:

    seed_measurement_datastore.py   ->  CSV + tệp    (không chạm psycopg2)
    seed_isolation_fixture.py       ->  PostgreSQL   (tenant, user, membership)

Không bộ nào phủ cả hai, và hậu quả đã đo được: `iso_user_a` nhận `404` khi đọc
lớp của CHÍNH NÓ. Khi đối chứng dương hỏng như vậy thì mọi ca "đã chặn" ở nhóm
đối kháng mất nghĩa — không phân định được *cách ly đúng* với *tài khoản không
đọc được gì*.

Giao dịch có bù trừ
===================
PostgreSQL và hệ tệp không nằm chung một giao dịch ACID được, nên phải có giao
thức tường minh. Mười bước, và **marker READY là bước cuối cùng**:

     1  sinh fixture_id
     2  preflight — kiểm thứ tự kịch bản TỰ BIẾT trước khi ghi
     3  dựng cây, ghi labels.csv + samples.csv + tệp .npz
     4  mở giao dịch DB
     5  bảo đảm tenant / user / membership  (tái dùng seed_isolation_fixture)
     6  ghi 8 class + 8 sample
     7  COMMIT
     8  giao dịch MỚI để đọc lại
     9  đối chiếu DB <-> CSV <-> tệp, kiểm cả THIẾU lẫn THỪA
    10  tính dataset_fixture_hash, ghi fixture.json, rồi mới ghi marker READY

Hỏng bất kỳ đâu ở 4–9: dọn bù trừ CHỈ các đối tượng mang `fixture_id` này, xoá
cây, và **tuyệt đối không tạo marker READY**. `isolation_backend.sh` chỉ nhận cây
đã có marker, nên một fixture dở dang không bao giờ bị gắn vào phép đo.

Thời điểm tính `dataset_fixture_hash`
=====================================
Sau khi đối chiếu ba kho đạt, TRƯỚC khi chạy đối chứng dương. `control_update` và
`control_delete` được thiết kế để làm biến đổi đối tượng control, nên băm lại sau
pha đối chứng sẽ luôn khác — và khác biệt ấy là *mong đợi*, không phải hỏng. Hash
này đại diện cho TRẠNG THÁI BAN ĐẦU; tính bất biến của mục tiêu đối kháng do
`target_integrity_before/after` chịu trách nhiệm riêng.

Băm **manifest chuẩn hoá** (định danh + dòng CSV + hash tệp), không băm timestamp
hay đường dẫn tuyệt đối — nếu không thì cùng một fixture logic dựng lại sẽ cho
hash khác một cách vô ích.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from seed_isolation_fixture import (  # noqa: E402
    QUAN_TRI,
    _cursor,
    _dialect_cua,
    _gan_tu_cach_thanh_vien,
    _khang_dinh_la_thanh_vien,
    _khang_dinh_user_ton_tai,
    _tao_user,
    create_tenant,
    system_scope,
    tenant_scope,
)

MARKER = ".tenant-isolation-fixture"
MARKER_DANG_TAO = ".tenant-isolation-fixture.partial"

#: Đặt tệp này vào một cây fixture để KHÔNG lệnh dọn nào xoá nó, kể cả khi người
#: gọi đã truyền `--cleanup-previous`. Dành cho cây đang giữ bằng chứng.
#: Xem `.measurement/evidence/README.md` về vì sao nó tồn tại.
RETAIN = ".retain"
NOW = "2026-08-15T00:00:00+00:00"

BEN = {
    "iso_a": {"ten": "ISO Tenant A", "user": "iso_user_a"},
    "iso_b": {"ten": "ISO Tenant B", "user": "iso_user_b"},
}

#: `(ký tự hex cho sample_uid, tên ngắn cho class_uid)`.
#:
#: `samples` mang ràng buộc `samples_uid_is_hex10`:
#:     CHECK (sample_uid ~ '^[0-9a-f]{10}$')
#: — ĐÚNG mười ký tự, mọi ký tự phải là hex. Cách đặt tên dễ đọc kiểu
#: `s`+tenant+`cont`+hậu tố sinh ra `sacont702c2f`: mười hai ký tự, và `s`/`o`/`t`
#: không phải hex. PostgreSQL từ chối, CSV thì nhận — cây fixture có bốn mẫu mà
#: cơ sở dữ liệu không có mẫu nào, và điều đó chỉ lộ khi đối chiếu tay.
#:
#: Tên ngắn phải KHÁC NHAU Ở ĐẦU. Lấy sáu ký tự đầu của tên vai trò cho ra
#: `contro` cho cả ba đối chứng — mười ký tự đầu của `class_uid` giống hệt nhau.
MA_VAI_TRO = {
    "control_read":   ("c", "read"),
    "control_update": ("d", "upd"),
    "control_delete": ("e", "del"),
    "target":         ("f", "targ"),
}

HEX10 = re.compile(r"^[0-9a-f]{10}$")


# --------------------------------------------------------------------------
# 1–2. danh tính chuẩn + preflight
# --------------------------------------------------------------------------

def _doi_tuong(fixture_id: str, tenant: str, vai_tro: str) -> dict:
    """MỘT danh tính dùng xuyên cả ba kho.

    Không sinh một UID cho CSV rồi một UID khác cho DB và ánh xạ lại sau: ràng
    buộc của cơ sở dữ liệu là một phần của HỢP ĐỒNG fixture, không phải một lỗi
    phát hiện sau khi CSV đã ghi xong.
    """
    ma_hex, ten_ngan = MA_VAI_TRO[vai_tro]
    return {
        "fixture_id": fixture_id,
        "tenant_id": tenant,
        "vai_tro": vai_tro,
        "class_uid": f"{tenant.replace('_', '')}{ten_ngan}{uuid.uuid4().hex[:6]}",
        "sample_uid": f"{tenant[-1]}{ma_hex}{uuid.uuid4().hex[:8]}",
        "slug": f"{tenant}-{vai_tro}",
        "session_id": f"sess-{tenant}-{vai_tro}",
    }


def _preflight(dt: list[dict]) -> None:
    """Đừng để PostgreSQL phát hiện thứ mà kịch bản tự biết được."""
    loi = []
    for d in dt:
        if not HEX10.match(d["sample_uid"]):
            loi.append(f"sample_uid {d['sample_uid']!r} vi pham ^[0-9a-f]{{10}}$")
    for ten in ("class_uid", "sample_uid", "slug"):
        gia_tri = [d[ten] for d in dt]
        if len(set(gia_tri)) != len(gia_tri):
            loi.append(f"{ten} bi trung: {gia_tri}")
    # Alias control_* phải phân biệt được ở MƯỜI ký tự đầu, không chỉ ở hậu tố.
    dau = [d["class_uid"][:10] for d in dt]
    if len(set(dau)) != len(dau):
        loi.append(f"class_uid khong phan biet duoc o 10 ky tu dau: {dau}")
    if len({v[0] for v in MA_VAI_TRO.values()}) != len(MA_VAI_TRO):
        loi.append("ma hex vai tro khong doi mot khac nhau")
    if loi:
        raise SystemExit("PREFLIGHT HONG:\n  " + "\n  ".join(loi))
    print(f"  preflight dat — {len(dt)} doi tuong, dinh danh doi mot khac nhau")


# --------------------------------------------------------------------------
# 3. cây + CSV + tệp
# --------------------------------------------------------------------------

def _ghi_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def _noi_dung_npz(d: dict) -> bytes:
    """Nội dung tệp mẫu — tất định theo danh tính, KHÔNG ngẫu nhiên.

    Tất định để hash tệp tái lập được: cùng một fixture logic dựng lại phải cho
    cùng manifest. Đây không phải `.npz` thật; bộ đo chỉ cần một tệp tồn tại, có
    nội dung phân biệt được, và băm được.
    """
    return (f"voya-iso-fixture\n{d['fixture_id']}\n{d['tenant_id']}\n"
            f"{d['vai_tro']}\n{d['class_uid']}\n{d['sample_uid']}\n").encode()


#: Cây fixture được gắn vào container đo ở đây. Xem chú thích ở cột `file_path`
#: trong `_dung_cay` về việc vì sao CSV phải mang đường TUYỆT ĐỐI theo cách
#: container nhìn thấy, chứ không phải đường tương đối như kho sản xuất.
PREFIX_TEP_TRONG_CONTAINER = "/isodata"


def _dung_cay(goc: Path, dt: list[dict],
              prefix_tep: str = PREFIX_TEP_TRONG_CONTAINER
              ) -> tuple[list[dict], list[dict]]:
    from app.dataset_manager import LABEL_FIELDS
    from app.dataset_samples import SAMPLE_FIELDS

    nhan, mau = [], []
    for i, d in enumerate(dt):
        nhan.append({
            "class_uid": d["class_uid"], "class_idx": str(i), "slug": d["slug"],
            "label_original": f"lop {d['vai_tro']} cua {d['tenant_id']}",
            "language": "vn", "dialect": d["dialect"], "region": "unclassified",
            "is_active": "true", "hands_required": "2",
            "folder_name": d["slug"], "created_at": NOW,
            "tenant_id": d["tenant_id"],
        })
        mau.append({
            "sample_uid": d["sample_uid"], "class_uid": d["class_uid"],
            "slug": d["slug"],
            "label_original": f"mau {d['vai_tro']} cua {d['tenant_id']}",
            "language": "vn", "dialect": d["dialect"],
            # PHẢI trùng giá trị dùng ở `_ghi_db`. Bản đầu ghi `measurement` vào
            # CSV và `camera` vào PostgreSQL — hai kho mô tả cùng một mẫu bằng
            # hai nguồn khác nhau, đúng loại lệch mà kịch bản này sinh ra để
            # loại bỏ. Validator không bắt vì nó chưa so cột này.
            "source_type": "camera", "session_id": d["session_id"],
            "seq_len": "16", "fps_original": "30", "fps_processed": "30",
            # Đường TUYỆT ĐỐI theo cách container đo nhìn thấy cây, không phải
            # đường tương đối như `dataset/samples.csv` của sản xuất.
            #
            # Vì sao lệch khỏi sản xuất một cách CÓ CHỦ Ý
            # -------------------------------------------
            # Endpoint đọc dữ liệu mẫu phân giải theo hai nhánh, theo thứ tự:
            #
            #     1. `Path(file_path).exists()`  -> trả tệp cục bộ
            #     2. materialise từ kho đám mây  -> cần liên kết tải về
            #
            # Sản xuất ghi đường tương đối và luôn rơi vào nhánh 2, vì tệp thật
            # nằm trên kho đám mây. Cây fixture thì cố ý KHÔNG có liên kết ấy:
            # một phép đo cách ly không được phụ thuộc vào một dịch vụ ngoài,
            # và cũng không được phát yêu cầu ra Internet giữa lượt đo.
            #
            # Ghi đường tương đối ở đây làm nhánh 1 trượt (thư mục làm việc của
            # ứng dụng không phải gốc cây dữ liệu) rồi nhánh 2 cũng trượt, và
            # đối chứng dương "chủ sở hữu đọc được mẫu của chính mình" nhận 404.
            # Đó là 404 của HẠ TẦNG FIXTURE, nhưng nó làm VÔ HIỆU cả lượt đo —
            # đúng như bộ đo đã từ chối công bố ngày 16/08/2026.
            #
            # Đường tuyệt đối đưa nhánh 1 vào cuộc. Nhánh 1 là mã sản xuất thật,
            # không phải đường vòng dựng riêng cho phép đo.
            "file_path": f"{prefix_tep}/{d['file_path']}",
            "created_at": NOW, "tenant_id": d["tenant_id"],
            # Cùng giá trị mà `_ghi_db` ghi vào `samples.auth_user_id`. Hai kho
            # lệch nhau ở cột này thì đối chứng dương đạt ở kho này và trượt ở
            # kho kia, tuỳ đường mã nào được chạm.
            "auth_user_id": d["auth_user_id"],
        })
        tep = goc / d["file_path"]
        tep.parent.mkdir(parents=True, exist_ok=True)
        tep.write_bytes(_noi_dung_npz(d))

    _ghi_csv(goc / "labels.csv", list(LABEL_FIELDS), nhan)
    _ghi_csv(goc / "samples.csv", list(SAMPLE_FIELDS), mau)
    return nhan, mau


# --------------------------------------------------------------------------
# 5–7. PostgreSQL
# --------------------------------------------------------------------------

def _bao_dam_tenant(tenant: str, ten_hien: str) -> None:
    with system_scope("gieo fixture do luong"):
        with _cursor() as cur:
            cur.execute("SELECT 1 FROM tenants WHERE tenant_id = %s", (tenant,))
            if cur.fetchone():
                return
        create_tenant(tenant, display_name=ten_hien, slug=tenant, clone_catalog=True)


def _don_luot_truoc() -> int:
    """Xoá lớp/mẫu của các lượt gieo TRƯỚC trong hai tenant đo.

    Vì sao cần, và vì sao xoá theo tenant chứ theo `fixture_id`
    ----------------------------------------------------------
    `classes` mang ràng buộc duy nhất TỔ HỢP:

        uq_classes_tenant_slug_lang_dialect_region

    Lượt gieo thứ hai sinh `class_uid` mới nhưng giữ nguyên `slug`
    (`iso_a-control_read`…), nên nó đụng đúng ràng buộc ấy —
    `ON CONFLICT (class_uid) DO NOTHING` không đỡ được vì xung đột nằm ở một khoá
    khác. Đo được thật ở lượt chạy thứ hai, không phải suy luận.

    Dọn theo `fixture_id` không giải quyết được: hàng của lượt TRƯỚC mang
    `fixture_id` khác, mà chính chúng mới là thứ chặn đường. Nên phạm vi dọn là
    hai tenant `iso_a`/`iso_b` — chúng tồn tại DUY NHẤT để phục vụ phép đo này,
    không giữ dữ liệu nghiên cứu nào, nên xoá sạch là đúng ngữ nghĩa chứ không
    phải một cú quét rộng tay.

    Xoá mẫu trước lớp: `samples.class_uid` là khoá ngoại.
    """
    tong = 0
    for tenant in BEN:
        with tenant_scope(tenant):
            with _cursor() as cur:
                cur.execute("DELETE FROM samples WHERE tenant_id = %s", (tenant,))
                tong += cur.rowcount or 0
                cur.execute("DELETE FROM classes WHERE tenant_id = %s", (tenant,))
                tong += cur.rowcount or 0
    return tong


def _ghi_db(dt: list[dict]) -> None:
    """8 class + 8 sample, dưới ĐÚNG ngữ cảnh tenant của từng đối tượng.

    Ghi dưới `tenant_scope` chứ không `system_scope`: fixture phải đi qua đúng
    đường ghi mà ứng dụng đi, nếu không thì một chính sách RLS phần ghi bị hỏng
    sẽ không lộ ra ở đây mà lộ ra giữa phép đo.
    """
    for d in dt:
        with tenant_scope(d["tenant_id"]):
            with _cursor() as cur:
                cur.execute(
                    "INSERT INTO classes (class_uid, slug, label_original, language, "
                    "dialect, tenant_id, is_active) "
                    "VALUES (%s, %s, %s, 'vn', %s, %s, TRUE) "
                    "ON CONFLICT (class_uid) DO NOTHING",
                    (d["class_uid"], d["slug"],
                     f"lop {d['vai_tro']} cua {d['tenant_id']}",
                     d["dialect"], d["tenant_id"]))
                cur.execute(
                    "INSERT INTO samples (sample_uid, class_uid, slug, label_original, "
                    "language, dialect, tenant_id, source_type, status, session_id, "
                    "auth_user_id) "
                    "VALUES (%s, %s, %s, %s, 'vn', %s, %s, 'camera', 'ready', %s, %s) "
                    "ON CONFLICT (sample_uid) DO NOTHING",
                    (d["sample_uid"], d["class_uid"], d["slug"],
                     f"mau {d['vai_tro']} cua {d['tenant_id']}",
                     d["dialect"], d["tenant_id"], d["session_id"],
                     # CHỦ SỞ HỮU THẬT. Thiếu cột này thì `get_sample_owner()` trả
                     # None, và endpoint đổi nhãn/xoá từ chối 403 NGAY CẢ với mẫu
                     # của chính người gọi — nên ca đối chứng dương không bao giờ
                     # chạm tới cổng phạm vi tenant nằm phía sau. Lượt đo
                     # 15/08/2026 hỏng đúng như vậy: mọi ca dừng ở quyền sở hữu,
                     # và cách ly tenant chưa từng bị kiểm.
                     d["auth_user_id"] or None))


def _don_bu_tru(dt: list[dict]) -> None:
    """Xoá CHỈ các đối tượng thuộc lượt gieo này. Không đụng gì khác."""
    print("  don bu tru...")
    for d in dt:
        try:
            with tenant_scope(d["tenant_id"]):
                with _cursor() as cur:
                    cur.execute("DELETE FROM samples WHERE sample_uid = %s",
                                (d["sample_uid"],))
                    cur.execute("DELETE FROM classes WHERE class_uid = %s",
                                (d["class_uid"],))
        except Exception as e:  # pragma: no cover
            print(f"    [warn] khong xoa duoc {d['class_uid']}: {e}")


# --------------------------------------------------------------------------
# 9. validator — THIẾU và THỪA
# --------------------------------------------------------------------------

def _doi_chieu(goc: Path, dt: list[dict]) -> None:
    """Đối chiếu hai chiều DB <-> CSV <-> tệp.

    Kiểm cả **thừa** chứ không chỉ "hàng mong đợi có tồn tại": một lượt gieo
    trước sót lại trong CSV sẽ làm bộ đo thấy đối tượng mà manifest không mô tả,
    và đó cũng là một fixture không tin được.
    """
    loi: list[str] = []

    mong_class = {d["class_uid"] for d in dt}
    mong_sample = {d["sample_uid"] for d in dt}

    db_class, db_sample = set(), set()
    for d in dt:
        with tenant_scope(d["tenant_id"]):
            with _cursor() as cur:
                cur.execute(
                    "SELECT class_uid FROM classes WHERE class_uid = ANY(%s)",
                    (list(mong_class),))
                db_class |= {r[0] for r in cur.fetchall()}
                cur.execute(
                    "SELECT sample_uid FROM samples WHERE sample_uid = ANY(%s)",
                    (list(mong_sample),))
                db_sample |= {r[0] for r in cur.fetchall()}

    with open(goc / "labels.csv", encoding="utf-8") as f:
        csv_class = {r["class_uid"] for r in csv.DictReader(f)}
    with open(goc / "samples.csv", encoding="utf-8") as f:
        hang_mau = list(csv.DictReader(f))
    csv_sample = {r["sample_uid"] for r in hang_mau}

    for ten, mong, db, trong_csv in (
            ("class", mong_class, db_class, csv_class),
            ("sample", mong_sample, db_sample, csv_sample)):
        if mong - db:
            loi.append(f"{ten}: DB THIEU {sorted(mong - db)}")
        if db - mong:
            loi.append(f"{ten}: DB THUA {sorted(db - mong)}")
        if mong - trong_csv:
            loi.append(f"{ten}: CSV THIEU {sorted(mong - trong_csv)}")
        if trong_csv - mong:
            loi.append(f"{ten}: CSV THUA {sorted(trong_csv - mong)}")

    # Cột nghiệp vụ phải khớp giữa hai kho, không chỉ khoá.
    #
    # Bản đầu chỉ so tập UID, nên nó bỏ qua việc CSV ghi `source_type=measurement`
    # còn PostgreSQL ghi `camera`: hai kho mô tả cùng một mẫu bằng hai nguồn khác
    # nhau mà vẫn "đối chiếu đạt". Một validator chỉ so khoá sẽ chứng nhận đúng
    # loại lệch mà nó sinh ra để loại bỏ.
    theo_uid = {d["sample_uid"]: d for d in dt}
    for r in hang_mau:
        d = theo_uid.get(r["sample_uid"])
        if not d:
            continue
        if r.get("tenant_id") != d["tenant_id"]:
            loi.append(f"sample {r['sample_uid']}: CSV tenant_id="
                       f"{r.get('tenant_id')!r} != {d['tenant_id']!r}")
        with tenant_scope(d["tenant_id"]):
            with _cursor() as cur:
                cur.execute(
                    "SELECT class_uid, slug, dialect, source_type, session_id "
                    "FROM samples WHERE sample_uid = %s", (d["sample_uid"],))
                hang = cur.fetchone()
        if not hang:
            continue
        for cot, gia_tri_db in zip(
                ("class_uid", "slug", "dialect", "source_type", "session_id"), hang):
            if (r.get(cot) or "") != (gia_tri_db or ""):
                loi.append(f"sample {d['sample_uid']}: {cot} CSV="
                           f"{r.get(cot)!r} != DB={gia_tri_db!r}")

    # tệp tồn tại và đúng nội dung
    for d in dt:
        tep = goc / d["file_path"]
        if not tep.exists():
            loi.append(f"thieu tep mau {d['file_path']}")
        elif tep.read_bytes() != _noi_dung_npz(d):
            loi.append(f"tep mau sai noi dung {d['file_path']}")

    if loi:
        raise RuntimeError("DOI CHIEU HONG:\n  " + "\n  ".join(loi))
    print(f"  doi chieu dat — DB {len(db_class)}/{len(mong_class)} class, "
          f"{len(db_sample)}/{len(mong_sample)} sample; CSV va tep khop")


# --------------------------------------------------------------------------
# 10. manifest chuẩn hoá + hash
# --------------------------------------------------------------------------

def _manifest(dt: list[dict]) -> list[dict]:
    return sorted(
        ({"tenant_id": d["tenant_id"], "vai_tro": d["vai_tro"],
          "class_uid": d["class_uid"], "sample_uid": d["sample_uid"],
          "slug": d["slug"], "session_id": d["session_id"],
          "file_path": d["file_path"],
          "file_sha256": hashlib.sha256(_noi_dung_npz(d)).hexdigest()}
         for d in dt),
        key=lambda r: (r["tenant_id"], r["vai_tro"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/src/.measurement")
    # Vì sao dọn là VIỆC PHẢI XIN, không phải mặc định
    # ------------------------------------------------
    # Bản đầu dọn theo mặc định: mọi thư mục `iso-*` có marker đều bị `rmtree`,
    # trừ khi người gọi nhớ truyền `--keep`. Ngày 16/08/2026 điều đó xoá mất cây
    # pháp y `iso-20260815-180124-d011ee` — cây đang giữ trạng thái split-brain
    # quan sát được của lỗi ghi hai mặt phẳng. Phần CSV và `.npz` của nó không
    # dựng lại được; chỉ ảnh chụp PostgreSQL trích trước đó là còn.
    #
    # Bài học không phải "nhớ truyền --keep". Một thao tác phá huỷ không hoàn
    # tác được mà mặc định BẬT thì sớm muộn sẽ chạy vào lúc không ai định chạy.
    # Nên mặc định giờ là giữ, và dọn phải nói ra.
    ap.add_argument("--cleanup-previous", action="store_true",
                    help="XOA cac cay cu CUNG PREFIX. Khong mac dinh.")
    ap.add_argument("--keep", action="store_true",
                    help="giu cac cay cu (nay la mac dinh; co de tuong thich)")
    # Cây tái hiện KHÔNG được mang tên cây pháp y. Prefix riêng để (a) người đọc
    # phân biệt được `historical observation` với `reproduction fixture`, và
    # (b) một lượt dọn của prefix này không với tới prefix kia.
    ap.add_argument("--prefix", default="iso",
                    help="tien to thu muc: 'iso' (mac dinh) hoac 'repro'")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not re.fullmatch(r"[a-z][a-z0-9_-]{0,15}", args.prefix):
        raise SystemExit(f"--prefix khong hop le: {args.prefix!r}")

    with _cursor() as cur:
        cur.execute("SELECT current_database(), current_user")
        db, who = cur.fetchone()
    if db == "signdb":
        raise SystemExit(f"TU CHOI: dang tro vao san xuat ({db}). Dung lai.")
    if not args.quiet:
        print(f"== dich ==\n  csdl={db}  vai={who}")

    base = Path(args.base)
    base.mkdir(parents=True, exist_ok=True)
    if args.cleanup_previous and not args.keep:
        # Chỉ CÙNG PREFIX. Một lượt gieo `repro-*` không bao giờ với tới `iso-*`,
        # và ngược lại.
        for cu in sorted(base.glob(f"{args.prefix}-*")):
            if not ((cu / MARKER).exists() or (cu / MARKER_DANG_TAO).exists()):
                continue
            # Chốt chặn cuối: một cây được đánh dấu giữ lại thì không lệnh dọn
            # nào chạm tới, kể cả khi người gọi đã xin dọn. Bằng chứng phải sống
            # sót qua một thao tác gõ vội.
            if (cu / RETAIN).exists():
                print(f"  giu {cu.name} — co {RETAIN}")
                continue
            print(f"  xoa {cu.name}")
            shutil.rmtree(cu, ignore_errors=True)

    fixture_id = uuid.uuid4().hex[:12]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    goc = base / f"{args.prefix}-{stamp}-{fixture_id[:6]}"
    goc.mkdir(parents=True)

    # Marker DANG_TAO trước, marker READY sau. Hai tệp khác nhau cho hai mục
    # đích khác nhau: cái đầu để lượt sau nhận ra đây là cây đo mà dọn; cái sau
    # để `isolation_backend.sh` biết cây đã dùng được. Gộp làm một thì hoặc là
    # cây hỏng không được dọn, hoặc là cây dở dang bị gắn vào phép đo.
    (goc / MARKER_DANG_TAO).write_text(
        f"DANG TAO — fixture_id={fixture_id}\n"
        "Chua dung duoc. KHONG mount cay nay.\n", encoding="utf-8")

    dt = [_doi_tuong(fixture_id, t, v) for t in BEN for v in MA_VAI_TRO]
    if not args.quiet:
        print("== preflight ==")
    _preflight(dt)

    da_ghi_db = False
    try:
        if not args.quiet:
            print("== tenant / user / membership ==")
        for tenant, meta in BEN.items():
            _bao_dam_tenant(tenant, meta["ten"])
            dialect = _dialect_cua(tenant)
            _tao_user(tenant, meta["user"])
            uid = _khang_dinh_user_ton_tai(meta["user"])
            _gan_tu_cach_thanh_vien(tenant, uid)
            _khang_dinh_la_thanh_vien(meta["user"], tenant, uid)
            meta["user_id"] = uid
            meta["dialect"] = dialect
            for d in dt:
                if d["tenant_id"] == tenant:
                    d["dialect"] = dialect
                    d["file_path"] = f"vn/{dialect}/{d['slug']}/{d['sample_uid']}.npz"
                    # Chủ sở hữu gán ở ĐÂY chứ không trong `_doi_tuong`: id tài
                    # khoản chỉ biết được sau khi user đã tồn tại. Xem `_ghi_db`
                    # về vì sao thiếu nó thì đối chứng dương vô nghĩa.
                    d["auth_user_id"] = uid
            if not args.quiet:
                print(f"  {tenant}: user={meta['user']} ({uid[:8]}…) dialect={dialect}")

        # Quản trị viên nền tảng thuộc tenant A. Cần cho ca T2: cổng quyền sở
        # hữu đứng TRƯỚC cổng phạm vi, nên nếu không có tài khoản vượt được cổng
        # thứ nhất một cách hợp lệ thì cổng thứ hai không bao giờ bị kiểm.
        # `is_admin` mở quyền, KHÔNG miễn bất biến tư cách thành viên.
        _tao_user(QUAN_TRI["tenant"], QUAN_TRI["user"], is_admin=True)
        admin_id = _khang_dinh_user_ton_tai(QUAN_TRI["user"])
        _gan_tu_cach_thanh_vien(QUAN_TRI["tenant"], admin_id)
        _khang_dinh_la_thanh_vien(QUAN_TRI["user"], QUAN_TRI["tenant"], admin_id)
        if not args.quiet:
            print(f"  {QUAN_TRI['tenant']}: admin={QUAN_TRI['user']} "
                  f"({admin_id[:8]}…) is_admin=True")

        if not args.quiet:
            print("== don luot gieo truoc ==")
        so_cu = _don_luot_truoc()
        if not args.quiet:
            print(f"  xoa {so_cu} hang cu trong {'/'.join(BEN)}")

        if not args.quiet:
            print("== cay + CSV + tep ==")
        _dung_cay(goc, dt)

        if not args.quiet:
            print("== PostgreSQL ==")
        _ghi_db(dt)
        da_ghi_db = True

        if not args.quiet:
            print("== doi chieu ba kho ==")
        _doi_chieu(goc, dt)

    except BaseException as e:
        print(f"\nFAILED: {e}", file=sys.stderr)
        if da_ghi_db:
            _don_bu_tru(dt)
        shutil.rmtree(goc, ignore_errors=True)
        print("da don. KHONG tao marker READY.", file=sys.stderr)
        return 1

    manifest = _manifest(dt)
    fixture_hash = hashlib.sha256(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True,
                   separators=(",", ":")).encode()).hexdigest()

    (goc / "fixture.json").write_text(json.dumps({
        "fixture_id": fixture_id,
        "status": "READY",
        "database": db,
        "runtime_role": who,
        "dataset_fixture_hash": fixture_hash,
        "ben": {t: {k: v for k, v in m.items() if k != "ten"}
                for t, m in BEN.items()},
        "doi_tuong": manifest,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # READY là bước CUỐI CÙNG.
    (goc / MARKER_DANG_TAO).unlink()
    (goc / MARKER).write_text(
        f"READY — fixture_id={fixture_id}\n"
        f"dataset_fixture_hash={fixture_hash}\n"
        "Cay du lieu TONG HOP cho phep do cach ly tenant — xoa tuy y.\n"
        "KHONG BAO GIO tro VOYA_ISO_DATASET vao kho san xuat.\n", encoding="utf-8")

    if args.quiet:
        print(str(goc))
        return 0

    print(f"\n== READY ==\n  cay   {goc}\n  hash  {fixture_hash[:16]}…")
    for r in manifest:
        print(f"  {r['tenant_id']:6} {r['vai_tro']:14} class={r['class_uid']:24} "
              f"sample={r['sample_uid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

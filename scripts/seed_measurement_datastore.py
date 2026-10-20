#!/usr/bin/env python3
"""Dựng cây dữ liệu TỔNG HỢP, dùng-một-lần, cho phép đo cách ly tenant.

    python scripts/seed_measurement_datastore.py            # in ra đường dẫn
    VOYA_ISO_DATASET=$(python scripts/seed_measurement_datastore.py --quiet) \
        sh scripts/isolation_backend.sh up

Vì sao tệp này tồn tại
======================
Ngày 15/08/2026, một lượt dựng lại phép đo cách ly phát hiện `voya_backend_iso`
chạy **không gắn kho dữ liệu nào**. `labels.csv` trong container là tệp rỗng do
`_ensure_labels_file()` tự tạo, nên hai đường nghiệp vụ sau trả 404 cho MỌI
class_uid, của MỌI tenant:

    GET /api/v1/classes/{uid}/sessions
    GET /api/v1/dataset/samples/{uid}/data

Hai phép thử đối kháng tương ứng vẫn được chấm là "đã chặn". Đó là điểm kiếm
được từ hư không: chúng trả 404 y hệt kể cả khi cách ly thủng hoàn toàn.

Mặt phẳng lưu trữ THỨ HAI
=========================
Phát hiện ấy quan trọng hơn một lỗi fixture. Nó cho thấy cách ly tenant ở hệ này
có hai mặt phẳng, và RLS chỉ phủ một:

    hàng PostgreSQL   ->  RLS cưỡng chế
    hàng CSV/tệp      ->  RLS KHÔNG biết gì

Truy hết đường đọc `GET /api/v1/classes/{uid}/sessions`:

    get_current_user      chỉ XÁC THỰC
    find_class_meta       -> list_classes() -> labels.csv    KHÔNG lọc tenant
    list_session_rows     -> list_samples()  -> samples.csv   KHÔNG lọc tenant
    get_sample_owners     Postgres, chỉ để gắn cờ hiển thị `is_owner`

Cột `tenant_id` CÓ trong cả hai CSV. Không đường nào đọc nó. Cây dữ liệu này tồn
tại để biến câu hỏi ấy từ suy luận thành phép đo.

Vì sao TỔNG HỢP chứ không phải bản sao kho thật
===============================================
Bộ đo cố tình bắn `DELETE` mẫu và `DELETE` lớp. Gắn kho thật vào vùng phá huỷ là
đặt 3.860 mẫu nghiên cứu vào chỗ mà một lỗ cách ly sẽ chứng minh bằng cách xoá
chúng. Dữ liệu tổng hợp còn tốt hơn về phương pháp: xuất xứ rõ, huỷ tuỳ ý, và ít
dòng đủ để đọc bằng mắt khi một kết quả gây ngạc nhiên.

Vì sao ĐỐI CHỨNG và MỤC TIÊU là hai đối tượng khác nhau
=======================================================
Bộ thử có `DELETE`. Nếu đối chứng dương đọc đúng đối tượng mà nhóm đối kháng sau
đó xoá, thứ tự chạy sẽ quyết định kết quả: một loạt 404 "đẹp" xuất hiện chỉ vì
đối tượng đã biến mất. Đó là cùng một lỗi đã hai lần làm hỏng phép đo này, chỉ ở
một tầng khác. Nên mỗi tenant có:

    control_read     đối chứng dương cho ĐỌC
    control_update   đối chứng dương cho SỬA
    control_delete   đối chứng dương cho XOÁ — được phép biến mất
    target           mục tiêu đối kháng — phải KHÔNG đổi suốt pha đối chứng

Tách theo từng PHƯƠNG THỨC, không chỉ tách control khỏi target: đối chứng dương
có thao tác ghi và xoá, nên ba phép trên cùng một đối tượng sẽ tự phá lẫn nhau
theo thứ tự chạy.

Danh sách cột lấy từ CHÍNH mã ứng dụng (`LABEL_FIELDS`, `sample_fields()`), không
chép: một cột thêm vào lược đồ mà quên cập nhật ở đây sẽ tạo CSV thiếu cột, và bộ
đo sẽ hỏng theo kiểu trông như một kết quả đo.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

MARKER = ".tenant-isolation-fixture"
NOW = "2026-08-15T00:00:00+00:00"

#: Hai bên. Mỗi bên một đối tượng đối chứng và một đối tượng mục tiêu.
BEN = ("iso_a", "iso_b")


#: Mã một ký tự HEX cho từng vai trò, dùng dựng `sample_uid`.
#:
#: `samples` mang ràng buộc `samples_uid_is_hex10`:
#:     CHECK (sample_uid ~ '^[0-9a-f]{10}$')
#: — ĐÚNG mười ký tự, và mọi ký tự phải là hex.
#:
#: Cách đặt tên dễ đọc kiểu `s` + tenant + `cont` + hậu tố sinh ra
#: `sacont702c2f`: mười hai ký tự, và `s`/`o`/`t` không phải hex. PostgreSQL từ
#: chối, còn CSV thì nhận — nên cây fixture có bốn mẫu mà cơ sở dữ liệu không có
#: mẫu nào. Đúng kiểu lệch hai nguồn mà cả bộ đo này dựng ra để tránh, và nó chỉ
#: lộ khi đối chiếu thủ công.
#:
#: Nên `sample_uid` = <tenant: a|b><vai trò: c|d|e|f><8 hex ngẫu nhiên>. Vẫn đọc
#: được bằng mắt, và hợp lệ với ràng buộc.
#: `(ký tự hex cho sample_uid, tên ngắn cho class_uid)`.
#:
#: Tên ngắn phải KHÁC NHAU Ở ĐẦU. Lấy sáu ký tự đầu của tên vai trò cho ra
#: `contro` cho cả ba đối chứng — mười ký tự đầu của `class_uid` giống hệt nhau
#: và chỉ khác ở hậu tố ngẫu nhiên, tức là phải soi từng ký tự mới phân biệt
#: được. Điều đó phá đúng mục đích đã nêu ở trên.
MA_VAI_TRO = {
    "control_read":   ("c", "read"),
    "control_update": ("d", "upd"),
    "control_delete": ("e", "del"),
    "target":         ("f", "targ"),
}


def _doi_tuong(tenant: str, vai_tro: str) -> dict:
    """UID khác nhau rõ rệt để một kết quả bất ngờ đọc được bằng mắt.

    Bốn vai trò cho mỗi bên, KHÔNG dùng chung đối tượng giữa các phương thức:

        control_read      đối chứng dương cho ĐỌC
        control_update    đối chứng dương cho SỬA
        control_delete    đối chứng dương cho XOÁ
        target            mục tiêu đối kháng

    Đối chứng dương phải thử cả ba phương thức, vì bộ đối kháng thử cả ba: một
    ca `DELETE` xuyên tenant bị chặn chỉ có nghĩa khi đã biết tài khoản ấy xoá
    được thứ của CHÍNH nó. Nhưng ba phép ấy trên cùng một đối tượng thì sau
    `DELETE` nó biến mất, và mọi lần thử lại — hoặc một thay đổi thứ tự — rơi vào
    404 vô nghĩa. Tách theo phương thức thì kết quả không phụ thuộc thứ tự chạy.
    """
    hau_to = uuid.uuid4().hex[:6]
    ma_hex, ten_ngan = MA_VAI_TRO[vai_tro]
    return {
        "tenant": tenant, "vai_tro": vai_tro,
        "class_uid": f"{tenant.replace('_','')}{ten_ngan}{hau_to}",
        "sample_uid": f"{tenant[-1]}{ma_hex}{uuid.uuid4().hex[:8]}",
        "slug": f"{tenant}-{vai_tro}",
        "session": f"sess-{tenant}-{vai_tro}",
    }


def _ghi_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(REPO / ".measurement"),
                    help="thu muc cha; moi luot sinh mot cay moi ben trong")
    ap.add_argument("--keep", action="store_true",
                    help="giu cac cay cu thay vi xoa chung")
    ap.add_argument("--quiet", action="store_true",
                    help="chi in duong dan cay — de gan vao VOYA_ISO_DATASET")
    # Vì sao cây đo cần biết CHỦ SỞ HỮU
    # ---------------------------------
    # `POST /classes/{uid}/sessions/{sid}/reassign` kiểm quyền sở hữu TRƯỚC khi
    # chạm tới phạm vi tenant:
    #
    #     owner_id = get_sample_owner(sample_uid)      # samples.auth_user_id
    #     if not is_admin and owner_id != me: -> 403
    #
    # Một cây gieo không có `auth_user_id` cho `owner_id = None`, nên MỌI lượt
    # thử của tài khoản thường dừng ở 403 — kể cả lượt hợp lệ trên mẫu của chính
    # mình. Đó đúng là điều đã làm ca S của lượt đo trước vô nghĩa: nó bị chặn
    # bởi quyền sở hữu, và không nói được gì về cách ly tenant.
    #
    # Gán chủ sở hữu thật cho phép tách hai câu hỏi:
    #     T4  chủ sở hữu thật, cùng tenant     -> phải THÀNH CÔNG
    #     T1  chủ sở hữu thật, lớp đích khác tenant -> phải bị chặn bởi PHẠM VI
    # Không có bước này thì T4 không phân biệt được "phạm vi hỏng" với "không
    # phải chủ sở hữu".
    ap.add_argument("--owner", action="append", default=[], metavar="TENANT=UUID",
                    help="gan auth_user_id cho moi mau cua tenant (lap lai duoc)")
    args = ap.parse_args()

    chu_so_huu: dict[str, str] = {}
    for cap in args.owner:
        if "=" not in cap:
            raise SystemExit(f"--owner phai co dang TENANT=UUID, nhan duoc: {cap!r}")
        t, u = cap.split("=", 1)
        t, u = t.strip(), u.strip()
        if t not in BEN:
            raise SystemExit(f"--owner tro toi tenant la: {t!r} (chi co {BEN})")
        chu_so_huu[t] = u

    from app.dataset_manager import LABEL_FIELDS
    from app.dataset_samples import SAMPLE_FIELDS

    base = Path(args.base)
    base.mkdir(parents=True, exist_ok=True)

    # Dọn cây cũ: chúng đã bị bộ thử bắn `DELETE`, nên trạng thái của chúng
    # không còn nói lên điều gì. Chỉ xoá thư mục CÓ tệp đánh dấu — không bao giờ
    # xoá một thư mục lạ nằm trong `--base`.
    if not args.keep:
        for cu in base.glob("iso-*"):
            # `.retain` thắng mọi lệnh dọn. Ngày 16/08/2026 vòng lặp này (ở
            # `seed_cross_store.py`, cùng một khuôn) đã xoá cây pháp y đang giữ
            # bằng chứng split-brain duy nhất. Một thư mục tự tuyên bố "đừng
            # xoá tôi" là rẻ hơn nhiều so với việc nhớ truyền `--keep`.
            if (cu / ".retain").exists():
                continue
            if (cu / MARKER).exists():
                shutil.rmtree(cu, ignore_errors=True)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    goc = base / f"iso-{stamp}-{uuid.uuid4().hex[:6]}"
    goc.mkdir(parents=True)

    # Tệp đánh dấu TRƯỚC dữ liệu: một lượt hỏng giữa chừng vẫn để lại thư mục
    # nhận diện được là cây đo, chứ không lẫn với cây thật.
    (goc / MARKER).write_text(
        "Cay du lieu TONG HOP cho phep do cach ly tenant.\n"
        "Sinh boi scripts/seed_measurement_datastore.py — xoa tuy y.\n"
        "KHONG BAO GIO tro VOYA_ISO_DATASET vao kho san xuat.\n",
        encoding="utf-8")

    doi_tuong = [_doi_tuong(t, v) for t in BEN for v in MA_VAI_TRO]

    nhan, mau = [], []
    for i, d in enumerate(doi_tuong):
        nhan.append({
            "class_uid": d["class_uid"], "class_idx": str(i), "slug": d["slug"],
            "label_original": f"lop {d['vai_tro']} cua {d['tenant']}",
            "language": "vn", "dialect": "bac", "region": "unclassified",
            "is_active": "true", "hands_required": "2",
            "folder_name": d["slug"], "created_at": NOW,
            "tenant_id": d["tenant"],
        })
        mau.append({
            "sample_uid": d["sample_uid"], "class_uid": d["class_uid"],
            "slug": d["slug"], "label_original": f"mau {d['vai_tro']} cua {d['tenant']}",
            "language": "vn", "dialect": "bac", "source_type": "measurement",
            "session_id": d["session"], "seq_len": "16",
            "fps_original": "30", "fps_processed": "30", "completeness": "1.0",
            "file_path": f"vn/bac/{d['slug']}/{d['sample_uid']}.npz",
            "created_at": NOW, "tenant_id": d["tenant"],
            "auth_user_id": chu_so_huu.get(d["tenant"], ""),
        })
        thu_muc = goc / "vn" / "bac" / d["slug"]
        thu_muc.mkdir(parents=True, exist_ok=True)
        # Tệp .npz THẬT, không phải chỗ giữ chỗ rỗng.
        #
        # `sync_reassign_sample` TỪ CHỐI khi không có bản .npz trên máy
        # (`SAMPLE_NOT_MATERIALIZED`, 409). Một cây không có tệp làm T4 dừng ở
        # đó và không bao giờ chạm tới đoạn ghi hai mặt phẳng — tức là bộ đo báo
        # "đã chặn" cho một đường mã chưa từng chạy. Cùng loại điểm-kiếm-từ-
        # hư-không mà cây này sinh ra để gỡ.
        #
        # Nội dung phải đọc được bằng `np.load`: đường xem trước/khung hình mở
        # thật. Hình dạng lấy theo `seq_len=16` ở trên.
        np.savez_compressed(
            thu_muc / f"{d['sample_uid']}.npz",
            keypoints=np.zeros((16, 225), dtype=np.float32))
        (thu_muc / f"{d['sample_uid']}.json").write_text(
            json.dumps({"sample_uid": d["sample_uid"], "class_uid": d["class_uid"],
                        "tenant_id": d["tenant"]}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    _ghi_csv(goc / "labels.csv", list(LABEL_FIELDS), nhan)
    _ghi_csv(goc / "samples.csv", list(SAMPLE_FIELDS), mau)

    for d in doi_tuong:
        d["auth_user_id"] = chu_so_huu.get(d["tenant"], "")
    fixture = {"root": str(goc), "chu_so_huu": chu_so_huu, "doi_tuong": doi_tuong}
    (goc / "fixture.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.quiet:
        print(str(goc))
        return 0

    print(f"cay do: {goc}")
    print(f"  labels.csv   {len(nhan)} dong")
    print(f"  samples.csv  {len(mau)} dong")
    for d in doi_tuong:
        print(f"  {d['tenant']:6} {d['vai_tro']:8} class={d['class_uid']} "
              f"sample={d['sample_uid']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

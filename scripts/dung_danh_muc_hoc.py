# -*- coding: utf-8 -*-
"""Dựng `backend/app/data/qipedc_catalog.json` từ mục lục QIPEDC đã lập.

Đầu vào: `qipedc_nhan.csv` (sinh bởi `lap_muc_luc_qipedc.py` + `gan_nhan_qipedc.py`,
nằm ở thư mục video đã tải — mặc định `E:/CTU_ProjectOutside/qipedc_mau`).
Đầu ra: một JSON gọn (~880 KB) cho trang "Học ký hiệu": mã, từ, slug, vùng,
từ loại, định nghĩa. KHÔNG có video — video chỉ liên kết sang trang chính
thức của QIPEDC cho tới khi có văn bản cho phép sử dụng.

    python scripts/dung_danh_muc_hoc.py [--nguon <thu_muc>]

`slug` dùng cùng quy tắc với `frontend/src/utils/markdownOutline.slugify` và
với `classes.slug` của kho (bỏ dấu, `đ`→`d`, khoảng trắng→`-`), để một từ
QIPEDC tra được lớp tương ứng trong dữ liệu của mình bằng `slug`.
"""
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys
import unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # pragma: no cover
    pass

REPO = pathlib.Path(__file__).resolve().parents[1]
DICH = REPO / "backend" / "app" / "data" / "qipedc_catalog.json"


def slugify(text: str) -> str:
    t = text.replace("đ", "d").replace("Đ", "D")
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-") or "muc"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--nguon", default=r"E:/CTU_ProjectOutside/qipedc_mau")
    a = ap.parse_args()
    src = pathlib.Path(a.nguon) / "qipedc_nhan.csv"
    rows = list(csv.DictReader(src.open(encoding="utf-8-sig")))
    out = []
    for r in rows:
        word = (r.get("nhan") or "").strip()
        if not word:
            continue
        out.append({
            "code": r["ma_qipedc"],
            "base": r["ma_goc"],
            "word": word,
            "slug": slugify(word),
            "region": (r.get("vung") or "").strip(),   # bac | trung | nam | khong_ghi
            "pos": (r.get("tu_loai") or "").strip(),
            "kind": (r.get("loai_von_tu") or "").strip(),
            "definition": (r.get("dinh_nghia") or "").strip(),
        })
    DICH.parent.mkdir(parents=True, exist_ok=True)
    DICH.write_bytes(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    print(f"{len(out)} mục -> {DICH} ({DICH.stat().st_size} byte)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

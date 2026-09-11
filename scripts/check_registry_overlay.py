#!/usr/bin/env python3
"""Lớp phủ registry có còn phủ hết mọi service dùng ảnh tự dựng không?

    python scripts/check_registry_overlay.py

Thoát 0 = phủ đủ, 1 = có service bị bỏ sót hoặc thừa. Chỉ đọc.

Vì sao cần một phép kiểm riêng cho chuyện này
----------------------------------------------
`docker-compose.registry.yml` phải liệt kê BẢY service, và bảy cái đó chỉ dùng
BA ảnh — năm service dùng chung ảnh backend. Thêm một service mới dùng ảnh
backend (một worker thứ hai, một lệnh chạy một lần) mà quên thêm vào lớp phủ
thì KHÔNG có gì hỏng: compose lặng lẽ dùng `image:` của tệp gốc, tức là tag cục
bộ `voya_backend:latest` — thứ trên máy triển khai hoặc là ảnh của lần dựng tay
gần nhất, hoặc là không tồn tại.

Kết quả là dạng lệch tệ nhất: sáu container chạy ảnh đã ghim, một container
chạy thứ khác, và tất cả đều "healthy". Cùng một lớp lỗi với lần quên
`celery-beat` trong một danh sách viết tay ở nơi khác của kho này.

Phép kiểm này rẻ, chạy trong CI, và nói thẳng ra tên service bị thiếu.
"""
from __future__ import annotations

import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name: str) -> dict:
    path = ROOT / name
    if not path.exists():
        print(f"[FAIL] khong thay {name}", file=sys.stderr)
        raise SystemExit(2)
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def main() -> int:
    base = load("docker-compose.yml")
    overlay = load("docker-compose.registry.yml")

    # "Service tu dung anh" = service co `build:`. Do la dinh nghia dung: mot
    # service keo `postgres:17` tu Docker Hub thi khong lien quan gi toi lop phu
    # nay, con mot service co build context thi anh cua no PHAI den tu dau do.
    need = {
        name
        for name, spec in (base.get("services") or {}).items()
        if isinstance(spec, dict) and "build" in spec
    }
    have = set((overlay.get("services") or {}).keys())

    missing = sorted(need - have)
    extra = sorted(have - need)

    if not missing and not extra:
        print(f"Lop phu registry phu du {len(need)} service tu dung anh.")
        return 0

    if missing:
        print("[FAIL] docker-compose.registry.yml BO SOT service tu dung anh:", file=sys.stderr)
        for name in missing:
            img = (base["services"][name] or {}).get("image", "(khong khai image)")
            print(f"    - {name}  (tep goc dung {img})", file=sys.stderr)
        print(
            "\n    Hau qua neu de nguyen: service nay chay anh CUC BO tren may trien khai\n"
            "    trong khi ca stack chay anh da ghim — va no van bao 'healthy'.",
            file=sys.stderr,
        )
    if extra:
        print("[FAIL] lop phu khai service khong co trong docker-compose.yml:", file=sys.stderr)
        for name in extra:
            print(f"    - {name}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Danh mục từ vựng cho trang "Học ký hiệu" — đọc từ `data/qipedc_catalog.json`.

Nguồn: Danh mục NNKH tiếng Việt của dự án QIPEDC (Bộ GD&ĐT), 4.362 mục, do
`scripts/dung_danh_muc_hoc.py` gọn hoá từ mục lục đã lập ngày 14/08/2026.

Ba điều cố ý
------------
1. **Chỉ siêu dữ liệu, không video.** Video mẫu nằm trên máy chủ QIPEDC; trang
   học LIÊN KẾT sang đó kèm ghi nguồn. Sao chép 4.000 video vào hệ thống là
   phân phối lại, cần văn bản cho phép — chưa có thì không làm.
2. **Không quy một biến thể là chuẩn.** Cùng một từ có thể có ba video Bắc /
   Trung / Nam; danh mục giữ cả ba như ba biến thể ngang nhau. 2.759/4.362 mục
   không ghi vùng — hiện là "chung", không suy đoán vùng cho chúng.
3. **Nối với dữ liệu của mình bằng `slug`.** Lớp trong `classes` và mục QIPEDC
   cùng quy tắc slug (bỏ dấu, `đ`→`d`), nên "ký hiệu này đã có mẫu trong hệ
   thống chưa" trả lời được mà không cần bảng ánh xạ tay.

Tìm kiếm không phân biệt dấu và hoa/thường ("cam on" ra "cảm ơn"), vì học sinh
và phụ huynh gõ không dấu là chuyện thường.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "qipedc_catalog.json"

#: Trang chính thức để xem video; mã mục ghép vào để người học tìm đúng từ.
QIPEDC_DICTIONARY_URL = "https://qipedc.moet.gov.vn/dictionary"
QIPEDC_VIDEO_URL = "https://qipedc.moet.gov.vn/videos/{code}.mp4"

REGION_NAME = {"bac": "Bắc", "trung": "Trung", "nam": "Nam", "khong_ghi": "Chung"}


def slugify(text: str) -> str:
    t = (text or "").replace("đ", "d").replace("Đ", "D")
    t = unicodedata.normalize("NFD", t)
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn")
    t = t.lower()
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-")


@lru_cache(maxsize=1)
def _entries() -> List[Dict[str, Any]]:
    with CATALOG_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=1)
def _words() -> List[Dict[str, Any]]:
    """Gộp các biến thể vùng của cùng một từ (theo `slug`) thành một mục."""
    by_slug: Dict[str, Dict[str, Any]] = {}
    for e in _entries():
        w = by_slug.get(e["slug"])
        if w is None:
            w = by_slug[e["slug"]] = {
                "slug": e["slug"],
                "word": e["word"],
                "pos": e["pos"],
                "kind": e["kind"],
                "definition": e["definition"],
                "variants": [],
            }
        if not w["definition"] and e["definition"]:
            w["definition"] = e["definition"]
        w["variants"].append({
            "code": e["code"],
            "region": e["region"],
            "region_name": REGION_NAME.get(e["region"], e["region"]),
            "video_url": QIPEDC_VIDEO_URL.format(code=e["code"]),
        })
    out = list(by_slug.values())
    out.sort(key=lambda w: w["slug"])
    return out


def search(q: str = "", region: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Tìm theo từ (không dấu, không phân biệt hoa/thường), lọc theo vùng.

    Ưu tiên: khớp đầu từ trước, khớp giữa từ sau — để "chao" ra "chào" trước
    "chim chào mào".
    """
    needle = slugify(q)
    region = (region or "").strip()
    hits: List[tuple[int, Dict[str, Any]]] = []
    for w in _words():
        if region and not any(v["region"] == region for v in w["variants"]):
            continue
        if not needle:
            hits.append((1, w))
            continue
        s = w["slug"]
        if s == needle:
            hits.append((0, w))
        elif s.startswith(needle):
            hits.append((1, w))
        elif needle in s:
            hits.append((2, w))
    hits.sort(key=lambda t: (t[0], t[1]["slug"]))
    return [w for _, w in hits[:max(1, min(limit, 200))]]


def get(slug: str) -> Optional[Dict[str, Any]]:
    slug = slugify(slug)
    for w in _words():
        if w["slug"] == slug:
            return w
    return None


def count() -> Dict[str, int]:
    return {"entries": len(_entries()), "words": len(_words())}

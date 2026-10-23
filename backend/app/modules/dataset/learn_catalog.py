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

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "qipedc_catalog.json"

#: Trang chính thức để xem video; mã mục ghép vào để người học tìm đúng từ.
QIPEDC_DICTIONARY_URL = "https://qipedc.moet.gov.vn/dictionary"
QIPEDC_VIDEO_URL = "https://qipedc.moet.gov.vn/videos/{code}.mp4"

REGION_NAME = {"bac": "Bắc", "trung": "Trung", "nam": "Nam", "khong_ghi": "Chung"}

#: Ba loại mục trong danh mục — từ thường chiếm 4.259/4.362; bảng chữ cái và
#: chữ số là hai bộ nhỏ nhưng là thứ người mới học tìm ĐẦU TIÊN, nên có bộ lọc.
KIND_NAME = {"tu_thuong": "Từ thường", "bang_chu_cai": "Bảng chữ cái", "chu_so": "Chữ số"}

#: Từ loại đưa lên bộ lọc: chỉ những nhóm ĐỦ LỚN. Danh mục ghi hơn 30 nhãn từ
#: loại ("tt, dt", "Khẩu ngữ", …) mà 25 nhãn chỉ có dưới 10 mục — đem cả lên
#: là một ô chọn 30 dòng không ai dùng. Ngưỡng ở `facets()`.
POS_FACET_MIN = 20


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


def _norm(text: str) -> str:
    return (text or "").strip().lower()


def filter_words(
    q: str = "",
    region: str = "",
    kind: str = "",
    pos: str = "",
    letter: str = "",
) -> List[Dict[str, Any]]:
    """Mọi mục khớp, ĐÃ xếp hạng, CHƯA cắt trang.

    Tìm theo từ (không dấu, không phân biệt hoa/thường), rồi lọc theo vùng,
    loại mục, từ loại và chữ cái đầu. Ưu tiên: khớp đúng → khớp đầu từ → khớp
    giữa từ — để "chao" ra "chào" trước "chim chào mào". Khi không gõ gì thì
    theo thứ tự bảng chữ cái, tức là duyệt được như một cuốn từ điển.

    Trả cả danh sách để nơi gọi đếm được tổng và cắt trang; `search()` bên
    dưới là lối cũ giữ cho tương thích.
    """
    needle = slugify(q)
    region = (region or "").strip()
    kind = (kind or "").strip()
    pos_n = _norm(pos)
    letter = slugify(letter)[:1]
    hits: List[tuple[int, Dict[str, Any]]] = []
    for w in _words():
        if region and not any(v["region"] == region for v in w["variants"]):
            continue
        if kind and w["kind"] != kind:
            continue
        if pos_n and _norm(w["pos"]) != pos_n:
            continue
        if letter and not w["slug"].startswith(letter):
            continue
        s = w["slug"]
        if not needle:
            hits.append((1, w))
        elif s == needle:
            hits.append((0, w))
        elif s.startswith(needle):
            hits.append((1, w))
        elif needle in s:
            hits.append((2, w))
    # Chữ trước số: không gõ gì mà trang đầu toàn "0", "1 000 000" thì trông
    # như một bảng số chứ không phải từ điển. Có từ khoá thì hạng khớp vẫn đi trước.
    hits.sort(key=lambda t: (t[0], t[1]["slug"][:1].isdigit(), t[1]["slug"]))
    return [w for _, w in hits]


def search(q: str = "", region: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Lối cũ: `filter_words` cắt còn `limit` mục đầu."""
    return filter_words(q, region)[:max(1, min(limit, 200))]


@lru_cache(maxsize=1)
def facets() -> Dict[str, Any]:
    """Các nhóm để dựng bộ lọc, kèm số từ mỗi nhóm — tính một lần, danh mục
    là tệp tĩnh. Chữ cái đầu chỉ liệt kê những chữ CÓ từ, để thanh A–Z không
    có nút chết."""
    words = _words()
    kinds = {k: 0 for k in KIND_NAME}
    regions = {r: 0 for r in REGION_NAME}
    pos_count: Dict[str, int] = {}
    letters: Dict[str, int] = {}
    for w in words:
        kinds[w["kind"]] = kinds.get(w["kind"], 0) + 1
        for r in {v["region"] for v in w["variants"]}:
            regions[r] = regions.get(r, 0) + 1
        p = (w["pos"] or "").strip()
        if p:
            pos_count[p] = pos_count.get(p, 0) + 1
        first = w["slug"][:1]
        if first:
            letters[first] = letters.get(first, 0) + 1
    return {
        "kinds": [{"key": k, "name": KIND_NAME.get(k, k), "count": n} for k, n in kinds.items() if n],
        "regions": [{"key": r, "name": REGION_NAME.get(r, r), "count": n} for r, n in regions.items() if n],
        "pos": sorted(
            ({"name": p, "count": n} for p, n in pos_count.items() if n >= POS_FACET_MIN),
            key=lambda x: -x["count"],
        ),
        "letters": sorted(letters),
    }


def get(slug: str) -> Optional[Dict[str, Any]]:
    slug = slugify(slug)
    for w in _words():
        if w["slug"] == slug:
            return w
    return None


def count() -> Dict[str, int]:
    return {"entries": len(_entries()), "words": len(_words())}

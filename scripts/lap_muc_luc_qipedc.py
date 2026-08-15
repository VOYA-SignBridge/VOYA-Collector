# -*- coding: utf-8 -*-
"""Ghép danh mục QIPEDC vào các tệp video đã tải, xuất mục lục tra được.

Trả lời câu "video này là từ gì": mỗi tệp `.mp4` được nối với từ, định nghĩa,
từ loại và biến thể phương ngữ lấy từ `qipedc_danhmuc.json`.

    .venv/Scripts/python.exe scripts/lap_muc_luc_qipedc.py --thu-muc <dir>

Xuất `qipedc_muc_luc.csv` (đầy đủ) và in thống kê để dùng cho luận văn.
"""
import argparse, collections, csv, json, os, re, statistics, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

TEN_VUNG = {"B": "Bắc", "N": "Nam", "T": "Trung", "": "(không ghi vùng)"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", required=True)
    a = ap.parse_args()

    p_dm = os.path.join(a.thu_muc, "qipedc_danhmuc.json")
    if not os.path.exists(p_dm):
        print("Chưa có %s — chạy tai_mau_qipedc.py --chi-danh-muc trước." % p_dm)
        return 1
    dm = {x["_id"]: x for x in json.load(open(p_dm, encoding="utf-8"))
          if x.get("_id")}
    tep = {f[:-4]: os.path.join(a.thu_muc, f)
           for f in os.listdir(a.thu_muc) if f.endswith(".mp4")}

    hang = []
    for ma in sorted(tep):
        x = dm.get(ma, {})
        m = re.match(r"^([A-Za-z]+)(\d+)([BNT]?)$", ma)
        hang.append({
            "ma": ma,
            "tu": x.get("word", ""),
            "tu_khong_dau": x.get("_word", ""),
            "tu_loai": (x.get("tl") or "").strip(),
            "vung": TEN_VUNG.get(m.group(3) if m else "", "?"),
            "ma_goc": (m.group(1) + m.group(2)) if m else ma,
            "dinh_nghia": (x.get("description") or "").replace("\n", " ").strip(),
            "byte": os.path.getsize(tep[ma]),
            "trong_danh_muc": ma in dm,
        })

    ra = os.path.join(a.thu_muc, "qipedc_muc_luc.csv")
    with open(ra, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(hang[0].keys()))
        w.writeheader()
        w.writerows(hang)
    print("Đã ghi %s (%d dòng)\n" % (ra, len(hang)))

    # ---- thống kê ----------------------------------------------------
    thieu = [h for h in hang if not h["trong_danh_muc"]]
    print("Tệp đã tải            %d" % len(hang))
    print("  khớp danh mục       %d" % (len(hang) - len(thieu)))
    if thieu:
        print("  KHÔNG có trong danh mục: %s"
              % ", ".join(h["ma"] for h in thieu[:8]))
    print("  tổng dung lượng     %.1f MB"
          % (sum(h["byte"] for h in hang) / 1048576))
    print("  trung vị mỗi tệp    %.0f KB"
          % (statistics.median(h["byte"] for h in hang) / 1024))

    print("\nTheo vùng phương ngữ:")
    for k, v in collections.Counter(h["vung"] for h in hang).most_common():
        print("  %-18s %5d  (%.1f%%)" % (k, v, 100 * v / len(hang)))

    goc = collections.defaultdict(set)
    for h in hang:
        goc[h["ma_goc"]].add(h["vung"])
    day_du = sum(1 for v in goc.values()
                 if {"Bắc", "Nam", "Trung"} <= v)
    print("\nTừ gốc (không tính biến thể)  %d" % len(goc))
    print("  có ĐỦ cả ba vùng            %d  (%.1f%%)"
          % (day_du, 100 * day_du / len(goc)))
    print("  chỉ có bản không ghi vùng   %d  (%.1f%%)"
          % (sum(1 for v in goc.values() if v == {"(không ghi vùng)"}),
             100 * sum(1 for v in goc.values() if v == {"(không ghi vùng)"}) / len(goc)))

    print("\nTheo từ loại:")
    for k, v in collections.Counter(
            h["tu_loai"] or "(trống)" for h in hang).most_common(8):
        print("  %-16s %5d" % (k, v))

    co_dn = sum(1 for h in hang if h["dinh_nghia"])
    print("\nCó định nghĩa        %d / %d  (%.1f%%)"
          % (co_dn, len(hang), 100 * co_dn / len(hang)))

    print("\nVài dòng đầu:")
    for h in hang[:5]:
        print("  %-9s %-22s %-12s %s"
              % (h["ma"], h["tu"][:22], h["vung"], h["dinh_nghia"][:46]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

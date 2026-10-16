# -*- coding: utf-8 -*-
"""Gán nhãn đầy đủ cho bộ video QIPEDC đã tải.

Mỗi tệp `.mp4` được nối với: ngôn ngữ, vùng miền, loại vốn từ, nhãn (từ), từ
loại và định nghĩa. Tên trường và giá trị khớp **đúng bộ từ vựng chuẩn của nền
tảng** đọc từ `dataset/vocabulary_registry.json`, để bảng này nhập được thẳng
mà không phải ánh xạ lại.

HAI TRỤC ĐỘC LẬP, KHÔNG GỘP
---------------------------
  * `vung`        — **vùng miền địa lý**: Bắc / Trung / Nam. Lấy từ hậu tố
                    `B`/`N`/`T` của mã QIPEDC.
  * `loai_von_tu` — **phương ngữ**, hiểu theo nghĩa *tập vốn từ con*: bảng chữ
                    cái, chữ số, hoặc vốn từ của một lĩnh vực chuyên ngành /
                    một tập thể nhỏ / một cá nhân. Đây chính là trục mà trường
                    `dialect` của nền tảng biểu diễn (`bang-chu-cai`, `spa`,
                    `can-tho`, `hoa-de`).

Hai trục này **độc lập**: hai người cùng miền Nam vẫn có thể dùng hai tập vốn
từ khác nhau, và cùng một chữ cái vẫn có ba dạng ký hiệu theo ba miền.

Trường `dialect` hiện hành của nền tảng đang gộp **cả hai trục cộng thêm một
thứ thứ ba** — kiểm trên `dataset/labels.csv` (63 lớp):

    bang-chu-cai  30 lớp  -> PHƯƠNG NGỮ (tập vốn từ)
    can-tho        9      -> PHƯƠNG NGỮ (tập thể / địa phương)
    spa            9      -> PHƯƠNG NGỮ (lĩnh vực chuyên ngành)
    hoa-de         8      -> PHƯƠNG NGỮ (tập thể / địa phương)
    common         4      -> PHẠM VI, không phải phương ngữ nào cả
    bac/nam/trung  3      -> VÙNG MIỀN, không phải phương ngữ

56/63 lớp dùng trường đó đúng nghĩa phương ngữ; 3 lớp dùng nó để chứa vùng
miền và 4 lớp dùng nó để chứa phạm vi. Chính vì một cột không giữ được hai
trục mà 1.034 mẫu chữ cái mất thông tin vùng — xem
`docs/00-thesis/DOI_CHIEU_QIPEDC.md` §4.

QUY TẮC KHÔNG BỊA
-----------------
Video không có hậu tố `B`/`N`/`T` thì **để trống vùng**, ghi `khong_ghi`. Đó
là *từ điển chưa thu biến thể vùng cho từ đó*, KHÔNG phải *từ đó không có
biến thể vùng*, và càng không phải "vùng chung". Suy ra vùng từ nơi thu hoặc
từ người ký là bịa siêu dữ liệu — đúng loại lỗi đã kiểm kê ở
`docs/10-issues/HARDCODED_VOCABULARY_AUDIT.md`.

    python scripts/gan_nhan_qipedc.py --thu-muc <dir>
"""
import argparse, collections, csv, json, os, re, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")

# hậu tố mã QIPEDC -> (vung, tên vùng, recognition_profile tương ứng)
VUNG = {
    "B": ("bac",       "Miền Bắc",   "north"),
    "N": ("nam",       "Miền Nam",   "south"),
    "T": ("trung",     "Miền Trung", "central"),
    "":  ("khong_ghi", "(từ điển không ghi vùng)", ""),
}
# trường `type` của QIPEDC -> (loai_von_tu, tên, dialect_id nền tảng)
# `chu_so` CHƯA có dialect_id tương ứng trong bộ chuẩn 9 phương ngữ của nền
# tảng — phải thêm mới trước khi nhập, không được nhét tạm vào `bang-chu-cai`.
LOAI = {
    0: ("tu_thuong",    "Từ vựng thường", ""),
    1: ("chu_so",       "Chữ số",         "<CHƯA CÓ>"),
    2: ("bang_chu_cai", "Bảng chữ cái",   "bang-chu-cai"),
}


def doc_tu_vung_chuan():
    p = "dataset/vocabulary_registry.json"
    if not os.path.exists(p):
        return set(), set()
    d = json.load(open(p, encoding="utf-8"))
    return ({x["dialect_id"] for x in d.get("dialects", [])},
            {x["profile_id"] for x in d.get("profiles", [])})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", required=True)
    ap.add_argument("--ra", default=None)
    a = ap.parse_args()

    p_dm = os.path.join(a.thu_muc, "qipedc_danhmuc.json")
    if not os.path.exists(p_dm):
        print("Thiếu %s" % p_dm)
        return 1
    dm = {x["_id"]: x for x in json.load(open(p_dm, encoding="utf-8"))
          if x.get("_id")}
    tep = sorted(f for f in os.listdir(a.thu_muc) if f.endswith(".mp4"))
    if not tep:
        print("Không có tệp .mp4 nào trong %s" % a.thu_muc)
        return 1

    hop_le_d, hop_le_p = doc_tu_vung_chuan()
    hang = []
    for f in tep:
        ma = f[:-4]
        x = dm.get(ma, {})
        m = re.match(r"^([A-Za-z]+)(\d+)([BNT]?)$", ma)
        hau = m.group(3) if m else ""
        vung, vung_ten, profile = VUNG.get(hau, VUNG[""])
        loai, loai_ten, dialect_id = LOAI.get(x.get("type", 0), LOAI[0])
        # Hồ sơ nhận dạng của nền tảng chỉ có MỘT ô, nên bảng chữ cái buộc
        # phải chọn `alphabet` và mất vùng. Cột `vung` giữ nguyên thông tin đó
        # để lúc nhập không mất — xem ghi chú đầu tệp.
        p_goi_y = "alphabet" if loai == "bang_chu_cai" else profile
        hang.append({
            "tep": f,
            "ma_qipedc": ma,
            "ma_goc": (m.group(1) + m.group(2)) if m else ma,
            "nguon": "qipedc",
            "ngon_ngu": "vn",
            "ngon_ngu_ten": "Ngôn ngữ ký hiệu Việt Nam",
            # --- trục 1: vùng miền địa lý ---
            "vung": vung,
            "vung_ten": vung_ten,
            # --- trục 2: phương ngữ = tập vốn từ con ---
            "loai_von_tu": loai,
            "loai_von_tu_ten": loai_ten,
            "nhan": (x.get("word") or "").strip(),
            "nhan_khong_dau": (x.get("_word") or "").strip(),
            "tu_loai": (x.get("tl") or "").strip(),
            "dinh_nghia": (x.get("description") or "").replace("\n", " ").strip(),
            # gợi ý ánh xạ sang từ vựng chuẩn của nền tảng — CHƯA nhập
            "dialect_id_goi_y": dialect_id,
            "recognition_profile_goi_y": p_goi_y,
            "co_trong_danh_muc": int(ma in dm),
            "byte": os.path.getsize(os.path.join(a.thu_muc, f)),
        })

    ra = a.ra or os.path.join(a.thu_muc, "qipedc_nhan.csv")
    with open(ra, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(hang[0].keys()))
        w.writeheader()
        w.writerows(hang)

    # ---- kiểm & thống kê ----------------------------------------------
    thieu_nhan = [h for h in hang if not h["nhan"]]
    la_p = {h["recognition_profile_goi_y"] for h in hang} - hop_le_p - {""}
    la_d = {h["dialect_id_goi_y"] for h in hang} - hop_le_d - {""}

    print("Đã ghi %s — %d dòng\n" % (ra, len(hang)))
    print("Ngôn ngữ            vn — Ngôn ngữ ký hiệu Việt Nam (toàn bộ %d tệp)"
          % len(hang))
    print("\nTheo vùng:")
    for k, v in collections.Counter(
            (h["vung"], h["vung_ten"]) for h in hang).most_common():
        print("  %-10s %-26s %5d  (%.1f%%)"
              % (k[0], k[1], v, 100 * v / len(hang)))
    print("\nTheo phương ngữ / tập vốn từ (trục 2):")
    for k, v in collections.Counter(
            (h["loai_von_tu"], h["loai_von_tu_ten"], h["dialect_id_goi_y"] or "(trống)")
            for h in hang).most_common():
        print("  %-14s %-18s %5d   -> dialect_id %s" % (k[0], k[1], v, k[2]))

    print("\nHồ sơ nhận dạng gợi ý (nền tảng chỉ có MỘT ô — bảng chữ cái mất vùng):")
    for k, v in collections.Counter(
            (h["recognition_profile_goi_y"] or "(trống)", h["vung"])
            for h in hang).most_common():
        print("  profile=%-10s vung=%-10s %5d" % (k[0], k[1], v))

    print("\nKIỂM:")
    print("  thiếu nhãn (không có trong danh mục) : %d %s"
          % (len(thieu_nhan), [h["ma_qipedc"] for h in thieu_nhan][:5]))
    print("  dialect_id chưa có trong bộ chuẩn    : %s" % (sorted(la_d) or "không"))
    print("  profile lạ so với chuẩn nền tảng     : %s" % (sorted(la_p) or "không"))
    co_dn = sum(1 for h in hang if h["dinh_nghia"])
    print("  có định nghĩa                        : %d / %d (%.1f%%)"
          % (co_dn, len(hang), 100 * co_dn / len(hang)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Đối chiếu danh mục từ vựng của nền tảng với chuẩn quốc gia QIPEDC.

Trả lời hai câu cho Chương 4:
  1. Bao nhiêu lớp ký hiệu của nền tảng có trong từ điển quốc gia?
  2. Nền tảng phủ được bao nhiêu phần vốn từ có biến thể vùng miền?

Ghép theo văn bản đã chuẩn hoá (bỏ dấu, hạ chữ thường, bỏ phần chú trong
ngoặc), không ghép theo mã — hai hệ mã hoàn toàn độc lập.

    python scripts/doi_chieu_danhmuc_qipedc.py --danh-muc <qipedc_danhmuc.json>
"""
import argparse, collections, csv, json, os, re, sys, unicodedata

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")
VUNG = {"B": "bac", "N": "nam", "T": "trung"}


def chuan(s):
    """Bỏ dấu, hạ chữ thường, bỏ phần trong ngoặc, gộp khoảng trắng."""
    s = (s or "").lower()
    s = re.sub(r"\([^)]*\)", " ", s)          # bỏ chú thích trong ngoặc
    s = s.replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--danh-muc", required=True)
    ap.add_argument("--nhan", default="dataset/labels.csv")
    a = ap.parse_args()

    qi = json.load(open(a.danh_muc, encoding="utf-8"))
    # gom theo từ gốc: từ -> {vùng có sẵn}
    tu_vung = collections.defaultdict(set)
    tu_goc = {}
    for x in qi:
        m = re.match(r"^([A-Za-z]+\d+)([BNT]?)$", x.get("_id", ""))
        if not m:
            continue
        k = chuan(x.get("word"))
        if not k:
            continue
        tu_vung[k].add(VUNG.get(m.group(2), "khong_ghi"))
        tu_goc.setdefault(k, x)

    nt = list(csv.DictReader(open(a.nhan, encoding="utf-8")))
    print("=" * 72)
    print("ĐỐI CHIẾU DANH MỤC — nền tảng ↔ QIPEDC")
    print("=" * 72)
    print("QIPEDC   : %d mục video, %d từ riêng biệt" % (len(qi), len(tu_vung)))
    print("Nền tảng : %d lớp ký hiệu (%s)" % (len(nt), a.nhan))

    du_ba = {k for k, v in tu_vung.items() if {"bac", "nam", "trung"} <= v}
    print("\nQIPEDC có đủ cả ba vùng cho %d / %d từ  (%.1f%%)"
          % (len(du_ba), len(tu_vung), 100 * len(du_ba) / len(tu_vung)))

    khop, lech = [], []
    for r in nt:
        k = chuan(r.get("label_original") or r.get("slug"))
        if k in tu_vung:
            khop.append((r, k))
        else:
            lech.append((r, k))
    print("\nLớp của nền tảng CÓ trong từ điển quốc gia : %d / %d  (%.1f%%)"
          % (len(khop), len(nt), 100 * len(khop) / len(nt)))
    print("Lớp KHÔNG khớp                             : %d" % len(lech))

    # phân loại chỗ không khớp
    nhom = collections.Counter(r.get("dialect", "?") for r, _ in lech)
    print("  không khớp, theo trường `dialect` của nền tảng:")
    for k, v in nhom.most_common():
        print("     %-14s %3d" % (k, v))

    print("\nCác lớp KHỚP (nền tảng ← QIPEDC), kèm vùng mà QIPEDC có:")
    for r, k in sorted(khop, key=lambda z: z[1]):
        v = sorted(tu_vung[k] - {"khong_ghi"})
        print("  %-22s %-14s QIPEDC: %s"
              % ((r.get("label_original") or "")[:22], r.get("dialect", ""),
                 ", ".join(v) if v else "chỉ bản không ghi vùng"))

    # phủ vùng miền
    phu = [k for _, k in khop if k in du_ba]
    print("\nTrong %d lớp khớp, số lớp mà QIPEDC có đủ ba vùng: %d" % (len(khop), len(phu)))
    nt_vung = collections.Counter(
        r.get("dialect") for r in nt if r.get("dialect") in ("bac", "nam", "trung"))
    print("Nền tảng tự gán nhãn vùng cho: %d lớp %s"
          % (sum(nt_vung.values()), dict(nt_vung) or ""))

    print("\n" + "-" * 72)
    print("ĐỌC KẾT QUẢ")
    print("-" * 72)
    print("Con số thấp KHÔNG phải khiếm khuyết của nền tảng: danh mục hiện tại")
    print("là danh mục của một bản mẫu, thu theo chiến dịch hẹp (bảng chữ cái,")
    print("hoa-đề, Cần Thơ). Ý nghĩa của phép đối chiếu là ĐỊNH LƯỢNG khoảng")
    print("cách giữa 'vốn từ đã có chuẩn quốc gia' và 'vốn từ đã có dữ liệu")
    print("thu' — tức đúng khoảng trống mà đề tài nêu ở mục 1.1: Việt Nam đã")
    print("có chuẩn từ vựng, cái thiếu là hạ tầng để nhiều đơn vị cùng sinh ra")
    print("dữ liệu theo chuẩn đó.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

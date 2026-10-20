# -*- coding: utf-8 -*-
"""Đo hiệu quả lưu trữ của biểu diễn theo điểm mốc (mục tiêu MT6).

Không dùng numpy — đọc thẳng tiêu đề .npy bên trong .npz bằng zipfile, vì
numpy trong `.venv_py313_backup` segfault trên máy này.

Đo ba thứ, tách bạch cái ĐO ĐƯỢC với cái SUY RA:

  A. Kích thước thật của kho điểm mốc — đo trực tiếp trên đĩa.
  B. Chi phí trên mỗi khung và mỗi giây thu — đo, sau khi lấy số khung từ
     tiêu đề mảng.
  C. So sánh với video — KHÔNG đo được nếu không có tệp video. Script in ra
     bảng tỉ lệ theo từng mức bitrate để người viết chọn, và tự đo bitrate
     thật nếu tìm thấy video.

    python scripts/do_hieu_qua_luu_tru.py
    python scripts/do_hieu_qua_luu_tru.py --json ket_qua.json
"""
import io, json, os, re, statistics, sys, zipfile

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")

FPS_THU = 30          # nhịp thu của trình duyệt, xem backend/app/config.py
THU_MUC = {
    "features": "dataset/features",   # chuỗi ĐÃ chuẩn hoá — đầu vào mô hình
    "raw": "dataset/raw",             # chuỗi TRƯỚC chuẩn hoá — kho bản ghi nguồn
}


def doc_shape(npz_path):
    """Trả {ten_mang: (shape, dtype, so_byte_giai_nen)} — không cần numpy."""
    ra = {}
    try:
        with zipfile.ZipFile(npz_path) as z:
            for it in z.infolist():
                if not it.filename.endswith(".npy"):
                    continue
                with z.open(it) as f:
                    magic = f.read(6)
                    if magic != b"\x93NUMPY":
                        continue
                    major = f.read(1)[0]
                    f.read(1)
                    hlen = int.from_bytes(f.read(2 if major == 1 else 4), "little")
                    head = f.read(hlen).decode("latin1")
                m_s = re.search(r"'shape':\s*\(([^)]*)\)", head)
                m_d = re.search(r"'descr':\s*'([^']+)'", head)
                if not m_s:
                    continue
                shape = tuple(int(x) for x in re.findall(r"\d+", m_s.group(1)))
                ra[it.filename[:-4]] = (shape, m_d.group(1) if m_d else "?",
                                        it.file_size)
    except Exception:
        return None
    return ra


def quet(goc):
    ds = []
    for root, _, files in os.walk(goc):
        for fn in files:
            if fn.endswith(".npz"):
                ds.append(os.path.join(root, fn))
    return ds


def so_khung(info):
    """Số khung = chiều đầu của mảng chuỗi dài nhất."""
    tot = None
    for ten, (shape, _, _) in info.items():
        if len(shape) >= 2:
            if tot is None or shape[0] > tot:
                tot = shape[0]
    return tot


ket_qua = {}


def phan_tich_bo_cuc(tep):
    """Gom tệp theo TẬP MẢNG nó chứa. Hai tệp cùng số khung có thể chênh nhau
    hơn hai lần dung lượng chỉ vì một bên lưu chuỗi ba lần."""
    nhom = {}
    for p in tep:
        info = doc_shape(p)
        if not info:
            continue
        khoa = tuple(sorted(info))
        k = so_khung(info)
        if not k:
            continue
        nhom.setdefault(khoa, []).append((os.path.getsize(p), k))
    return nhom


print("=" * 78)
print("A. KHO ĐIỂM MỐC — ĐO TRỰC TIẾP TRÊN ĐĨA")
print("=" * 78)

for ten, goc in THU_MUC.items():
    tep = quet(goc)
    if not tep:
        print("\n%-10s KHÔNG CÓ TỆP (%s)" % (ten, goc))
        continue
    cs = [os.path.getsize(p) for p in tep]
    tong = sum(cs)
    khung, giai_nen = [], []
    for p in tep:
        info = doc_shape(p)
        if not info:
            continue
        k = so_khung(info)
        if k:
            khung.append(k)
            giai_nen.append(sum(v[2] for v in info.values()))
    d = {
        "so_tep": len(tep),
        "tong_byte": tong,
        "trung_vi_byte": int(statistics.median(cs)),
        "trung_binh_byte": int(statistics.fmean(cs)),
        "nho_nhat_byte": min(cs),
        "lon_nhat_byte": max(cs),
    }
    if khung:
        d["so_tep_doc_duoc_shape"] = len(khung)
        d["trung_vi_khung"] = int(statistics.median(khung))
        d["tong_khung"] = sum(khung)
        d["byte_moi_khung"] = round(tong / sum(khung), 1)
        d["byte_moi_giay"] = round(tong / sum(khung) * FPS_THU, 1)
        d["ty_le_nen"] = round(sum(giai_nen) / tong, 2) if giai_nen else None
    ket_qua[ten] = d

    print("\n%s  (%s)" % (ten.upper(), goc))
    print("  số tệp                    %s" % f"{d['so_tep']:,}")
    print("  tổng dung lượng           %.1f MB" % (tong / 1024 / 1024))
    print("  trung vị / tệp            %.1f KB" % (d["trung_vi_byte"] / 1024))
    print("  nhỏ nhất – lớn nhất       %.1f – %.1f KB"
          % (d["nho_nhat_byte"] / 1024, d["lon_nhat_byte"] / 1024))
    if khung:
        print("  trung vị số khung / mẫu   %d  (~%.2f giây ở %d fps)"
              % (d["trung_vi_khung"], d["trung_vi_khung"] / FPS_THU, FPS_THU))
        print("  chi phí mỗi khung         %.1f byte" % d["byte_moi_khung"])
        print("  chi phí mỗi giây thu      %.2f KB/s" % (d["byte_moi_giay"] / 1024))
        if d["ty_le_nen"]:
            print("  tỉ lệ nén của .npz        %.2f×  (mảng thô / tệp trên đĩa)"
                  % d["ty_le_nen"])

    nhom = phan_tich_bo_cuc(tep)
    if len(nhom) > 1:
        print("\n  Tách theo bố cục tệp — %d bố cục cùng tồn tại:" % len(nhom))
        d["bo_cuc"] = []
        for khoa, ds in sorted(nhom.items(), key=lambda x: -len(x[1])):
            byte = sum(a for a, _ in ds)
            kh = sum(b for _, b in ds)
            mang_chuoi = [t for t in khoa if t != "meta" and "mask" not in t]
            print("    %4d tệp (%.1f%%)  %6.1f B/khung  |  %s"
                  % (len(ds), 100 * len(ds) / len(tep), byte / kh,
                     ", ".join(khoa)))
            d["bo_cuc"].append({
                "mang": list(khoa), "so_tep": len(ds), "tong_byte": byte,
                "byte_moi_khung": round(byte / kh, 1),
                "so_ban_sao_chuoi": len(mang_chuoi),
            })

# --------------------------------------------------------------------------
print("\n" + "=" * 78)
print("B. ĐỐI CHIẾU VỚI VIDEO")
print("=" * 78)

VIDEO_EXT = (".mp4", ".webm", ".mov", ".avi", ".mkv")
videos = []
for goc in ("dataset/raw_videos", "dataset"):
    for root, _, files in os.walk(goc):
        for fn in files:
            if fn.lower().endswith(VIDEO_EXT):
                videos.append(os.path.join(root, fn))
    if videos:
        break

if videos:
    cs = [os.path.getsize(p) for p in videos]
    print("\nTìm thấy %d tệp video, tổng %.1f MB, trung vị %.1f KB."
          % (len(videos), sum(cs) / 1024 / 1024, statistics.median(cs) / 1024))
    print("Đo bitrate thật cần thời lượng — chạy:")
    print("  ffprobe -v error -show_entries format=duration,bit_rate -of json <tệp>")
    ket_qua["video"] = {"so_tep": len(videos), "tong_byte": sum(cs)}
else:
    print("\nKHÔNG CÓ TỆP VIDEO trên máy này (`dataset/raw_videos/uploads.csv` rỗng).")
    print("Vì vậy tỉ lệ dưới đây là SUY RA từ bitrate giả định, KHÔNG phải số đo.")
    print("Muốn có số đo thật: thu 5 mẫu qua giao diện với `KEEP_RAW_VIDEO=1`,")
    print("rồi chạy lại script này.")

f = ket_qua.get("features")
if f and f.get("byte_moi_giay"):
    kb_s = f["byte_moi_giay"] / 1024
    print("\nĐiểm mốc (đã chuẩn hoá): **%.2f KB mỗi giây thu** — số đo." % kb_s)
    print("\n| Bitrate video | KB/giây | Tỉ lệ so với điểm mốc | Tiết kiệm |")
    print("|---|---|---|---|")
    for mbps, nhan in [(0.5, "webcam 480p tiết kiệm"),
                       (1.0, "480p thường"),
                       (2.5, "720p thường"),
                       (5.0, "1080p thường")]:
        v_kb = mbps * 1000 / 8
        print("| %.1f Mbps (%s) | %.0f | %.0f× | %.2f%% |"
              % (mbps, nhan, v_kb, v_kb / kb_s, (1 - kb_s / v_kb) * 100))
    print("\nĐọc bảng: mỗi dòng là MỘT giả định bitrate, không phải kết quả đo.")
    print("Chọn một dòng thì phải nói rõ trong luận văn đó là cấu hình nào.")

if "--json" in sys.argv:
    out = sys.argv[sys.argv.index("--json") + 1]
    io.open(out, "w", encoding="utf-8").write(
        json.dumps(ket_qua, ensure_ascii=False, indent=2))
    print("\nĐã ghi %s" % out)

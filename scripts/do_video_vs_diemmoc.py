# -*- coding: utf-8 -*-
"""Đo GHÉP CẶP: cùng một đoạn ký hiệu, video chiếm bao nhiêu và chuỗi điểm mốc
trích từ chính nó chiếm bao nhiêu.

VÌ SAO CẦN
----------
`scripts/do_hieu_qua_luu_tru.py` đo được phía điểm mốc, nhưng máy phát triển
không có tệp video nào nên phần so sánh phải giả định bitrate — và khoảng
7×–72× là quá rộng để viết vào luận văn. Script này lấy một mẫu nhỏ video
công khai của từ điển QIPEDC \\cite{bogddt_qipedc_2019}, chạy đúng cấu hình
MediaPipe mà nền tảng dùng khi thu, rồi so từng cặp.

GIỚI HẠN PHẢI NÊU TRONG LUẬN VĂN
--------------------------------
Video QIPEDC là bản quay studio đã qua hậu kỳ và nén để phát trên web, KHÔNG
phải luồng webcam mà CTU-SignBridge thu. Vì vậy tỉ lệ đo được đặc trưng cho
"video như QIPEDC phân phối", không phải "video như nền tảng thu". Đây vẫn là
một mốc so sánh CÓ TÊN và TÁI LẬP ĐƯỢC — hơn hẳn một bitrate giả định — nhưng
đừng phát biểu nó như thể đã đo trên dữ liệu của chính hệ thống.

Cấu hình khớp với nền tảng (frontend/src/config/handTracking.ts hồ sơ `capture`
và backend/app/config.py SEQ_LEN):
    maxNumHands 2 · modelComplexity 1 · minDetection 0.70 · minTracking 0.75
    chuỗi lưu trữ lấy mẫu lại về 60 khung · np.savez_compressed

CÁCH DÙNG
---------
    .venv/Scripts/python.exe scripts/do_video_vs_diemmoc.py --tai 40
    .venv/Scripts/python.exe scripts/do_video_vs_diemmoc.py --thu-muc <dir>

Tải về thư mục tạm, KHÔNG ghi vào `dataset/`. Xoá thư mục đó là sạch.
"""
import argparse, io, json, os, statistics, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

REPO = r"e:\CTU_ProjectOutside\VOYA-Collector"
os.chdir(REPO)

GOC = "https://qipedc.moet.gov.vn/videos/%s.mp4"
SEQ_LEN = 60          # backend/app/config.py
MAX_HANDS = 2
COMPLEXITY = 1        # hồ sơ `capture`
MIN_DET, MIN_TRACK = 0.70, 0.75


# Dò ngày 14/08/2026: mã tiền tố D chạy tới khoảng D0600, không tới D4000.
# Con số ~4.000 video của từ điển là do mỗi mục có thể có ba biến thể phương
# ngữ (B/N/T) và còn các tiền tố khác ngoài D.
MA_CAO_NHAT = 620


def chon_ma(so_luong):
    """Rải đều mã trên toàn dải thay vì lấy N mã đầu — N mã liền nhau nhiều
    khả năng cùng một buổi quay, cùng người ký, cùng thiết lập."""
    buoc = max(1, MA_CAO_NHAT // max(1, so_luong))
    ra, n = [], 1
    while n <= MA_CAO_NHAT:
        ra.append("D%04d" % n)
        n += buoc
    # thêm mã kề bên để bù những mã trống, vẫn giữ thứ tự rải đều
    bu = []
    for ma in ra:
        k = int(ma[1:])
        bu += ["D%04d" % (k + d) for d in (1, 2, 3) if k + d <= MA_CAO_NHAT]
    return ra + bu


MAY_CHU = "qipedc.moet.gov.vn"


def van_tay_chung_chi():
    """SHA-256 của chứng chỉ máy chủ, dùng để GHIM danh tính.

    Chứng chỉ Let's Encrypt của QIPEDC hết hạn 16/07/2026 nên `requests` từ
    chối kết nối. Tắt xác minh hoàn toàn thì mất luôn khả năng biết mình đang
    nói chuyện với ai. Thay vào đó: lấy chứng chỉ một lần, ghim vân tay, và
    kiểm lại ở mọi kết nối sau — bỏ qua đúng phần *hạn dùng*, giữ nguyên phần
    *danh tính*. Nội dung tải về là video công khai, không gửi đi thông tin
    xác thực nào.
    """
    import hashlib, ssl
    pem = ssl.get_server_certificate((MAY_CHU, 443), timeout=20)
    der = ssl.PEM_cert_to_DER_cert(pem)
    return hashlib.sha256(der).hexdigest()


def _ket_noi(van_tay):
    import hashlib, http.client, ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    c = http.client.HTTPSConnection(MAY_CHU, 443, timeout=30, context=ctx)
    c.connect()
    that = hashlib.sha256(c.sock.getpeercert(binary_form=True)).hexdigest()
    if that != van_tay:
        c.close()
        raise SystemExit("DỪNG: vân tay chứng chỉ đổi giữa chừng (%s…). "
                         "Không tải tiếp." % that[:16])
    return c


def tai(ma, thu_muc, van_tay):
    """Thử mã trần rồi tới ba biến thể phương ngữ. Trả đường dẫn hoặc None."""
    for hau in ("", "B", "N", "T"):
        c = None
        try:
            c = _ket_noi(van_tay)
            c.request("GET", "/videos/%s.mp4" % (ma + hau),
                      headers={"User-Agent": "CTU-SignBridge thesis measurement",
                               "Accept": "video/mp4"})
            r = c.getresponse()
            data = r.read()
            if r.status == 200 and data[4:8] == b"ftyp":
                p = os.path.join(thu_muc, ma + hau + ".mp4")
                with open(p, "wb") as f:
                    f.write(data)
                return p
        except SystemExit:
            raise
        except Exception:
            pass
        finally:
            if c:
                c.close()
        time.sleep(0.3)
    return None


def do_video(p, cv2):
    cap = cv2.VideoCapture(p)
    if not cap.isOpened():
        return None
    fps = cap.get(cv2.CAP_PROP_FPS) or 0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    cap.release()
    if not fps or not n:
        return None
    return {"fps": round(fps, 2), "so_khung": n, "rong": w, "cao": h,
            "giay": round(n / fps, 3), "byte": os.path.getsize(p)}


def trich_diem_moc(p, cv2, mp_hands, np):
    """126 giá trị mỗi khung: 21 điểm × 3 toạ độ × 2 bàn tay, trái trước phải."""
    cap = cv2.VideoCapture(p)
    chuoi = []
    with mp_hands.Hands(static_image_mode=False, max_num_hands=MAX_HANDS,
                        model_complexity=COMPLEXITY,
                        min_detection_confidence=MIN_DET,
                        min_tracking_confidence=MIN_TRACK) as hands:
        while True:
            ok, khung = cap.read()
            if not ok:
                break
            kq = hands.process(cv2.cvtColor(khung, cv2.COLOR_BGR2RGB))
            v = np.zeros(126, dtype=np.float32)
            if kq.multi_hand_landmarks:
                for lm, ht in zip(kq.multi_hand_landmarks,
                                  kq.multi_handedness or []):
                    nhan = ht.classification[0].label      # 'Left' / 'Right'
                    lech = 0 if nhan == "Left" else 63
                    for i, d in enumerate(lm.landmark[:21]):
                        v[lech + i * 3:lech + i * 3 + 3] = (d.x, d.y, d.z)
            chuoi.append(v)
    cap.release()
    if not chuoi:
        return None, 0.0
    seq = np.stack(chuoi)
    # Tỉ lệ khung bắt được ít nhất một bàn tay. Khung không bắt được là vector
    # toàn số 0, nén cực tốt — nên một tệp .npz nhỏ bất thường KHÔNG có nghĩa
    # biểu diễn hiệu quả, mà thường nghĩa là hỏng phát hiện.
    phat_hien = float((np.abs(seq).sum(axis=1) > 0).mean())
    return seq, phat_hien


def lay_mau_lai(seq, n, np):
    """Lấy mẫu lại về n khung — nền tảng lưu cố định SEQ_LEN khung."""
    if len(seq) == n:
        return seq
    idx = np.linspace(0, len(seq) - 1, n)
    return seq[np.round(idx).astype(int)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tai", type=int, default=40, help="số video muốn tải")
    ap.add_argument("--thu-muc", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    import cv2, numpy as np
    import mediapipe as mp
    mp_hands = mp.solutions.hands

    thu_muc = a.thu_muc or os.path.join(
        os.environ.get("TEMP", "."), "qipedc_mau")
    os.makedirs(thu_muc, exist_ok=True)
    print("Thư mục làm việc: %s" % thu_muc)

    # ---- tải ----------------------------------------------------------
    co_san = [os.path.join(thu_muc, f) for f in os.listdir(thu_muc)
              if f.endswith(".mp4")]
    if len(co_san) < a.tai:
        van_tay = van_tay_chung_chi()
        print("\nGhim vân tay chứng chỉ %s: %s…" % (MAY_CHU, van_tay[:24]))
        print("(chứng chỉ máy chủ đã hết hạn — bỏ qua hạn dùng, giữ kiểm danh tính)")
        print("Tải %d video (1 yêu cầu mỗi ~0,5 giây)…" % a.tai)
        for ma in chon_ma(a.tai):
            if len(co_san) >= a.tai:
                break
            if any(os.path.basename(x).startswith(ma) for x in co_san):
                continue
            p = tai(ma, thu_muc, van_tay)
            if p:
                co_san.append(p)
                print("  %-8s %7.1f KB" % (ma, os.path.getsize(p) / 1024))
            time.sleep(0.5)
    print("\nCó %d video." % len(co_san))
    if not co_san:
        print("Không tải được video nào — kiểm tra mạng.")
        return 1

    # ---- đo -----------------------------------------------------------
    print("\nChạy MediaPipe (complexity=%d, %d bàn tay)…" % (COMPLEXITY, MAX_HANDS))
    cap_dat = []
    for i, p in enumerate(sorted(co_san), 1):
        v = do_video(p, cv2)
        if not v:
            continue
        seq, phat_hien = trich_diem_moc(p, cv2, mp_hands, np)
        if seq is None:
            continue
        # (1) chuỗi lưu trữ như nền tảng: lấy mẫu lại về SEQ_LEN khung
        p60 = os.path.join(thu_muc, os.path.basename(p)[:-4] + ".seq60.npz")
        np.savez_compressed(p60, sequence=lay_mau_lai(seq, SEQ_LEN, np),
                            meta={"nguon": os.path.basename(p)})
        # (2) chuỗi đầy đủ — để tính chi phí trên mỗi giây
        pfull = os.path.join(thu_muc, os.path.basename(p)[:-4] + ".full.npz")
        np.savez_compressed(pfull, sequence=seq, meta={})
        v.update({
            "ma": os.path.basename(p)[:-4],
            "khung_trich": int(len(seq)),
            "byte_seq60": os.path.getsize(p60),
            "byte_full": os.path.getsize(pfull),
            "ty_le_phat_hien": round(phat_hien, 3),
        })
        v["ty_le_seq60"] = v["byte"] / v["byte_seq60"]
        v["ty_le_full"] = v["byte"] / v["byte_full"]
        cap_dat.append(v)
        print("  [%2d/%2d] %-8s %5.2fs  video %6.1f KB | 60 khung %5.1f KB"
              " | đủ %5.1f KB  → %5.1f×  | bắt được tay %5.1f%%"
              % (i, len(co_san), v["ma"], v["giay"],
                 v["byte"] / 1024, v["byte_seq60"] / 1024,
                 v["byte_full"] / 1024, v["ty_le_seq60"], phat_hien * 100))

    if not cap_dat:
        print("Không đo được cặp nào.")
        return 1

    # ---- tổng hợp -----------------------------------------------------
    def tv(k):
        return statistics.median(x[k] for x in cap_dat)

    print("\n" + "=" * 74)
    print("KẾT QUẢ — %d cặp video ↔ điểm mốc" % len(cap_dat))
    print("=" * 74)
    do_phan_giai = {}
    for x in cap_dat:
        do_phan_giai["%dx%d" % (x["rong"], x["cao"])] = \
            do_phan_giai.get("%dx%d" % (x["rong"], x["cao"]), 0) + 1
    print("\nMẫu video: trung vị %.2f giây, %.1f fps, độ phân giải %s"
          % (tv("giay"), tv("fps"),
             ", ".join("%s (%d)" % kv for kv in
                       sorted(do_phan_giai.items(), key=lambda z: -z[1]))))
    v_kbs = tv("byte") / 1024 / tv("giay")
    f_kbs = tv("byte_full") / 1024 / tv("giay")
    print("\n| Đại lượng | Video | Điểm mốc (đủ khung) | Điểm mốc (60 khung) |")
    print("|---|---|---|---|")
    print("| Trung vị mỗi mẫu | %.1f KB | %.1f KB | %.1f KB |"
          % (tv("byte") / 1024, tv("byte_full") / 1024, tv("byte_seq60") / 1024))
    print("| Trên mỗi giây thu | %.1f KB/s | %.2f KB/s | — (cố định) |"
          % (v_kbs, f_kbs))
    print("| Bitrate tương đương | %.2f Mbps | %.3f Mbps | — |"
          % (v_kbs * 8 / 1000, f_kbs * 8 / 1000))

    def bao(ds, nhan):
        if not ds:
            print("  %-32s (không có mẫu nào)" % nhan)
            return
        a = sorted(x["ty_le_seq60"] for x in ds)
        b = sorted(x["ty_le_full"] for x in ds)
        print("  %-32s n=%2d | 60 khung %5.1f× (%.1f–%.1f) | đủ khung %4.1f× (%.1f–%.1f)"
              % (nhan, len(ds), statistics.median(a), a[0], a[-1],
                 statistics.median(b), b[0], b[-1]))

    print("\n**Tỉ lệ video / điểm mốc (ghép cặp, cùng đoạn ký hiệu):**")
    bao(cap_dat, "toàn mẫu")
    tot = [x for x in cap_dat if x["ty_le_phat_hien"] >= 0.90]
    kem = [x for x in cap_dat if x["ty_le_phat_hien"] < 0.90]
    bao(tot, "chỉ mẫu bắt được tay ≥90%")
    bao(kem, "mẫu bắt được tay <90%")
    if tot:
        m = statistics.median(x["ty_le_seq60"] for x in tot)
        print("\n  → CON SỐ DÙNG ĐƯỢC: **%.0f×**, tiết kiệm **%.1f%%**"
              % (m, (1 - 1 / m) * 100))
    print("\n  Vì sao phải lọc: khung không bắt được tay là vector toàn số 0 và")
    print("  nén gần như miễn phí. Một tệp .npz nhỏ bất thường phản ánh HỎNG")
    print("  PHÁT HIỆN chứ không phải biểu diễn hiệu quả — gộp chung sẽ thổi")
    print("  phồng tỉ lệ tiết kiệm.")
    ph = sorted(x["ty_le_phat_hien"] for x in cap_dat)
    print("\nTỉ lệ khung bắt được tay: trung vị %.1f%%, khoảng %.1f–%.1f%%"
          % (statistics.median(ph) * 100, ph[0] * 100, ph[-1] * 100))

    print("\nGIỚI HẠN: video QIPEDC là bản quay studio đã nén để phát web, không")
    print("phải luồng webcam của nền tảng. Xem phần đầu tệp script này.")

    if a.json:
        io.open(a.json, "w", encoding="utf-8").write(
            json.dumps(cap_dat, ensure_ascii=False, indent=2))
        print("\nĐã ghi %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# -*- coding: utf-8 -*-
"""Thử các cấu hình trích xuất điểm mốc, đo tỉ lệ khung bắt được bàn tay.

VẤN ĐỀ
------
Chạy MediaPipe với hồ sơ `capture` của nền tảng lên video từ điển QIPEDC chỉ
bắt được tay ở trung vị 81% số khung. Nguyên nhân không phải ngưỡng mà là
**kích thước bàn tay trong khung**: video 1280×720 nhưng người ký chiếm chưa
tới một phần ba chiều ngang, nền còn lại trống. MediaPipe hạ mẫu về 192×192
để dò lòng bàn tay, nên một bàn tay ~100 px thật sự chỉ còn ~15 px.

Đối chiếu: chính nền tảng, thu bằng webcam ở cự ly gần, đạt **100%** khung có
ít nhất một bàn tay trên cả 1.997 mẫu có mặt nạ hợp lệ. Vậy đây là vấn đề của
việc trích xuất từ video bên ngoài, không phải của đường thu.

CÁCH CẮT KHUNG
--------------
Không dùng ngưỡng màu nền: logo QIPEDC và chữ chú thích cũng khác màu nền và
sẽ lọt vào khung cắt. Dùng **phương sai theo thời gian** — logo và chữ đứng
yên, chỉ người ký chuyển động.

    .venv/Scripts/python.exe scripts/thu_cau_hinh_nhandang.py --so-video 12
"""
import argparse, json, os, statistics, sys, time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")

# (tên, cắt khung, ngưỡng phát hiện, ngưỡng bám, độ phức tạp, dò lại mọi khung)
CAU_HINH = [
    ("A gốc (hồ sơ capture)",      False, 0.70, 0.75, 1, False),
    ("B toàn khung, ngưỡng 0,50",  False, 0.50, 0.50, 1, False),
    ("C cắt khung, ngưỡng 0,70",   True,  0.70, 0.75, 1, False),
    ("D cắt khung, ngưỡng 0,50",   True,  0.50, 0.50, 1, False),
    ("E cắt + dò lại mọi khung",   True,  0.50, 0.50, 1, True),
]


def vung_chuyen_dong(p, cv2, np, so_mau=24, le=0.12):
    """Khung bao của vùng có phương sai theo thời gian — tức người ký."""
    cap = cv2.VideoCapture(p)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    if n < 4:
        cap.release()
        return None
    idx = np.linspace(0, n - 1, min(so_mau, n)).astype(int)
    khung = []
    for i in idx:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, f = cap.read()
        if ok:
            khung.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32))
    cap.release()
    if len(khung) < 4:
        return None
    sd = np.stack(khung).std(axis=0)
    # ngưỡng thích nghi: giữ phần động nhất
    nguong = max(4.0, float(np.percentile(sd, 97)) * 0.25)
    mat_na = (sd > nguong).astype("uint8")
    mat_na = cv2.morphologyEx(mat_na, cv2.MORPH_CLOSE, np.ones((9, 9), "uint8"))
    ys, xs = np.nonzero(mat_na)
    if len(xs) < 200:
        return None
    H, W = sd.shape
    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()
    # nới ra: bàn tay có thể vươn ra ngoài vùng động chính
    dx, dy = int((x1 - x0) * le), int((y1 - y0) * le)
    x0 = max(0, x0 - dx); x1 = min(W - 1, x1 + dx)
    y0 = max(0, y0 - dy); y1 = min(H - 1, y1 + dy)
    if (x1 - x0) < 64 or (y1 - y0) < 64:
        return None
    return int(x0), int(y0), int(x1), int(y1)


def ty_le_bat_duoc(p, cv2, np, mp_hands, cat, det, track, cx, tinh):
    hop = vung_chuyen_dong(p, cv2, np) if cat else None
    cap = cv2.VideoCapture(p)
    tot = tong = 0
    with mp_hands.Hands(static_image_mode=tinh, max_num_hands=2,
                        model_complexity=cx,
                        min_detection_confidence=det,
                        min_tracking_confidence=track) as hands:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            if hop:
                x0, y0, x1, y1 = hop
                f = f[y0:y1, x0:x1]
            kq = hands.process(cv2.cvtColor(f, cv2.COLOR_BGR2RGB))
            tong += 1
            if kq.multi_hand_landmarks:
                tot += 1
    cap.release()
    return (tot / tong if tong else 0.0), hop


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", required=True)
    ap.add_argument("--so-video", type=int, default=12)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    import cv2, numpy as np
    import mediapipe as mp
    mp_hands = mp.solutions.hands

    kq_cu = os.path.join(os.path.dirname(a.thu_muc), "vid.json")
    ds = []
    if os.path.exists(kq_cu):
        d = json.load(open(kq_cu, encoding="utf-8"))
        d.sort(key=lambda x: x["ty_le_phat_hien"])
        # lấy phần lớn là mẫu KÉM, kèm vài mẫu tốt để bảo đảm không làm hỏng
        # thứ vốn đã chạy được
        ds = [x["ma"] for x in d[:a.so_video - 3]] + [x["ma"] for x in d[-3:]]
    if not ds:
        ds = sorted(f[:-4] for f in os.listdir(a.thu_muc)
                    if f.endswith(".mp4"))[:a.so_video]
    tep = [os.path.join(a.thu_muc, m + ".mp4") for m in ds]
    tep = [p for p in tep if os.path.exists(p)]
    print("Thử trên %d video (%d mẫu kém nhất + 3 mẫu tốt nhất)\n"
          % (len(tep), max(0, len(tep) - 3)))

    bang = {}
    for ten, cat, det, track, cx, tinh in CAU_HINH:
        t0 = time.time()
        r = []
        for p in tep:
            v, hop = ty_le_bat_duoc(p, cv2, np, mp_hands, cat, det, track, cx, tinh)
            r.append(v)
        bang[ten] = r
        print("%-30s trung vị %5.1f%%  | thấp nhất %5.1f%%  | ≥90%%: %2d/%d  | %4.0f giây"
              % (ten, statistics.median(r) * 100, min(r) * 100,
                 sum(1 for v in r if v >= 0.9), len(r), time.time() - t0),
              flush=True)

    goc = bang[CAU_HINH[0][0]]
    print("\nSo với cấu hình gốc, theo từng video:")
    print("  %-10s %8s" % ("video", "gốc"),
          "".join("%10s" % t.split()[0] for t, *_ in CAU_HINH[1:]))
    for i, p in enumerate(tep):
        ma = os.path.basename(p)[:-4]
        print("  %-10s %7.1f%%" % (ma, goc[i] * 100),
              "".join("%9.1f%%" % (bang[t][i] * 100) for t, *_ in CAU_HINH[1:]))

    tot_nhat = max(bang, key=lambda k: statistics.median(bang[k]))
    print("\nTỐT NHẤT: %s — trung vị %.1f%% (gốc %.1f%%)"
          % (tot_nhat, statistics.median(bang[tot_nhat]) * 100,
             statistics.median(goc) * 100))

    if a.json:
        json.dump({k: v for k, v in bang.items()},
                  open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("Đã ghi %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

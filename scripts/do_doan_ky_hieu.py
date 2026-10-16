# -*- coding: utf-8 -*-
"""Đo phần video thực sự có ký hiệu, tách khỏi phần đứng nghỉ.

PHÁT HIỆN DẪN TỚI SCRIPT NÀY
----------------------------
Chạy MediaPipe lên video từ điển QIPEDC chỉ "bắt được tay" ở trung vị 81% số
khung, và ban đầu điều đó bị hiểu là hỏng phát hiện. Thử hạ ngưỡng, cắt khung
theo vùng chuyển động, dò lại mọi khung — trung vị chỉ nhích từ 45,2% lên
49,3% trên nhóm mẫu kém. Xem lại khung hình thì rõ nguyên nhân: những khung đó
người ký **đứng nghỉ, hai tay buông xuôi ra ngoài khung**. Không có bàn tay
nào để bắt.

Vậy đại lượng cần đo không phải "tỉ lệ phát hiện" mà là **tỉ lệ khung có ký
hiệu**, và trong đoạn có ký hiệu thì phát hiện đạt bao nhiêu.

Hệ quả cho đề tài: video từ điển KHÔNG dùng thẳng làm dữ liệu huấn luyện được
— phải cắt đoạn trước. Đây là bằng chứng đo được cho khẳng định ở mục 1.1 và
1.2.5 của Chương 1 rằng QIPEDC là nguồn tham chiếu vốn từ, không phải bộ dữ
liệu sẵn dùng.

    .venv/Scripts/python.exe scripts/do_doan_ky_hieu.py --thu-muc <dir>
"""
import argparse, json, os, statistics, sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

os.chdir(r"e:\CTU_ProjectOutside\VOYA-Collector")
KHE_CHO_PHEP = 6      # khung hụt liên tiếp vẫn coi là trong cùng một đoạn ký


def chuoi_phat_hien(p, cv2, mp_hands, det=0.5, track=0.5):
    cap = cv2.VideoCapture(p)
    co = []
    with mp_hands.Hands(static_image_mode=False, max_num_hands=2,
                        model_complexity=1, min_detection_confidence=det,
                        min_tracking_confidence=track) as h:
        while True:
            ok, f = cap.read()
            if not ok:
                break
            co.append(bool(h.process(
                cv2.cvtColor(f, cv2.COLOR_BGR2RGB)).multi_hand_landmarks))
    cap.release()
    return co


def doan_ky(co, khe=KHE_CHO_PHEP):
    """Đoạn dài nhất có ký hiệu, cho phép hụt tối đa `khe` khung liên tiếp."""
    tot = [i for i, v in enumerate(co) if v]
    if not tot:
        return None
    doan, dau, truoc = [], tot[0], tot[0]
    for i in tot[1:]:
        if i - truoc - 1 > khe:
            doan.append((dau, truoc))
            dau = i
        truoc = i
    doan.append((dau, truoc))
    return max(doan, key=lambda d: d[1] - d[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thu-muc", required=True)
    ap.add_argument("--so-video", type=int, default=40)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()

    import cv2
    import mediapipe as mp
    mp_hands = mp.solutions.hands

    tep = sorted(os.path.join(a.thu_muc, f) for f in os.listdir(a.thu_muc)
                 if f.endswith(".mp4"))[:a.so_video]
    print("Phân tích %d video\n" % len(tep))
    print("  %-9s %6s %7s %8s %9s %9s" %
          ("video", "khung", "vào", "ra", "có ký", "trong đoạn"))
    ds = []
    for p in tep:
        ma = os.path.basename(p)[:-4]
        co = chuoi_phat_hien(p, cv2, mp_hands)
        if not co:
            continue
        d = doan_ky(co)
        if not d:
            continue
        i0, i1 = d
        trong = co[i0:i1 + 1]
        r = {
            "ma": ma, "khung": len(co),
            "dan_vao": i0, "dan_ra": len(co) - 1 - i1,
            "khung_doan_ky": i1 - i0 + 1,
            "ty_le_co_ky": (i1 - i0 + 1) / len(co),
            "phat_hien_toan_video": sum(co) / len(co),
            "phat_hien_trong_doan": sum(trong) / len(trong),
        }
        ds.append(r)
        print("  %-9s %6d %6d %8d %8.1f%% %9.1f%%"
              % (ma, r["khung"], r["dan_vao"], r["dan_ra"],
                 r["ty_le_co_ky"] * 100, r["phat_hien_trong_doan"] * 100),
              flush=True)

    if not ds:
        print("Không phân tích được video nào.")
        return 1

    def tv(k):
        return statistics.median(x[k] for x in ds)

    print("\n" + "=" * 72)
    print("TỔNG HỢP — %d video" % len(ds))
    print("=" * 72)
    print("  Dẫn vào (đứng nghỉ đầu video)   trung vị %5.1f khung ≈ %.2f giây"
          % (tv("dan_vao"), tv("dan_vao") / 30))
    print("  Dẫn ra  (đứng nghỉ cuối video)  trung vị %5.1f khung ≈ %.2f giây"
          % (tv("dan_ra"), tv("dan_ra") / 30))
    print("  Phần thực sự có ký hiệu         trung vị %5.1f%% thời lượng"
          % (tv("ty_le_co_ky") * 100))
    print()
    print("  Phát hiện tính trên TOÀN video  trung vị %5.1f%%"
          % (tv("phat_hien_toan_video") * 100))
    print("  Phát hiện tính TRONG đoạn ký    trung vị %5.1f%%   <-- số đúng"
          % (tv("phat_hien_trong_doan") * 100))
    dat = sum(1 for x in ds if x["phat_hien_trong_doan"] >= 0.9)
    print("  Số mẫu đạt >=90%% trong đoạn ký  %d/%d (%.1f%%)"
          % (dat, len(ds), 100 * dat / len(ds)))
    print("\n  Kết luận: chênh lệch giữa hai dòng trên KHÔNG phải chất lượng")
    print("  phát hiện, mà là phần video người ký đứng nghỉ. Muốn dùng video")
    print("  từ điển làm dữ liệu thì phải cắt đoạn trước, không phải chỉnh")
    print("  ngưỡng MediaPipe.")

    if a.json:
        json.dump(ds, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("\nĐã ghi %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())

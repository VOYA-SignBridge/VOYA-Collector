import numpy as np
import cv2
import os
import csv

# ====== CONFIG ======
ROOT = r"E:\CTU_ProjectOutside\VOYA-Collector"

CSV_FILES = [
    (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\train.csv", "train"),
    (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\val.csv", "val"),
    (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\test.csv", "test"),
]

CANVAS_W, CANVAS_H = 960, 540

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),
    (0,17)
]

# ====== LOAD CSV ======
all_samples = []

for csv_path, split in CSV_FILES:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames or "file_path" not in reader.fieldnames:
            raise ValueError(f"{csv_path} missing file_path")

        for row in reader:
            rel_path = row["file_path"].lstrip("/")
            full_path = os.path.join(ROOT, rel_path)

            all_samples.append({
                "path": full_path,
                "split": split,
                "label": row.get("label_slug", ""),
                "class_idx": row.get("class_idx", -1)
            })

print(f"Total samples: {len(all_samples)}")

# ====== FUNCTIONS ======
def load_npz(npz_path):
    data = np.load(npz_path, allow_pickle=False)

    key = "sequence" if "sequence" in data else (
          "features" if "features" in data else list(data.keys())[0])

    x = np.asarray(data[key], dtype=np.float32)

    assert x.ndim == 2 and x.shape[1] == 126, f"Bad shape: {x.shape}"
    return x


def draw_hand(frame, pts, color):
    # skip invalid
    if not np.isfinite(pts).all():
        return

    if np.linalg.norm(pts) < 1e-6:
        return

    p2 = []
    for i in range(21):
        px = int(np.clip(pts[i,0], 0, 1) * (CANVAS_W-1))
        py = int(np.clip(pts[i,1], 0, 1) * (CANVAS_H-1))
        p2.append((px, py))
        cv2.circle(frame, (px, py), 3, color, -1)

    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, p2[a], p2[b], color, 2)


def replay_sample(x, meta):
    prev = None

    for t in range(x.shape[0]):
        frame = np.full((CANVAS_H, CANVAS_W, 3), 20, dtype=np.uint8)

        left = x[t, :63].reshape(21, 3)
        right = x[t, 63:].reshape(21, 3)

        # ===== DEBUG (frame đầu) =====
        if t == 0:
            print("Range:", x.min(), x.max())
            print("Left mean X:", np.mean(left[:,0]))
            print("Right mean X:", np.mean(right[:,0]))

        # ===== DRAW =====
        draw_hand(frame, left, (0,165,255))
        draw_hand(frame, right, (255,255,0))

        # ===== centroid =====
        for pts, c in [(left,(0,165,255)), (right,(255,255,0))]:
            if np.linalg.norm(pts) > 1e-6:
                cx = int(np.mean(np.clip(pts[:,0],0,1)) * (CANVAS_W-1))
                cy = int(np.mean(np.clip(pts[:,1],0,1)) * (CANVAS_H-1))
                cv2.circle(frame, (cx, cy), 6, c, 2)

        # ===== detect missing =====
        if np.linalg.norm(left) < 1e-6:
            cv2.putText(frame, "LEFT MISSING", (700, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

        if np.linalg.norm(right) < 1e-6:
            cv2.putText(frame, "RIGHT MISSING", (700, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

        # ===== jitter check =====
        if prev is not None:
            vel = np.linalg.norm(x[t] - prev)
            if vel > 10:
                cv2.putText(frame, "JITTER!", (700, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
        prev = x[t]

        # ===== overlay =====
        cv2.putText(frame, f"{meta['split']} | {meta['label']}", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,200,255), 2)

        cv2.putText(frame, os.path.basename(meta["path"]), (20, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200,200,200), 1)

        cv2.putText(frame, f"frame {t+1}/{x.shape[0]}", (20, 90),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200,200,200), 2)

        cv2.imshow("NPZ Replay", frame)

        key = cv2.waitKey(60) & 0xFF
        if key == ord('q'):
            return "quit"
        elif key == ord('n'):
            return "next"
        elif key == ord('p'):
            return "prev"

    return "next"


# ====== LOOP ======
idx = 0

while 0 <= idx < len(all_samples):
    meta = all_samples[idx]
    path = meta["path"]

    if not os.path.exists(path):
        print(f"[MISSING] {path}")
        idx += 1
        continue

    print(f"{idx+1}/{len(all_samples)} | {meta['split']} | {meta['label']}")

    try:
        x = load_npz(path)
    except Exception as e:
        print(f"[ERROR] {e}")
        idx += 1
        continue

    action = replay_sample(x, meta)

    if action == "quit":
        break
    elif action == "next":
        idx += 1
    elif action == "prev":
        idx -= 1

cv2.destroyAllWindows()
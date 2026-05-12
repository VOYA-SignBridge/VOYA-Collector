import numpy as np
import cv2
import os
import sys
import csv
from pathlib import Path

ROOT = r"E:\CTU_ProjectOutside\VOYA-Collector"
CANVAS_W, CANVAS_H = 960, 540

HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),
    (0,17)
]

def load_npz(npz_path):
    """Load NPZ with proper normalization"""
    data = np.load(npz_path, allow_pickle=True)
    key = "sequence" if "sequence" in data else (
          "features" if "features" in data else list(data.keys())[0])
    x = np.asarray(data[key], dtype=np.float32)
    
    # ========= AUTO-NORMALIZE =========
    # Data range: [-1.112, 0.154] -> cần normalize về [0, 1]
    x_min, x_max = x.min(), x.max()
    if x_max > x_min:
        x = (x - x_min) / (x_max - x_min)
        print(f"  ✓ Normalized: [{x_min:.3f}, {x_max:.3f}] -> [0, 1]")
    
    assert x.ndim == 2 and x.shape[1] == 126, f"Bad shape: {x.shape}"
    return x


def draw_hand(frame, pts, color):
    """Vẽ hand landmarks (coordinate already in [0, 1])"""
    if not np.isfinite(pts).all():
        return
    if np.linalg.norm(pts) < 1e-6:
        return

    p2 = []
    for i in range(21):
        # Clip và convert to pixel
        px = int(np.clip(pts[i,0], 0, 1) * (CANVAS_W-1))
        py = int(np.clip(pts[i,1], 0, 1) * (CANVAS_H-1))
        p2.append((px, py))
        cv2.circle(frame, (px, py), 3, color, -1)

    for a, b in HAND_CONNECTIONS:
        cv2.line(frame, p2[a], p2[b], color, 2)


def replay_sample(x, meta):
    """Replay video frame-by-frame"""
    prev = None

    for t in range(x.shape[0]):
        frame = np.full((CANVAS_H, CANVAS_W, 3), 20, dtype=np.uint8)

        left = x[t, :63].reshape(21, 3)
        right = x[t, 63:].reshape(21, 3)

        if t == 0:
            print(f"  Frame range: [{x.min():.3f}, {x.max():.3f}]")
            print(f"  Left mean: {np.mean(left[:,0]):.3f}")
            print(f"  Right mean: {np.mean(right[:,0]):.3f}")

        # Draw both hands
        draw_hand(frame, left, (0,165,255))   # Orange = left
        draw_hand(frame, right, (255,255,0))  # Cyan = right

        # Draw centroids
        for pts, c in [(left,(0,165,255)), (right,(255,255,0))]:
            if np.linalg.norm(pts) > 1e-6:
                cx = int(np.mean(np.clip(pts[:,0],0,1)) * (CANVAS_W-1))
                cy = int(np.mean(np.clip(pts[:,1],0,1)) * (CANVAS_H-1))
                cv2.circle(frame, (cx, cy), 6, c, 2)

        # Detect missing hands
        if np.linalg.norm(left) < 1e-6:
            cv2.putText(frame, "LEFT MISSING", (700, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

        if np.linalg.norm(right) < 1e-6:
            cv2.putText(frame, "RIGHT MISSING", (700, 70),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)

        # Detect jitter
        if prev is not None:
            vel = np.linalg.norm(x[t] - prev)
            if vel > 0.5:  # Adjusted threshold for normalized data
                cv2.putText(frame, f"JITTER: {vel:.2f}", (700, 100),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
        prev = x[t]

        # Overlay info
        cv2.putText(frame, f"{meta.get('label', '?')}", (20, 30),
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


def load_from_csv():
    CSV_FILES = [
        (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\train.csv", "train"),
        (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\val.csv", "val"),
        (r"E:\CTU_ProjectOutside\VOYA-Collector\processed\splits\test.csv", "test"),
    ]

    all_samples = []
    for csv_path, split in CSV_FILES:
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rel_path = row["file_path"].lstrip("/")
                full_path = os.path.join(ROOT, rel_path)
                all_samples.append({
                    "path": full_path,
                    "split": split,
                    "label": row.get("label_slug", ""),
                    "class_idx": row.get("class_idx", -1)
                })

    print(f"Loaded {len(all_samples)} samples from CSV")
    return all_samples


def load_from_folder(folder):
    folder = Path(folder)
    npz_files = sorted(folder.glob("**/*.npz"))
    
    samples = []
    for npz_path in npz_files:
        samples.append({
            "path": str(npz_path),
            "label": npz_path.parent.name,
        })
    
    print(f"Found {len(samples)} .npz files in {folder}")
    return samples


def load_single_file(file_path):
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return None
    
    return [{
        "path": file_path,
        "label": os.path.basename(file_path),
    }]


def interactive_choose_file():
    print("\n=== Mode: Chọn file NPZ ===")
    
    root_path = Path(ROOT) / "dataset"
    
    if not root_path.exists():
        print(f"Dataset folder not found: {root_path}")
        return None
    
    npz_files = sorted(root_path.glob("**/*.npz"))
    
    if not npz_files:
        print("No .npz files found")
        return None
    
    print(f"Found {len(npz_files)} files:")
    for i, f in enumerate(npz_files[:50]):
        print(f"  {i}: {f.relative_to(root_path)}")
    
    if len(npz_files) > 50:
        print(f"  ... and {len(npz_files) - 50} more")
    
    try:
        idx = int(input("\nChọn số (0-{}): ".format(len(npz_files)-1)))
        if 0 <= idx < len(npz_files):
            return [{
                "path": str(npz_files[idx]),
                "label": npz_files[idx].parent.name,
            }]
    except (ValueError, IndexError):
        print("Invalid choice")
    
    return None


def main():
    samples = []
    swap_hands = False
    
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        # Check for --swap flag
        if "--swap" in sys.argv:
            swap_hands = True
        
        if arg == "--csv":
            samples = load_from_csv()
        elif arg == "--folder":
            folder = sys.argv[2] if len(sys.argv) > 2 else str(Path(ROOT) / "dataset")
            samples = load_from_folder(folder)
        elif arg == "--interactive":
            samples = interactive_choose_file()
        elif arg != "--swap":
            samples = load_single_file(arg)
    else:
        samples = interactive_choose_file()
    
    if not samples:
        print("No samples to replay")
        return
    
    print(f"\nReplaying {len(samples)} file(s)")
    if swap_hands:
        print("⚠ SWAP enabled: swapping left/right hands")
    print("Controls: [Q]uit | [N]ext | [P]revious\n")
    
    idx = 0
    while 0 <= idx < len(samples):
        meta = samples[idx]
        path = meta["path"]
        
        if not os.path.exists(path):
            print(f"[SKIP] File not found: {path}")
            idx += 1
            continue
        
        print(f"\n[{idx+1}/{len(samples)}] {meta.get('label', '?')} | {os.path.basename(path)}")
        
        try:
            x = load_npz(path)
            # ✅ SWAP if needed
            if swap_hands:
                x_swapped = x.copy()
                x_swapped[:, :63] = x[:, 63:]    # right → left
                x_swapped[:, 63:] = x[:, :63]    # left → right
                x = x_swapped
            print(f"  Shape: {x.shape}")
        except Exception as e:
            print(f"  [ERROR] {e}")
            idx += 1
            continue
        
        action = replay_sample(x, meta)
        
        if action == "quit":
            break
        elif action == "next":
            idx += 1
        elif action == "prev":
            idx = max(0, idx - 1)
    
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
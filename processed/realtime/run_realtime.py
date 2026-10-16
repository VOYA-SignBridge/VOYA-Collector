from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont

import argparse
import json
import re
import time
import sys
import numpy as np
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]

BACKEND_DIR = ROOT / "processed"

if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))
from shared.normalization import ( normalize_hands_vector_126, )

try:
    import cv2
except Exception as e:  # pragma: no cover
    cv2 = None  # type: ignore

try:
    import mediapipe as mp
except Exception as e:  # pragma: no cover
    mp = None  # type: ignore

import torch
import torch.nn as nn
try:
    from dataset_versioning import get_analysis_dir
except Exception:
    get_analysis_dir = None  # type: ignore


@dataclass
class ModelBundle:
    model: nn.Module
    feature_dim: int
    num_classes: int
    label_map: List[str]
    device: str


class Chomp1d(nn.Module):
    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, : x.size(2) - self.chomp_size]


class TemporalBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int, dilation: int, dropout: float):
        super().__init__()
        pad = (kernel_size - 1) * dilation
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size, padding=pad, dilation=dilation)
        self.chomp1 = Chomp1d(pad)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size, padding=pad, dilation=dilation)
        self.chomp2 = Chomp1d(pad)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)
        self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        self.out_relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.drop1(self.relu1(self.chomp1(self.conv1(x))))
        out = self.drop2(self.relu2(self.chomp2(self.conv2(out))))
        res = x if self.downsample is None else self.downsample(x)
        return self.out_relu(out + res)


class TCNClassifier(nn.Module):
    def __init__(
        self,
        feature_dim: int,
        num_classes: int,
        channels: int = 64,
        levels: int = 3,
        kernel_size: int = 5,
        dropout: float = 0.3,
    ):
        super().__init__()
        self.proj = nn.Conv1d(feature_dim, channels, kernel_size=1)
        blocks = []
        for i in range(levels):
            dilation = 2 ** i
            blocks.append(TemporalBlock(channels, channels, kernel_size, dilation, dropout))
        self.network = nn.Sequential(*blocks)
        self.classifier = nn.Linear(channels, num_classes)

    def forward(self, x_btd: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        # x_btd: [B, T, D] -> [B, D, T]
        x = x_btd.transpose(1, 2)
        x = self.proj(x)
        x = self.network(x)
        # NOTE: lengths parameter is always set to args.window (hardcoded as 60 in the caller).
        # This makes the masked GAP code mathematically equivalent to unmasked mean(dim=2).
        # The masked pooling is semantically correct but operationally a no-op.
        # Pooling contract: unmasked_gap_v1 (matches train_tcn.py).
        b, c, t = x.shape
        mask = torch.arange(t, device=x.device).unsqueeze(0) < lengths.unsqueeze(1)
        mask = mask.unsqueeze(1)
        x = x.masked_fill(~mask, 0.0)
        denom = lengths.clamp(min=1).unsqueeze(1).to(x.dtype)
        pooled = x.sum(dim=2) / denom
        logits = self.classifier(pooled)
        return logits


def _slugify(text: str) -> str:
    s = (text or "").strip().lower()
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9\-\+_]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "subset"


def load_latest_checkpoint(out_dir: Path, *, tag: str = "") -> Tuple[Path, dict]:
    summaries = sorted(out_dir.glob('tcn_*.json'))
    if not summaries:
        raise FileNotFoundError(f'No summaries found in {out_dir}')

    tag_s = _slugify(tag) if (tag or "").strip() else ""
    if tag_s:
        filtered = [p for p in summaries if f"tcn_{tag_s}_" in p.name]
        if not filtered:
            raise FileNotFoundError(f"No summaries found for tag='{tag_s}' in {out_dir}")
        summaries = filtered

    latest = summaries[-1]
    meta = json.loads(latest.read_text(encoding='utf-8'))
    ckpt = Path(meta.get('checkpoint', ''))
    if not ckpt.exists():
        # fallback: pick latest .pt
        pts = sorted(out_dir.glob('tcn_*.pt'))
        if not pts:
            raise FileNotFoundError('No checkpoint found')
        ckpt = pts[-1]
    return ckpt, meta


def _load_label_map_from_index_to_label(i2l_path: Path, *, num_classes: int) -> List[str]:
    label_map: List[str] = [str(i) for i in range(num_classes)]
    try:
        data = json.loads(i2l_path.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            m = {int(k): v for k, v in data.items()}
            label_map = []
            for i in range(num_classes):
                v = m.get(i, {}) if isinstance(m.get(i, {}), dict) else {}
                name = v.get('label_original') or v.get('label_slug') or v.get('label_key') or str(i)
                label_map.append(str(name))
    except Exception:
        pass
    return label_map


def _label_map_from_checkpoint(obj: dict, *, num_classes: int) -> Optional[List[str]]:
    """Build an index->label list from checkpoint contents.

    Trainer checkpoints store either:
    - idx_to_label: {index(int/str): label_key(str)}
    - label_to_idx: {label_key(str): index(int/str)}

    This is the most reliable source to stay compatible with the model.
    """
    i2l = obj.get("idx_to_label")
    if isinstance(i2l, dict):
        out: List[str] = []
        for i in range(num_classes):
            v = i2l.get(i, i2l.get(str(i), str(i)))
            out.append(str(v))
        return out

    l2i = obj.get("label_to_idx")
    if isinstance(l2i, dict):
        inv: dict[int, str] = {}
        for k, v in l2i.items():
            try:
                inv[int(v)] = str(k)
            except Exception:
                continue
        out = [inv.get(i, str(i)) for i in range(num_classes)]
        return out

    return None


def build_model_from_ckpt(ckpt_path: Path, device: str, *, meta: Optional[dict] = None) -> ModelBundle:
    # FIX for PyTorch 2.6+ (weights_only=True became default)
    obj = torch.load(ckpt_path, map_location=device, weights_only=False)

    feature_dim = int( obj.get('feature_dim', 126) )
    num_classes = int(obj.get('num_classes'))

    # Trainer uses "model_config"; keep backward-compat with older keys.
    cfg = obj.get('model_config') or obj.get('config') or {}
    channels = int(cfg.get('channels', 64)) if isinstance(cfg, dict) else 64
    levels = int(cfg.get('levels', 3)) if isinstance(cfg, dict) else 3
    kernel_size = int(cfg.get('kernel_size', 5)) if isinstance(cfg, dict) else 5
    dropout = float(cfg.get('dropout', 0.3)) if isinstance(cfg, dict) else 0.3

    model = TCNClassifier(
        feature_dim=feature_dim,
        num_classes=num_classes,
        channels=channels,
        levels=levels,
        kernel_size=kernel_size,
        dropout=dropout,
    )
    model.load_state_dict(obj['model_state_dict'])
    model.to(device).eval()

    # label map:
    # - ALWAYS prefer checkpoint-embedded mapping for compatibility with num_classes/order.
    # - Optionally replace display names using an index_to_label.json that matches this checkpoint.
    label_map = _label_map_from_checkpoint(obj, num_classes=num_classes)
    lookup_path = (
        ROOT
        / "processed"
        / "analysis"
        / "index_to_label.json"
    )

    if lookup_path.exists():

        display_lookup = (
            _load_label_original_lookup(
                lookup_path
            )
        )

        label_map = [
            display_lookup.get(x, x)
            for x in label_map
        ]
    label_source = "checkpoint"
    if label_map is None:
        label_map = [str(i) for i in range(num_classes)]
        label_source = "fallback"

    print(f"[realtime] label_map_source={label_source} num_classes={num_classes}")

    return ModelBundle(
        model=model,
        feature_dim=feature_dim,
        num_classes=num_classes,
        label_map=label_map,
        device=device,
    )


def extract_hands_126(frame_bgr: np.ndarray, hands) -> Tuple[np.ndarray, np.ndarray, bool]:
    feat = np.zeros(
        126,
        dtype=np.float32
    )

    has_hand = False

    h, w = frame_bgr.shape[:2]
    frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    result = hands.process(frame_rgb)

    left = np.zeros((21, 3), dtype=np.float32)
    right = np.zeros((21, 3), dtype=np.float32)

    has_hand = False

    if result.multi_hand_landmarks and result.multi_handedness:
        has_hand = True   # ----> HAND DETECTED
        for lm, hd in zip(result.multi_hand_landmarks, result.multi_handedness):
            label = hd.classification[0].label.lower()
            coords = np.array([[p.x, p.y, p.z] for p in lm.landmark], dtype=np.float32)
            if label == 'right':
                left = coords
            else:
                right = coords
            mp.solutions.drawing_utils.draw_landmarks(frame_bgr, lm, mp.solutions.hands.HAND_CONNECTIONS)

        feat = np.concatenate(
            [left.reshape(-1), right.reshape(-1)],
            axis=0
        ).astype(np.float32)

        # IMPORTANT:
        # must match training preprocessing
        feat = normalize_hands_vector_126(feat)

    return feat, frame_bgr, has_hand


def softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x)
    return e / np.clip(e.sum(axis=-1, keepdims=True), 1e-9, None)

def draw_text_vietnamese(frame_bgr, text, pos=(10, 30), color=(0, 255, 0), font_size=32):
    """Draw Vietnamese text with proper font support and outline for better readability."""
    # convert BGR → RGB
    img = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img)

    draw = ImageDraw.Draw(pil_img)

    # Try multiple font paths for cross-platform support
    font_paths = [
        r"C:\Windows\Fonts\arial.ttf",          # Windows
        r"C:\Windows\Fonts\ARIALUNI.TTF",       # Windows Unicode
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
        "/System/Library/Fonts/Helvetica.ttc",   # macOS
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",  # Linux alt
    ]
    
    font = None
    for font_path in font_paths:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except:
            continue
    
    if font is None:
        font = ImageFont.load_default()

    # Draw text with black outline for better readability
    x, y = pos
    outline_color = (0, 0, 0)  # Black outline
    # Draw outline (8 directions)
    for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    # Draw main text
    draw.text(pos, text, font=font, fill=color)
    
    # convert RGB back to BGR
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

def _load_label_original_lookup(
    path: Path,
) -> dict[str, str]:

    out = {}

    try:
        data = json.loads(
            path.read_text(encoding="utf-8")
        )

        if isinstance(data, dict):

            for _, meta in data.items():

                if not isinstance(meta, dict):
                    continue

                key = str(
                    meta.get("label_key", "")
                ).strip()

                original = str(
                    meta.get("label_original", "")
                ).strip()

                if key:
                    out[key] = (
                        original or key
                    )

    except Exception:
        pass

    return out

def main() -> None:
    parser = argparse.ArgumentParser(description='Realtime sign recognition using TCN + MediaPipe Hands')
    parser.add_argument('--checkpoint', type=Path, default=None, help='Path to .pt checkpoint (optional)')
    parser.add_argument('--outputs_dir', type=Path, default=Path('processed/train_utils/outputs'))
    parser.add_argument('--dialect', type=str, default='', help="Load latest checkpoint for this dialect (e.g. 'hoa-de').")
    parser.add_argument('--tag', type=str, default='', help="Load latest checkpoint by tag (matches trainer prefix, e.g. 'dialect-hoa-de').")
    parser.add_argument('--window', type=int, default=60, help='Temporal window size (frames)')
    parser.add_argument('--every', type=int, default=2, help='Run inference every N frames')
    parser.add_argument('--video', type=str, default='', help='Optional video file path; empty uses webcam')
    parser.add_argument('--device', type=str, default='cuda' if torch.cuda.is_available() else 'cpu')
    parser.add_argument('--smoothing', type=float, default=0.7, help='EMA smoothing for logits [0-1]')
    parser.add_argument('--vote_window', type=int, default=5, help='Temporal voting window size (predictions)')
    parser.add_argument('--vote_min_conf', type=float, default=0.6, help='Min confidence to include in voting [0-1]')
    parser.add_argument('--max_latency_ms', type=float, default=50.0, help='Target max inference latency in ms')
    parser.add_argument('--max_every', type=int, default=6, help='Max inference stride for latency control')
    
    # Display and stability parameters
    parser.add_argument('--confidence_threshold', type=float, default=0.6, help='Minimum confidence to display prediction [0-1]')
    parser.add_argument('--stable_frames', type=int, default=3, help='Frames needed to confirm label switch')
    parser.add_argument('--hold_frames', type=int, default=15, help='Frames to hold label after loss')
    parser.add_argument('--show_fps', action='store_true', help='Show FPS and stats on screen')
    parser.add_argument('--font_size', type=int, default=32, help='Font size for displayed text')
    
    args = parser.parse_args()

    if cv2 is None or mp is None:
        raise SystemExit('Please install opencv-python and mediapipe: pip install opencv-python mediapipe')

    if args.checkpoint is None:
        tag = (args.tag or '').strip()
        if not tag and (args.dialect or '').strip():
            tag = f"dialect-{args.dialect.strip()}"
        ckpt, meta = load_latest_checkpoint(args.outputs_dir, tag=tag)
    else:
        ckpt = args.checkpoint
        meta = {}

    bundle = build_model_from_ckpt(ckpt, args.device, meta=meta)
    feature_dim = bundle.feature_dim
    if feature_dim != 126:
        raise SystemExit(f'Model feature_dim={feature_dim} must match feature extractor (126).')

    hands = mp.solutions.hands.Hands(static_image_mode=False, max_num_hands=2, model_complexity=1, min_detection_confidence=0.5, min_tracking_confidence=0.5)

    cap = cv2.VideoCapture(0 if not args.video else args.video)
    if not cap.isOpened():
        raise SystemExit('Could not open webcam/video')

    buf: Deque[np.ndarray] = deque(maxlen=args.window)
    ema_logits = None
    frame_idx = 0
    vote_labels: Deque[str] = deque(maxlen=max(1, int(args.vote_window)))
    vote_confs: Deque[float] = deque(maxlen=max(1, int(args.vote_window)))
    adaptive_every = max(1, int(args.every))
    
    # Label persistence/stability tracking
    display_label = ""
    display_conf = 0.0
    candidate_label = ""
    candidate_count = 0
    hold_counter = 0
    
    # FPS tracking
    fps_start_time = time.time()
    fps_frame_count = 0
    current_fps = 0.0
    inference_time_ms = 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # FPS calculation
            fps_frame_count += 1
            if fps_frame_count >= 30:
                elapsed = time.time() - fps_start_time
                current_fps = fps_frame_count / elapsed if elapsed > 0 else 0.0
                fps_frame_count = 0
                fps_start_time = time.time()

            feat, vis, has_hand = extract_hands_126(frame, hands)

            # if NO HAND → clear buffer and displayed label immediately
            if not has_hand:
                buf.clear()
                ema_logits = None
                vote_labels.clear()
                vote_confs.clear()
                display_label = ""
                display_conf = 0.0
                candidate_label = ""
                candidate_count = 0
                hold_counter = 0
                
                # Show stats if enabled
                if args.show_fps:
                    stats_text = f"FPS: {current_fps:.1f} | No hand detected"
                    vis = draw_text_vietnamese(vis, stats_text, (10, 30), (100, 100, 100), args.font_size // 2)
                
                cv2.imshow("Sign Recognition (q to quit)", vis)
                frame_idx += 1
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                continue

            # ----- HAND DETECTED → normal flow -----
            if feat.shape[0] < feature_dim:
                feat = np.pad(feat, (0, feature_dim - feat.shape[0]))
            elif feat.shape[0] > feature_dim:
                feat = feat[:feature_dim]

            buf.append(feat.astype(np.float32))

            pred_label = ""
            pred_conf = 0.0
            did_infer = False

            if len(buf) >= max(8, args.window // 3) and (frame_idx % adaptive_every == 0):
                did_infer = True
                inference_start = time.time()
                
                X = np.stack(list(buf), axis=0)
                lengths = torch.tensor( [args.window], dtype=torch.long, device=bundle.device )
                X_pad = np.zeros((1, args.window, feature_dim), dtype=np.float32)
                t = min(args.window, X.shape[0])
                X_pad[0, -t:] = X[-t:]

                with torch.no_grad():
                    logits = bundle.model(torch.from_numpy(X_pad).to(bundle.device), lengths)
                    vec = logits.cpu().numpy()[0]
                    if ema_logits is None:
                        ema_logits = vec
                    else:
                        alpha = float(args.smoothing)
                        ema_logits = alpha * ema_logits + (1 - alpha) * vec

                    probs = softmax(ema_logits)
                    idx = int(np.argmax(probs))
                    pred_label = bundle.label_map[idx]
                    pred_conf = float(probs[idx])
                
                inference_time_ms = (time.time() - inference_start) * 1000

                if pred_label and pred_conf >= float(args.vote_min_conf):
                    vote_labels.append(pred_label)
                    vote_confs.append(pred_conf)

                if vote_labels:
                    counts = Counter(vote_labels)
                    vote_label = counts.most_common(1)[0][0]
                    confs = [c for l, c in zip(vote_labels, vote_confs) if l == vote_label]
                    if confs:
                        pred_label = vote_label
                        pred_conf = float(sum(confs) / len(confs))

                # Adaptive latency control (best-effort)
                if inference_time_ms > float(args.max_latency_ms):
                    adaptive_every = min(int(args.max_every), adaptive_every + 1)
                elif adaptive_every > int(args.every) and inference_time_ms < float(args.max_latency_ms) * 0.7:
                    adaptive_every = max(int(args.every), adaptive_every - 1)

            # ----- Label persistence logic (debounce + hysteresis) -----
            # Debounce rule:
            # - Only switch labels after *consecutive* confident predictions.
            # - Frames where inference is skipped (--every) must NOT break the streak.
            if did_infer and pred_label and pred_conf >= args.confidence_threshold:
                if pred_label == display_label:
                    # Same label: refresh hold counter and update confidence
                    display_conf = pred_conf
                    hold_counter = args.hold_frames
                    candidate_label = ""
                    candidate_count = 0
                elif pred_label == candidate_label:
                    # Building consensus for new label
                    candidate_count += 1
                    if candidate_count >= args.stable_frames:
                        # Switch to new label
                        display_label = pred_label
                        display_conf = pred_conf
                        hold_counter = args.hold_frames
                        candidate_label = ""
                        candidate_count = 0
                else:
                    # New candidate label
                    candidate_label = pred_label
                    candidate_count = 1
            else:
                # No (confident) prediction: use hold counter
                if hold_counter > 0:
                    hold_counter -= 1
                else:
                    # Hold expired: clear display
                    if display_label:
                        display_label = ""
                        display_conf = 0.0
                        candidate_label = ""
                        candidate_count = 0

                # If we DID run inference but it wasn't confident enough,
                # reset the candidate so stability requires consecutive confident hits.
                if did_infer:
                    candidate_label = ""
                    candidate_count = 0
            
            # ----- Draw display label if exists -----
            y_offset = 30
            if display_label:
                txt = f"{display_label} ({display_conf*100:.1f}%)"
                vis = draw_text_vietnamese(vis, txt, (10, y_offset), (0, 255, 0), args.font_size)
                y_offset += args.font_size + 10
            
            # ----- Draw stats if enabled -----
            if args.show_fps:
                stats_lines = [
                    f"FPS: {current_fps:.1f}",
                    f"Buffer: {len(buf)}/{args.window}",
                    f"Inference: {inference_time_ms:.1f}ms (every={adaptive_every})",
                ]
                if candidate_label and candidate_count > 0:
                    stats_lines.append(f"Candidate: {candidate_label} ({candidate_count}/{args.stable_frames})")
                if hold_counter > 0 and not pred_label:
                    stats_lines.append(f"Hold: {hold_counter}/{args.hold_frames}")
                
                stats_text = " | ".join(stats_lines)
                vis = draw_text_vietnamese(vis, stats_text, (10, y_offset), (200, 200, 200), args.font_size // 2)

            cv2.imshow("Sign Recognition (q to quit)", vis)

            frame_idx += 1
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        hands.close()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont

import argparse
import json
import re
import time
import threading
import urllib.error
import urllib.request
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import tensorflow as tf
import keras

try:
    import cv2
except Exception as e:  # pragma: no cover
    cv2 = None  # type: ignore

try:
    import mediapipe as mp
except Exception as e:  # pragma: no cover
    mp = None  # type: ignore

try:
    from train_model.dataset_versioning import get_analysis_dir
except Exception:
    get_analysis_dir = None  # type: ignore

@dataclass
class ModelBundle:
    model: tf.keras.Model
    in_dim: int
    num_classes: int
    label_map: List[str]
    device: str


LHAND_START, LHAND_END  = 21, 42
RHAND_START, RHAND_END  = 0, 21

_HAND_LANDMARKER_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
_HAND_LANDMARKER_MODEL_PATH = Path(__file__).resolve().parent / "assets" / "hand_landmarker.task"
_POSE_LANDMARKER_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/latest/pose_landmarker_lite.task"
_POSE_LANDMARKER_MODEL_PATH = Path(__file__).resolve().parent / "assets" / "pose_landmarker_lite.task"


def _ensure_mp_models():
    for url, path in [(_HAND_LANDMARKER_MODEL_URL, _HAND_LANDMARKER_MODEL_PATH)]:
        if path.exists() and path.stat().st_size > 0:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".task.download")
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                path.write_bytes(response.read())
        except Exception as exc:
            if tmp_path.exists():
                try: tmp_path.unlink()
                except: pass
            raise RuntimeError(f"Failed to download {path.name}: {exc}") from exc


def init_mediapipe():
    if mp is None:
        raise RuntimeError("mediapipe is not available")
    _ensure_mp_models()
    
    hands_options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(_HAND_LANDMARKER_MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.3,
        min_hand_presence_confidence=0.3,
        min_tracking_confidence=0.8
    )
    
    return mp.tasks.vision.HandLandmarker.create_from_options(hands_options)


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

    for summary in reversed(summaries):
        try:
            meta = json.loads(summary.read_text(encoding='utf-8'))
            ckpt = Path(meta.get('checkpoint', ''))
            if ckpt.exists() and ckpt.suffix == '.h5':
                return ckpt, meta
        except Exception:
            pass

    # fallback: pick latest .h5
    h5s = sorted(out_dir.glob('tcn_*.h5'))
    if not h5s:
        raise FileNotFoundError('No .h5 checkpoint found')
    ckpt = h5s[-1]
    
    meta_path = ckpt.with_suffix('.json')
    meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}
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


def build_model_from_ckpt(ckpt_path: Path, meta: dict, device: str) -> ModelBundle:
    in_dim = int(meta.get('in_dim', 126))

    # Define compute_masked_pooling as plain function (no keras import needed)
    # tf.keras.models.load_model accepts plain functions in custom_objects
    def compute_masked_pooling(inputs):
        x_val, lens_val = inputs
        t = tf.shape(x_val)[1]
        mask = tf.sequence_mask(lens_val, maxlen=t, dtype=x_val.dtype)
        mask = tf.expand_dims(mask, axis=-1)
        x_masked = x_val * mask
        denom = tf.cast(tf.maximum(lens_val, 1), x_val.dtype)
        denom = tf.expand_dims(denom, axis=-1)
        return tf.reduce_sum(x_masked, axis=1) / denom

    def build_tcn_model(
        in_dim: int,
        num_classes: int,
        channels: int = 64,
        levels: int = 3,
        kernel_size: int = 5,
        dropout: float = 0.3,
        use_proj: bool = True,
        proj_dim: Optional[int] = None,
    ) -> keras.Model:
        inputs = keras.Input(shape=(None, in_dim), name="inputs")
        lengths = keras.Input(shape=(), dtype=tf.int32, name="lengths")

        proj_dim = proj_dim or channels
        
        x = inputs
        if use_proj and in_dim != proj_dim:
            x = keras.layers.Conv1D(filters=proj_dim, kernel_size=1, padding='same', name="proj")(x)
            
        current_in = proj_dim if (use_proj and in_dim != proj_dim) else in_dim
        
        for i in range(levels):
            dilation = 2 ** i
            c1 = keras.layers.Conv1D(
                filters=channels,
                kernel_size=kernel_size,
                padding='causal',
                dilation_rate=dilation,
                kernel_initializer='he_normal',
                name=f"tblock_{i}_conv1"
            )(x)
            r1 = keras.layers.ReLU(name=f"tblock_{i}_relu1")(c1)
            d1 = keras.layers.Dropout(dropout, name=f"tblock_{i}_drop1")(r1)
            
            c2 = keras.layers.Conv1D(
                filters=channels,
                kernel_size=kernel_size,
                padding='causal',
                dilation_rate=dilation,
                kernel_initializer='he_normal',
                name=f"tblock_{i}_conv2"
            )(d1)
            r2 = keras.layers.ReLU(name=f"tblock_{i}_relu2")(c2)
            d2 = keras.layers.Dropout(dropout, name=f"tblock_{i}_drop2")(r2)
            
            if current_in != channels:
                res = keras.layers.Conv1D(
                    filters=channels,
                    kernel_size=1,
                    padding='same',
                    kernel_initializer='he_normal',
                    name=f"tblock_{i}_downsample"
                )(x)
            else:
                res = x
                
            x = keras.layers.Add(name=f"tblock_{i}_add")([d2, res])
            x = keras.layers.ReLU(name=f"tblock_{i}_out_relu")(x)
            current_in = channels
            
        pooled = keras.layers.Lambda(
            compute_masked_pooling,
            name="masked_pool"
        )([x, lengths])
        
        outputs = keras.layers.Dense(num_classes, name="classifier", dtype=tf.float32)(pooled)
        return keras.Model(inputs=[inputs, lengths], outputs=outputs, name="tcn_classifier")

    # label map logic — label_map in summary.json is {label_key: index} (str->int)
    label_map: List[str] = []
    l2i = meta.get('label_map')  # type: Optional[dict]
    if l2i and isinstance(l2i, dict):
        # Invert: {label_key: index} -> {index: label_key}
        inv_map = {int(v): str(k) for k, v in l2i.items()}
        num_classes = int(meta.get('num_classes', len(inv_map)))
        num_classes = max(num_classes, max(inv_map.keys()) + 1) if inv_map else num_classes
        for i in range(num_classes):
            label_map.append(inv_map.get(i, str(i)))
    else:
        num_classes = int(meta.get('num_classes', 4))
        # Fallback will try index_to_label.json below

    # Extract architecture config from nested 'config' dict in summary.json
    cfg_meta = meta.get('config', {})
    # Rebuild Model in Python (bypassing Keras Config serialization bugs entirely!)
    model = build_tcn_model(
        in_dim=in_dim,
        num_classes=num_classes,
        channels=int(cfg_meta.get('channels', meta.get('channels', 64))),
        levels=int(cfg_meta.get('levels', meta.get('levels', 3))),
        kernel_size=int(cfg_meta.get('kernel_size', meta.get('kernel_size', 5))),
        dropout=0.0  # set dropout to 0 for inference
    )

    # Initialize model inputs so weights can be loaded
    dummy_x = tf.zeros((1, 1, in_dim))
    dummy_lens = tf.constant([1], dtype=tf.int32)
    model([dummy_x, dummy_lens])

    # Load Weights directly from the .h5 file
    model.load_weights(str(ckpt_path))

    if not label_map:
        # Try to infer num_classes from the model's output layer
        try:
            num_classes = int(model.output_shape[-1])
        except Exception:
            num_classes = int(meta.get('num_classes', 0))

        # Fallback label resolution: try index_to_label.json from analysis dir
        i2l_path: Optional[Path] = None
        # 1. Next to the checkpoint (subset mode writes it there)
        subset_i2l = ckpt_path.parent / 'index_to_label.json'
        if subset_i2l.exists():
            i2l_path = subset_i2l
        elif get_analysis_dir:
            cand = get_analysis_dir() / 'index_to_label.json'
            if cand.exists():
                i2l_path = cand
        else:
            cand = Path(__file__).resolve().parents[2] / 'processed' / 'analysis' / 'index_to_label.json'
            if cand.exists():
                i2l_path = cand

        if i2l_path:
            label_map = _load_label_map_from_index_to_label(i2l_path, num_classes=num_classes)
        else:
            label_map = [str(i) for i in range(num_classes)]

    if not label_map:
        raise SystemExit(
            f'label_map is empty after loading checkpoint. '
            f'Ensure the sidecar .json exists next to {ckpt_path.name}, '
            f'or that processed/analysis/index_to_label.json is present.'
        )

    num_classes = len(label_map)  # canonical source of truth

    return ModelBundle(
        model=model,
        in_dim=in_dim,
        num_classes=num_classes,
        label_map=label_map,
        device=device,
    )


class ThreadedCamera:
    def __init__(self, src=0):
        self.cap = cv2.VideoCapture(src)
        if isinstance(src, int) or src == 0 or src == '0':
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            self.cap.set(cv2.CAP_PROP_FPS, 30)
        self.ret, self.frame = self.cap.read()
        self.stopped = False
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        while not self.stopped:
            self.ret, self.frame = self.cap.read()
        self.cap.release()

    def read(self):
        if self.frame is not None:
            return self.ret, self.frame.copy()
        return self.ret, None

    def release(self):
        self.stopped = True
        if self.thread.is_alive():
            self.thread.join()

    def isOpened(self):
        return self.cap.isOpened()


def extract_hybrid(res_hands) -> Tuple[np.ndarray, np.ndarray, bool]:
    frame_data = np.full((42, 3), np.nan, dtype=np.float32)

    if res_hands and res_hands.hand_landmarks and res_hands.handedness:
        for hand_lms, handedness in zip(res_hands.hand_landmarks, res_hands.handedness):
            label = handedness[0].category_name.lower()
            slot = LHAND_START if label == 'left' else RHAND_START
            
            # Prevent overwriting if already populated by a higher confidence hand
            if np.isnan(frame_data[slot, 0]):
                for i, lm in enumerate(hand_lms):
                    if i < 21:
                        frame_data[slot + i] = [lm.x, lm.y, lm.z]

    has_hand = not (np.isnan(frame_data[LHAND_START, 0]) and np.isnan(frame_data[RHAND_START, 0]))
    # Return raw frame_data (with NaN) for tracker, and also a flat 0-filled feat for the model
    feat_126 = np.nan_to_num(frame_data, nan=0.0).reshape(126)
    return feat_126, frame_data, has_hand


def draw_landmarks_cv2(frame: np.ndarray, feat_126: np.ndarray) -> np.ndarray:
    """Draw landmarks on ALREADY-FLIPPED frame (mirror view)."""
    h, w, _ = frame.shape
    vec = feat_126.reshape(42, 3)
    
    HAND_CONNECTIONS = [
        (0, 1), (1, 2), (2, 3), (3, 4),
        (5, 6), (6, 7), (7, 8),
        (9, 10), (10, 11), (11, 12),
        (13, 14), (14, 15), (15, 16),
        (17, 18), (18, 19), (19, 20),
        (0, 5), (5, 9), (9, 13), (13, 17), (0, 17)
    ]

    def _draw_hand(start_idx, dot_color, line_color, radius=4, thickness=2):
        pts = []
        for i in range(21):
            lm = vec[start_idx + i]
            if lm[0] == 0.0 and lm[1] == 0.0 and lm[2] == 0.0:
                pts.append(None)
            else:
                pts.append((int(lm[0] * w), int(lm[1] * h)))

        if all(p is None for p in pts):
            return
            
        for p1, p2 in HAND_CONNECTIONS:
            if pts[p1] is not None and pts[p2] is not None:
                cv2.line(frame, pts[p1], pts[p2], line_color, thickness)
                
        for p in pts:
            if p is not None:
                cv2.circle(frame, p, radius, dot_color, -1)

    _draw_hand(LHAND_START, (0, 255, 0), (144, 238, 144))
    _draw_hand(RHAND_START, (0, 0, 255), (128, 128, 255))
    return frame


def softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x)
    return e / np.clip(e.sum(axis=-1, keepdims=True), 1e-9, None)

def draw_text_vietnamese(frame_bgr, text, pos=(10, 30), color=(0, 255, 0), font_size=32):
    """Draw Vietnamese text with proper font support and outline for better readability."""
    img = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(img)

    draw = ImageDraw.Draw(pil_img)

    font_paths = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\ARIALUNI.TTF",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
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

    x, y = pos
    outline_color = (0, 0, 0)
    for dx, dy in [(-2, -2), (-2, 0), (-2, 2), (0, -2), (0, 2), (2, -2), (2, 0), (2, 2)]:
        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
    draw.text(pos, text, font=font, fill=color)
    
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


class LabelStabilityTracker:
    def __init__(self, stable_frames: int = 3, hold_frames: int = 15, min_conf: float = 0.6):
        self.stable_frames = stable_frames
        self.hold_frames = hold_frames
        self.min_conf = min_conf

        self.display_label = ""
        self.display_conf = 0.0
        self.candidate_label = ""
        self.candidate_count = 0
        self.hold_counter = 0

    def update(self, pred_label: str, pred_conf: float, has_prediction: bool = True) -> Tuple[str, float]:
        if has_prediction and pred_label and pred_conf >= self.min_conf:
            if pred_label == self.display_label:
                # Same label: refresh hold counter
                self.display_conf = pred_conf
                self.hold_counter = self.hold_frames
                self.candidate_label = ""
                self.candidate_count = 0
            elif pred_label == self.candidate_label:
                # Building consensus toward a new label
                self.candidate_count += 1
                if self.candidate_count >= self.stable_frames:
                    self.display_label = pred_label
                    self.display_conf = pred_conf
                    self.hold_counter = self.hold_frames
                    self.candidate_count = 0
                    self.candidate_label = ""
            else:
                # New candidate — reset streak
                self.candidate_label = pred_label
                self.candidate_count = 1
        else:
            # No confident prediction: count down hold
            if self.hold_counter > 0:
                self.hold_counter -= 1
            else:
                self.display_label = ""
                self.display_conf = 0.0
                self.candidate_label = ""
                self.candidate_count = 0
            # If inference ran but wasn't confident, reset candidate streak
            if has_prediction:
                self.candidate_label = ""
                self.candidate_count = 0

        return self.display_label, self.display_conf


class SignPredictor:
    def __init__(self, bundle: ModelBundle, window: int = 60, ema_alpha: float = 0.7, vote_window: int = 5, vote_min_conf: float = 0.6):
        self.bundle = bundle
        self.window = window
        self.ema_alpha = ema_alpha
        self.vote_window = vote_window
        self.vote_min_conf = vote_min_conf

        self.buffer = deque(maxlen=window)
        self.ema_logits = None
        self.vote_labels = deque(maxlen=vote_window)
        self.vote_confs = deque(maxlen=vote_window)

        self.is_detecting = False
        self.last_inference_ms = 0.0
        self.inference_count = 0
        self.total_inference_ms = 0.0

    @property
    def avg_inference_ms(self) -> float:
        return self.total_inference_ms / max(1, self.inference_count)

    def push_frame(self, feat: np.ndarray, has_hand: bool):
        self.is_detecting = has_hand
        if not has_hand:
            self.buffer.clear()
            self.ema_logits = None
            return "", 0.0, False

        self.buffer.append(feat)
        return self._predict()

    def _predict(self):
        if len(self.buffer) < 5:
            return "", 0.0, False

        t0 = time.perf_counter()

        X = np.stack(list(self.buffer), axis=0)
        X_pad = np.zeros((1, self.window, self.bundle.in_dim), dtype=np.float32)
        t = min(self.window, X.shape[0])
        X_pad[0, -t:] = X[-t:]
        
        X_tf = tf.convert_to_tensor(X_pad, dtype=tf.float32)
        lengths_tf = tf.convert_to_tensor([min(X.shape[0], self.window)], dtype=tf.int32)

        logits = self.bundle.model([X_tf, lengths_tf], training=False).numpy()[0]

        if self.ema_logits is None:
            self.ema_logits = logits
        else:
            self.ema_logits = self.ema_alpha * self.ema_logits + (1 - self.ema_alpha) * logits

        probs = softmax(self.ema_logits)
        best_idx = int(np.argmax(probs))
        pred_label = self.bundle.label_map[best_idx]
        pred_conf = float(probs[best_idx])

        if pred_label and pred_conf >= self.vote_min_conf:
            self.vote_labels.append(pred_label)
            self.vote_confs.append(pred_conf)

        if self.vote_labels:
            counts = Counter(self.vote_labels)
            vote_label = counts.most_common(1)[0][0]
            confs = [c for l, c in zip(self.vote_labels, self.vote_confs) if l == vote_label]
            if confs:
                pred_label = vote_label
                pred_conf = float(sum(confs) / len(confs))

        elapsed_ms = (time.perf_counter() - t0) * 1000
        self.last_inference_ms = elapsed_ms
        self.total_inference_ms += elapsed_ms
        self.inference_count += 1

        return pred_label, pred_conf, True


def _clean_label(raw_label: str) -> str:
    """Extract display-friendly label from label_key (e.g. 'vn/xin-chao' -> 'Xin Chào')."""
    part = raw_label.split('/')[-1]  # strip language/dialect prefix
    return part.replace('-', ' ').title()


def render_prediction_overlay(
    frame: np.ndarray,
    disp_label: str,
    disp_conf: float,
    stability_state: dict,
    buffer_size: int,
    window_size: int,
    current_fps: float,
    avg_latency_ms: float,
    font_size: int,
    show_fps: bool,
) -> np.ndarray:
    """Render full overlay matching run_realtime_pro style."""
    h, w = frame.shape[:2]
    y_offset = 30

    # --- Prediction text + confidence bar ---
    if disp_label:
        clean = _clean_label(disp_label)
        txt = f"{clean} ({disp_conf*100:.1f}%)"
        frame = draw_text_vietnamese(frame, txt, (10, y_offset), (0, 255, 0), font_size)
        y_offset += font_size + 8

        # Confidence bar (matching pro visual style)
        bar_w = int(w * 0.35)
        bar_h = 8
        bar_x, bar_y = 10, y_offset
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (60, 60, 60), -1)
        filled = int(bar_w * disp_conf)
        bar_color = (0, 200, 100) if disp_conf >= 0.8 else (0, 165, 255) if disp_conf >= 0.6 else (0, 80, 200)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled, bar_y + bar_h), bar_color, -1)
        y_offset += bar_h + 8

    # --- Stats overlay (only when show_fps=True) ---
    if show_fps:
        small = font_size // 2
        stats_parts = [f"FPS:{current_fps:.1f}", f"Buf:{buffer_size}/{window_size}", f"Lat:{avg_latency_ms:.1f}ms"]

        cand = stability_state.get('candidate_label', '')
        cand_count = stability_state.get('candidate_count', 0)
        stable_req = stability_state.get('stable_frames_required', 3)
        if cand:
            stats_parts.append(f"Cand:{cand}({cand_count}/{stable_req})")

        hold = stability_state.get('hold_counter', 0)
        if hold > 0:
            stats_parts.append(f"Hold:{hold}")

        stats_txt = " | ".join(stats_parts)
        frame = draw_text_vietnamese(frame, stats_txt, (10, y_offset), (180, 180, 180), small)

    return frame


def main() -> None:
    parser = argparse.ArgumentParser(description='Realtime sign recognition using TCN/H5 + MediaPipe Hands')
    parser.add_argument('--checkpoint', type=Path, default=None, help='Path to .h5 checkpoint (optional)')
    parser.add_argument('--outputs_dir', type=Path, default=Path('processed/train_utils/outputs'))
    parser.add_argument('--dialect', type=str, default='', help="Load latest checkpoint for this dialect.")
    parser.add_argument('--tag', type=str, default='', help="Load latest checkpoint by tag.")
    parser.add_argument('--window', type=int, default=60, help='Temporal window size (frames)')
    parser.add_argument('--every', type=int, default=2, help='Run inference every N frames')
    parser.add_argument('--video', type=str, default='', help='Optional video file path; empty uses webcam')
    parser.add_argument('--device', type=str, default='CPU')
    parser.add_argument('--smoothing', type=float, default=0.7, help='EMA smoothing for logits [0-1]')
    parser.add_argument('--vote_window', type=int, default=5, help='Temporal voting window size')
    parser.add_argument('--vote_min_conf', type=float, default=0.6, help='Min confidence for voting')
    parser.add_argument('--max_latency_ms', type=float, default=50.0, help='Target max inference latency (ms)')
    parser.add_argument('--max_every', type=int, default=6, help='Max inference stride for latency control')
    parser.add_argument('--confidence_threshold', type=float, default=0.6, help='Min confidence to display [0-1]')
    parser.add_argument('--stable_frames', type=int, default=3, help='Frames needed to confirm label switch')
    parser.add_argument('--hold_frames', type=int, default=15, help='Frames to hold label after loss')
    parser.add_argument('--show_fps', action='store_true', help='Show FPS and stats overlay')
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
        meta_path = ckpt.with_suffix('.json')
        meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}

    print(f"[INFO] Loading checkpoint: {ckpt}")
    bundle = build_model_from_ckpt(ckpt, meta, args.device)
    in_dim = bundle.in_dim
    if in_dim != 126:
        raise SystemExit(f'Model in_dim={in_dim} must match feature extractor (126).')
    print(f"[INFO] Model: in_dim={in_dim}, num_classes={bundle.num_classes}, labels={bundle.label_map[:5]}...")

    hand_model = init_mediapipe()
    predictor = SignPredictor(
        bundle, 
        window=args.window, 
        ema_alpha=args.smoothing, 
        vote_window=args.vote_window, 
        vote_min_conf=args.vote_min_conf
    )
    stability_tracker = LabelStabilityTracker(
        stable_frames=args.stable_frames, 
        hold_frames=args.hold_frames, 
        min_conf=args.confidence_threshold
    )

    cap = ThreadedCamera(0 if not args.video else args.video)
    if not cap.isOpened():
        raise SystemExit('Could not open webcam/video')

    frame_idx = 0
    adaptive_every = max(1, args.every)
    
    fps_start_time = time.time()
    fps_frame_count = 0
    current_fps = 0.0
    
    t_start_ns = time.perf_counter_ns()

    try:
        with ThreadPoolExecutor(max_workers=2) as mp_executor:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                fps_frame_count += 1
                if fps_frame_count >= 30:
                    elapsed = time.time() - fps_start_time
                    current_fps = fps_frame_count / elapsed if elapsed > 0 else 0.0
                    fps_frame_count = 0
                    fps_start_time = time.time()

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                current_ms = (time.perf_counter_ns() - t_start_ns) // 1_000_000
                
                future_hands = mp_executor.submit(hand_model.detect_for_video, mp_image, current_ms)
                res_hands = future_hands.result()

                feat, frame_data_raw, has_hand = extract_hybrid(res_hands)

                # Draw landmarks on raw frame before flip
                draw_landmarks_cv2(frame, feat)
                vis = cv2.flip(frame, 1)

                pred_label, pred_conf, has_pred = predictor.push_frame(feat, has_hand)
                disp_label, disp_conf = stability_tracker.update(pred_label, pred_conf, has_pred)

                # Build stability state dict for stats display
                stability_state = {
                    'candidate_label': stability_tracker.candidate_label,
                    'candidate_count': stability_tracker.candidate_count,
                    'stable_frames_required': args.stable_frames,
                    'hold_counter': stability_tracker.hold_counter,
                }

                vis = render_prediction_overlay(
                    vis,
                    disp_label, disp_conf,
                    stability_state,
                    buffer_size=len(predictor.buffer),
                    window_size=args.window,
                    current_fps=current_fps,
                    avg_latency_ms=predictor.avg_inference_ms,
                    font_size=args.font_size,
                    show_fps=args.show_fps,
                )

                cv2.imshow("Sign Recognition H5 (q to quit)", vis)

                frame_idx += 1
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    finally:
        cap.release()
        hand_model.close()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

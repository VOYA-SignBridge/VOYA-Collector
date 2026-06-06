from __future__ import annotations
from PIL import Image, ImageDraw, ImageFont

import argparse
import json
import re
import time
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
    for url, path in [(_HAND_LANDMARKER_MODEL_URL, _HAND_LANDMARKER_MODEL_PATH),
                      (_POSE_LANDMARKER_MODEL_URL, _POSE_LANDMARKER_MODEL_PATH)]:
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
    
    pose_options = mp.tasks.vision.PoseLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(_POSE_LANDMARKER_MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_segmentation_masks=False,
    )
    
    hands_options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(_HAND_LANDMARKER_MODEL_PATH)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
        min_hand_detection_confidence=0.5,
        min_hand_presence_confidence=0.5,
        min_tracking_confidence=0.5
    )
    
    return (mp.tasks.vision.PoseLandmarker.create_from_options(pose_options),
            mp.tasks.vision.HandLandmarker.create_from_options(hands_options))


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
        # fallback: pick latest .h5
        h5s = sorted(out_dir.glob('tcn_*.h5'))
        if not h5s:
            raise FileNotFoundError('No checkpoint found')
        ckpt = h5s[-1]
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

    # Rebuild Model in Python (bypassing Keras Config serialization bugs entirely!)
    model = build_tcn_model(
        in_dim=in_dim,
        num_classes=num_classes,
        channels=int(meta.get('channels', 64)),
        levels=int(meta.get('levels', 3)),
        kernel_size=int(meta.get('kernel_size', 5)),
        dropout=0.0 # set dropout to 0 for inference
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


class HandTracker:
    class _P:
        __slots__ = ('x', 'y')
        def __init__(self, x: float, y: float): self.x = x; self.y = y

    def __init__(self, ema_alpha: float = 0.45, miss_ttl: int = 5, max_jump: float = 0.28):
        self.alpha    = ema_alpha
        self.ttl      = miss_ttl
        self.max_jump = max_jump
        self._ema_l   = None
        self._ema_r   = None
        self._miss_l  = 0
        self._miss_r  = 0

    def anchors(self):
        P = self._P
        return (
            P(*self._ema_l) if self._ema_l else None,
            P(*self._ema_r) if self._ema_r else None,
        )

    def is_plausible(self, x: float, y: float, slot: int) -> bool:
        ema = self._ema_l if slot == LHAND_START else self._ema_r
        if ema is None:
            return True
        return ((x - ema[0])**2 + (y - ema[1])**2)**0.5 < self.max_jump

    def update(self, frame_data_42x3: np.ndarray):
        """Cập nhật EMA từ frame_data dạng (42,3) còn NaN (raw từ extract_hybrid).
        Dùng NaN để phân biệt tay không có vs tay ở tọa độ gần (0,0)."""
        vec = frame_data_42x3
        def _upd(ema, miss, slot):
            w = vec[slot]
            if not np.isnan(w[0]):  # NaN = không có tay; 0.0 hợp lệ = tay ở góc màn hình
                wx, wy = float(w[0]), float(w[1])
                if ema is None:
                    return (wx, wy), 0
                return (self.alpha*wx + (1-self.alpha)*ema[0],
                        self.alpha*wy + (1-self.alpha)*ema[1]), 0
            miss += 1
            return (None if miss >= self.ttl else ema), miss
        self._ema_l, self._miss_l = _upd(self._ema_l, self._miss_l, LHAND_START)
        self._ema_r, self._miss_r = _upd(self._ema_r, self._miss_r, RHAND_START)

    def reset(self):
        self._ema_l = self._ema_r = None
        self._miss_l = self._miss_r = 0


def extract_hybrid(res_pose, res_hands, tracker=None) -> Tuple[np.ndarray, bool]:
    frame_data = np.full((42, 3), np.nan, dtype=np.float32)

    anchor_l = None
    anchor_r = None
    if tracker is not None:
        anchor_l, anchor_r = tracker.anchors()

    if res_pose and res_pose.pose_landmarks and len(res_pose.pose_landmarks) > 0:
        pose_lms = res_pose.pose_landmarks[0]
        if anchor_l is None and getattr(pose_lms[15], 'visibility', 1.0) > 0.4:
            anchor_l = pose_lms[15]
        if anchor_r is None and getattr(pose_lms[16], 'visibility', 1.0) > 0.4:
            anchor_r = pose_lms[16]

    def _dist(a, b):
        return ((a.x - b.x)**2 + (a.y - b.y)**2) ** 0.5

    def _slot_for_hand(wrist) -> int:
        if anchor_l is not None and anchor_r is not None:
            slot = LHAND_START if _dist(wrist, anchor_l) < _dist(wrist, anchor_r) else RHAND_START
        elif anchor_l is not None:
            slot = LHAND_START if _dist(wrist, anchor_l) < 0.15 else RHAND_START
        elif anchor_r is not None:
            slot = RHAND_START if _dist(wrist, anchor_r) < 0.15 else LHAND_START
        else:
            slot = LHAND_START if wrist.x >= 0.5 else RHAND_START

        if tracker is not None and not tracker.is_plausible(wrist.x, wrist.y, slot):
            other = RHAND_START if slot == LHAND_START else LHAND_START
            if tracker.is_plausible(wrist.x, wrist.y, other):
                slot = other
        return slot

    def _is_duplicate_hand(wrist, threshold=0.1):
        if not np.isnan(frame_data[LHAND_START, 0]):
            l_wrist = frame_data[LHAND_START]
            if ((wrist.x - l_wrist[0])**2 + (wrist.y - l_wrist[1])**2)**0.5 < threshold:
                return True
        if not np.isnan(frame_data[RHAND_START, 0]):
            r_wrist = frame_data[RHAND_START]
            if ((wrist.x - r_wrist[0])**2 + (wrist.y - r_wrist[1])**2)**0.5 < threshold:
                return True
        return False

    if res_hands and res_hands.hand_landmarks:
        for hand_lms in res_hands.hand_landmarks:
            wrist = hand_lms[0]
            slot  = _slot_for_hand(wrist)
            if np.isnan(frame_data[slot, 0]) and not _is_duplicate_hand(wrist):
                for i, lm in enumerate(hand_lms):
                    if i < 21:
                        frame_data[slot + i] = [lm.x, lm.y, lm.z]

    has_hand = not (np.isnan(frame_data[LHAND_START, 0]) and np.isnan(frame_data[RHAND_START, 0]))
    # Return raw frame_data (with NaN) for tracker, and also a flat 0-filled feat for the model
    feat_126 = np.nan_to_num(frame_data, nan=0.0).reshape(126)
    return feat_126, frame_data, has_hand


def draw_landmarks_cv2(frame: np.ndarray, feat_126: np.ndarray) -> np.ndarray:
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


class SignPredictor:
    def __init__(self, bundle: ModelBundle, window: int = 60, slide: int = 30, topk: int = 3):
        self.bundle = bundle
        self.window = window
        self.slide = slide
        self.topk = topk

        self.buffer = []

        self.last_label = ""
        self.last_confidence = 0.0
        self.is_detecting = False
        self.hand_detected = False
        self._grace_count = 0
        self._recent_labels = []
        self._last_known_vec = None

        self.GRACE_MAX = 8
        self.CLEAR_AFTER = 20

    def push_frame(self, feat: np.ndarray, has_hand: bool) -> bool:
        self.hand_detected = has_hand

        if has_hand:
            self.is_detecting = True
            self._grace_count = 0
            self._last_known_vec = feat.copy()
            self.buffer.append(feat)
        elif self._grace_count < self.GRACE_MAX and self._last_known_vec is not None:
            self._grace_count += 1
            self.buffer.append(self._last_known_vec)
        else:
            self._grace_count += 1
            if self._grace_count >= self.CLEAR_AFTER:
                self.buffer = []
                self.is_detecting = False
                self._last_known_vec = None

        if len(self.buffer) >= self.window:
            self._predict()
            self.buffer = self.buffer[self.slide:]
            return True

        return False

    def _predict(self):
        seq = np.stack(self.buffer[:self.window], axis=0)
        X_tf = tf.convert_to_tensor(seq[None, ...], dtype=tf.float32)
        lengths_tf = tf.convert_to_tensor([self.window], dtype=tf.int32)

        logits = self.bundle.model([X_tf, lengths_tf], training=False)
        probs = softmax(logits.numpy()[0])

        top_idx = np.argsort(probs)[::-1][:self.topk]
        best_idx = top_idx[0]
        raw_label = self.bundle.label_map[best_idx]
        raw_conf = float(probs[best_idx])

        self._recent_labels.append(raw_label)
        if len(self._recent_labels) > 3:
            self._recent_labels.pop(0)

        from collections import Counter
        vote = Counter(self._recent_labels).most_common(1)[0]
        if vote[1] >= 2:
            self.last_label = raw_label
            self.last_confidence = raw_conf

    def reset(self):
        self.buffer = []
        self.last_label = ""
        self.last_confidence = 0.0
        self.is_detecting = False
        self._grace_count = 0
        self._recent_labels = []
        self._last_known_vec = None


def main() -> None:
    parser = argparse.ArgumentParser(description='Realtime sign recognition using TCN + MediaPipe Hands')
    parser.add_argument('--checkpoint', type=Path, default=None, help='Path to .h5 checkpoint (optional)')
    parser.add_argument('--outputs_dir', type=Path, default=Path('processed/train_utils/outputs'))
    parser.add_argument('--dialect', type=str, default='', help="Load latest checkpoint for this dialect (e.g. 'hoa-de').")
    parser.add_argument('--tag', type=str, default='', help="Load latest checkpoint by tag (matches trainer prefix, e.g. 'dialect-hoa-de').")
    parser.add_argument('--window', type=int, default=60, help='Temporal window size (frames)')
    parser.add_argument('--every', type=int, default=2, help='Run inference every N frames')
    parser.add_argument('--video', type=str, default='', help='Optional video file path; empty uses webcam')
    parser.add_argument('--device', type=str, default='CPU')
    parser.add_argument('--smoothing', type=float, default=0.7, help='EMA smoothing for logits [0-1]')
    parser.add_argument('--vote_window', type=int, default=5, help='Temporal voting window size (predictions)')
    parser.add_argument('--vote_min_conf', type=float, default=0.6, help='Min confidence to include in voting [0-1]')
    parser.add_argument('--max_latency_ms', type=float, default=50.0, help='Target max inference latency in ms')
    parser.add_argument('--max_every', type=int, default=6, help='Max inference stride for latency control')
    
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
        meta_path = ckpt.with_suffix('.json')
        meta = json.loads(meta_path.read_text(encoding='utf-8')) if meta_path.exists() else {}

    bundle = build_model_from_ckpt(ckpt, meta, args.device)
    in_dim = bundle.in_dim
    if in_dim != 126:
        raise SystemExit(f'Model in_dim={in_dim} must match feature extractor (126).')

    pose_model, hand_model = init_mediapipe()
    tracker = HandTracker()
    predictor = SignPredictor(bundle, window=args.window, slide=args.window // 2)

    cap = cv2.VideoCapture(0 if not args.video else args.video)
    if not cap.isOpened():
        raise SystemExit('Could not open webcam/video')

    frame_idx = 0
    
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
                
                future_pose = mp_executor.submit(pose_model.detect_for_video, mp_image, current_ms)
                future_hands = mp_executor.submit(hand_model.detect_for_video, mp_image, current_ms)
                res_pose = future_pose.result()
                res_hands = future_hands.result()

                feat, frame_data_raw, has_hand = extract_hybrid(res_pose, res_hands, tracker)
                tracker.update(frame_data_raw)

                draw_landmarks_cv2(frame, feat)
                vis = cv2.flip(frame, 1)

                predictor.push_frame(feat, has_hand)

                y_offset = 30
                if predictor.last_label and predictor.last_confidence >= args.confidence_threshold:
                    clean_label = predictor.last_label.split('/')[-1].replace('-', ' ')
                    txt = f"{clean_label.capitalize()} ({predictor.last_confidence*100:.1f}%)"
                    vis = draw_text_vietnamese(vis, txt, (10, y_offset), (0, 255, 0), args.font_size)
                    y_offset += args.font_size + 10
                
                if args.show_fps:
                    stats_lines = [
                        f"FPS: {current_fps:.1f}",
                        f"Buffer: {len(predictor.buffer)}/{args.window}",
                        f"Detecting: {predictor.is_detecting}",
                    ]
                    stats_text = " | ".join(stats_lines)
                    vis = draw_text_vietnamese(vis, stats_text, (10, y_offset), (200, 200, 200), args.font_size // 2)

                cv2.imshow("Sign Recognition (q to quit)", vis)

                frame_idx += 1
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    finally:
        cap.release()
        pose_model.close()
        hand_model.close()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()

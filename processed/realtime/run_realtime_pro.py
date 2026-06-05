"""
Professional Real-time Sign Language Recognition System
========================================================

A production-ready implementation featuring:
- Class-based architecture for maintainability
- Comprehensive logging and monitoring
- Configuration management
- Error handling and recovery
- Performance optimization
- Metrics collection
- Professional visualization

Author: VOYA Team
Version: 2.0.0
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import mediapipe as mp
except ImportError:
    mp = None

import torch
import torch.nn as nn
try:
    from train_model.dataset_versioning import get_analysis_dir
except Exception:
    get_analysis_dir = None  # type: ignore


# ============================================================================
# Configuration Management
# ============================================================================

@dataclass
class ModelConfig:
    """Model architecture configuration."""
    in_dim: int = 126
    num_classes: int = 10
    channels: int = 64
    levels: int = 3
    kernel_size: int = 5
    dropout: float = 0.3


@dataclass
class InferenceConfig:
    """Inference pipeline configuration."""
    window_size: int = 60
    min_buffer_size: int = 8
    inference_every_n_frames: int = 2
    ema_alpha: float = 0.7
    confidence_threshold: float = 0.6
    vote_window: int = 5
    vote_min_confidence: float = 0.6
    max_latency_ms: float = 50.0
    max_every: int = 6
    device: str = "cuda" if torch.cuda.is_available() else "cpu"


@dataclass
class StabilityConfig:
    """Label stability and persistence configuration."""
    stable_frames_required: int = 3
    hold_frames_after_loss: int = 15
    min_confidence_display: float = 0.6


@dataclass
class MediaPipeConfig:
    """MediaPipe Hands configuration."""
    static_image_mode: bool = False
    max_num_hands: int = 2
    model_complexity: int = 1
    min_detection_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


@dataclass
class VisualizationConfig:
    """Visualization and display configuration."""
    font_size: int = 32
    stats_font_size: int = 16
    show_fps: bool = False
    show_confidence: bool = True
    show_landmarks: bool = True
    window_name: str = "Sign Language Recognition"
    
    # Colors (BGR format)
    color_prediction: Tuple[int, int, int] = (0, 255, 0)
    color_stats: Tuple[int, int, int] = (200, 200, 200)
    color_warning: Tuple[int, int, int] = (0, 165, 255)
    color_outline: Tuple[int, int, int] = (0, 0, 0)


@dataclass
class SystemConfig:
    """Main system configuration."""
    model: ModelConfig = field(default_factory=ModelConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    stability: StabilityConfig = field(default_factory=StabilityConfig)
    mediapipe: MediaPipeConfig = field(default_factory=MediaPipeConfig)
    visualization: VisualizationConfig = field(default_factory=VisualizationConfig)
    
    checkpoint_path: Optional[Path] = None
    outputs_dir: Path = Path("processed/train_utils/outputs")
    video_source: str = ""  # Empty for webcam
    log_level: str = "INFO"
    enable_metrics: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> SystemConfig:
        """Create configuration from command-line arguments."""
        config = cls()
        
        # Update from args
        config.checkpoint_path = args.checkpoint
        config.outputs_dir = args.outputs_dir
        config.video_source = args.video
        config.log_level = args.log_level
        
        config.inference.window_size = args.window
        config.inference.inference_every_n_frames = args.every
        config.inference.ema_alpha = args.smoothing
        config.inference.device = args.device
        config.inference.vote_window = args.vote_window
        config.inference.vote_min_confidence = args.vote_min_conf
        config.inference.max_latency_ms = args.max_latency_ms
        config.inference.max_every = args.max_every
        
        config.stability.stable_frames_required = args.stable_frames
        config.stability.hold_frames_after_loss = args.hold_frames
        config.stability.min_confidence_display = args.confidence_threshold
        
        config.visualization.show_fps = args.show_fps
        config.visualization.font_size = args.font_size
        config.enable_metrics = args.enable_metrics
        
        return config


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Setup structured logging."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level.upper()))
    
    # Console handler with formatting
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    return logger


# ============================================================================
# Metrics Collection
# ============================================================================

@dataclass
class PerformanceMetrics:
    """Performance metrics collector."""
    frame_count: int = 0
    inference_count: int = 0
    total_inference_time: float = 0.0
    total_preprocessing_time: float = 0.0
    
    fps_history: Deque[float] = field(default_factory=lambda: deque(maxlen=30))
    latency_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    confidence_history: Deque[float] = field(default_factory=lambda: deque(maxlen=100))
    
    def update_inference(self, duration: float, confidence: float):
        """Update inference metrics."""
        self.inference_count += 1
        self.total_inference_time += duration
        self.latency_history.append(duration * 1000)  # ms
        self.confidence_history.append(confidence)
    
    def update_fps(self, fps: float):
        """Update FPS metric."""
        self.fps_history.append(fps)
    
    @property
    def avg_inference_time(self) -> float:
        """Average inference time in ms."""
        if self.inference_count == 0:
            return 0.0
        return (self.total_inference_time / self.inference_count) * 1000
    
    @property
    def avg_confidence(self) -> float:
        """Average confidence score."""
        if not self.confidence_history:
            return 0.0
        return float(np.mean(self.confidence_history))
    
    @property
    def current_fps(self) -> float:
        """Current FPS estimate."""
        if not self.fps_history:
            return 0.0
        return float(np.mean(self.fps_history))
    
    def get_summary(self) -> Dict[str, float]:
        """Get metrics summary."""
        return {
            "avg_inference_ms": self.avg_inference_time,
            "avg_confidence": self.avg_confidence,
            "current_fps": self.current_fps,
            "total_frames": self.frame_count,
            "total_inferences": self.inference_count,
        }


# ============================================================================
# Model Architecture (TCN)
# ============================================================================

class Chomp1d(nn.Module):
    """Chomping layer to ensure causality in TCN."""
    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, : x.size(2) - self.chomp_size]


class TemporalBlock(nn.Module):
    """Temporal block with dilated convolutions and residual connection."""
    def __init__(
        self, 
        in_channels: int, 
        out_channels: int, 
        kernel_size: int, 
        dilation: int, 
        dropout: float
    ):
        super().__init__()
        pad = (kernel_size - 1) * dilation
        
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size, 
                              padding=pad, dilation=dilation)
        self.chomp1 = Chomp1d(pad)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)
        
        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size, 
                              padding=pad, dilation=dilation)
        self.chomp2 = Chomp1d(pad)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)
        
        self.downsample = (
            nn.Conv1d(in_channels, out_channels, 1) 
            if in_channels != out_channels else None
        )
        self.out_relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.drop1(self.relu1(self.chomp1(self.conv1(x))))
        out = self.drop2(self.relu2(self.chomp2(self.conv2(out))))
        res = x if self.downsample is None else self.downsample(x)
        return self.out_relu(out + res)


class TCNClassifier(nn.Module):
    """Temporal Convolutional Network for sequence classification."""
    def __init__(
        self, 
        in_dim: int, 
        num_classes: int, 
        channels: int = 64, 
        levels: int = 3, 
        kernel_size: int = 5, 
        dropout: float = 0.3
    ):
        super().__init__()
        self.proj = nn.Conv1d(in_dim, channels, kernel_size=1)
        
        blocks = []
        for i in range(levels):
            dilation = 2 ** i
            blocks.append(TemporalBlock(channels, channels, kernel_size, dilation, dropout))
        self.network = nn.Sequential(*blocks)
        
        self.classifier = nn.Linear(channels, num_classes)

    def forward(self, x_btd: torch.Tensor, lengths: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x_btd: [B, T, D] - Batch, Time, Features
            lengths: [B] - Actual sequence lengths
        
        Returns:
            logits: [B, num_classes]
        """
        # Transpose to [B, D, T] for Conv1d
        x = x_btd.transpose(1, 2)
        x = self.proj(x)
        x = self.network(x)
        
        # Masked Global Average Pooling
        b, c, t = x.shape
        mask = torch.arange(t, device=x.device).unsqueeze(0) < lengths.unsqueeze(1)
        mask = mask.unsqueeze(1)
        x = x.masked_fill(~mask, 0.0)
        
        denom = lengths.clamp(min=1).unsqueeze(1).to(x.dtype)
        pooled = x.sum(dim=2) / denom
        
        logits = self.classifier(pooled)
        return logits


# ============================================================================
# Model Bundle & Loading
# ============================================================================

@dataclass
class ModelBundle:
    """Container for model and metadata."""
    model: nn.Module
    in_dim: int
    num_classes: int
    label_map: List[str]
    device: str
    
    def predict(self, features: torch.Tensor, lengths: torch.Tensor) -> Tuple[np.ndarray, np.ndarray]:
        """
        Run prediction.
        
        Returns:
            logits: [num_classes]
            probs: [num_classes]
        """
        with torch.no_grad():
            logits = self.model(features, lengths)
            logits_np = logits.cpu().numpy()[0]
            probs = self._softmax(logits_np)
        return logits_np, probs
    
    @staticmethod
    def _softmax(x: np.ndarray) -> np.ndarray:
        """Numerically stable softmax."""
        x = x - x.max()
        e = np.exp(x)
        return e / e.sum()


def load_checkpoint(checkpoint_path: Path, device: str, logger: logging.Logger) -> ModelBundle:
    """Load model from checkpoint."""
    logger.info(f"Loading checkpoint from {checkpoint_path}")
    
    # Workaround for Python 3.13 checkpoint loaded in Python 3.12
    import sys
    import pathlib
    if 'pathlib._local' not in sys.modules:
        sys.modules['pathlib._local'] = pathlib
    
    try:
        obj = torch.load(checkpoint_path, map_location=device, weights_only=False)
    except Exception as e:
        logger.error(f"Failed to load checkpoint: {e}")
        raise
    
    in_dim = int(obj.get('in_dim', 126))
    num_classes = int(obj.get('num_classes'))
    
    # Build model
    model = TCNClassifier(in_dim=in_dim, num_classes=num_classes)
    model.load_state_dict(obj['model_state'])
    model.to(device).eval()
    
    logger.info(f"Model loaded: in_dim={in_dim}, num_classes={num_classes}, device={device}")
    
    # Load label map
    label_map = _load_label_map(num_classes, logger)
    
    return ModelBundle(
        model=model,
        in_dim=in_dim,
        num_classes=num_classes,
        label_map=label_map,
        device=device,
    )


def _load_label_map(num_classes: int, logger: logging.Logger) -> List[str]:
    """Load label mapping from index_to_label.json."""
    if get_analysis_dir:
        label_file = get_analysis_dir() / 'index_to_label.json'
    else:
        root = Path(__file__).resolve().parents[2]
        label_file = root / 'processed' / 'analysis' / 'index_to_label.json'
    
    # Default fallback
    label_map = [f"Class_{i}" for i in range(num_classes)]
    
    if not label_file.exists():
        logger.warning(f"Label map not found at {label_file}, using defaults")
        return label_map
    
    try:
        data = json.loads(label_file.read_text(encoding='utf-8'))
        if isinstance(data, dict):
            label_map = []
            for i in range(num_classes):
                entry = data.get(str(i), {})
                name = entry.get('label_original', f"Class_{i}")
                label_map.append(name)
            logger.info(f"Loaded {len(label_map)} labels from {label_file}")
    except Exception as e:
        logger.warning(f"Failed to load label map: {e}, using defaults")
    
    return label_map


def find_latest_checkpoint(outputs_dir: Path, logger: logging.Logger) -> Path:
    """Find the latest checkpoint in outputs directory."""
    # Try to find summary files
    summaries = sorted(outputs_dir.glob('tcn_*.json'))
    if summaries:
        latest = summaries[-1]
        meta = json.loads(latest.read_text(encoding='utf-8'))
        ckpt = Path(meta.get('checkpoint', ''))
        if ckpt.exists():
            logger.info(f"Found checkpoint from summary: {ckpt}")
            return ckpt
    
    # Fallback: find latest .pt file
    checkpoints = sorted(outputs_dir.glob('tcn_*.pt'))
    if not checkpoints:
        raise FileNotFoundError(f"No checkpoints found in {outputs_dir}")
    
    ckpt = checkpoints[-1]
    logger.info(f"Found latest checkpoint: {ckpt}")
    return ckpt


# ============================================================================
# Feature Extraction
# ============================================================================

class HandFeatureExtractor:
    """MediaPipe-based hand feature extractor."""
    
    def __init__(self, config: MediaPipeConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        if mp is None:
            raise ImportError("MediaPipe not installed. Run: pip install mediapipe")
        
        self.hands = mp.solutions.hands.Hands(
            static_image_mode=config.static_image_mode,
            max_num_hands=config.max_num_hands,
            model_complexity=config.model_complexity,
            min_detection_confidence=config.min_detection_confidence,
            min_tracking_confidence=config.min_tracking_confidence,
        )
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_hands = mp.solutions.hands
        
        self.logger.info("HandFeatureExtractor initialized")
    
    def extract(self, frame_bgr: np.ndarray, draw_landmarks: bool = True) -> Tuple[np.ndarray, np.ndarray, bool]:
        """
        Extract hand features from frame.
        
        Args:
            frame_bgr: Input frame in BGR format
            draw_landmarks: Whether to draw landmarks on frame
        
        Returns:
            features: [126] - Concatenated left/right hand landmarks
            frame_bgr: Frame with landmarks drawn (if draw_landmarks=True)
            has_hand: Whether any hand was detected
        """
        h, w = frame_bgr.shape[:2]
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        result = self.hands.process(frame_rgb)
        
        left = np.zeros((21, 3), dtype=np.float32)
        right = np.zeros((21, 3), dtype=np.float32)
        has_hand = False
        
        if result.multi_hand_landmarks and result.multi_handedness:
            has_hand = True
            for lm, hd in zip(result.multi_hand_landmarks, result.multi_handedness):
                label = hd.classification[0].label.lower()
                coords = np.array([[p.x, p.y, p.z] for p in lm.landmark], dtype=np.float32)
                
                if label == 'left':
                    left = coords
                else:
                    right = coords
                
                if draw_landmarks:
                    self.mp_drawing.draw_landmarks(
                        frame_bgr, lm, self.mp_hands.HAND_CONNECTIONS
                    )
        
        features = np.concatenate([left.reshape(-1), right.reshape(-1)], axis=0)
        return features, frame_bgr, has_hand
    
    def close(self):
        """Release resources."""
        self.hands.close()
        self.logger.info("HandFeatureExtractor closed")


# ============================================================================
# Label Stability Tracker
# ============================================================================

class LabelStabilityTracker:
    """Tracks label stability with hysteresis to reduce flickering."""
    
    def __init__(self, config: StabilityConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        self.display_label: str = ""
        self.display_conf: float = 0.0
        self.candidate_label: str = ""
        self.candidate_count: int = 0
        self.hold_counter: int = 0
        
        self.logger.debug("LabelStabilityTracker initialized")
    
    def update(self, pred_label: str, pred_conf: float, has_prediction: bool = True) -> Tuple[str, float]:
        """
        Update with new prediction.
        
        Args:
            pred_label: Predicted label
            pred_conf: Prediction confidence
        
        Returns:
            display_label: Label to display
            display_conf: Confidence to display
        """
        # Only process candidate/switching when a prediction was produced.
        # Frames where inference is skipped (--every) should NOT break the streak.
        if has_prediction and pred_label and pred_conf >= self.config.min_confidence_display:
            if pred_label == self.display_label:
                # Same label: refresh
                self.display_conf = pred_conf
                self.hold_counter = self.config.hold_frames_after_loss
                self.candidate_label = ""
                self.candidate_count = 0
            elif pred_label == self.candidate_label:
                # Building consensus
                self.candidate_count += 1
                if self.candidate_count >= self.config.stable_frames_required:
                    # Switch to new label
                    self.logger.debug(f"Label switched: {self.display_label} -> {pred_label}")
                    self.display_label = pred_label
                    self.display_conf = pred_conf
                    self.hold_counter = self.config.hold_frames_after_loss
                    self.candidate_count = 0
                    self.candidate_label = ""
            else:
                # New candidate
                self.candidate_label = pred_label
                self.candidate_count = 1
        else:
            # No confident prediction: use hold counter
            if self.hold_counter > 0:
                self.hold_counter -= 1
            else:
                if self.display_label:
                    self.logger.debug(f"Label cleared: {self.display_label}")
                    self.display_label = ""
                    self.display_conf = 0.0
                    self.candidate_label = ""
                    self.candidate_count = 0

            # If we DID run inference but it wasn't confident enough,
            # reset the candidate so stability requires consecutive confident hits.
            if has_prediction:
                self.candidate_label = ""
                self.candidate_count = 0
        
        return self.display_label, self.display_conf
    
    def reset(self):
        """Reset all state."""
        self.display_label = ""
        self.display_conf = 0.0
        self.candidate_label = ""
        self.candidate_count = 0
        self.hold_counter = 0
        self.logger.debug("Stability tracker reset")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state for debugging."""
        return {
            "display_label": self.display_label,
            "display_conf": self.display_conf,
            "candidate_label": self.candidate_label,
            "candidate_count": self.candidate_count,
            "hold_counter": self.hold_counter,
            "stable_frames_required": self.config.stable_frames_required,
        }


# ============================================================================
# Visualization
# ============================================================================

class VisualizationManager:
    """Manages all visualization and overlay rendering."""
    
    def __init__(self, config: VisualizationConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        
        # Try to load fonts
        self.font = self._load_font(config.font_size)
        self.stats_font = self._load_font(config.stats_font_size)
        
        self.logger.info("VisualizationManager initialized")
    
    def _load_font(self, size: int) -> ImageFont.FreeTypeFont:
        """Load TrueType font with fallback."""
        font_paths = [
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\ARIALUNI.TTF",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        
        for path in font_paths:
            try:
                return ImageFont.truetype(path, size)
            except:
                continue
        
        self.logger.warning(f"Could not load TrueType font, using default")
        return ImageFont.load_default()
    
    def draw_text_with_outline(
        self, 
        frame: np.ndarray, 
        text: str, 
        pos: Tuple[int, int], 
        color: Tuple[int, int, int],
        font: ImageFont.FreeTypeFont,
        outline_width: int = 2
    ) -> np.ndarray:
        """Draw text with outline using PIL."""
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        draw = ImageDraw.Draw(pil_img)
        
        x, y = pos
        # Draw outline
        for dx in range(-outline_width, outline_width + 1):
            for dy in range(-outline_width, outline_width + 1):
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), text, font=font, fill=self.config.color_outline)
        
        # Draw main text
        draw.text(pos, text, font=font, fill=color)
        
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    
    def render_prediction(
        self, 
        frame: np.ndarray, 
        label: str, 
        confidence: float
    ) -> np.ndarray:
        """Render prediction on frame."""
        if not label:
            return frame
        
        text = f"{label} ({confidence*100:.1f}%)" if self.config.show_confidence else label
        frame = self.draw_text_with_outline(
            frame, text, (10, 30), 
            self.config.color_prediction, 
            self.font
        )
        return frame
    
    def render_stats(
        self, 
        frame: np.ndarray, 
        metrics: PerformanceMetrics,
        buffer_size: int,
        window_size: int,
        stability_state: Dict[str, Any]
    ) -> np.ndarray:
        """Render statistics overlay."""
        if not self.config.show_fps:
            return frame
        
        stats_lines = [
            f"FPS: {metrics.current_fps:.1f}",
            f"Buffer: {buffer_size}/{window_size}",
            f"Latency: {metrics.avg_inference_time:.1f}ms",
        ]
        
        # Add candidate info
        if stability_state['candidate_label']:
            stable_req = stability_state.get('stable_frames_required', 3)
            stats_lines.append(
                f"Candidate: {stability_state['candidate_label']} "
                f"({stability_state['candidate_count']}/{stable_req})"
            )
        
        # Add hold info
        if stability_state['hold_counter'] > 0:
            stats_lines.append(f"Hold: {stability_state['hold_counter']}")
        
        text = " | ".join(stats_lines)
        y_offset = 30 + self.config.font_size + 10
        
        frame = self.draw_text_with_outline(
            frame, text, (10, y_offset),
            self.config.color_stats,
            self.stats_font,
            outline_width=1
        )
        
        return frame
    
    def render_warning(self, frame: np.ndarray, message: str) -> np.ndarray:
        """Render warning message."""
        frame = self.draw_text_with_outline(
            frame, message, (10, 30),
            self.config.color_warning,
            self.font
        )
        return frame


# ============================================================================
# Main Recognition System
# ============================================================================

class SignLanguageRecognizer:
    """Main real-time sign language recognition system."""
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = setup_logger(__name__, config.log_level)
        
        self.logger.info("=" * 60)
        self.logger.info("Sign Language Recognition System v2.0")
        self.logger.info("=" * 60)
        
        # Initialize components
        self._init_model()
        self._init_feature_extractor()
        self._init_video_capture()
        self._init_processing_pipeline()
        self._init_visualization()
        
        # Metrics
        self.metrics = PerformanceMetrics() if config.enable_metrics else None
        
        self.logger.info("System initialized successfully")
    
    def _init_model(self):
        """Initialize model."""
        if self.config.checkpoint_path is None:
            self.config.checkpoint_path = find_latest_checkpoint(
                self.config.outputs_dir, self.logger
            )
        
        self.model_bundle = load_checkpoint(
            self.config.checkpoint_path,
            self.config.inference.device,
            self.logger
        )
        
        # Validate feature dimension
        if self.model_bundle.in_dim != 126:
            raise RuntimeError(
                f"Model in_dim={self.model_bundle.in_dim} must match extractor (126)."
            )
    
    def _init_feature_extractor(self):
        """Initialize hand feature extractor."""
        self.extractor = HandFeatureExtractor(self.config.mediapipe, self.logger)
    
    def _init_video_capture(self):
        """Initialize video capture."""
        if cv2 is None:
            raise ImportError("OpenCV not installed. Run: pip install opencv-python")
        
        source = self.config.video_source or 0
        self.cap = cv2.VideoCapture(source)
        
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video source: {source}")
        
        self.logger.info(f"Video capture initialized: {source}")
    
    def _init_processing_pipeline(self):
        """Initialize processing pipeline."""
        self.buffer: Deque[np.ndarray] = deque(maxlen=self.config.inference.window_size)
        self.ema_logits: Optional[np.ndarray] = None
        self.frame_idx = 0
        self.vote_labels: Deque[str] = deque(maxlen=max(1, int(self.config.inference.vote_window)))
        self.vote_confs: Deque[float] = deque(maxlen=max(1, int(self.config.inference.vote_window)))
        self.adaptive_every = max(1, int(self.config.inference.inference_every_n_frames))
        
        self.stability_tracker = LabelStabilityTracker(
            self.config.stability, self.logger
        )
    
    def _init_visualization(self):
        """Initialize visualization."""
        self.viz_manager = VisualizationManager(self.config.visualization, self.logger)
    
    def _process_frame_features(self, features: np.ndarray) -> np.ndarray:
        """Process features (pad/truncate only; no normalization)."""
        in_dim = self.model_bundle.in_dim
        
        # Pad or truncate to match model input dimension
        if features.shape[0] < in_dim:
            features = np.pad(features, (0, in_dim - features.shape[0]))
        elif features.shape[0] > in_dim:
            features = features[:in_dim]
        
        return features.astype(np.float32)
    
    def _run_inference(self) -> Tuple[str, float, float]:
        """
        Run model inference on current buffer.
        
        Returns:
            pred_label: Predicted label
            pred_conf: Prediction confidence
        """
        if len(self.buffer) < self.config.inference.min_buffer_size:
            return "", 0.0, 0.0
        
        # Prepare input
        X = np.stack(list(self.buffer), axis=0)  # [T, D]
        lengths = torch.tensor([X.shape[0]], dtype=torch.long, device=self.model_bundle.device)
        
        # Pad to window size
        X_pad = np.zeros((1, self.config.inference.window_size, self.model_bundle.in_dim), 
                        dtype=np.float32)
        t = min(self.config.inference.window_size, X.shape[0])
        X_pad[0, -t:] = X[-t:]
        
        # Run inference
        start_time = time.time()
        logits, probs = self.model_bundle.predict(
            torch.from_numpy(X_pad).to(self.model_bundle.device),
            lengths
        )
        inference_time = time.time() - start_time
        inference_time_ms = inference_time * 1000.0
        
        # Apply EMA smoothing
        if self.ema_logits is None:
            self.ema_logits = logits
        else:
            alpha = self.config.inference.ema_alpha
            self.ema_logits = alpha * self.ema_logits + (1 - alpha) * logits
        
        # Get prediction from smoothed logits
        probs = self.model_bundle._softmax(self.ema_logits)
        idx = int(np.argmax(probs))
        pred_label = self.model_bundle.label_map[idx]
        pred_conf = float(probs[idx])

        if pred_label and pred_conf >= float(self.config.inference.vote_min_confidence):
            self.vote_labels.append(pred_label)
            self.vote_confs.append(pred_conf)

        if self.vote_labels:
            counts = Counter(self.vote_labels)
            vote_label = counts.most_common(1)[0][0]
            confs = [c for l, c in zip(self.vote_labels, self.vote_confs) if l == vote_label]
            if confs:
                pred_label = vote_label
                pred_conf = float(sum(confs) / len(confs))
        
        # Update metrics
        if self.metrics:
            self.metrics.update_inference(inference_time, pred_conf)
        
        # Adaptive latency control (best-effort)
        if inference_time_ms > float(self.config.inference.max_latency_ms):
            self.adaptive_every = min(int(self.config.inference.max_every), self.adaptive_every + 1)
        elif self.adaptive_every > int(self.config.inference.inference_every_n_frames) and inference_time_ms < float(self.config.inference.max_latency_ms) * 0.7:
            self.adaptive_every = max(int(self.config.inference.inference_every_n_frames), self.adaptive_every - 1)

        return pred_label, pred_conf, inference_time_ms
    
    def _handle_no_hand(self, frame: np.ndarray) -> np.ndarray:
        """Handle case when no hand is detected."""
        # Clear all state
        self.buffer.clear()
        self.ema_logits = None
        self.vote_labels.clear()
        self.vote_confs.clear()
        self.adaptive_every = max(1, int(self.config.inference.inference_every_n_frames))
        self.stability_tracker.reset()
        
        # Show stats if enabled
        if self.config.visualization.show_fps and self.metrics:
            frame = self.viz_manager.render_stats(
                frame, self.metrics, 0, 
                self.config.inference.window_size,
                self.stability_tracker.get_state()
            )
        
        return frame
    
    def _handle_hand_detected(self, frame: np.ndarray, features: np.ndarray) -> np.ndarray:
        """Handle case when hand is detected."""
        # Process and buffer features
        features = self._process_frame_features(features)
        self.buffer.append(features)
        
        # Run inference periodically
        pred_label, pred_conf = "", 0.0
        has_prediction = (self.frame_idx % self.adaptive_every == 0)
        if has_prediction:
            pred_label, pred_conf, _ = self._run_inference()

        # Update stability tracker
        display_label, display_conf = self.stability_tracker.update(
            pred_label, pred_conf, has_prediction=has_prediction
        )
        
        # Render visualization
        frame = self.viz_manager.render_prediction(frame, display_label, display_conf)
        
        if self.config.visualization.show_fps and self.metrics:
            frame = self.viz_manager.render_stats(
                frame, self.metrics,
                len(self.buffer), self.config.inference.window_size,
                self.stability_tracker.get_state()
            )
        
        return frame
    
    def run(self):
        """Main processing loop."""
        self.logger.info("Starting main loop")
        
        fps_counter = 0
        fps_start = time.time()
        
        try:
            while True:
                ret, frame = self.cap.read()
                if not ret:
                    self.logger.warning("Failed to read frame")
                    break
                
                # Extract features
                features, frame, has_hand = self.extractor.extract(
                    frame, 
                    draw_landmarks=self.config.visualization.show_landmarks
                )
                
                # Process based on hand detection
                if has_hand:
                    frame = self._handle_hand_detected(frame, features)
                else:
                    frame = self._handle_no_hand(frame)
                
                # Update FPS
                fps_counter += 1
                if fps_counter >= 30:
                    elapsed = time.time() - fps_start
                    current_fps = fps_counter / elapsed if elapsed > 0 else 0.0
                    if self.metrics:
                        self.metrics.update_fps(current_fps)
                        self.metrics.frame_count += fps_counter
                    fps_counter = 0
                    fps_start = time.time()
                
                # Display
                cv2.imshow(self.config.visualization.window_name, frame)
                
                self.frame_idx += 1
                
                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    self.logger.info("Quit signal received")
                    break
        
        except KeyboardInterrupt:
            self.logger.info("Interrupted by user")
        except Exception as e:
            self.logger.error(f"Error in main loop: {e}", exc_info=True)
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Cleanup resources."""
        self.logger.info("Cleaning up resources")
        
        if hasattr(self, 'cap'):
            self.cap.release()
        
        if hasattr(self, 'extractor'):
            self.extractor.close()
        
        cv2.destroyAllWindows()
        
        # Print final metrics
        if self.metrics:
            self.logger.info("=" * 60)
            self.logger.info("Final Metrics:")
            for key, value in self.metrics.get_summary().items():
                self.logger.info(f"  {key}: {value:.2f}")
            self.logger.info("=" * 60)
        
        self.logger.info("Cleanup complete")


# ============================================================================
# CLI Entry Point
# ============================================================================

def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Professional Real-time Sign Language Recognition System',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    # Model & Checkpoint
    parser.add_argument('--checkpoint', type=Path, default=None,
                       help='Path to .pt checkpoint (auto-detect if not specified)')
    parser.add_argument('--outputs_dir', type=Path, 
                       default=Path('processed/train_utils/outputs'),
                       help='Directory containing checkpoints')
    
    # Input Source
    parser.add_argument('--video', type=str, default='',
                       help='Video file path (empty for webcam)')
    
    # Inference Parameters
    parser.add_argument('--window', type=int, default=60,
                       help='Temporal window size (frames)')
    parser.add_argument('--every', type=int, default=2,
                       help='Run inference every N frames')
    parser.add_argument('--smoothing', type=float, default=0.7,
                       help='EMA smoothing factor [0-1]')
    parser.add_argument('--vote_window', type=int, default=5,
                       help='Temporal voting window size (predictions)')
    parser.add_argument('--vote_min_conf', type=float, default=0.6,
                       help='Min confidence to include in voting [0-1]')
    parser.add_argument('--max_latency_ms', type=float, default=50.0,
                       help='Target max inference latency in ms')
    parser.add_argument('--max_every', type=int, default=6,
                       help='Max inference stride for latency control')
    parser.add_argument('--device', type=str, 
                       default='cuda' if torch.cuda.is_available() else 'cpu',
                       help='Device (cuda/cpu)')
    
    # Stability Parameters
    parser.add_argument('--confidence_threshold', type=float, default=0.6,
                       help='Minimum confidence to display [0-1]')
    parser.add_argument('--stable_frames', type=int, default=3,
                       help='Frames required to confirm label switch')
    parser.add_argument('--hold_frames', type=int, default=15,
                       help='Frames to hold label after loss')
    
    # Visualization
    parser.add_argument('--show_fps', action='store_true',
                       help='Show FPS and statistics')
    parser.add_argument('--font_size', type=int, default=32,
                       help='Font size for text overlay')
    
    # System
    parser.add_argument('--log_level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level')
    parser.add_argument('--enable_metrics', action='store_true',
                       help='Enable detailed metrics collection')
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    config = SystemConfig.from_args(args)
    
    recognizer = SignLanguageRecognizer(config)
    recognizer.run()


if __name__ == '__main__':
    main()

from __future__ import annotations

import random
from typing import Optional

import numpy as np


SEQ_LEN = 60
FEATURE_DIM = 126

NUM_HANDS = 2
NUM_POINTS = 21
POINT_DIM = 3


class SignAugment:
    """
    Train-time augmentation for sign language sequences.

    Designed specifically for:
    - fixed shape: (60, 126)
    - MediaPipe Hands
    - TCN / temporal models
    - realtime-compatible training

    IMPORTANT:
    - DOES NOT swap left/right hands
    - DOES NOT mirror semantics
    - DOES NOT change feature dimensionality
    - ONLY used in train loader
    """

    def __init__(
        self,
        p: float = 0.9,
        noise_std: float = 0.01,
        scale_range: tuple[float, float] = (0.95, 1.05),
        translation_std: float = 0.015,
        dropout_prob: float = 0.02,
        temporal_mask_prob: float = 0.15,
        temporal_jitter_prob: float = 0.25,
        max_temporal_shift: int = 2,
    ):
        self.p = p

        self.noise_std = noise_std
        self.scale_range = scale_range
        self.translation_std = translation_std
        self.dropout_prob = dropout_prob

        self.temporal_mask_prob = temporal_mask_prob
        self.temporal_jitter_prob = temporal_jitter_prob
        self.max_temporal_shift = max_temporal_shift

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """
        Input:
            x: (60,126)

        Output:
            augmented x with SAME shape
        """

        if random.random() > self.p:
            return np.ascontiguousarray(
                x.astype(np.float32)
            )

        x = np.asarray(x, dtype=np.float32).copy()

        if x.shape != (SEQ_LEN, FEATURE_DIM):
            raise ValueError(
                f"Expected {(SEQ_LEN, FEATURE_DIM)}, got {x.shape}"
            )

        x = self._spatial_noise(x)
        x = self._spatial_scale(x)
        x = self._spatial_translation(x)

        x = self._landmark_dropout(x)

        x = self._temporal_mask(x)
        x = self._temporal_jitter(x)

        x = np.nan_to_num(
            x,
            nan=0.0,
            posinf=0.0,
            neginf=0.0
        )

        x = np.clip(x, -5.0, 5.0)

        return np.ascontiguousarray(
            x.astype(np.float32)
        )

    # =========================================================
    # Spatial
    # =========================================================

    def _reshape(self, x: np.ndarray) -> np.ndarray:
        return x.reshape(
            SEQ_LEN,
            NUM_HANDS,
            NUM_POINTS,
            POINT_DIM
        )

    def _flatten(self, x: np.ndarray) -> np.ndarray:
        return x.reshape(SEQ_LEN, FEATURE_DIM)

    def _spatial_noise(self, x: np.ndarray) -> np.ndarray:
        """
        Small gaussian coordinate noise.
        """

        noise = np.random.normal(
            0.0,
            self.noise_std,
            size=x.shape
        ).astype(np.float32)

        mask = (x != 0).astype(np.float32)

        x = x + noise * mask

        return x

    def _spatial_scale(self, x: np.ndarray) -> np.ndarray:
        """
        Uniform scaling around origin.
        """

        scale = random.uniform(
            self.scale_range[0],
            self.scale_range[1]
        )

        arr = self._reshape(x)

        arr[..., :2] *= scale

        return self._flatten(arr)

    def _spatial_translation(self, x: np.ndarray) -> np.ndarray:
        """
        Small XY translation.
        """

        tx = np.random.normal(0, self.translation_std)
        ty = np.random.normal(0, self.translation_std)

        arr = self._reshape(x)

        mask = np.any(arr != 0, axis=-1, keepdims=True)

        arr[..., 0] += tx * mask[..., 0]
        arr[..., 1] += ty * mask[..., 0]

        return self._flatten(arr)

    # =========================================================
    # Landmark dropout
    # =========================================================

    def _landmark_dropout(self, x: np.ndarray) -> np.ndarray:
        """
        Randomly drop a few landmarks.
        Simulates MediaPipe instability.
        """

        arr = self._reshape(x)

        for h in range(NUM_HANDS):

            for p in range(NUM_POINTS):

                if random.random() < self.dropout_prob:
                    arr[:, h, p, :] = 0.0

        return self._flatten(arr)

    # =========================================================
    # Temporal
    # =========================================================

    def _temporal_mask(self, x: np.ndarray) -> np.ndarray:
        """
        Randomly mask a few frames.
        Simulates tracking drops.
        """

        if random.random() > self.temporal_mask_prob:
            return x

        x = x.copy()

        n_masks = random.randint(1, 3)

        for _ in range(n_masks):

            idx = random.randint(0, SEQ_LEN - 1)

            x[idx] = 0.0

        return x

    def _temporal_jitter(self, x: np.ndarray) -> np.ndarray:
        """
        Small temporal rolling.
        Simulates timing variation.
        """

        if random.random() > self.temporal_jitter_prob:
            return x

        shift = random.randint(
            -self.max_temporal_shift,
            self.max_temporal_shift
        )

        if shift == 0:
            return x

        return np.roll(x, shift, axis=0)


def build_train_augment() -> SignAugment:
    """
    Default augmentation pipeline for training.
    """

    return SignAugment(
        p=0.9,
        noise_std=0.008,
        scale_range=(0.97, 1.03),
        translation_std=0.01,
        dropout_prob=0.015,
        temporal_mask_prob=0.15,
        temporal_jitter_prob=0.25,
        max_temporal_shift=2,
    )
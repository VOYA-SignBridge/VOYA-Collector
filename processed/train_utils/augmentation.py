from __future__ import annotations

import random
from typing import Optional

import numpy as np


SEQ_LEN = 60
FEATURE_DIM = 126

# Bumped whenever the SEMANTICS of a transform change (not its parameters).
#   v1_image_space_mirror  -- mirror was x -> 1-x (wrong for wrist-centered
#                             storage; inflated hand span ~3.1x). Never stamped
#                             into checkpoints; inferred by absence.
#   v2_wrist_centered_mirror -- mirror is x -> -x about the wrist origin, and
#                             temporal masking is disabled by default.
AUGMENTATION_CONTRACT_VERSION = "v2_wrist_centered_mirror"

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
    - _mirror_handedness (p=mirror_prob) DOES mirror X and swap the two hand
      slots TOGETHER — a deliberate, semantics-preserving transform given this
      project's swapped-handedness convention (see its docstring). No other
      transform touches hand identity.
    - DOES NOT change feature dimensionality
    - ONLY used in the train loader (never validation/test)
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
        mirror_prob: float = 0.5,
        max_temporal_shift: int = 2,
    ):
        self.p = p

        self.noise_std = noise_std
        self.scale_range = scale_range
        self.translation_std = translation_std
        self.dropout_prob = dropout_prob

        self.temporal_mask_prob = temporal_mask_prob
        self.temporal_jitter_prob = temporal_jitter_prob
        self.mirror_prob = mirror_prob
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
        x = self._mirror_handedness(x)

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

    def _mirror_handedness(
        self,
        x: np.ndarray
    ) -> np.ndarray:
        """
        Mirror augmentation for handedness diversity.

        Operates on WRIST-CENTERED coordinates (the on-disk storage contract:
        shared/normalization.normalize_single_hand puts each hand's wrist at
        x=y=0 and divides by hand span). The correct reflection in that space
        is x -> -x about the wrist origin.

        DO NOT use the image-space form (x -> 1-x). That is only valid for raw
        MediaPipe coordinates in [0,1]; applied to wrist-centered data it
        translates the hand by +1.0 and — because the wrist sits at exactly
        x=0 — a `!= 0` guard would skip the wrist itself, tearing the hand
        apart (measured: hand x-span inflated 3.1x, coordinates moved to a
        region never produced at inference). See tests/test_augmentation_geometry.py.

        Guarantees:
        - wrist stays at the origin (reflection fixes x=0);
        - all pairwise landmark distances and hand span are preserved exactly;
        - absent hand slots (all-zero 63-dim blocks) stay all-zero;
        - fully padded frames stay all-zero;
        - applying the mirror twice is the identity.

        This project uses swapped handedness semantics (MediaPipe right -> left
        slot), so the two anatomical slots are swapped after reflection.
        """

        if random.random() > self.mirror_prob:
            return x

        arr = self._reshape(x).copy()

        # -----------------------------------------
        # Reflect X about the wrist origin, per present hand only.
        # A hand slot is "absent" iff its whole 63-dim block is zero; leaving
        # it untouched keeps the missing-hand encoding unambiguous.
        # -----------------------------------------

        present = np.any(arr != 0.0, axis=(2, 3))  # (T, NUM_HANDS)

        arr[..., 0] = np.where(
            present[..., None],
            -arr[..., 0],
            arr[..., 0],
        )

        # Collapse any -0.0 produced by negating an exact zero (e.g. the wrist)
        # back to +0.0 so zero-tests stay byte-stable.
        arr[..., 0] = arr[..., 0] + 0.0

        # -----------------------------------------
        # Swap anatomical hand slots (fancy-index -> contiguous copy)
        # -----------------------------------------

        arr = arr[:, [1, 0]]

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


# Named augmentation profiles for ablation studies. "full" is the historical
# default; "none" disables augmentation entirely (returns None).
#
# temporal_mask_prob is 0.0 in every shipped profile as of the 2026-07-21
# stabilization patch. _temporal_mask zeroes an ENTIRE frame, which is
# indistinguishable from "both hands absent" and from tail padding under the
# current 126-dim storage contract — a masked frame silently becomes a
# missing-hand frame. Re-enabling it needs an explicit frame-validity channel
# (a model input-contract change, deliberately NOT part of this patch).
# The transform is kept in the class so the decision stays reversible via
# --aug_set temporal_mask_probability=... for a dedicated experiment.
TEMPORAL_MASK_DISABLED_REASON = (
    "temporal_mask zeroes whole frames, which is ambiguous with the "
    "missing-hand / padding encoding in the 126-dim contract"
)

AUGMENTATION_PROFILES = {
    "full": dict(p=0.9, noise_std=0.008, scale_range=(0.97, 1.03), translation_std=0.01,
                 mirror_prob=0.5, dropout_prob=0.015,
                 temporal_mask_prob=0.0, temporal_jitter_prob=0.25, max_temporal_shift=2),
    "spatial": dict(p=0.9, noise_std=0.008, scale_range=(0.97, 1.03), translation_std=0.01,
                    mirror_prob=0.5, dropout_prob=0.015,
                    temporal_mask_prob=0.0, temporal_jitter_prob=0.0, max_temporal_shift=0),
    "temporal": dict(p=0.9, noise_std=0.0, scale_range=(1.0, 1.0), translation_std=0.0,
                     mirror_prob=0.0, dropout_prob=0.0,
                     temporal_mask_prob=0.0, temporal_jitter_prob=0.25, max_temporal_shift=2),
    "none": None,
}

# CLI override name -> SignAugment kwarg (spec-facing names differ slightly).
AUG_OVERRIDE_KEYS = {
    "noise_sigma": "noise_std",
    "scale_range": "scale_range",
    "translation_sigma": "translation_std",
    "mirror_probability": "mirror_prob",
    "landmark_dropout_probability": "dropout_prob",
    "temporal_mask_probability": "temporal_mask_prob",
    "temporal_roll_probability": "temporal_jitter_prob",
}


def build_train_augment(profile: str = "full", overrides: Optional[dict] = None):
    """Build the train-time augmentation for a named profile.

    Returns None for profile "none" (no augmentation). Overrides use the
    spec-facing names in AUG_OVERRIDE_KEYS. Validation/test loaders must
    always pass augment_fn=None — never wire this into eval.
    """
    if profile not in AUGMENTATION_PROFILES:
        raise ValueError(f"Unknown augmentation profile '{profile}'. "
                         f"Available: {sorted(AUGMENTATION_PROFILES)}")
    base = AUGMENTATION_PROFILES[profile]
    if base is None:
        if overrides:
            raise ValueError("augmentation profile 'none' does not accept overrides")
        return None
    params = dict(base)
    for key, value in (overrides or {}).items():
        if key not in AUG_OVERRIDE_KEYS:
            raise ValueError(f"Unknown augmentation override '{key}'. "
                             f"Available: {sorted(AUG_OVERRIDE_KEYS)}")
        params[AUG_OVERRIDE_KEYS[key]] = value
    return SignAugment(**params)


def augment_config_dict(profile: str, overrides: Optional[dict] = None) -> dict:
    """Serializable snapshot of the effective augmentation config (for the
    checkpoint contract and result summaries).

    Carries AUGMENTATION_CONTRACT_VERSION so a checkpoint records WHICH mirror
    semantics produced it: runs stamped "v1_image_space_mirror" (or carrying no
    version at all) were trained with the broken x -> 1-x mirror and are not
    research-valid. See scripts/audit_checkpoint_validity.py.
    """
    base = AUGMENTATION_PROFILES.get(profile)
    if base is None:
        return {
            "profile": profile,
            "enabled": False,
            "augmentation_contract_version": AUGMENTATION_CONTRACT_VERSION,
        }
    params = dict(base)
    for key, value in (overrides or {}).items():
        params[AUG_OVERRIDE_KEYS[key]] = value
    params["scale_range"] = list(params["scale_range"])
    return {
        "profile": profile,
        "enabled": True,
        "augmentation_contract_version": AUGMENTATION_CONTRACT_VERSION,
        **params,
    }

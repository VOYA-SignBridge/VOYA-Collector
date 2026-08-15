"""Geometry invariants for train-time augmentation (stabilization patch 2026-07-21).

Guards the storage contract that on-disk sequences are WRIST-CENTERED
(shared/normalization.normalize_single_hand: wrist at x=y=0, scaled by hand
span, z left raw). The historical mirror used the image-space form x -> 1-x,
which is only correct for raw MediaPipe coordinates; on wrist-centered data it
translated the hand by +1.0 and skipped the wrist itself (its x is exactly 0,
so a `!= 0` guard excluded it), inflating hand span ~3.1x.

Run:  python tests/test_augmentation_geometry.py
Pure numpy — no torch, no FastAPI.

Covers:
  G1  wrist stays at the origin
  G2  pairwise landmark distances + hand span preserved
  G3  all-zero (absent) hand slot stays all-zero
  G4  fully padded frames stay all-zero
  G5  missing-hand slot semantics survive the slot swap
  G6  mirror twice == identity
  G7  temporal masking is off in every shipped profile
  G8  no transform in a shipped profile invents/destroys hand presence
  G9  real on-disk samples keep their coordinate range after mirroring
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from processed.train_utils.augmentation import (  # noqa: E402
    AUGMENTATION_PROFILES,
    FEATURE_DIM,
    SEQ_LEN,
    SignAugment,
    build_train_augment,
)

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def mirror_only() -> SignAugment:
    """Isolate the mirror: every other transform neutralised."""
    return SignAugment(
        p=1.0, noise_std=0.0, scale_range=(1.0, 1.0), translation_std=0.0,
        dropout_prob=0.0, temporal_mask_prob=0.0, temporal_jitter_prob=0.0,
        mirror_prob=1.0, max_temporal_shift=0,
    )


def make_hand(rng: np.random.Generator) -> np.ndarray:
    """One synthetic wrist-centered hand: (21, 3), wrist at origin in xy."""
    h = rng.normal(0.0, 0.15, size=(21, 3)).astype(np.float32)
    h[0, 0] = 0.0
    h[0, 1] = 0.0
    return h


def make_sequence(rng, *, left=True, right=True, valid_frames=SEQ_LEN) -> np.ndarray:
    """(60, 126) sequence; frames >= valid_frames are all-zero padding."""
    seq = np.zeros((SEQ_LEN, FEATURE_DIM), dtype=np.float32)
    for t in range(valid_frames):
        if left:
            seq[t, :63] = make_hand(rng).reshape(-1)
        if right:
            seq[t, 63:] = make_hand(rng).reshape(-1)
    return seq


def hands(seq: np.ndarray) -> np.ndarray:
    return seq.reshape(SEQ_LEN, 2, 21, 3)


def pairwise(hand_xy: np.ndarray) -> np.ndarray:
    d = hand_xy[:, None, :] - hand_xy[None, :, :]
    return np.linalg.norm(d, axis=-1)


def main() -> int:
    rng = np.random.default_rng(20260721)
    aug = mirror_only()

    print("[G1 wrist stays at the origin]")
    seq = make_sequence(rng)
    out = hands(aug(seq))
    wrists = out[:, :, 0, :2]
    check("all wrists at (0,0) after mirror", np.allclose(wrists, 0.0, atol=0.0),
          f"max |wrist| = {np.abs(wrists).max()}")
    check("no negative zero left in x", not np.any(np.signbit(out[..., 0]) & (out[..., 0] == 0.0)))

    print("[G2 distances and hand span preserved]")
    seq = make_sequence(rng)
    src, dst = hands(seq), hands(aug(seq))
    # slot k of the output corresponds to slot 1-k of the input (slots swapped)
    max_dist_err = 0.0
    max_span_err = 0.0
    for t in range(SEQ_LEN):
        for k in (0, 1):
            a = src[t, k, :, :2]
            b = dst[t, 1 - k, :, :2]
            max_dist_err = max(max_dist_err, float(np.abs(pairwise(a) - pairwise(b)).max()))
            span_a = max(a[:, 0].max() - a[:, 0].min(), a[:, 1].max() - a[:, 1].min())
            span_b = max(b[:, 0].max() - b[:, 0].min(), b[:, 1].max() - b[:, 1].min())
            max_span_err = max(max_span_err, abs(span_a - span_b))
    check("all pairwise landmark distances preserved", max_dist_err < 1e-6, max_dist_err)
    check("hand span preserved", max_span_err < 1e-6, max_span_err)
    check("z axis untouched by mirror",
          np.allclose(src[:, 0, :, 2], dst[:, 1, :, 2], atol=0.0))

    print("[G3 absent hand slot stays all-zero]")
    seq = make_sequence(rng, left=True, right=False)
    out = hands(aug(seq))
    # input right slot was empty -> after the swap it lands in the left slot
    check("empty slot still exactly zero", np.all(out[:, 0] == 0.0),
          f"nonzero count = {int(np.count_nonzero(out[:, 0]))}")
    check("populated slot still populated", np.any(out[:, 1] != 0.0))

    print("[G4 padding frames stay all-zero]")
    seq = make_sequence(rng, valid_frames=40)
    out = aug(seq)
    check("padded tail frames remain zero", np.all(out[40:] == 0.0),
          f"nonzero = {int(np.count_nonzero(out[40:]))}")
    check("valid frames remain non-zero", np.all(np.any(out[:40] != 0.0, axis=1)))

    print("[G5 missing-hand mask survives every shipped profile]")
    for name in ("full", "spatial", "temporal"):
        fn = build_train_augment(name)
        seq = make_sequence(rng, left=True, right=False, valid_frames=45)
        before = np.any(hands(seq) != 0.0, axis=(2, 3))
        random.seed(7)
        np.random.seed(7)
        after = np.any(hands(np.asarray(fn(seq))) != 0.0, axis=(2, 3))
        # a mirror may swap the two columns; compare as multisets per frame
        same = np.array_equal(np.sort(before, axis=1), np.sort(after, axis=1))
        check(f"{name}: per-frame hand-presence count unchanged", same,
              f"before={before.sum()} after={after.sum()}")

    print("[G6 mirror twice == identity]")
    seq = make_sequence(rng, valid_frames=50)
    check("double mirror restores input exactly",
          np.array_equal(aug(aug(seq)), seq),
          f"max diff = {np.abs(aug(aug(seq)) - seq).max()}")
    seq1 = make_sequence(rng, left=False, right=True, valid_frames=33)
    check("double mirror identity with one hand missing",
          np.array_equal(aug(aug(seq1)), seq1))

    print("[G7 temporal masking disabled in shipped profiles]")
    for name, params in AUGMENTATION_PROFILES.items():
        if params is None:
            continue
        check(f"{name}: temporal_mask_prob == 0.0",
              float(params["temporal_mask_prob"]) == 0.0, params["temporal_mask_prob"])

    print("[G8 shipped profiles never zero a whole valid frame]")
    for name in ("full", "spatial", "temporal"):
        fn = build_train_augment(name)
        zeroed = 0
        for trial in range(40):
            random.seed(trial)
            np.random.seed(trial)
            seq = make_sequence(rng, valid_frames=SEQ_LEN)
            out = np.asarray(fn(seq))
            zeroed += int(np.sum(~np.any(out != 0.0, axis=1)))
        check(f"{name}: no valid frame turned all-zero", zeroed == 0, f"{zeroed} frames")

    print("[G9 real on-disk samples keep their coordinate range]")
    feats = sorted((REPO_ROOT / "dataset" / "features").rglob("*.npz"))[:40]
    if not feats:
        print("  SKIP: no local feature files")
    else:
        worst_ratio = 0.0
        worst_max = 0.0
        for f in feats:
            with np.load(f, allow_pickle=True) as z:
                if "sequence" not in z:
                    continue
                s = np.asarray(z["sequence"], dtype=np.float32)
            if s.shape != (SEQ_LEN, FEATURE_DIM):
                continue
            a, b = hands(s), hands(aug(s))
            for t in range(SEQ_LEN):
                for k in (0, 1):
                    src_h, dst_h = a[t, k], b[t, 1 - k]
                    if not np.any(src_h != 0.0):
                        continue
                    sa = src_h[:, 0].max() - src_h[:, 0].min()
                    sb = dst_h[:, 0].max() - dst_h[:, 0].min()
                    if sa > 1e-6:
                        worst_ratio = max(worst_ratio, abs(sb / sa - 1.0))
                    worst_max = max(worst_max, float(np.abs(dst_h[:, 0]).max()))
        check("real samples: x-span unchanged by mirror", worst_ratio < 1e-4, worst_ratio)
        check("real samples: |x| stays in the wrist-centered range (<1.0)",
              worst_max < 1.0, worst_max)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())


# ---------------------------------------------------------------------------
# Vỏ pytest, và ĐÍNH CHÍNH cho bản đầu của chú thích này.
#
# Bản đầu viết rằng tệp này "chưa từng được kiểm trong CI". SAI. Nó nằm trong
# `conftest.STANDALONE_SUITES` từ trước, và `test_research_suites.py` chạy nó
# như một TIẾN TRÌNH CON, lấy mã thoát làm phán quyết. Phép quét AST chỉ đo
# được "pytest thu 0 hàm test_* từ tệp này" — đúng, nhưng KHÔNG đồng nghĩa với
# "không chạy", vì bộ chạy nằm ở chỗ khác.
#
# Vỏ này vẫn có ích, chỉ là vì lý do khiêm tốn hơn: gọi thẳng
# `pytest <tệp này>` giờ chạy được thay vì thu 0 ca. Bộ chạy thật vẫn là
# `test_research_suites.py`.
#
# Chốt `assert PASSED or FAILED` thì đáng giữ, và nó đã bắt được một ca thật:
# một kịch bản in "SKIP:" rồi `return 0` sẽ thành XANH ở CẢ HAI đường.
# ---------------------------------------------------------------------------

def test_toan_bo_kich_ban() -> None:
    ma = main()
    assert PASSED or FAILED, (
        "không ca nào chạy — kịch bản trả về xanh mà chưa kiểm gì cả")
    assert ma == 0, "; ".join(f"{n}: {d}" for n, d in FAILED)

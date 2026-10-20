"""Standalone tests for the live-capture QC module (app/processing/quality.py).

Run locally (only needs numpy) or inside the backend container:
    python tests/test_quality.py
    docker exec -w /workspace/backend voya_backend python tests/test_quality.py

Covers:
  Q1  presence ratios on clean 1-hand / 2-hand sequences
  Q2  completeness semantics per hands_required (0 / 1 / 2)
  Q3  jitter_p95: smooth motion low, teleporting wrist high
  Q4  absent-hand frames do NOT inflate jitter (zero-padding spikes excluded)
  Q5  evaluate_quality tiers: clean, warn, reject, disabled hand checks
  Q6  parse_hands_required coercion table
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.processing.quality import (
    QualityMetrics,
    parse_hands_required,
    compute_quality_metrics,
    evaluate_quality,
    hand_presence,
    wrist_jitter_p95,
    REJECT_HANDS_MISSING,
    REJECT_EXTREME_JITTER,
    REJECT_TOO_FEW_VALID_FRAMES,
    WARN_MISSING_REQUIRED_HAND,
    WARN_HIGH_JITTER,
    WARN_LOW_HAND_PRESENCE,
)

PASSED: list[str] = []
FAILED: list[tuple[str, str]] = []

T, D = 60, 126

CFG = SimpleNamespace(
    qc_min_valid_ratio=0.7,
    qc_reject_hands_ratio=0.30,
    qc_warn_hands_ratio=0.80,
    qc_reject_jitter=0.35,
    qc_warn_jitter=0.12,
)


def check(name: str, cond: bool, detail: str = "") -> None:
    """Ghi nhan ket qua, VA nem khi sai.

    Cau `raise` la bat buoc, khong phai trang tri. Tep nay von la script chay
    tay: verdict nam o `sys.exit(1 if FAILED else 0)` cuoi `main()`, nen
    `check` chi can ghi vao danh sach. Nhung pytest KHONG goi `main()` - no
    thu tung ham `test_*` mot. Khong co `raise` thi moi ham o day xanh vo
    dieu kien, ke ca khi moi phep kiem ben trong deu sai.

    Da do, khong phai suy doan: sua mot dieu kien thanh hang sai roi chay
    `pytest ...::test_config_defaults` van ra "1 passed".

    `main()` boc try/except quanh tung test nen che do chay tay van nguyen;
    khac biet duy nhat la no dung o phep kiem sai DAU TIEN trong mot ham thay
    vi gom het - dung cach pytest van bao loi.
    """
    if cond:
        PASSED.append(name)
        print(f"  PASS  {name}")
        return
    FAILED.append((name, str(detail)))
    print(f"  FAIL  {name}  -> {detail}")
    raise AssertionError(f"{name}" + (f"  -> {detail}" if detail else ""))


def make_seq(
    left: bool = True,
    right: bool = True,
    present_ratio: float = 1.0,
    teleport_every: int = 0,
    teleport_dist: float = 0.5,
) -> np.ndarray:
    """Synthetic (60,126) sequence: smooth sinusoidal wrist path in 0..1 coords.

    present_ratio < 1 zeroes trailing frames of BOTH hand blocks.
    teleport_every > 0 displaces the wrist by teleport_dist every N frames.
    """
    rng = np.random.default_rng(42)
    seq = np.zeros((T, D), dtype=np.float32)
    t = np.arange(T, dtype=np.float32)
    for offset, enabled in ((0, left), (63, right)):
        if not enabled:
            continue
        base_x = 0.5 + 0.1 * np.sin(t / 10.0)
        base_y = 0.5 + 0.1 * np.cos(t / 10.0)
        for lm in range(21):
            seq[:, offset + lm * 3 + 0] = base_x + 0.01 * lm + rng.normal(0, 1e-4, T)
            seq[:, offset + lm * 3 + 1] = base_y + 0.01 * lm + rng.normal(0, 1e-4, T)
            seq[:, offset + lm * 3 + 2] = 0.02 + rng.normal(0, 1e-5, T)
        if teleport_every > 0:
            for i in range(teleport_every, T, teleport_every):
                seq[i, offset:offset + 63] += teleport_dist
    if present_ratio < 1.0:
        cut = int(round(T * present_ratio))
        seq[cut:, :] = 0.0
    return seq


def test_presence_ratios():
    print("[Q1 presence ratios]")
    seq = make_seq(left=True, right=True)
    m = compute_quality_metrics(seq, hands_required=2)
    check("2-hand: left_ratio == 1", m.left_hand_ratio == 1.0, m.left_hand_ratio)
    check("2-hand: both_ratio == 1", m.both_hands_ratio == 1.0, m.both_hands_ratio)

    seq = make_seq(left=True, right=False)
    m = compute_quality_metrics(seq, hands_required=2)
    check("1-hand: right_ratio == 0", m.right_hand_ratio == 0.0, m.right_hand_ratio)
    check("1-hand: both_ratio == 0", m.both_hands_ratio == 0.0, m.both_hands_ratio)
    check("1-hand: any_ratio == 1", m.any_hand_ratio == 1.0, m.any_hand_ratio)

    left, right = hand_presence(make_seq(left=True, right=True, present_ratio=0.5))
    check("present_ratio=0.5: 30 left frames", int(np.count_nonzero(left)) == 30, int(np.count_nonzero(left)))


def test_completeness_semantics():
    print("[Q2 completeness semantics]")
    seq = make_seq(left=True, right=False)
    m2 = compute_quality_metrics(seq, hands_required=2)
    m1 = compute_quality_metrics(seq, hands_required=1)
    m0 = compute_quality_metrics(seq, hands_required=0)
    check("required=2 -> completeness = both (0)", m2.completeness == 0.0, m2.completeness)
    check("required=1 -> completeness = any (1)", m1.completeness == 1.0, m1.completeness)
    check("unknown  -> completeness = any (1)", m0.completeness == 1.0, m0.completeness)


def test_jitter():
    print("[Q3 jitter]")
    smooth = wrist_jitter_p95(make_seq())
    check("smooth motion: jitter_p95 < warn (0.12)", smooth < CFG.qc_warn_jitter, smooth)

    jumpy = wrist_jitter_p95(make_seq(teleport_every=10, teleport_dist=0.5))
    check("teleporting wrist: jitter_p95 > reject (0.35)", jumpy > CFG.qc_reject_jitter, jumpy)
    check("jitter orders: jumpy > smooth", jumpy > smooth, (jumpy, smooth))


def test_jitter_ignores_absence():
    print("[Q4 jitter ignores absent frames]")
    # Alternate present/absent frames: every consecutive pair has one absent
    # frame, so NO valid pair exists -> jitter must be 0, not a padding spike.
    seq = make_seq()
    seq[::2, :] = 0.0
    j = wrist_jitter_p95(seq)
    check("alternating absence: jitter == 0", j == 0.0, j)

    # One absent gap in the middle: the 0->x and x->0 transitions are excluded.
    seq = make_seq()
    seq[30, :] = 0.0
    j = wrist_jitter_p95(seq)
    check("single gap: jitter stays < warn", j < CFG.qc_warn_jitter, j)


def test_evaluate_tiers():
    print("[Q5 evaluate tiers]")
    def metrics(**kw):
        base = dict(left_hand_ratio=1.0, right_hand_ratio=1.0, both_hands_ratio=1.0,
                    any_hand_ratio=1.0, completeness=1.0, jitter_p95=0.01,
                    activity=0.01, hands_required=2)
        base.update(kw)
        return QualityMetrics(**base)

    v = evaluate_quality(metrics(), CFG)
    check("clean: no reject", v.reject_code is None, v.reject_code)
    check("clean: no warnings", v.warning_codes == [], v.warning_codes)
    check("clean: flags empty", v.flags == "", v.flags)

    v = evaluate_quality(metrics(completeness=0.5, both_hands_ratio=0.5), CFG)
    check("warn tier: MISSING_REQUIRED_HAND", WARN_MISSING_REQUIRED_HAND in v.warning_codes, v.warning_codes)
    check("warn tier: not rejected", v.reject_code is None, v.reject_code)

    v = evaluate_quality(metrics(completeness=0.1, both_hands_ratio=0.1), CFG)
    check("reject tier: QC_HANDS_MISSING", v.reject_code == REJECT_HANDS_MISSING, v.reject_code)

    v = evaluate_quality(metrics(jitter_p95=0.2), CFG)
    check("jitter warn: HIGH_JITTER", WARN_HIGH_JITTER in v.warning_codes, v.warning_codes)
    v = evaluate_quality(metrics(jitter_p95=0.4), CFG)
    check("jitter reject: QC_EXTREME_JITTER", v.reject_code == REJECT_EXTREME_JITTER, v.reject_code)

    v = evaluate_quality(metrics(any_hand_ratio=0.5, completeness=0.5, both_hands_ratio=0.5), CFG)
    check("empty frames: QC_TOO_FEW_VALID_FRAMES", v.reject_code == REJECT_TOO_FEW_VALID_FRAMES, v.reject_code)

    # hands_required unknown: hand-requirement checks off, presence warn still on
    v = evaluate_quality(metrics(hands_required=0, completeness=0.75, any_hand_ratio=0.75, both_hands_ratio=0.0), CFG)
    check("unknown hands: no hand reject", v.reject_code is None, v.reject_code)
    check("unknown hands: LOW_HAND_PRESENCE warn", WARN_LOW_HAND_PRESENCE in v.warning_codes, v.warning_codes)

    # all-zero sequence end-to-end
    v = evaluate_quality(compute_quality_metrics(np.zeros((T, D), dtype=np.float32), 2), CFG)
    check("all-zero seq: rejected", v.reject_code == REJECT_TOO_FEW_VALID_FRAMES, v.reject_code)


def test_parse_hands_required():
    print("[Q6 parse_hands_required]")
    cases = [(1, 1), (2, 2), ("1", 1), ("2", 2), (" 2 ", 2),
             (0, None), ("0", None), ("", None), (None, None), ("abc", None), (3, None)]
    for raw, expected in cases:
        got = parse_hands_required(raw)
        check(f"parse({raw!r}) == {expected}", got == expected, got)


def main() -> int:
    for fn in (test_presence_ratios, test_completeness_semantics, test_jitter,
               test_jitter_ignores_absence, test_evaluate_tiers, test_parse_hands_required):
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            FAILED.append((fn.__name__, f"exception: {exc!r}"))
            print(f"  FAIL  {fn.__name__}  -> exception: {exc!r}")
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for name, detail in FAILED:
        print(f"  FAILED: {name}: {detail}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())

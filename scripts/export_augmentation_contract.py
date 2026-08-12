"""Export the augmentation contract for the methodology section.

Everything below is read from processed/train_utils/augmentation.py at run
time. Nothing is transcribed by hand — if the table in the paper disagrees
with the code, regenerate it instead of editing the Markdown.

Usage:
    python scripts/export_augmentation_contract.py
    python scripts/export_augmentation_contract.py --out-dir reports

Writes:
    reports/augmentation_contract.json    machine-readable, exact defaults
    reports/augmentation_contract.md      the table to paste into the paper
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import json
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in _sys.path:
    _sys.path.insert(0, str(REPO_ROOT))

import numpy as np  # noqa: E402

from processed.train_utils.augmentation import (  # noqa: E402
    AUGMENTATION_CONTRACT_VERSION,
    AUGMENTATION_PROFILES,
    AUG_OVERRIDE_KEYS,
    FEATURE_DIM,
    SEQ_LEN,
    TEMPORAL_MASK_DISABLED_REASON,
    SignAugment,
    augment_config_dict,
)

PROFILE_ORDER = ("none", "spatial", "temporal", "full")


def _fmt(value) -> str:
    if value is None:
        return "--"
    if isinstance(value, (list, tuple)):
        return f"[{value[0]:g}, {value[1]:g}]"
    if isinstance(value, float):
        return "off" if value == 0.0 else f"{value:g}"
    return str(value)


def verify_mirror_geometry() -> dict:
    """Prove, at export time, that the shipped mirror is the wrist-centered
    reflection the contract claims — so the exported document cannot describe
    an implementation that no longer exists."""
    rng = np.random.default_rng(0)
    seq = np.zeros((SEQ_LEN, FEATURE_DIM), dtype=np.float32)
    hand = rng.normal(0.0, 0.15, size=(21, 3)).astype(np.float32)
    hand[0, 0] = 0.0
    hand[0, 1] = 0.0
    seq[:, :63] = hand.reshape(-1)

    mirror = SignAugment(
        p=1.0, noise_std=0.0, scale_range=(1.0, 1.0), translation_std=0.0,
        dropout_prob=0.0, temporal_mask_prob=0.0, temporal_jitter_prob=0.0,
        mirror_prob=1.0, max_temporal_shift=0,
    )
    out = mirror(seq).reshape(SEQ_LEN, 2, 21, 3)
    src = hand[:, :2]
    dst = out[0, 1, :, :2]  # slot swap

    def pdist(a):
        d = a[:, None, :] - a[None, :, :]
        return np.linalg.norm(d, axis=-1)

    span_src = float(max(src[:, 0].ptp(), src[:, 1].ptp()))
    span_dst = float(max(dst[:, 0].ptp(), dst[:, 1].ptp()))
    twice = mirror(mirror(seq))

    return {
        "transform": "x -> -x about the wrist origin, then anatomical slot swap",
        "wrist_offset_after_mirror": float(np.abs(dst[0]).max()),
        "max_pairwise_distance_error": float(np.abs(pdist(src) - pdist(dst)).max()),
        "hand_span_ratio": (span_dst / span_src) if span_src > 0 else None,
        "empty_slot_stays_zero": bool(np.all(out[:, 0] == 0.0)),
        "involution_exact": bool(np.array_equal(twice, seq)),
        "z_axis_untouched": bool(np.allclose(out[0, 1, :, 2], hand[:, 2], atol=0.0)),
    }


def build_contract() -> dict:
    profiles = {}
    for name in PROFILE_ORDER:
        if name not in AUGMENTATION_PROFILES:
            continue
        profiles[name] = augment_config_dict(name)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "augmentation_contract_version": AUGMENTATION_CONTRACT_VERSION,
        "input_shape": [SEQ_LEN, FEATURE_DIM],
        "coordinate_space": "wrist_centered_per_hand_scaled_by_hand_span (z raw)",
        "applied_to": "train split only; validation and test are never augmented",
        "mirror_geometry": verify_mirror_geometry(),
        "temporal_mask_policy": {
            "default": "disabled in every shipped profile",
            "reason": TEMPORAL_MASK_DISABLED_REASON,
            "reenable_requires": "a frame-validity channel in the model input contract",
            "override_flag": "--aug_set temporal_mask_probability=<p>",
        },
        "cli_overrides": dict(AUG_OVERRIDE_KEYS),
        "profiles": profiles,
    }


def render_markdown(contract: dict) -> str:
    rows = []
    for name in PROFILE_ORDER:
        p = contract["profiles"].get(name)
        if p is None:
            continue
        if not p.get("enabled"):
            rows.append((name, "--", "--", "--", "--", "--", "--", "--", "--"))
            continue
        rows.append((
            name,
            _fmt(p.get("p")),
            _fmt(p.get("noise_std")),
            _fmt(p.get("scale_range")),
            _fmt(p.get("translation_std")),
            _fmt(p.get("mirror_prob")),
            _fmt(p.get("dropout_prob")),
            _fmt(p.get("temporal_jitter_prob")),
            _fmt(p.get("temporal_mask_prob")),
        ))

    g = contract["mirror_geometry"]
    out = [
        "# Augmentation contract\n",
        f"\n> Generated by `scripts/export_augmentation_contract.py` on "
        f"{contract['generated_at']}. **Do not edit by hand** — regenerate.\n",
        f"\n- Contract version: `{contract['augmentation_contract_version']}`\n",
        f"- Input shape: `{contract['input_shape'][0]} x {contract['input_shape'][1]}`\n",
        f"- Coordinate space: {contract['coordinate_space']}\n",
        f"- Applied to: {contract['applied_to']}\n",
        "\n## Profiles\n\n",
        "| Profile | Apply prob. | Noise (sigma) | Scale | Translation (sigma) | "
        "Mirror | Landmark dropout | Temporal roll | Temporal mask |\n",
        "|---|---|---|---|---|---|---|---|---|\n",
    ]
    for r in rows:
        out.append("| " + " | ".join(f"`{r[0]}`" if i == 0 else r[i]
                                     for i in range(len(r))) + " |\n")

    out += [
        "\n`--` = transform not applied. `off` = probability 0.\n",
        "\n## Mirror geometry (verified at export time)\n\n",
        f"Transform: **{g['transform']}**\n\n",
        "| Property | Value |\n|---|---|\n",
        f"| Wrist offset after mirror | {g['wrist_offset_after_mirror']:.2e} |\n",
        f"| Max pairwise-distance error | {g['max_pairwise_distance_error']:.2e} |\n",
        f"| Hand-span ratio | {g['hand_span_ratio']:.6f} |\n",
        f"| Empty slot stays zero | {g['empty_slot_stays_zero']} |\n",
        f"| Mirror twice == identity | {g['involution_exact']} |\n",
        f"| z axis untouched | {g['z_axis_untouched']} |\n",
        "\nThe mirror is an isometry in the wrist-centered frame: the wrist is the "
        "fixed point of the reflection, so all inter-landmark distances and the hand "
        "span are preserved exactly, and the two anatomical hand slots are swapped so "
        "a mirrored left hand occupies the right slot.\n",
        "\n## Temporal masking\n\n",
        f"- Default: **{contract['temporal_mask_policy']['default']}**\n",
        f"- Reason: {contract['temporal_mask_policy']['reason']}\n",
        f"- Re-enabling requires: {contract['temporal_mask_policy']['reenable_requires']}\n",
        f"- Debug override: `{contract['temporal_mask_policy']['override_flag']}`\n",
        "\nThe `temporal` profile therefore contains only temporal roll, which "
        "reorders existing frames and cannot create a dead frame or a frame that is "
        "ambiguous with padding or with a missing hand.\n",
    ]
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    ap.add_argument("--print", action="store_true", help="also print the Markdown")
    args = ap.parse_args()

    contract = build_contract()
    g = contract["mirror_geometry"]

    problems = []
    if g["wrist_offset_after_mirror"] > 1e-6:
        problems.append(f"wrist moved by {g['wrist_offset_after_mirror']:.2e}")
    if g["max_pairwise_distance_error"] > 1e-6:
        problems.append(f"distances changed by {g['max_pairwise_distance_error']:.2e}")
    if g["hand_span_ratio"] is None or abs(g["hand_span_ratio"] - 1.0) > 1e-4:
        problems.append(f"hand span ratio {g['hand_span_ratio']}")
    if not g["involution_exact"]:
        problems.append("mirroring twice is not the identity")
    if not g["empty_slot_stays_zero"]:
        problems.append("empty hand slot became non-zero")
    for name, p in contract["profiles"].items():
        if p.get("enabled") and float(p.get("temporal_mask_prob", 0.0)) > 0.0:
            problems.append(f"profile '{name}' has temporal_mask_prob > 0")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    jpath = args.out_dir / "augmentation_contract.json"
    mpath = args.out_dir / "augmentation_contract.md"
    jpath.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    md = render_markdown(contract)
    mpath.write_text(md, encoding="utf-8")

    if args.print:
        print(md)
    print(f"contract version : {contract['augmentation_contract_version']}")
    print(f"json             -> {jpath}")
    print(f"markdown         -> {mpath}")

    if problems:
        print("\n[FAIL] the shipped augmentation does NOT satisfy the contract:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("[OK] shipped augmentation satisfies the contract (geometry verified).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

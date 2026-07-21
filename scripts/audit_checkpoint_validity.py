"""Inventory every checkpoint and flag which ones are research-valid.

Read-only. NEVER deletes, moves or rewrites a checkpoint.

Why this exists
---------------
Between 2026-05-14 (commit 7168f9a/25f8885, which wired SignAugment into the
train loader) and 2026-07-21 (stabilization patch), train-time mirroring used
the image-space form  x -> 1-x  on data that is stored WRIST-CENTERED. On that
storage contract the transform:
  * translates the hand by +1.0 into a coordinate region never seen at
    inference, and
  * skips the wrist itself (its x is exactly 0, excluded by the `!= 0` guard),
    inflating measured hand x-span ~3.1x.
With the shipped defaults (p=0.9, mirror_prob=0.5) that corrupted ~45% of every
training batch. Any model fitted under it is not comparable to a post-fix run
and must not be reported as an experimental result.

Verdicts
--------
  research_valid = true   augmentation disabled, or mirror_prob == 0, or the
                          run is stamped with a post-fix augmentation contract
  research_valid = false  mirror was demonstrably active
  research_valid = null   cannot be determined from the artifact (legacy
                          checkpoint with no training_config); treated as
                          NOT reportable and listed under "unverifiable"

Usage:
    python scripts/audit_checkpoint_validity.py
    python scripts/audit_checkpoint_validity.py --roots processed/train_utils/outputs \
        --out-dir reports --json --markdown
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

# The broken mirror was live in the train loader across this window.
BROKEN_MIRROR_FROM = "2026-05-14"
BROKEN_MIRROR_UNTIL = "2026-07-21"
POST_FIX_CONTRACTS = {"v2_wrist_centered_mirror"}

DEFAULT_ROOTS = [
    REPO_ROOT / "processed" / "train_utils" / "outputs",
    REPO_ROOT / "backend" / "realtime_service" / "config" / "checkpoints",
]


def _augmentation_of(ckpt: dict) -> dict | None:
    tc = ckpt.get("training_config")
    if isinstance(tc, dict) and isinstance(tc.get("augmentation"), dict):
        return tc["augmentation"]
    if isinstance(ckpt.get("augmentation"), dict):
        return ckpt["augmentation"]
    return None


def _classify(ckpt: dict) -> tuple[object, str]:
    """Return (research_valid, reason). research_valid may be True/False/None."""
    aug = _augmentation_of(ckpt)

    if aug is None:
        return None, (
            "no training_config.augmentation recorded (pre-contract checkpoint); "
            "trained via train_tcn.py, which has applied the broken mirror by "
            f"default since {BROKEN_MIRROR_FROM} — assume affected"
        )

    contract = str(aug.get("augmentation_contract_version") or "")
    if contract in POST_FIX_CONTRACTS:
        return True, f"stamped post-fix augmentation contract '{contract}'"

    if aug.get("enabled") is False or str(aug.get("profile")) == "none":
        return True, "augmentation disabled for this run (profile='none')"

    mirror = aug.get("mirror_prob")
    if mirror is None:
        return None, "augmentation recorded but mirror_prob absent — cannot determine"
    if float(mirror) == 0.0:
        return True, "mirror_prob == 0.0 (broken transform never applied)"

    p = float(aug.get("p", 1.0))
    share = p * float(mirror)
    return False, (
        f"broken image-space mirror active: profile='{aug.get('profile')}' "
        f"p={p} mirror_prob={mirror} -> ~{share:.0%} of training samples distorted"
    )


def scan(roots: list[Path]) -> list[dict]:
    try:
        import torch
    except ImportError:
        print("[ERROR] torch is required to read checkpoints.")
        raise SystemExit(2)

    rows: list[dict] = []
    for root in roots:
        if not root.exists():
            print(f"[WARN] root not found, skipping: {root}")
            continue
        for pt in sorted(root.rglob("*.pt")):
            rel = pt.relative_to(REPO_ROOT).as_posix() if pt.is_relative_to(REPO_ROOT) else str(pt)
            try:
                ckpt = torch.load(pt, map_location="cpu", weights_only=False)
            except Exception as exc:  # unreadable artifact is itself a finding
                rows.append({
                    "checkpoint": rel, "readable": False, "research_valid": None,
                    "reason": f"unreadable: {exc}", "size_bytes": pt.stat().st_size,
                })
                continue

            valid, reason = _classify(ckpt)
            aug = _augmentation_of(ckpt) or {}
            tc = ckpt.get("training_config") if isinstance(ckpt.get("training_config"), dict) else {}
            metrics = ckpt.get("metrics") if isinstance(ckpt.get("metrics"), dict) else {}
            rows.append({
                "checkpoint": rel,
                "readable": True,
                "research_valid": valid,
                "reason": reason,
                "created_at": ckpt.get("created_at") or "",
                "model_type": ckpt.get("model_type") or "",
                "recognition_profile": ckpt.get("recognition_profile", ""),
                "dataset_version": ckpt.get("dataset_version", ""),
                "split_version": ckpt.get("split_version", ""),
                "num_classes": ckpt.get("num_classes"),
                "seed": ckpt.get("seed"),
                "epochs": tc.get("epochs"),
                "git_commit": (ckpt.get("git_commit") or "")[:8],
                "has_contract_v2": "recognition_profile" in ckpt,
                "augmentation_profile": aug.get("profile", ""),
                "mirror_prob": aug.get("mirror_prob"),
                "augmentation_contract_version": aug.get("augmentation_contract_version", ""),
                "test_acc": metrics.get("test_acc"),
                "test_f1": metrics.get("test_f1"),
                "size_bytes": pt.stat().st_size,
            })
    return rows


def _bucket(rows: list[dict]) -> dict:
    return {
        "valid": [r for r in rows if r["research_valid"] is True],
        "invalid": [r for r in rows if r["research_valid"] is False],
        "unverifiable": [r for r in rows if r["research_valid"] is None],
    }


def render_markdown(rows: list[dict]) -> str:
    b = _bucket(rows)
    out: list[str] = []
    out.append("# Checkpoint validity inventory\n")
    out.append(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n")
    out.append(
        "\n**No checkpoint was deleted or modified.** This report only classifies "
        "which artifacts may be cited as experimental results.\n"
    )
    out.append(
        f"\nBroken-mirror window: `{BROKEN_MIRROR_FROM}` .. `{BROKEN_MIRROR_UNTIL}` "
        "(train-time `x -> 1-x` applied to wrist-centered storage).\n"
    )
    out.append(
        f"\n| bucket | count |\n|---|---|\n"
        f"| research_valid = true | {len(b['valid'])} |\n"
        f"| research_valid = false | {len(b['invalid'])} |\n"
        f"| unverifiable (treat as not reportable) | {len(b['unverifiable'])} |\n"
        f"| **total** | **{len(rows)}** |\n"
    )

    for title, key in (("research_valid = false", "invalid"),
                       ("unverifiable", "unverifiable"),
                       ("research_valid = true", "valid")):
        out.append(f"\n## {title}\n")
        items = b[key]
        if not items:
            out.append("\n_(none)_\n")
            continue
        out.append("\n| checkpoint | profile | classes | epochs | test_acc | reason |\n")
        out.append("|---|---|---|---|---|---|\n")
        for r in items:
            acc = "" if r.get("test_acc") is None else f"{float(r['test_acc']):.4f}"
            out.append(
                f"| `{Path(r['checkpoint']).name}` | {r.get('recognition_profile') or '-'} "
                f"| {r.get('num_classes') or '-'} | {r.get('epochs') or '-'} | {acc or '-'} "
                f"| {r['reason']} |\n"
            )
    out.append(
        "\n## Required action\n\n"
        "Every row above that is not `research_valid = true` must be re-trained "
        "after the 2026-07-21 stabilization patch before it can appear in a paper "
        "table. Re-trained runs are stamped "
        "`training_config.augmentation.augmentation_contract_version = "
        "'v2_wrist_centered_mirror'`, which this script recognises automatically.\n"
    )
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--roots", type=Path, nargs="*", default=DEFAULT_ROOTS)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    ap.add_argument("--json", action="store_true", help="write JSON report")
    ap.add_argument("--markdown", action="store_true", help="write Markdown report")
    args = ap.parse_args()

    rows = scan(list(args.roots))
    if not rows:
        print("No checkpoints found.")
        return 0

    b = _bucket(rows)
    print(f"scanned {len(rows)} checkpoint(s)")
    print(f"  research_valid = true         : {len(b['valid'])}")
    print(f"  research_valid = false        : {len(b['invalid'])}")
    print(f"  unverifiable (not reportable) : {len(b['unverifiable'])}")

    if args.json or args.markdown:
        args.out_dir.mkdir(parents=True, exist_ok=True)
    if args.json:
        p = args.out_dir / "checkpoint_validity.json"
        p.write_text(json.dumps({
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "broken_mirror_window": [BROKEN_MIRROR_FROM, BROKEN_MIRROR_UNTIL],
            "summary": {k: len(v) for k, v in b.items()},
            "checkpoints": rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"json     -> {p}")
    if args.markdown:
        p = args.out_dir / "checkpoint_validity.md"
        p.write_text(render_markdown(rows), encoding="utf-8")
        print(f"markdown -> {p}")

    # Exit 0 always: this is a report, not a gate.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

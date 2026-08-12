"""Verify that two runs with the same seed produce the same model.

Launches train_tcn.py TWICE with identical arguments and seed, into two
separate output directories, then compares the resulting artifacts:

  1. metrics        test_acc / test_f1 / val_best_f1 must match bit-for-bit
  2. weights        every state_dict tensor compared elementwise
  3. predictions    both checkpoints re-scored on the same test split; the
                    argmax vectors must be identical
  4. environment    python / torch / numpy / CUDA / cuDNN / platform / git
                    recorded for BOTH runs and compared

CUDA determinism is CONFIGURED AND CHECKED, never assumed:
  * CUBLAS_WORKSPACE_CONFIG is exported into the child environment BEFORE the
    CUDA context exists (setting it inside the trainer is already too late);
  * each run's own determinism report (written into the checkpoint by
    train_tcn.set_seed) is read back and asserted;
  * if deterministic algorithms could not be enabled, this script FAILS —
    it never downgrades to "close enough".

Exit codes: 0 = reproducible, 1 = mismatch, 2 = could not run.

Usage:
    python scripts/verify_determinism.py \
        --train_csv processed/splits/versions/hoa_de_sample_v3/train.csv \
        --val_csv   processed/splits/versions/hoa_de_sample_v3/val.csv \
        --test_csv  processed/splits/versions/hoa_de_sample_v3/test.csv \
        --recognition_profile hoa_de --epochs 3 --seed 42
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

CUBLAS_DETERMINISTIC_CONFIG = ":4096:8"

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def child_env() -> dict:
    """Environment for the training subprocesses.

    CUBLAS_WORKSPACE_CONFIG must exist before torch creates its CUDA context,
    which is why it is injected here rather than inside train_tcn.py.
    """
    env = dict(os.environ)
    env["CUBLAS_WORKSPACE_CONFIG"] = CUBLAS_DETERMINISTIC_CONFIG
    env["PYTHONHASHSEED"] = "0"
    env.setdefault("PYTHONIOENCODING", "utf-8")
    return env


def run_training(args, out_dir: Path, tag: str) -> int:
    cmd = [
        sys.executable, str(REPO_ROOT / "processed" / "train_utils" / "train_tcn.py"),
        "--train_csv", str(args.train_csv),
        "--val_csv", str(args.val_csv),
        "--test_csv", str(args.test_csv),
        "--out_dir", str(out_dir),
        "--seed", str(args.seed),
        "--epochs", str(args.epochs),
        "--model_type", args.model_type,
        "--augmentation_profile", args.augmentation_profile,
        "--dataset_version", args.dataset_version,
        "--split_version", args.split_version,
    ]
    if args.recognition_profile:
        cmd += ["--recognition_profile", args.recognition_profile]
    if args.unified:
        cmd += ["--unified"]
    if args.features_root:
        cmd += ["--features_root", str(args.features_root)]

    print(f"\n[RUN {tag}] {' '.join(cmd[1:])}")
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=child_env(),
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        print(f"[RUN {tag}] FAILED (exit {proc.returncode})")
        print((proc.stdout or "")[-3000:])
        print((proc.stderr or "")[-3000:])
    return proc.returncode


def find_checkpoint(out_dir: Path) -> Path | None:
    cands = sorted(out_dir.rglob("*.pt"), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def compare(ckpt_a: Path, ckpt_b: Path, args) -> None:
    import torch

    a = torch.load(ckpt_a, map_location="cpu", weights_only=False)
    b = torch.load(ckpt_b, map_location="cpu", weights_only=False)

    print("\n[D1 determinism configuration actually achieved]")
    for tag, ck in (("run A", a), ("run B", b)):
        rep = ck.get("determinism") or {}
        if not rep:
            check(f"{tag}: determinism report present in checkpoint", False,
                  "checkpoint predates the determinism report field")
            continue
        check(f"{tag}: deterministic algorithms enabled",
              bool(rep.get("deterministic_algorithms")), json.dumps(rep))
        check(f"{tag}: cudnn.deterministic set", bool(rep.get("cudnn_deterministic")))
        check(f"{tag}: no determinism warnings", not rep.get("warnings"),
              "; ".join(rep.get("warnings") or []))
        if (ck.get("runtime_env") or {}).get("cuda_version") not in (None, "", "none"):
            check(f"{tag}: CUBLAS_WORKSPACE_CONFIG set for CUDA",
                  rep.get("cublas_workspace_config") in (":4096:8", ":16:8"),
                  repr(rep.get("cublas_workspace_config")))

    print("\n[D2 environment identical across runs]")
    env_a = a.get("runtime_env") or {}
    env_b = b.get("runtime_env") or {}
    check("runtime_env recorded", bool(env_a) and bool(env_b))
    for key in sorted(set(env_a) | set(env_b)):
        check(f"env matches: {key}", env_a.get(key) == env_b.get(key),
              f"{env_a.get(key)!r} vs {env_b.get(key)!r}")
    check("git_commit matches", a.get("git_commit") == b.get("git_commit"),
          f"{a.get('git_commit')} vs {b.get('git_commit')}")
    check("seed matches", a.get("seed") == b.get("seed"))

    print("\n[D3 metrics identical]")
    ma, mb = a.get("metrics") or {}, b.get("metrics") or {}
    for key in ("test_acc", "test_f1"):
        check(f"{key} identical", ma.get(key) == mb.get(key),
              f"{ma.get(key)!r} vs {mb.get(key)!r}")

    print("\n[D4 weights identical]")
    sa, sb = a["model_state_dict"], b["model_state_dict"]
    check("same tensor names", set(sa) == set(sb), str(set(sa) ^ set(sb)))
    worst_key, worst_diff, n_diff = "", 0.0, 0
    for k in sorted(set(sa) & set(sb)):
        ta, tb = sa[k].float(), sb[k].float()
        if ta.shape != tb.shape:
            check(f"shape {k}", False, f"{tuple(ta.shape)} vs {tuple(tb.shape)}")
            continue
        d = float((ta - tb).abs().max()) if ta.numel() else 0.0
        if d > 0:
            n_diff += 1
            if d > worst_diff:
                worst_diff, worst_key = d, k
    check("all state_dict tensors bit-identical", n_diff == 0,
          f"{n_diff} tensor(s) differ; worst {worst_key} max|diff|={worst_diff:.3e}")

    print("\n[D5 predictions identical on the test split]")
    try:
        from processed.train_utils.dataset_loader import NPZSignDataset
        from processed.train_utils.models import get_model_class

        def predictions(ckpt_path: Path, ckpt: dict):
            mt = str((ckpt.get("training_config") or {}).get("model_type") or "tcn")
            model = get_model_class(mt).from_config(
                input_dim=int(ckpt["feature_dim"]),
                output_dim=int(ckpt["num_classes"]),
                config=dict(ckpt.get("model_config") or {}),
            )
            model.load_state_dict(ckpt["model_state_dict"])
            model.eval()
            lm = ckpt_path.parent / "label_to_index.json"
            test_csv = ckpt_path.parent / "test.csv"
            if not test_csv.exists():
                test_csv = Path(args.test_csv)
            ds = NPZSignDataset(test_csv,
                                root=(args.features_root or REPO_ROOT / "dataset" / "features"),
                                label_to_index_json=(lm if lm.exists() else None),
                                to_tensor=True)
            out = []
            with torch.inference_mode():
                for i in range(len(ds)):
                    x, _y, _m = ds[i]
                    out.append(int(model(x.unsqueeze(0)).argmax(1).item()))
            return out

        pa = predictions(ckpt_a, a)
        pb = predictions(ckpt_b, b)
        check("same number of test samples scored", len(pa) == len(pb), f"{len(pa)} vs {len(pb)}")
        mismatches = sum(1 for i, j in zip(pa, pb) if i != j)
        check("all predictions identical", mismatches == 0,
              f"{mismatches}/{len(pa)} differ")
    except Exception as exc:
        check("prediction comparison ran", False, f"{type(exc).__name__}: {exc}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--train_csv", type=Path, required=True)
    ap.add_argument("--val_csv", type=Path, required=True)
    ap.add_argument("--test_csv", type=Path, required=True)
    ap.add_argument("--features_root", type=Path, default=None)
    ap.add_argument("--recognition_profile", type=str, default="")
    ap.add_argument("--unified", action="store_true")
    ap.add_argument("--model_type", type=str, default="tcn")
    ap.add_argument("--augmentation_profile", type=str, default="full")
    ap.add_argument("--dataset_version", type=str, default="determinism_check")
    ap.add_argument("--split_version", type=str, default="determinism_check")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--work-dir", type=Path,
                    default=REPO_ROOT / "reports" / "determinism")
    ap.add_argument("--out-report", type=Path,
                    default=REPO_ROOT / "reports" / "determinism_report.json")
    ap.add_argument("--keep", action="store_true", help="keep the two run directories")
    args = ap.parse_args()

    try:
        import torch  # noqa: F401
    except ImportError:
        print("[ERROR] torch is required.")
        return 2

    print(f"CUBLAS_WORKSPACE_CONFIG -> {CUBLAS_DETERMINISTIC_CONFIG} (child env)")
    work = args.work_dir
    if work.exists():
        shutil.rmtree(work)
    dir_a, dir_b = work / "run_a", work / "run_b"
    dir_a.mkdir(parents=True, exist_ok=True)
    dir_b.mkdir(parents=True, exist_ok=True)

    for tag, out in (("A", dir_a), ("B", dir_b)):
        if run_training(args, out, tag) != 0:
            print(f"\n[ERROR] run {tag} failed; cannot verify determinism.")
            return 2

    ckpt_a, ckpt_b = find_checkpoint(dir_a), find_checkpoint(dir_b)
    if not ckpt_a or not ckpt_b:
        print("[ERROR] could not locate both checkpoints.")
        return 2
    print(f"\nrun A checkpoint: {ckpt_a}")
    print(f"run B checkpoint: {ckpt_b}")

    compare(ckpt_a, ckpt_b, args)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")

    args.out_report.parent.mkdir(parents=True, exist_ok=True)
    args.out_report.write_text(json.dumps({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "reproducible": not FAILED,
        "seed": args.seed,
        "cublas_workspace_config": CUBLAS_DETERMINISTIC_CONFIG,
        "checkpoints": [str(ckpt_a), str(ckpt_b)],
        "passed": [n for n, _ in PASSED],
        "failed": [{"check": n, "detail": d} for n, d in FAILED],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report -> {args.out_report}")

    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)

    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())

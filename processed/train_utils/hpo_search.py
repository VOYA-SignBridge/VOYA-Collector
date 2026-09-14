"""Systematic hyperparameter search for the sign-language training pipeline.

Why this exists: every model_type in train_utils/models/ trains with
hand-set defaults (TCN channels=64/levels=3, BiGRU hidden_size=64, HandGCN
gcn_channels=64, ...) and nothing in the repo ever searched around them —
so a "we tuned it" claim had no run to point to.

THREE METHODOLOGY DECISIONS, each made because the naive version measured
the wrong thing. They are the difference between a sweep that produces a
number and one that survives a question.

1. SIGNER-INDEPENDENT OBJECTIVE (--loso_dir).
   The deployment split (e.g. alphabet_deploy_v23) puts all six signers in
   train AND val AND test, so its validation score answers "does this work
   for a signer it already saw". Tuning on it selects hyperparameters for
   the easy question; the measured gap between the two questions on this
   dataset is 0.596 vs 0.965. In LOSO mode the objective is instead the
   mean macro-F1 on each fold's HELD-OUT signer — the question that
   actually matters.

   Leakage guard: folds are split into --tune_folds (their held-out signer
   drives the search) and --holdout_folds (never read during the search, so
   the number reported on them is not inflated by selection). Inside a
   fold, early stopping still uses that fold's val split, which contains
   only training signers — so the held-out signer is read exactly once, at
   the end, as the fold's score.

2. MULTI-SEED CONFIRMATION (--confirm_seeds).
   On this dataset a single run's val macro-F1 moves by sd≈0.039 (range
   0.094 across four seeds of one fixed config). Two consequences: any
   ranking of trials closer than ~0.1 is noise, and taking the max over N
   trials inflates the winner by roughly +0.05 on its own (winner's curse).
   So the search picks CANDIDATES, and a second phase re-runs the top ones
   over several seeds and reports mean ± sd. The number to quote is the
   confirmed mean, never the search's best-trial value.

3. MULTI-OBJECTIVE (--objective f1_and_size).
   Maximizing F1 alone drifts toward wider models — the exact opposite of
   the requirement that these models be light enough to ship to mobile. The
   honest formulation optimizes both at once and reports a Pareto front, so
   the accuracy cost of every size reduction is visible rather than assumed.
   Optuna cannot prune multi-objective studies (Trial.report raises
   NotImplementedError), so pruning is available only with --objective f1.

Each trial shells out to train_tcn.py exactly like the Celery trainer does
(backend/app/training_tasks.py::_build_cmd), so a trial trains through the
SAME code path as a real job rather than a reimplementation that could
drift from it.

This script never trains the final model: it prints the train_tcn.py
command (with --run-purpose research) for the winning config, so the
citable checkpoint stays a deliberate, ordinary research run.

Example — signer-independent, size-aware search over TCN:

  python -m processed.train_utils.hpo_search \
      --model_type tcn \
      --loso_dir processed/splits/versions/alphabet_loso_v23 \
      --tune_folds S002,S004,S005 \
      --holdout_folds S001,S013,S017 \
      --features_root dataset/features \
      --recognition_profile alphabet \
      --objective f1_and_size \
      --n_trials 40 --max_epochs 25 --patience 6 \
      --confirm_top_k 3 --confirm_seeds 42,1,7 \
      --out_dir processed/train_utils/outputs/hpo/tcn_alphabet
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import NSGAIISampler, TPESampler

REPO_ROOT = Path(__file__).resolve().parents[2]
TERMINATE_GRACE_SECONDS = 15
POLL_INTERVAL_SECONDS = 1.0

SUPPORTED_MODEL_TYPES = ["tcn", "cnn", "lstm", "bigru_attention", "hdgcn"]

# Architecture-shape knobs per model_type. Everything else (lr, dropout,
# weight_decay, batch_size) is shared, so only this table changes when a new
# architecture joins the registry.
ARCH_KNOBS: Dict[str, Sequence[str]] = {
    "tcn": ("channels", "levels", "kernel_size", "temporal_pool"),
    "cnn": ("channels", "kernel_size", "num_conv_layers"),
    "lstm": ("hidden_size", "num_layers"),
    "bigru_attention": ("hidden_size", "num_layers"),
    "hdgcn": ("gcn_channels", "num_gcn_layers", "temporal_channels"),
}


class Fold:
    """One training unit: a (train, val, test) CSV triple plus a name.

    In LOSO mode `name` is the held-out signer and `test.csv` contains only
    that signer, so the fold's test score IS the signer-independent number.
    In single-split mode there is exactly one fold named "single".
    """

    def __init__(self, name: str, train: Path, val: Path, test: Path):
        self.name = name
        self.train = train
        self.val = val
        self.test = test


def _resolve_folds(args: argparse.Namespace) -> Tuple[List[Fold], List[Fold]]:
    """Return (tune_folds, holdout_folds)."""
    if not args.loso_dir:
        if not (args.train_csv and args.val_csv and args.test_csv):
            raise SystemExit(
                "Pass either --loso_dir (signer-independent, recommended) or all of "
                "--train_csv/--val_csv/--test_csv.")
        return [Fold("single", args.train_csv, args.val_csv, args.test_csv)], []

    def _load(signers: str, label: str) -> List[Fold]:
        out: List[Fold] = []
        for sid in [s.strip() for s in (signers or "").split(",") if s.strip()]:
            d = args.loso_dir / f"test_{sid}"
            if not d.is_dir():
                raise SystemExit(f"{label}: fold directory not found: {d}")
            triple = (d / "train.csv", d / "val.csv", d / "test.csv")
            if not all(p.exists() for p in triple):
                raise SystemExit(f"{label}: fold {d} is missing one of train/val/test.csv")
            out.append(Fold(sid, *triple))
        return out

    tune = _load(args.tune_folds, "--tune_folds")
    holdout = _load(args.holdout_folds, "--holdout_folds")
    if not tune:
        raise SystemExit("--loso_dir requires a non-empty --tune_folds.")
    overlap = {f.name for f in tune} & {f.name for f in holdout}
    if overlap:
        raise SystemExit(
            f"Folds {sorted(overlap)} appear in BOTH --tune_folds and --holdout_folds. "
            f"A fold used to choose hyperparameters cannot also report an unbiased "
            f"score for them.")
    return tune, holdout


def _suggest_config(trial: "optuna.Trial", model_type: str) -> Dict[str, Any]:
    """Sample one hyperparameter set: shared optimization knobs + this
    architecture's shape knobs."""
    cfg: Dict[str, Any] = {
        "lr": trial.suggest_float("lr", 1e-4, 3e-3, log=True),
        "weight_decay": trial.suggest_float("weight_decay", 1e-5, 1e-2, log=True),
        "dropout": trial.suggest_float("dropout", 0.1, 0.5),
        "batch_size": trial.suggest_categorical("batch_size", [16, 32, 64]),
    }
    knobs = ARCH_KNOBS[model_type]
    if "channels" in knobs:
        cfg["channels"] = trial.suggest_categorical("channels", [32, 48, 64, 96, 128])
    if "levels" in knobs:
        cfg["levels"] = trial.suggest_int("levels", 2, 4)
    if "kernel_size" in knobs:
        cfg["kernel_size"] = trial.suggest_categorical("kernel_size", [3, 5, 7])
    if "num_conv_layers" in knobs:
        cfg["num_conv_layers"] = trial.suggest_int("num_conv_layers", 1, 4)
    if "temporal_pool" in knobs:
        cfg["temporal_pool"] = trial.suggest_categorical(
            "temporal_pool", ["gap", "attention", "mean_max"])
    if "hidden_size" in knobs:
        cfg["hidden_size"] = trial.suggest_categorical("hidden_size", [32, 48, 64, 96, 128])
    if "num_layers" in knobs:
        cfg["num_layers"] = trial.suggest_int("num_layers", 1, 3)
    if "gcn_channels" in knobs:
        cfg["gcn_channels"] = trial.suggest_categorical("gcn_channels", [32, 48, 64, 96])
    if "num_gcn_layers" in knobs:
        cfg["num_gcn_layers"] = trial.suggest_int("num_gcn_layers", 1, 3)
    if "temporal_channels" in knobs:
        cfg["temporal_channels"] = trial.suggest_categorical(
            "temporal_channels", [64, 96, 128, 160])
    return cfg


PASSTHROUGH_FLAGS = (
    "channels", "levels", "kernel_size", "num_conv_layers", "temporal_pool",
    "hidden_size", "num_layers", "gcn_channels", "num_gcn_layers", "temporal_channels",
)


def _build_cmd(
    *,
    model_type: str,
    hp: Dict[str, Any],
    args: argparse.Namespace,
    fold: Fold,
    metrics_file: Path,
    seed: int,
    out_dir: Path,
) -> List[str]:
    cmd = [
        sys.executable, "-m", "processed.train_utils.train_tcn",
        f"--model_type={model_type}",
        f"--epochs={args.max_epochs}",
        f"--patience={args.patience}",
        f"--batch_size={hp['batch_size']}",
        f"--lr={hp['lr']}",
        f"--weight_decay={hp['weight_decay']}",
        f"--dropout={hp['dropout']}",
        f"--seed={seed}",
        f"--metrics_file={metrics_file}",
        f"--out_dir={out_dir}",
        # HPO runs are exploratory by construction: they are short, they are
        # many, and none of them is the checkpoint anyone cites.
        "--run-purpose=smoke_test",
        f"--device={args.device}",
        f"--train_csv={fold.train}",
        f"--val_csv={fold.val}",
        f"--test_csv={fold.test}",
    ]
    for key in PASSTHROUGH_FLAGS:
        if key in hp:
            cmd.append(f"--{key}={hp[key]}")
    if args.features_root:
        cmd.append(f"--features_root={args.features_root}")
    if args.recognition_profile:
        cmd.append(f"--recognition_profile={args.recognition_profile}")
    if args.unified:
        cmd.append("--unified")
    if args.dataset_version:
        cmd.append(f"--dataset_version={args.dataset_version}")
    if args.split_version:
        cmd.append(f"--split_version={args.split_version}")
    return cmd


class RunResult:
    def __init__(self) -> None:
        self.ok = False
        self.returncode: Optional[int] = None
        self.best_val_f1 = 0.0
        self.test_f1 = 0.0
        self.test_acc = 0.0
        self.param_count: Optional[int] = None
        self.latency_p50_ms: Optional[float] = None


def _run_training(
    *,
    cmd: List[str],
    metrics_file: Path,
    log_file: Path,
    on_epoch=None,
    should_stop=None,
) -> RunResult:
    """Run one train_tcn.py subprocess, tailing its JSONL metrics live.

    `on_epoch(epoch, best_val_f1)` is called as epochs land, and
    `should_stop()` is polled so a caller (the pruner) can end the run early.
    Same tailing shape as training_tasks.py::_consume_new_metric_lines.
    """
    result = RunResult()
    if metrics_file.exists():
        metrics_file.unlink()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["PYTHONUNBUFFERED"] = "1"

    log_handle = open(log_file, "w", encoding="utf-8", errors="replace")
    process = subprocess.Popen(
        cmd, cwd=str(REPO_ROOT), stdout=log_handle, stderr=subprocess.STDOUT, env=env,
    )

    metrics_pos = 0
    stopped_early = False

    def _drain() -> None:
        nonlocal metrics_pos
        if not metrics_file.exists():
            return
        with open(metrics_file, "r", encoding="utf-8") as mf:
            mf.seek(metrics_pos)
            while True:
                line = mf.readline()
                if not line or not line.endswith("\n"):
                    break
                metrics_pos = mf.tell()
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                kind = payload.get("type")
                if kind == "epoch":
                    result.best_val_f1 = max(
                        result.best_val_f1, float(payload.get("val_f1") or 0.0))
                    if on_epoch is not None:
                        on_epoch(int(payload.get("epoch") or 0), result.best_val_f1)
                elif kind == "final":
                    result.test_f1 = float(payload.get("test_f1") or 0.0)
                    result.test_acc = float(payload.get("test_acc") or 0.0)
                    ev = payload.get("evaluation") or {}
                    eff = ev.get("efficiency") or {}
                    if eff.get("param_count") is not None:
                        result.param_count = int(eff["param_count"])
                    lat = (eff.get("cpu_inference_latency_ms") or {}).get("p50")
                    if lat is not None:
                        result.latency_p50_ms = float(lat)

    try:
        while True:
            rc = process.poll()
            _drain()
            if rc is not None:
                break
            if should_stop is not None and should_stop():
                stopped_early = True
                try:
                    process.terminate()
                    process.wait(timeout=TERMINATE_GRACE_SECONDS)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                break
            time.sleep(POLL_INTERVAL_SECONDS)
    finally:
        log_handle.close()
        _drain()

    result.returncode = process.returncode
    result.ok = (not stopped_early) and process.returncode == 0
    return result


def _score_key(args: argparse.Namespace) -> str:
    """Which per-fold number is the objective.

    LOSO: the fold's test split is the held-out signer, so test macro-F1 is
    the signer-independent score. Single-split: that split's test set is the
    final report set and must stay untouched, so the objective is val.
    """
    return "test_f1" if args.loso_dir else "best_val_f1"


def _evaluate_config(
    *,
    hp: Dict[str, Any],
    folds: List[Fold],
    args: argparse.Namespace,
    seed: int,
    work_dir: Path,
    tag: str,
    should_stop=None,
    on_fold_done=None,
) -> Optional[Dict[str, Any]]:
    """Train `hp` on every fold at one seed. None means the caller should
    treat this config as unusable (a run failed, or it was stopped early)."""
    key = _score_key(args)
    per_fold: List[float] = []
    param_count: Optional[int] = None
    latency: Optional[float] = None

    for idx, fold in enumerate(folds):
        metrics_file = work_dir / f"{tag}_{fold.name}_s{seed}.jsonl"
        log_file = work_dir / f"{tag}_{fold.name}_s{seed}.log"
        out_dir = work_dir / f"{tag}_{fold.name}_s{seed}_out"
        cmd = _build_cmd(
            model_type=args.model_type, hp=hp, args=args, fold=fold,
            metrics_file=metrics_file, seed=seed, out_dir=out_dir,
        )
        res = _run_training(
            cmd=cmd, metrics_file=metrics_file, log_file=log_file,
            should_stop=should_stop,
        )
        if not res.ok:
            print(f"[HPO] {tag}: fold {fold.name} did not finish "
                  f"(rc={res.returncode}); see {log_file.name}")
            return None
        per_fold.append(getattr(res, key))
        if res.param_count is not None:
            param_count = res.param_count
        if res.latency_p50_ms is not None:
            latency = res.latency_p50_ms
        if on_fold_done is not None:
            on_fold_done(idx, float(statistics.mean(per_fold)))

    return {
        "mean": float(statistics.mean(per_fold)),
        "per_fold": per_fold,
        "param_count": param_count,
        "latency_p50_ms": latency,
    }


def _run_trial(
    trial: "optuna.Trial",
    *,
    args: argparse.Namespace,
    tune_folds: List[Fold],
    trials_dir: Path,
    multi_objective: bool,
):
    hp = _suggest_config(trial, args.model_type)

    # Pruning is single-objective only (Optuna raises NotImplementedError on
    # Trial.report for multi-objective studies), and it acts between folds:
    # a config already behind the pack after fold 1 need not train fold 3.
    def _on_fold_done(idx: int, running_mean: float) -> None:
        if multi_objective:
            return
        trial.report(running_mean, step=idx)

    def _should_stop() -> bool:
        return (not multi_objective) and trial.should_prune()

    outcome = _evaluate_config(
        hp=hp, folds=tune_folds, args=args, seed=args.seed,
        work_dir=trials_dir, tag=f"trial{trial.number:04d}",
        should_stop=_should_stop, on_fold_done=_on_fold_done,
    )

    if outcome is None:
        # A failed or stopped run is marked pruned, NOT scored 0.0: feeding a
        # fabricated terrible value to the sampler would teach it to avoid a
        # region of the space for a reason that has nothing to do with the
        # hyperparameters there.
        raise optuna.TrialPruned()

    trial.set_user_attr("per_fold", outcome["per_fold"])
    trial.set_user_attr("param_count", outcome["param_count"])
    trial.set_user_attr("latency_p50_ms", outcome["latency_p50_ms"])

    if multi_objective:
        # Objective 2 is param count (deterministic given the config, so it
        # carries none of the seed noise that objective 1 does).
        params = outcome["param_count"]
        if params is None:
            raise optuna.TrialPruned()
        return outcome["mean"], float(params)
    return outcome["mean"]


def _confirm(
    *,
    candidates: List["optuna.trial.FrozenTrial"],
    args: argparse.Namespace,
    tune_folds: List[Fold],
    holdout_folds: List[Fold],
    confirm_dir: Path,
) -> List[Dict[str, Any]]:
    """Re-run each candidate over several seeds so the reported number is a
    mean +/- sd instead of a single draw that won a max-of-N lottery."""
    seeds = [int(s) for s in args.confirm_seeds.split(",") if s.strip()]
    report_folds = holdout_folds or tune_folds
    scope = ("held-out folds " + ",".join(f.name for f in holdout_folds)) if holdout_folds \
        else ("tune folds " + ",".join(f.name for f in tune_folds))
    print(f"\n[HPO] confirming {len(candidates)} candidate(s) over seeds {seeds} on {scope}")
    if not holdout_folds:
        print("[HPO] NOTE: no --holdout_folds given, so the confirmation reuses the "
              "folds that chose these configs - the number stays selection-biased.")

    rows: List[Dict[str, Any]] = []
    for rank, t in enumerate(candidates):
        scores: List[float] = []
        param_count = t.user_attrs.get("param_count")
        latency = t.user_attrs.get("latency_p50_ms")
        for seed in seeds:
            outcome = _evaluate_config(
                hp=t.params, folds=report_folds, args=args, seed=seed,
                work_dir=confirm_dir, tag=f"confirm{t.number:04d}",
            )
            if outcome is None:
                continue
            scores.append(outcome["mean"])
            if outcome["param_count"] is not None:
                param_count = outcome["param_count"]
            if outcome["latency_p50_ms"] is not None:
                latency = outcome["latency_p50_ms"]

        if not scores:
            print(f"[HPO] candidate trial #{t.number}: every confirmation run failed.")
            continue
        rows.append({
            "rank": rank,
            "trial_number": t.number,
            "params": t.params,
            "search_score": (t.values[0] if t.values else None),
            "confirmed_mean": float(statistics.mean(scores)),
            "confirmed_sd": float(statistics.stdev(scores)) if len(scores) > 1 else 0.0,
            "confirmed_scores": scores,
            "n_seeds": len(scores),
            "param_count": param_count,
            "latency_p50_ms": latency,
        })
    rows.sort(key=lambda r: r["confirmed_mean"], reverse=True)
    return rows


def main() -> None:
    p = argparse.ArgumentParser(
        description="Signer-independent, size-aware hyperparameter search.")
    p.add_argument("--model_type", required=True, choices=SUPPORTED_MODEL_TYPES)

    # Signer-independent (recommended) fold mode
    p.add_argument("--loso_dir", type=Path, default=None,
                   help="Directory of leave-one-signer-out folds (test_S001/, ...). "
                        "Objective becomes mean macro-F1 on each fold's HELD-OUT signer.")
    p.add_argument("--tune_folds", type=str, default="",
                   help="Comma-separated signer ids whose folds drive the search.")
    p.add_argument("--holdout_folds", type=str, default="",
                   help="Comma-separated signer ids never read during the search; "
                        "used only to report a selection-unbiased final number.")

    # Single-split mode (kept for quick exploratory sweeps)
    p.add_argument("--train_csv", type=Path, default=None)
    p.add_argument("--val_csv", type=Path, default=None)
    p.add_argument("--test_csv", type=Path, default=None)

    p.add_argument("--features_root", type=Path, default=None)
    p.add_argument("--recognition_profile", type=str, default="")
    p.add_argument("--unified", action="store_true")
    p.add_argument("--dataset_version", type=str, default="hpo")
    p.add_argument("--split_version", type=str, default="")

    p.add_argument("--objective", type=str, default="f1",
                   choices=["f1", "f1_and_size"],
                   help="f1: single objective, pruning enabled. f1_and_size: Pareto "
                        "front over (macro-F1 up, parameter count down) - the honest "
                        "formulation when the model must also be small enough to ship, "
                        "but Optuna cannot prune multi-objective studies.")
    p.add_argument("--n_trials", type=int, default=40)
    p.add_argument("--max_epochs", type=int, default=25,
                   help="Epoch cap per trial - short on purpose so a bad region of "
                        "the space fails fast. Configs are re-checked at full length "
                        "only in the final research run.")
    p.add_argument("--patience", type=int, default=6)
    p.add_argument("--seed", type=int, default=42,
                   help="Seed used during the SEARCH, so trials differ by "
                        "hyperparameters rather than by seed noise. The confirmation "
                        "phase is what varies seeds.")
    p.add_argument("--device", type=str, default="cpu")
    p.add_argument("--timeout_seconds", type=int, default=None)
    p.add_argument("--n_startup_trials", type=int, default=5)
    p.add_argument("--n_warmup_steps", type=int, default=0,
                   help="MedianPruner warmup, counted in FOLDS (pruning acts between "
                        "folds, not epochs).")
    p.add_argument("--confirm_top_k", type=int, default=3,
                   help="How many candidates to re-run over multiple seeds. 0 skips "
                        "confirmation (not recommended - see module docstring).")
    p.add_argument("--confirm_seeds", type=str, default="42,1,7")
    p.add_argument("--study_name", type=str, default=None)
    p.add_argument("--out_dir", type=Path, required=True)
    args = p.parse_args()

    tune_folds, holdout_folds = _resolve_folds(args)
    multi_objective = args.objective == "f1_and_size"

    if args.study_name is None:
        args.study_name = f"{args.model_type}_{args.recognition_profile or 'run'}_{args.objective}"

    args.out_dir.mkdir(parents=True, exist_ok=True)
    trials_dir = args.out_dir / "trials"
    confirm_dir = args.out_dir / "confirm"
    trials_dir.mkdir(parents=True, exist_ok=True)
    confirm_dir.mkdir(parents=True, exist_ok=True)
    storage = f"sqlite:///{(args.out_dir / 'study.db').resolve()}"

    common = dict(study_name=args.study_name, storage=storage, load_if_exists=True)
    if multi_objective:
        study = optuna.create_study(
            directions=["maximize", "minimize"],
            sampler=NSGAIISampler(seed=args.seed),
            **common,
        )
    else:
        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=args.seed),
            pruner=MedianPruner(
                n_startup_trials=args.n_startup_trials,
                n_warmup_steps=args.n_warmup_steps,
            ),
            **common,
        )

    print(f"[HPO] study={args.study_name}  storage={storage}")
    print(f"[HPO] model_type={args.model_type}  objective={args.objective}  "
          f"n_trials={args.n_trials}  max_epochs={args.max_epochs}")
    if args.loso_dir:
        print(f"[HPO] objective = mean macro-F1 on HELD-OUT signer of folds: "
              f"{', '.join(f.name for f in tune_folds)}")
        print(f"[HPO] reserved (never read during search): "
              f"{', '.join(f.name for f in holdout_folds) or '(none)'}")
    else:
        print("[HPO] objective = best VALIDATION macro-F1 on a single split "
              "(not signer-independent - see module docstring).")

    study.optimize(
        lambda t: _run_trial(t, args=args, tune_folds=tune_folds,
                             trials_dir=trials_dir, multi_objective=multi_objective),
        n_trials=args.n_trials,
        timeout=args.timeout_seconds,
    )

    states = [t.state for t in study.trials]
    n_done = sum(1 for s in states if s == optuna.trial.TrialState.COMPLETE)
    n_pruned = sum(1 for s in states if s == optuna.trial.TrialState.PRUNED)
    print(f"\n[HPO] search done: {n_done} completed, {n_pruned} pruned/failed.")

    try:
        study.trials_dataframe().to_csv(args.out_dir / "trials.csv", index=False)
        print(f"[HPO] trial log: {args.out_dir / 'trials.csv'}")
    except Exception as e:
        print(f"[HPO] could not write trials.csv (non-fatal): {e}")

    if n_done == 0:
        print("[HPO] no trial completed - nothing to report.")
        return

    if multi_objective:
        front = sorted(study.best_trials, key=lambda t: -t.values[0])
        print(f"\n[HPO] Pareto front ({len(front)} non-dominated configs) - "
              f"each row is a different accuracy/size trade-off:")
        print(f"  {'trial':>6}  {'macro-F1':>9}  {'params':>10}  {'p50 ms':>8}")
        for t in front:
            lat = t.user_attrs.get("latency_p50_ms")
            print(f"  {t.number:>6}  {t.values[0]:>9.4f}  {int(t.values[1]):>10,}  "
                  f"{(f'{lat:.1f}' if lat else '-'):>8}")
        candidates = front[:args.confirm_top_k] if args.confirm_top_k else []
    else:
        done = [t for t in study.trials if t.state == optuna.trial.TrialState.COMPLETE]
        done.sort(key=lambda t: t.values[0], reverse=True)
        print(f"\n[HPO] top trials by search score:")
        for t in done[:max(args.confirm_top_k, 5)]:
            print(f"  trial {t.number:>4}: {t.values[0]:.4f}  {t.params}")
        candidates = done[:args.confirm_top_k] if args.confirm_top_k else []

    confirmed: List[Dict[str, Any]] = []
    if candidates:
        confirmed = _confirm(
            candidates=candidates, args=args, tune_folds=tune_folds,
            holdout_folds=holdout_folds, confirm_dir=confirm_dir,
        )
        print(f"\n[HPO] confirmed results (mean +/- sd over seeds - quote THESE):")
        print(f"  {'trial':>6}  {'mean':>7}  {'sd':>6}  {'search':>7}  {'params':>10}")
        for r in confirmed:
            sc = r["search_score"]
            print(f"  {r['trial_number']:>6}  {r['confirmed_mean']:>7.4f}  "
                  f"{r['confirmed_sd']:>6.4f}  {(f'{sc:.4f}' if sc is not None else '-'):>7}  "
                  f"{(r['param_count'] or 0):>10,}")
        if confirmed:
            top = confirmed[0]
            drop = (top["search_score"] or 0) - top["confirmed_mean"]
            if drop > 0:
                print(f"\n[HPO] the best trial's search score was {drop:+.4f} above its "
                      f"confirmed mean - that difference is the selection bias the "
                      f"confirmation phase exists to remove.")

    summary = {
        "model_type": args.model_type,
        "objective": args.objective,
        "signer_independent": bool(args.loso_dir),
        "tune_folds": [f.name for f in tune_folds],
        "holdout_folds": [f.name for f in holdout_folds],
        "search": {
            "n_trials": args.n_trials, "max_epochs": args.max_epochs,
            "patience": args.patience, "seed": args.seed,
            "completed": n_done, "pruned_or_failed": n_pruned,
        },
        "confirmed": confirmed,
    }
    (args.out_dir / "best_config.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n[HPO] saved: {args.out_dir / 'best_config.json'}")

    best_params = confirmed[0]["params"] if confirmed else candidates[0].params if candidates else None
    if best_params:
        flags = " ".join(f"--{k}={v}" for k, v in best_params.items())
        print(f"\n[HPO] to train the citable final model with this config, run:\n"
              f"python -m processed.train_utils.train_tcn --model_type={args.model_type} "
              f"{flags} --epochs=80 --patience=10 --run-purpose=research "
              f"--train_csv=<split>/train.csv --val_csv=<split>/val.csv --test_csv=<split>/test.csv "
              + (f"--features_root={args.features_root} " if args.features_root else "")
              + (f"--recognition_profile={args.recognition_profile} " if args.recognition_profile else ""))


if __name__ == "__main__":
    main()

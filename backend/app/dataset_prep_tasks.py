"""Prepare a dataset for training, from the web instead of from a shell.

Everything this task does already existed as scripts. That was the problem: a
person who collects data through the platform could not turn it into something
trainable without a terminal, so "new data arrived" always ended with someone
running four CLI tools in the right order with the right flags. The ordering is
not obvious either — the manifest has to exist before any split can reference
it, and the LOSO folds are re-partitioned from the research split rather than
from the manifest, because make_loso_folds reads a split directory.

The chain, in the order it has to run:

  1. create_dataset_manifest.py    freeze what exists now into a versioned,
                                   checksummed manifest
  2. validate_dataset_manifest.py  refuse to go further if it does not hold up
  3. make_splits.py  (sample)      deployment split: every signer in training,
                                   because the model people actually use should
                                   see everyone. Its metric is NOT
                                   signer-independent and is labelled as such.
  4. make_splits.py  (strict)      research split: signers held out, fail-closed
  5. make_loso_folds.py            leave-one-signer-out protocol, one fold per
                                   signer — what the published tables average.
                                   Takes the research split from step 4 as input.

Steps 3-5 run per recognition profile, so one press prepares both the everyday
path and the scientific one, and the two can never drift apart in which manifest
they describe.

Progress is written to a JSON file after every step rather than kept in memory:
preparation takes minutes, the UI polls, and a worker restart mid-run should
leave evidence of how far it got instead of a silent gap.

Dispatched with .delay() so it lands on the default queue. It must not go to the
"training" queue: that worker is concurrency 1 on the GPU, and a preparation run
would block training for its whole duration for no reason.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.worker import celery_app

logger = logging.getLogger(__name__)

WORKSPACE_ROOT = Path("/workspace")
MANIFEST_DIR = WORKSPACE_ROOT / "dataset" / "manifests"
VERSIONS_DIR = WORKSPACE_ROOT / "processed" / "splits" / "versions"
RUNS_DIR = WORKSPACE_ROOT / "processed" / "splits" / "prepare_runs"

_VERSION_RE = re.compile(r"dataset_manifest_(?P<stem>.+)_v(?P<n>\d+)\.csv$")

# Manifests written from now on carry the project name. The old ones keep theirs:
# 26 splits record the manifest they were cut from, and their metadata stores its
# checksum, so renaming those files would break provenance for every result
# already produced. Only the prefix for NEW manifests changes.
MANIFEST_PREFIX = "VSL2026"
LEGACY_MANIFEST_PREFIXES = ("isds2026",)
_STEP_TIMEOUT_S = 3600


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def next_manifest_version(prefix: str = MANIFEST_PREFIX) -> str:
    """Next unused manifest version. Manifests are immutable once written.

    The counter spans the old prefix as well as the new one. Counting only the
    new name would restart at v1 and hand out a number that already identifies a
    different snapshot, which is exactly the ambiguity version numbers exist to
    prevent.
    """
    highest = 0
    if MANIFEST_DIR.is_dir():
        for known in (prefix,) + LEGACY_MANIFEST_PREFIXES:
            for f in MANIFEST_DIR.glob(f"dataset_manifest_{known}_v*.csv"):
                m = _VERSION_RE.search(f.name)
                if m and m.group("stem") == known:
                    highest = max(highest, int(m.group("n")))
    return f"{prefix}_v{highest + 1}"


def _write_report(run_id: str, report: Dict[str, Any]) -> None:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    tmp = RUNS_DIR / f"{run_id}.json.tmp"
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(RUNS_DIR / f"{run_id}.json")


def read_report(run_id: str) -> Optional[Dict[str, Any]]:
    path = RUNS_DIR / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[PREP] không đọc được report %s: %s", run_id, exc)
        return None


def create_pending_report(run_id: str, version: str, profiles: List[str], seed: int) -> Dict[str, Any]:
    """Record the run as queued before the task is dispatched.

    Without this the report file only appears once a worker picks the job up,
    and the page starts polling the moment it has a run id — so the first few
    requests answered 404 and the screen said the run did not exist while it was
    in fact waiting in the queue. Writing it here also makes a job that is never
    picked up visible as "queued" instead of indistinguishable from a typo.
    """
    report = {
        "run_id": run_id,
        "status": "queued",
        "manifest_version": version,
        "manifest": f"dataset/manifests/dataset_manifest_{version}.csv",
        "profiles": profiles,
        "seed": seed,
        "started_at": _now(),
        "current_step": None,
        "steps": [],
        "artifacts": {},
        "warnings": [],
    }
    _write_report(run_id, report)
    return report


def _run(step: str, cmd: List[str], report: Dict[str, Any], run_id: str) -> bool:
    entry: Dict[str, Any] = {"step": step, "cmd": cmd, "started_at": _now()}
    report["steps"].append(entry)
    report["current_step"] = step
    _write_report(run_id, report)

    try:
        proc = subprocess.run(
            cmd, cwd=str(WORKSPACE_ROOT), capture_output=True, text=True,
            timeout=_STEP_TIMEOUT_S, env={"PYTHONPATH": str(WORKSPACE_ROOT), "PATH": "/usr/local/bin:/usr/bin:/bin"},
        )
        ok = proc.returncode == 0
        entry["returncode"] = proc.returncode
        # Keep the tail of both streams: enough to explain a failure without
        # storing megabytes of progress output in the report.
        entry["stdout_tail"] = (proc.stdout or "")[-3000:]
        entry["stderr_tail"] = (proc.stderr or "")[-3000:]
    except subprocess.TimeoutExpired:
        ok = False
        entry["returncode"] = -1
        entry["stderr_tail"] = f"quá {_STEP_TIMEOUT_S}s — đã dừng"
    except Exception as exc:
        ok = False
        entry["returncode"] = -1
        entry["stderr_tail"] = str(exc)

    entry["ok"] = ok
    entry["finished_at"] = _now()
    _write_report(run_id, report)
    return ok


# The validator reports four categories and exits non-zero on any of them.
# Three mean the manifest cannot be trusted. The fourth, orphan files, means
# only that something on disk is not referenced — which is the normal state
# here: excluded_samples.json deliberately drops samples while leaving their
# files in place so older manifest versions still resolve. Treating that as
# fatal would block preparation on a perfectly good dataset, so it is reported
# as a warning and the run continues.
_FATAL_CATEGORIES = ("missing files", "schema violations", "checksum mismatches")
_FAIL_LINE = re.compile(r"^\[FAIL\]\s*([^:]+):\s*(\d+)", re.MULTILINE)


def _validation_verdict(step: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """Split the validator's findings into blocking and advisory."""
    fatal: List[str] = []
    advisories: List[str] = []
    text = "\n".join([step.get("stdout_tail") or "", step.get("stderr_tail") or ""])

    for name, count in _FAIL_LINE.findall(text):
        label = f"{name.strip()}: {count}"
        (fatal if name.strip() in _FATAL_CATEGORIES else advisories).append(label)

    # A non-zero exit with nothing parsable means the tool itself broke; that is
    # never something to wave through.
    if step.get("returncode") not in (0, None) and not fatal and not advisories:
        fatal.append("trình kiểm định không chạy được (rc=%s)" % step.get("returncode"))
    return fatal, advisories


def _describe_split(name: str) -> Dict[str, Any]:
    meta_path = VERSIONS_DIR / name / "split_metadata.json"
    out: Dict[str, Any] = {"split_version": name, "exists": meta_path.exists()}
    if not meta_path.exists():
        return out
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception as exc:
        out["error"] = str(exc)
        return out
    out.update({
        "split_mode": meta.get("split_mode"),
        "num_classes": meta.get("num_classes"),
        "counts": meta.get("counts"),
        "class_coverage": meta.get("class_coverage"),
        "valid_for_research": meta.get("valid_for_research"),
        "invalid_reasons": meta.get("invalid_reasons") or [],
    })
    return out


@celery_app.task(bind=True, name="app.dataset_prep_tasks.prepare_dataset")
def prepare_dataset(
    self,
    run_id: str,
    profiles: Optional[List[str]] = None,
    version: Optional[str] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    profiles = [p for p in (profiles or ["alphabet", "hoa_de"]) if p]
    version = version or next_manifest_version()
    manifest = f"dataset/manifests/dataset_manifest_{version}.csv"

    report: Dict[str, Any] = {
        "run_id": run_id,
        "status": "running",
        "manifest_version": version,
        "manifest": manifest,
        "profiles": profiles,
        "seed": seed,
        "started_at": _now(),
        "current_step": None,
        "steps": [],
        "artifacts": {},
        "warnings": [],
    }
    _write_report(run_id, report)

    def fail(reason: str) -> Dict[str, Any]:
        report["status"] = "failed"
        report["error"] = reason
        report["finished_at"] = _now()
        report["current_step"] = None
        _write_report(run_id, report)
        logger.error("[PREP] %s thất bại: %s", run_id, reason)
        return report

    if not _run("create_manifest",
                ["python", "scripts/create_dataset_manifest.py", "--version", version],
                report, run_id):
        return fail("không tạo được manifest")

    _run("validate_manifest",
         ["python", "scripts/validate_dataset_manifest.py", "--version", version],
         report, run_id)

    fatal, advisories = _validation_verdict(report["steps"][-1])
    report["warnings"] = advisories
    _write_report(run_id, report)
    if fatal:
        return fail("manifest không hợp lệ: " + "; ".join(fatal))

    for profile in profiles:
        deploy = f"{profile}_deploy_{version.split('_')[-1]}"
        strict = f"{profile}_strict_{version.split('_')[-1]}"
        loso = f"{profile}_loso_{version.split('_')[-1]}"

        base = ["python", "-m", "processed.splits.make_splits",
                "--dataset_manifest", manifest,
                "--recognition_profile", profile,
                "--group_col", "signer_id",
                "--seed", str(seed)]

        # Deployment: every signer in training. Not signer-independent by design.
        _run(f"deploy_split:{profile}",
             base + ["--split_mode", "sample", "--fail_on_missing_eval",
                     "--output_version", deploy],
             report, run_id)

        # Research: signers held out, fail-closed. Not a user-facing choice —
        # make_splits.py itself refuses to write a split it cannot vouch for
        # (needs >= 3 signers per class; see its _assert_signer_disjoint /
        # invalid_reasons gate). A dialect too small for that (Cần Thơ, Spa)
        # fails here on purpose, every time, regardless of who runs it.
        strict_ok = _run(f"strict_split:{profile}",
             base + ["--split_mode", "strict_signer_disjoint",
                     "--exclude_unresolved_signers", "--output_version", strict],
             report, run_id)

        if strict_ok:
            # Folds are re-partitioned from the research split, not from the
            # manifest: make_loso_folds reads train/val/test out of a split
            # DIRECTORY and merges them before regrouping by signer. Handing it
            # the manifest CSV made it find no signer column at all, and the
            # split it would have produced would have carried no manifest
            # checksum, so every run trained on it would fail criterion C5.
            _run(f"loso_folds:{profile}",
                 ["python", "-m", "processed.splits.make_loso_folds",
                  "--source", f"processed/splits/versions/{strict}",
                  "--output_version", loso,
                  "--group_col", "signer_id", "--seed", str(seed)],
                 report, run_id)
        else:
            # Do not even attempt LOSO: its --source directory was never
            # written (strict_split exited before writing anything), so it
            # would fail a second time for the identical root cause and read
            # as a separate, more cryptic error ("source not found") instead
            # of the one real reason. Record one clear entry instead so the
            # stage still shows its true state (amber, not a silent grey
            # "pending forever") rather than two red steps for one cause.
            report["steps"].append({
                "step": f"loso_folds:{profile}",
                "cmd": [],
                "ok": False,
                "returncode": None,
                "started_at": _now(),
                "finished_at": _now(),
                "stdout_tail": "",
                "stderr_tail": (
                    f"skipped: no research split to fold ({profile} does not "
                    f"have enough signer coverage — see strict_split:{profile} above)"
                ),
            })
            report["warnings"].append(
                f"{profile}: not enough signer coverage for a research split "
                f"(needs at least 3 signers per class). Strict split and LOSO "
                f"folds were skipped for this dialect; the deployment split "
                f"above is unaffected and still usable for training."
            )
            _write_report(run_id, report)

        report["artifacts"][profile] = {
            "deployment": _describe_split(deploy),
            "research": _describe_split(strict),
            "loso": {
                "protocol": loso,
                "folds": sorted(
                    p.name for p in (VERSIONS_DIR / loso).iterdir()
                    if p.is_dir() and (p / "train.csv").exists()
                ) if (VERSIONS_DIR / loso).is_dir() else [],
            },
        }
        _write_report(run_id, report)

    produced = [a["deployment"] for a in report["artifacts"].values()
                if a["deployment"].get("exists")]
    report["status"] = "completed" if produced else "failed"
    if not produced:
        report["error"] = "không sinh được split triển khai nào"
    report["current_step"] = None
    report["finished_at"] = _now()
    _write_report(run_id, report)
    logger.info("[PREP] %s %s — manifest=%s", run_id, report["status"], version)
    return report

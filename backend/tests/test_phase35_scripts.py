"""Standalone tests for Phase 3.5 scripts: coverage report, pilot validation,
quarantine, signer merges. Temp workspace only — never touches real data.

Run:  python tests/test_phase35_scripts.py   (requires numpy)
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def _run(script: str, *argv):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *map(str, argv)],
                          capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT))


def _write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)


def test_coverage_report(ws: Path):
    print("[C1 coverage report]")
    mdir = ws / "manifests"
    fields = ["sample_id", "label_key", "vocabulary_scope", "recognition_profile",
              "signer_id", "session_id", "raw_landmarks_available", "quality_status"]
    rows = []
    for i in range(8):
        rows.append({"sample_id": f"a{i}", "label_key": "vn/common/ok",
                     "vocabulary_scope": "common", "recognition_profile": "",
                     "signer_id": f"S00{i % 2 + 1}", "session_id": f"sess{i % 2}",
                     "raw_landmarks_available": "1", "quality_status": "ok"})
    rows.append({"sample_id": "b0", "label_key": "vn/hoa_de/weak",
                 "vocabulary_scope": "profile_specific", "recognition_profile": "hoa_de",
                 "signer_id": "S001", "session_id": "", "raw_landmarks_available": "0",
                 "quality_status": "unknown"})
    _write_csv(mdir / "dataset_manifest_t.csv", fields, rows)
    r = _run("report_dataset_coverage.py", "--version", "t", "--manifest-dir", mdir,
             "--json-out", ws / "cov.json")
    check("coverage exit 0 (warnings allowed)", r.returncode == 0, r.stderr[-300:])
    rep = json.loads((ws / "cov.json").read_text(encoding="utf-8"))
    types = {w["type"] for w in rep["warnings"]}
    check("warns few_signers", "few_signers" in types, types)
    check("warns few_sessions", "few_sessions" in types, types)
    check("warns no_raw_landmarks", "no_raw_landmarks" in types, types)
    check("warns class_imbalance", "class_imbalance" in types, types)
    check("profiles include common + hoa_de",
          set(rep["profiles"]) >= {"common", "hoa_de"}, rep["profiles"].keys())
    r = _run("report_dataset_coverage.py", "--version", "t", "--manifest-dir", mdir, "--strict")
    check("--strict exits 1 with warnings", r.returncode == 1)


def test_pilot_validation(ws: Path):
    print("[C2 pilot validation]")
    feats = ws / "features" / "vn" / "hoa-de" / "class_ok_u1"
    feats.mkdir(parents=True)
    # Build a CONSISTENT raw -> normalized pair: the pilot gate re-derives the
    # normalized frames from landmarks_raw via the shared normalization module,
    # so the fixture must be a real product of that module (a pair of unrelated
    # random arrays would, correctly, be rejected).
    from processed.shared.normalization import normalize_hands_vector_126

    raw = np.random.rand(45, 126).astype(np.float32)
    raw[:, 63:] = 0.0  # right-hand slot absent -> exercises the per-hand masks
    seq = np.zeros((60, 126), dtype=np.float32)
    for t in range(raw.shape[0]):
        seq[t] = normalize_hands_vector_126(raw[t])
    fm = np.any(seq != 0.0, axis=1)
    good = feats / "sample_good.npz"
    np.savez_compressed(good, sequence=seq, landmarks_normalized=seq,
                        landmarks_raw=raw,
                        frame_valid_mask=fm,
                        left_hand_valid_mask=np.any(seq[:, :63] != 0.0, axis=1),
                        right_hand_valid_mask=np.any(seq[:, 63:] != 0.0, axis=1))
    # Mirrors exactly what the camera path writes: routers/upload.py builds the
    # QC + provenance meta and dataset_samples.save_sequence_npz stamps
    # storage_contract_version.
    good.with_suffix(".json").write_text(json.dumps({
        "signer_id": "S001", "session_id": "sess-1", "collection_campaign": "pilot_t",
        "normalization_version": "hands126_v1", "preprocess_contract_version": "v2",
        "storage_contract_version": "npz_v2", "quality_status": "ok",
        "completeness": 0.95, "jitter": 0.011,
        "left_hand_ratio": 1.0, "right_hand_ratio": 0.0}),
        encoding="utf-8")
    bad = feats / "sample_bad.npz"
    np.savez_compressed(bad, sequence=seq)  # legacy shape: no raw/masks/sidecar

    labels = ws / "labels.csv"
    _write_csv(labels, ["folder_name", "slug", "semantic_label", "vocabulary_scope", "recognition_profile"],
               [{"folder_name": "class_ok_u1", "slug": "ok", "semantic_label": "ok",
                 "vocabulary_scope": "profile_specific", "recognition_profile": "hoa_de"}])
    signers = ws / "signers.csv"
    _write_csv(signers, ["signer_id", "display_name", "is_active"],
               [{"signer_id": "S001", "display_name": "Trân", "is_active": "1"}])

    r = _run("validate_pilot_samples.py", "--paths", good, "--features-root", ws / "features",
             "--labels-csv", labels, "--signers-csv", signers, "--campaign", "pilot_t")
    check("valid v2 sample passes", r.returncode == 0, r.stdout[-300:])
    r = _run("validate_pilot_samples.py", "--paths", bad, "--features-root", ws / "features",
             "--labels-csv", labels, "--signers-csv", signers)
    check("legacy sample fails gate", r.returncode == 1, r.stdout[-300:])
    check("missing keys reported", "npz missing keys" in r.stdout, r.stdout[-300:])


def test_quarantine(ws: Path):
    print("[C3 quarantine]")
    victim_dir = ws / "dataset" / "features" / "vn" / "x" / "class_y"
    victim_dir.mkdir(parents=True)
    # Script resolves paths against REPO_ROOT; use a decisions file with an
    # absolute-ish relative path under the temp ws via REPO_ROOT trick:
    victim = victim_dir / "sample_z.npz"
    victim.write_bytes(b"npzdata")
    rel = victim.relative_to(ws)
    decisions = ws / "decisions.json"
    decisions.write_text(json.dumps({"files": [
        {"path": str(rel).replace("\\", "/"), "reason": "test orphan", "decision": "pending"}]}),
        encoding="utf-8")

    # quarantine script uses REPO_ROOT as base — run with ws as cwd via a tiny wrapper
    env_script = f"""
import sys, runpy
sys.argv = ['quarantine_files.py', '--decisions', r'{decisions}', '--quarantine-root', r'{ws / 'dataset' / 'quarantine'}']
import importlib.util
spec = importlib.util.spec_from_file_location('q', r'{SCRIPTS / 'quarantine_files.py'}')
m = importlib.util.module_from_spec(spec)
m.__dict__['__name__'] = 'q'
spec.loader.exec_module(m)
m.REPO_ROOT = __import__('pathlib').Path(r'{ws}')
sys.exit(m.main())
"""
    r = subprocess.run([sys.executable, "-c", env_script], capture_output=True, text=True, encoding="utf-8")
    check("pending -> nothing moves (dry-run)", r.returncode == 0 and victim.exists(), r.stdout[-200:])

    decisions.write_text(json.dumps({"files": [
        {"path": str(rel).replace("\\", "/"), "reason": "test orphan", "decision": "quarantine"}]}),
        encoding="utf-8")
    r = subprocess.run([sys.executable, "-c", env_script], capture_output=True, text=True, encoding="utf-8")
    check("quarantine without --confirm = dry-run", victim.exists(), r.stdout[-200:])

    env_script_confirm = env_script.replace("'--quarantine-root'", "'--confirm', '--quarantine-root'")
    r = subprocess.run([sys.executable, "-c", env_script_confirm], capture_output=True, text=True, encoding="utf-8")
    moved = list((ws / "dataset" / "quarantine").rglob("sample_z.npz"))
    check("--confirm moves file (not deleted)", (not victim.exists()) and len(moved) == 1,
          f"exists={victim.exists()} moved={moved} out={r.stdout[-200:]}")
    logs = list((ws / "dataset" / "quarantine").rglob("quarantine_log.json"))
    check("quarantine log written", len(logs) == 1)


def main() -> int:
    ws = Path(tempfile.mkdtemp(prefix="p35_"))
    try:
        test_coverage_report(ws)
        test_pilot_validation(ws)
        test_quarantine(ws)
    finally:
        shutil.rmtree(ws, ignore_errors=True)
    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())

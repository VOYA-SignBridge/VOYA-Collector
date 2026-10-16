"""Run the manifest release chain, stopping at the first failure.

Orchestration only — every step shells out to an existing tool. No validation
logic lives here, so there is exactly one implementation of each rule.

Chain:
    1. pilot validation        validate_pilot_samples.py --campaign
    2. duplicate audit         audit_duplicate_samples.py
    3. create manifest         create_dataset_manifest.py   (never --force)
    4. validate manifest       validate_dataset_manifest.py --check-checksums
    5. sample-level split      make_splits.py --dataset_manifest ...
    6. signer-disjoint split   make_splits.py --split_mode strict_signer_disjoint
                               (ATTEMPTED per profile; a hard failure here is
                               reported, not fatal — insufficient signer
                               diversity is a dataset fact, not a pipeline bug)
    7. aggregate               aggregate_experiment_results.py

Training is NOT run from here: an official run must be launched explicitly
with --run-purpose research so nobody trains a paper model by accident.

Every command, its exit code and the resulting checksums are written to
reports/release_log_<manifest-version>.json.

Usage:
    python scripts/prepare_research_release.py \
        --campaign isds2026_v4 \
        --manifest-version isds2026_v4 \
        --profiles alphabet hoa_de

    python scripts/prepare_research_release.py ... --dry-run
"""

from __future__ import annotations

import sys as _sys
sys_path_dir = __import__('pathlib').Path(__file__).resolve().parent
if str(sys_path_dir) not in _sys.path:
    _sys.path.insert(0, str(sys_path_dir))
import _console  # noqa: F401  (force UTF-8 console on Windows)

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / "scripts"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Release:
    def __init__(self, dry_run: bool):
        self.dry_run = dry_run
        self.steps: list = []

    def run(self, title: str, argv: list, *, fatal: bool = True) -> int:
        cmd = [sys.executable] + [str(a) for a in argv]
        printable = " ".join(str(a) for a in argv)
        print(f"\n{'=' * 72}\n[STEP] {title}\n  $ python {printable}\n{'=' * 72}")
        if self.dry_run:
            self.steps.append({"step": title, "command": printable,
                               "exit_code": None, "skipped": "dry-run"})
            print("  (dry-run: not executed)")
            return 0
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT))
        rc = proc.returncode
        self.steps.append({"step": title, "command": printable, "exit_code": rc,
                           "fatal": fatal})
        if rc != 0:
            if fatal:
                print(f"\n[ABORT] step failed (exit {rc}): {title}")
            else:
                print(f"\n[WARN] non-fatal step failed (exit {rc}): {title}")
        return rc


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--campaign", required=True,
                    help="collection_campaign stamped on the new samples")
    ap.add_argument("--manifest-version", required=True,
                    help="NEW manifest version (must not already exist)")
    ap.add_argument("--profiles", nargs="+", default=["alphabet", "hoa_de"])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--features-root", type=Path, default=REPO_ROOT / "dataset" / "features")
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "reports")
    ap.add_argument("--skip-pilot", action="store_true",
                    help="skip pilot validation (only when it already passed for this campaign)")
    ap.add_argument("--dry-run", action="store_true", help="print the chain without running it")
    ap.add_argument("--consent-snapshot", type=Path,
                    default=REPO_ROOT / "dataset" / "consent_snapshot.json",
                    help="Ảnh chụp đồng thuận. Kiểm ở đây, TRƯỚC khi chuỗi chạy.")
    ap.add_argument("--skip-consent-gate", action="store_true",
                    help="Bỏ qua cổng đồng thuận trên toàn chuỗi phát hành.")
    args = ap.parse_args()

    manifest_dir = REPO_ROOT / "dataset" / "manifests"
    manifest_csv = manifest_dir / f"dataset_manifest_{args.manifest_version}.csv"
    versions_dir = REPO_ROOT / "processed" / "splits" / "versions"

    # Refuse to start if the release would overwrite frozen artifacts.
    preflight = []
    if manifest_csv.exists():
        preflight.append(f"manifest already exists: {manifest_csv} — manifests are "
                         f"immutable, choose a NEW --manifest-version")
    planned_splits = []
    for profile in args.profiles:
        planned_splits.append(f"{profile}_sample_{args.manifest_version}")
        planned_splits.append(f"{profile}_signer_disjoint_{args.manifest_version}")
    for name in planned_splits:
        d = versions_dir / name
        if d.exists() and any(d.iterdir()):
            preflight.append(f"split version already exists: {d} — split versions "
                             f"are immutable, choose a new --manifest-version")
    # Cổng đồng thuận kiểm Ở ĐÂY, trước khi chuỗi chạy — dù bước 3 (dựng
    # manifest) cũng tự kiểm. Lý do: chuỗi này có bảy bước và bước tốn thời gian
    # nhất nằm TRƯỚC bước dựng manifest. Để nó chạy xong xác thực pilot rồi mới
    # báo "ảnh chụp đồng thuận quá hạn" là bắt người ta chờ để nhận một câu lẽ
    # ra nói được ngay giây đầu.
    if args.skip_consent_gate:
        print("[WARN] cong dong thuan BI BO QUA tren toan chuoi phat hanh")
    else:
        import sys as _s
        if str(REPO_ROOT / "backend") not in _s.path:
            _s.path.insert(0, str(REPO_ROOT / "backend"))
        try:
            from app.consent_gate import SnapshotUnusable, load_snapshot

            consents, _al, meta = load_snapshot(args.consent_snapshot)
            live = sum(1 for c in consents.values() if c.highest_live_rank is not None)
            print(f"[consent] anh chup ok: {len(consents)} nguoi ky, {live} con hieu luc, "
                  f"tao luc {meta.get('generated_at')}")
            if live == 0:
                preflight.append(
                    "khong co dong thuan nao con hieu luc — moi split muc "
                    "'research_release' se RONG. Thu dong thuan truoc, hoac chay "
                    "voi --skip-consent-gate neu that su muon.")
        except SnapshotUnusable as exc:
            preflight.append(f"cong dong thuan: {exc}")

    if preflight:
        print("[ABORT] pre-flight checks failed:")
        for p in preflight:
            print(f"  - {p}")
        return 2

    rel = Release(args.dry_run)
    started = datetime.now().isoformat(timespec="seconds")

    if not args.skip_pilot:
        if rel.run("1/7 pilot validation",
                   [SCRIPTS / "validate_pilot_samples.py", "--campaign", args.campaign,
                    "--features-root", args.features_root]) != 0:
            return _finish(rel, args, started, ok=False)
    else:
        print("[SKIP] pilot validation (--skip-pilot)")

    if rel.run("2/7 duplicate audit",
               [SCRIPTS / "audit_duplicate_samples.py",
                "--features-root", args.features_root]) != 0:
        return _finish(rel, args, started, ok=False)

    # NOTE: --force is never passed. A manifest release that would overwrite an
    # existing version must fail.
    if rel.run("3/7 create immutable manifest",
               [SCRIPTS / "create_dataset_manifest.py",
                "--version", args.manifest_version,
                "--features-root", args.features_root]) != 0:
        return _finish(rel, args, started, ok=False)

    if rel.run("4/7 validate manifest",
               [SCRIPTS / "validate_dataset_manifest.py",
                "--version", args.manifest_version,
                "--features-root", args.features_root,
                "--check-checksums"]) != 0:
        return _finish(rel, args, started, ok=False)

    split_results = {}
    for profile in args.profiles:
        name = f"{profile}_sample_{args.manifest_version}"
        rc = rel.run(f"5/7 sample-level split [{profile}]",
                     [SCRIPTS.parent / "processed" / "splits" / "make_splits.py",
                      "--dataset_manifest", manifest_csv,
                      "--recognition_profile", profile,
                      "--split_mode", "sample",
                      "--output_version", name,
                      "--seed", args.seed])
        split_results[name] = rc
        if rc != 0:
            return _finish(rel, args, started, ok=False, splits=split_results)

    for profile in args.profiles:
        name = f"{profile}_signer_disjoint_{args.manifest_version}"
        # Non-fatal: with too few signers this SHOULD fail, and that is a
        # dataset finding to report — not a reason to abandon the release.
        rc = rel.run(f"6/7 strict signer-disjoint split [{profile}] (attempt)",
                     [SCRIPTS.parent / "processed" / "splits" / "make_splits.py",
                      "--dataset_manifest", manifest_csv,
                      "--recognition_profile", profile,
                      "--split_mode", "strict_signer_disjoint",
                      "--group_col", "signer_id",
                      "--output_version", name,
                      "--seed", args.seed],
                     fatal=False)
        split_results[name] = rc

    rel.run("7/7 aggregate existing results",
            [SCRIPTS / "aggregate_experiment_results.py"], fatal=False)

    return _finish(rel, args, started, ok=True, splits=split_results)


def _finish(rel: Release, args, started: str, *, ok: bool, splits: dict | None = None) -> int:
    manifest_dir = REPO_ROOT / "dataset" / "manifests"
    manifest_csv = manifest_dir / f"dataset_manifest_{args.manifest_version}.csv"
    versions_dir = REPO_ROOT / "processed" / "splits" / "versions"

    checksums = {}
    if manifest_csv.exists():
        checksums[manifest_csv.name] = sha256_file(manifest_csv)

    split_meta = {}
    for name, rc in (splits or {}).items():
        meta_path = versions_dir / name / "split_metadata.json"
        if meta_path.exists():
            try:
                m = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                m = {}
            split_meta[name] = {
                "exit_code": rc,
                "valid_for_research": m.get("valid_for_research"),
                "invalid_reasons": m.get("invalid_reasons", []),
                "counts": m.get("counts"),
                "signer_counts": m.get("signer_counts"),
                "dataset_manifest_checksum": m.get("dataset_manifest_checksum"),
            }
        else:
            split_meta[name] = {"exit_code": rc, "written": False}

    log = {
        "started_at": started,
        "finished_at": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "campaign": args.campaign,
        "manifest_version": args.manifest_version,
        "profiles": args.profiles,
        "seed": args.seed,
        "dry_run": args.dry_run,
        "checksums": checksums,
        "splits": split_meta,
        "steps": rel.steps,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out = args.out_dir / f"release_log_{args.manifest_version}.json"
    out.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n{'=' * 72}")
    print(f"release chain: {'OK' if ok else 'FAILED'}")
    for name, info in split_meta.items():
        v = info.get("valid_for_research")
        tag = {True: "valid_for_research=true", False: "valid_for_research=FALSE"}.get(
            v, "not written")
        print(f"  {name:<45} {tag}")
    if checksums:
        for k, v in checksums.items():
            print(f"  {k}: sha256={v[:16]}...")
    print(f"log -> {out}")
    if ok:
        print("\nNext: train an official run explicitly, e.g.")
        print("  python processed/train_utils/train_tcn.py --run-purpose research \\")
        print(f"    --dataset_version {args.manifest_version} --split_version "
              f"{args.profiles[0]}_sample_{args.manifest_version} ...")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

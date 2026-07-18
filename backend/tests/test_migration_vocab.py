"""Standalone tests for scripts/migrate_legacy_vocabulary_schema.py.

Run:  python tests/test_migration_vocab.py
Uses a temp workspace — never touches the real dataset. Pure stdlib.
"""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "migrate_legacy_vocabulary_schema.py"
MAPPING = REPO_ROOT / "config" / "legacy_vocabulary_mapping.json"

PASSED: list = []
FAILED: list = []


def check(name: str, cond: bool, detail: str = "") -> None:
    (PASSED if cond else FAILED).append((name, detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + ("" if cond else f"  -> {detail}"))


def _mk_workspace() -> Path:
    ws = Path(tempfile.mkdtemp(prefix="vocab_mig_"))
    labels = ws / "labels.csv"
    with labels.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "class_uid", "class_idx", "slug", "label_original", "language", "dialect",
            "is_common_global", "is_common_language", "folder_name", "created_at", "migrated_at"])
        w.writeheader()
        w.writerow({"class_uid": "u1", "class_idx": "1", "slug": "rang-muoi", "label_original": "rang muối",
                    "language": "vn", "dialect": "hoa-de", "created_at": "t", "migrated_at": "t"})
        w.writerow({"class_uid": "u2", "class_idx": "2", "slug": "a", "label_original": "a",
                    "language": "vn", "dialect": "bang-chu-cai", "created_at": "t", "migrated_at": "t"})
        w.writerow({"class_uid": "u3", "class_idx": "3", "slug": "vao-lop", "label_original": "vào lớp",
                    "language": "vn", "dialect": "can-tho", "created_at": "t", "migrated_at": "t"})
        w.writerow({"class_uid": "u4", "class_idx": "4", "slug": "la", "label_original": "lạ",
                    "language": "vn", "dialect": "unknown-dialect", "created_at": "t", "migrated_at": "t"})
    src = ws / "split.csv"
    with src.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["sample_uid", "user_id"])
        w.writeheader()
        for name in ["Minh", "Minh", "minh", "Trân", "Tran", "user1"]:
            w.writerow({"sample_uid": "s", "user_id": name})
    return ws


def _run(ws: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT),
         "--mapping", str(MAPPING),
         "--labels-csv", str(ws / "labels.csv"),
         "--signers-csv", str(ws / "signers.csv"),
         "--signer-mapping-out", str(ws / "signer_mapping.json"),
         "--signer-sources", str(ws / "split.csv"),
         "--backup-dir", str(ws / "backups"),
         *extra],
        capture_output=True, text=True, encoding="utf-8", cwd=str(REPO_ROOT),
    )


def _read(path: Path):
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main() -> int:
    ws = _mk_workspace()
    try:
        print("[M1 dry-run writes nothing]")
        before = (ws / "labels.csv").read_bytes()
        r = _run(ws, "--dry-run")
        check("dry-run exit 0", r.returncode == 0, r.stderr[-400:])
        check("labels.csv unchanged", (ws / "labels.csv").read_bytes() == before)
        check("no signers.csv created", not (ws / "signers.csv").exists())
        check("no backup dir created", not (ws / "backups").exists())

        print("[M2 apply]")
        r = _run(ws)
        check("apply exit 0", r.returncode == 0, r.stderr[-400:])
        rows = _read(ws / "labels.csv")
        by_uid = {x["class_uid"]: x for x in rows}
        check("hoa-de confirmed -> profile_specific/hoa_de",
              by_uid["u1"]["vocabulary_scope"] == "profile_specific"
              and by_uid["u1"]["recognition_profile"] == "hoa_de")
        check("hoa-de semantic_label", by_uid["u1"]["semantic_label"] == "rang_muoi")
        check("bang-chu-cai NOT declared common (needs review)",
              by_uid["u2"]["vocabulary_scope"] == "" and by_uid["u2"]["vocabulary_group"] == "alphabet")
        check("can-tho NOT mapped to south",
              by_uid["u3"]["vocabulary_scope"] == ""
              and by_uid["u3"]["recognition_profile"] == "legacy_unassigned")
        check("unknown dialect reported, untouched", by_uid["u4"]["vocabulary_scope"] == "")
        check("backup created", any((ws / "backups").glob("labels_*.csv")))
        signers = _read(ws / "signers.csv")
        names = {s["display_name"]: s["signer_id"] for s in signers}
        check("5 distinct signers (no auto-merge)", len(signers) == 5, names)
        check("Minh vs minh separate IDs", names.get("Minh") != names.get("minh"), names)
        mapping = json.loads((ws / "signer_mapping.json").read_text(encoding="utf-8"))
        mc = mapping["merge_candidates_requiring_confirmation"]
        check("merge candidates reported (Minh/minh, Tran/Trân)", len(mc) >= 2, mc)

        print("[M3 idempotent]")
        after_first = (ws / "labels.csv").read_text(encoding="utf-8")
        r = _run(ws)
        check("second apply exit 0", r.returncode == 0, r.stderr[-400:])
        rows2 = _read(ws / "labels.csv")
        check("scope values unchanged on re-run",
              [x["vocabulary_scope"] for x in rows2] == [x["vocabulary_scope"] for x in rows])
        signers2 = _read(ws / "signers.csv")
        check("no duplicate signers on re-run", len(signers2) == 5, len(signers2))
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    for n, d in FAILED:
        print(f"  FAILED: {n}: {d}")
    return 1 if FAILED else 0


if __name__ == "__main__":
    raise SystemExit(main())

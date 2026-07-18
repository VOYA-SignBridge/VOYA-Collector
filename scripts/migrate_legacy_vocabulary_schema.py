"""Migrate legacy labels.csv / signer usernames to vocabulary schema v2.

Usage:
    python scripts/migrate_legacy_vocabulary_schema.py --dry-run \
        --mapping config/legacy_vocabulary_mapping.json
    python scripts/migrate_legacy_vocabulary_schema.py \
        --mapping config/legacy_vocabulary_mapping.json

Guarantees:
  - dry-run never writes anything;
  - a timestamped backup of every file it will touch is created first;
  - idempotent: already-filled v2 cells are NEVER overwritten;
  - no semantic guessing: only `status: confirmed` mapping entries assign a
    vocabulary_scope; everything else is reported for manual confirmation;
  - signer registry: one signer_id per DISTINCT raw name — visually similar
    names (Tran/Trân/trân) are NOT merged, only reported as merge candidates;
  - prints before/after statistics and writes a JSON report.

Pure stdlib — runnable on host and in any container.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from processed.shared.vocabulary import (  # noqa: E402
    LABEL_V2_FIELDS,
    semantic_label_from_slug,
    validate_label_v2,
)

SIGNER_FIELDS = ["signer_id", "display_name", "regional_group", "external_user_id", "is_active", "created_at"]


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _read_csv(path: Path):
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def _write_csv(path: Path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)


def _backup(path: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"{path.stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{path.suffix}"
    shutil.copy2(path, dest)
    return dest


def _strip_key(name: str) -> str:
    """Casefold + diacritic-stripped form — ONLY for detecting merge candidates
    to report; never used to actually merge identities."""
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.replace("đ", "d").replace("Đ", "d").casefold().strip()


def migrate_labels(labels_csv: Path, mapping: dict, *, dry_run: bool, backup_dir: Path):
    rows, fieldnames = _read_csv(labels_csv)
    for col in LABEL_V2_FIELDS:
        if col not in fieldnames:
            fieldnames.append(col)

    dialect_map = mapping.get("dialect_mapping", {})
    default_campaign = mapping.get("default_collection_campaign", "legacy_2026")

    stats_before = Counter((r.get("vocabulary_scope") or "<empty>").strip() or "<empty>" for r in rows)
    updated, skipped_already, needs_review, unmapped = 0, 0, [], []

    for r in rows:
        # Idempotency: a row that already carries a scope is left untouched.
        if (r.get("vocabulary_scope") or "").strip():
            skipped_already += 1
            continue

        dialect = (r.get("dialect") or "").strip()
        entry = dialect_map.get(dialect)
        slug = (r.get("slug") or "").strip()

        if not (r.get("semantic_label") or "").strip():
            r["semantic_label"] = semantic_label_from_slug(slug)
        if not (r.get("is_active") or "").strip():
            r["is_active"] = "1"
        if not (r.get("collection_campaign") or "").strip():
            r["collection_campaign"] = (entry or {}).get("collection_campaign", default_campaign)

        if entry is None:
            unmapped.append({"class_uid": r.get("class_uid"), "slug": slug, "dialect": dialect})
            continue

        if not (r.get("vocabulary_group") or "").strip():
            r["vocabulary_group"] = entry.get("vocabulary_group", "")

        if entry.get("status") == "confirmed":
            r["vocabulary_scope"] = entry.get("vocabulary_scope", "")
            r["recognition_profile"] = entry.get("recognition_profile", "")
            errs = validate_label_v2(r)
            if errs:
                unmapped.append({"class_uid": r.get("class_uid"), "slug": slug, "dialect": dialect, "errors": errs})
                r["vocabulary_scope"] = ""
                r["recognition_profile"] = ""
            else:
                updated += 1
        else:
            # needs_review: fill non-semantic fields only; scope stays unassigned.
            if not (r.get("recognition_profile") or "").strip():
                r["recognition_profile"] = entry.get("recognition_profile", "")
            needs_review.append({
                "class_uid": r.get("class_uid"), "slug": slug, "dialect": dialect,
                "note": entry.get("note", ""),
            })

    stats_after = Counter((r.get("vocabulary_scope") or "<empty>").strip() or "<empty>" for r in rows)

    if not dry_run:
        _backup(labels_csv, backup_dir)
        _write_csv(labels_csv, rows, fieldnames)

    return {
        "labels_total": len(rows),
        "labels_updated_confirmed": updated,
        "labels_already_migrated": skipped_already,
        "labels_needs_review": needs_review,
        "labels_unmapped": unmapped,
        "scope_stats_before": dict(stats_before),
        "scope_stats_after": dict(stats_after),
    }


def collect_legacy_signer_names(sources) -> Counter:
    counts: Counter = Counter()
    for src in sources:
        if not src.exists():
            continue
        rows, _ = _read_csv(src)
        for r in rows:
            name = (r.get("user_id") or "").strip()
            if name:
                counts[name] += 1
    return counts


def migrate_signers(signers_csv: Path, name_counts: Counter, signer_mapping_path: Path,
                    *, dry_run: bool, backup_dir: Path):
    existing_rows, fieldnames = ([], list(SIGNER_FIELDS))
    if signers_csv.exists():
        existing_rows, fieldnames = _read_csv(signers_csv)
        for col in SIGNER_FIELDS:
            if col not in fieldnames:
                fieldnames.append(col)

    by_display = {(r.get("display_name") or "").strip(): r for r in existing_rows}
    existing_ids = [r.get("signer_id") or "" for r in existing_rows]
    max_n = 0
    for sid in existing_ids:
        if sid.startswith("S") and sid[1:].isdigit():
            max_n = max(max_n, int(sid[1:]))

    created = []
    # Deterministic order: by sample count desc, then name.
    for name, _cnt in sorted(name_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if name in by_display:
            continue
        max_n += 1
        row = {
            "signer_id": f"S{max_n:03d}",
            "display_name": name,
            "regional_group": "",
            "external_user_id": "",
            "is_active": "1",
            "created_at": _now(),
        }
        existing_rows.append(row)
        by_display[name] = row
        created.append(row)

    # Merge candidates: identical after casefold+diacritics-strip → REPORT ONLY.
    groups: dict = {}
    for name in by_display:
        groups.setdefault(_strip_key(name), []).append(name)
    merge_candidates = [
        {"names": sorted(names),
         "signer_ids": sorted(by_display[n]["signer_id"] for n in names),
         "action_required": "confirm whether these are the same person; if so, edit the mapping file and re-run"}
        for key, names in sorted(groups.items()) if len(names) > 1
    ]

    name_to_id = {name: r["signer_id"] for name, r in by_display.items()}

    if not dry_run:
        if signers_csv.exists():
            _backup(signers_csv, backup_dir)
        signers_csv.parent.mkdir(parents=True, exist_ok=True)
        _write_csv(signers_csv, existing_rows, fieldnames)
        signer_mapping_path.parent.mkdir(parents=True, exist_ok=True)
        signer_mapping_path.write_text(
            json.dumps({"legacy_name_to_signer_id": name_to_id,
                        "merge_candidates_requiring_confirmation": merge_candidates},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return {
        "signers_total": len(existing_rows),
        "signers_created": len(created),
        "signer_name_to_id": name_to_id,
        "merge_candidates_requiring_confirmation": merge_candidates,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mapping", type=Path, default=REPO_ROOT / "config" / "legacy_vocabulary_mapping.json")
    ap.add_argument("--labels-csv", type=Path, default=REPO_ROOT / "dataset" / "labels.csv")
    ap.add_argument("--signers-csv", type=Path, default=REPO_ROOT / "dataset" / "signers.csv")
    ap.add_argument("--signer-mapping-out", type=Path,
                    default=REPO_ROOT / "config" / "legacy_signer_mapping.json")
    ap.add_argument("--signer-sources", type=Path, nargs="*",
                    default=[REPO_ROOT / "processed" / "splits" / "train.csv",
                             REPO_ROOT / "processed" / "splits" / "val.csv",
                             REPO_ROOT / "processed" / "splits" / "test.csv",
                             REPO_ROOT / "dataset" / "samples" / "samples.csv"])
    ap.add_argument("--backup-dir", type=Path, default=REPO_ROOT / "dataset" / "backups")
    ap.add_argument("--report-out", type=Path, default=None,
                    help="Write the JSON report here (default: alongside labels.csv; skipped in dry-run)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.labels_csv.exists():
        print(f"[ERROR] labels csv not found: {args.labels_csv}")
        return 2
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))

    label_report = migrate_labels(args.labels_csv, mapping, dry_run=args.dry_run, backup_dir=args.backup_dir)
    name_counts = collect_legacy_signer_names(args.signer_sources)
    signer_report = migrate_signers(args.signers_csv, name_counts, args.signer_mapping_out,
                                    dry_run=args.dry_run, backup_dir=args.backup_dir)

    report = {
        "generated_at": _now(),
        "dry_run": args.dry_run,
        "labels": label_report,
        "signers": signer_report,
    }

    print(f"\n=== MIGRATION {'DRY-RUN' if args.dry_run else 'APPLY'} REPORT ===")
    print(f"labels: total={label_report['labels_total']} "
          f"confirmed-updated={label_report['labels_updated_confirmed']} "
          f"already-migrated={label_report['labels_already_migrated']} "
          f"needs_review={len(label_report['labels_needs_review'])} "
          f"unmapped={len(label_report['labels_unmapped'])}")
    print(f"scope before: {label_report['scope_stats_before']}")
    print(f"scope after:  {label_report['scope_stats_after']}")
    print(f"signers: total={signer_report['signers_total']} created={signer_report['signers_created']} "
          f"merge-candidates={len(signer_report['merge_candidates_requiring_confirmation'])}")
    for mc in signer_report["merge_candidates_requiring_confirmation"]:
        print(f"  [CONFIRM] possible same person: {mc['names']} -> {mc['signer_ids']}")
    for nr in label_report["labels_needs_review"][:10]:
        print(f"  [REVIEW] {nr['dialect']}/{nr['slug']}: {nr['note']}")
    if label_report["labels_unmapped"]:
        print(f"  [UNMAPPED] {label_report['labels_unmapped']}")

    if not args.dry_run:
        report_path = args.report_out or args.labels_csv.parent / "migration_report_vocab_v2.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report -> {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

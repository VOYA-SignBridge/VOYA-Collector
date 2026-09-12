"""Extract the Vietnamese fingerspelling subset from the canonical samples CSV."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = REPO_ROOT / "dataset" / "samples" / "samples.csv"
DEFAULT_OUTPUT = REPO_ROOT / "dataset" / "alphabet" / "samples.csv"
DEFAULT_LABELS = REPO_ROOT / "dataset" / "alphabet" / "labels.csv"
DEFAULT_SUMMARY = REPO_ROOT / "dataset" / "alphabet" / "extraction_summary.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract rows whose dialect is 'bang-chu-cai'."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--dialect", default="bang-chu-cai")
    return parser.parse_args()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def main() -> None:
    args = parse_args()
    fieldnames, rows = read_csv(args.input)

    required_columns = {"sample_uid", "class_uid", "dialect"}
    missing_columns = sorted(required_columns.difference(fieldnames))
    if missing_columns:
        raise ValueError(
            f"Missing required columns in {args.input}: {', '.join(missing_columns)}"
        )

    wanted_dialect = args.dialect.strip().casefold()
    selected = [
        row
        for row in rows
        if (row.get("dialect") or "").strip().casefold() == wanted_dialect
    ]
    if not selected:
        raise ValueError(f"No rows found for dialect '{args.dialect}'")

    _, label_rows = read_csv(args.labels)
    label_by_uid = {
        (row.get("class_uid") or "").strip(): row
        for row in label_rows
        if (row.get("class_uid") or "").strip()
    }
    selected_class_uids = {
        (row.get("class_uid") or "").strip() for row in selected
    }
    missing_label_uids = sorted(selected_class_uids.difference(label_by_uid))
    if missing_label_uids:
        raise ValueError(
            "Alphabet samples reference class_uid values missing from labels.csv: "
            + ", ".join(missing_label_uids)
        )

    sample_uid_counts = Counter((row.get("sample_uid") or "").strip() for row in selected)
    duplicate_sample_uids = sorted(
        uid for uid, count in sample_uid_counts.items() if uid and count > 1
    )
    if duplicate_sample_uids:
        raise ValueError(
            "Duplicate sample_uid values in extracted subset: "
            + ", ".join(duplicate_sample_uids[:20])
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output.with_suffix(args.output.suffix + ".tmp")
    with temporary_output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(selected)
    temporary_output.replace(args.output)

    class_counts = Counter(
        (row.get("label_original") or row.get("slug") or row.get("class_uid") or "").strip()
        for row in selected
    )
    user_counts = Counter(
        (row.get("user_id") or "").strip() or "<missing>" for row in selected
    )

    local_feature_count = 0
    missing_local_feature_count = 0
    for row in selected:
        storage_key = (row.get("storage_key") or "").strip()
        if not storage_key:
            missing_local_feature_count += 1
            continue
        feature_path = REPO_ROOT / "dataset" / Path(storage_key)
        if feature_path.is_file():
            local_feature_count += 1
        else:
            missing_local_feature_count += 1

    summary = {
        "source": str(args.input),
        "output": str(args.output),
        "dialect": args.dialect,
        "source_rows": len(rows),
        "selected_rows": len(selected),
        "class_count": len(selected_class_uids),
        "class_counts": dict(sorted(class_counts.items())),
        "user_count": len(user_counts),
        "user_counts": dict(sorted(user_counts.items())),
        "local_feature_files": local_feature_count,
        "missing_local_feature_files": missing_local_feature_count,
        "duplicate_sample_uids": duplicate_sample_uids,
        "missing_label_uids": missing_label_uids,
    }
    args.summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

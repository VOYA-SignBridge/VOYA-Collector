"""Prepare current local CSV/NPZ data using the existing split implementation.

Does not train a model, rewrite source CSVs, normalize NPZ a second time, or
overwrite any existing split. Run from the repository root, for example:
    python scripts/prepare_local_training.py --run-id local-20261019
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    # Existing split scripts print Vietnamese. Windows pipe encoding may be
    # cp1252 even when the source files and CSVs are UTF-8.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", args.run_id):
        parser.error("run-id must contain only letters, digits, underscores and hyphens")
    prepared = ROOT / "dataset" / "prepared" / args.run_id
    if prepared.exists():
        parser.error(f"Already exists; choose another run-id: {prepared}")
    prepared.mkdir(parents=True)
    sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

    from processed.train_utils.label_mapping import consume_declared, partitions_agree
    from processed.train_utils.signer_identity import canonical_signer

    source_paths = {name: ROOT / "dataset" / f"{name}.csv" for name in ("labels", "samples")}
    source_hashes = {name: sha256(path) for name, path in source_paths.items()}
    for name, path in source_paths.items():
        shutil.copy2(path, prepared / f"source_{name}.csv")
    labels, label_fields = read_csv(source_paths["labels"])
    samples, sample_fields = read_csv(source_paths["samples"])
    lookup = {row["class_uid"]: row for row in labels}
    if len(lookup) != len(labels):
        raise ValueError("Duplicate class_uid in labels.csv")
    if len({row["sample_uid"] for row in samples}) != len(samples):
        raise ValueError("Duplicate sample_uid in samples.csv")

    features = (ROOT / "dataset" / "features").resolve()
    available = {path.resolve() for path in features.rglob("*.npz")}
    clean, excluded, corrections = [], [], []
    referenced = set()
    fingerprints = {}
    for index, original in enumerate(samples):
        row = dict(original)
        label = lookup.get(row.get("class_uid"))
        reason = ""
        if not label:
            reason = "unknown_class_uid"
        elif row.get("deleted_at", "").strip() or label.get("deleted_at", "").strip():
            reason = "deleted_sample_or_label"
        elif label.get("is_active", "1").strip() != "1":
            reason = "inactive_label"
        elif row.get("review_status", "").strip().lower() != "approved":
            reason = "not_approved"
        if reason:
            excluded.append({**row, "exclusion_reason": reason})
            continue

        # storage_key preserves the actual filename even when Excel corrupts
        # a hexadecimal-looking sample UID into scientific notation.
        key = (row.get("storage_key") or "").strip().replace("\\", "/")
        canonical = features / label["language"] / label["dialect"] / label["folder_name"]
        path = canonical / f"sample_{row['sample_uid']}.npz"
        stored = (ROOT / "dataset" / key).resolve() if key else path.resolve()
        if stored.is_relative_to(features) and stored.is_file():
            path = stored
        path = path.resolve()
        if not path.is_relative_to(features) or not path.is_file():
            excluded.append({**row, "exclusion_reason": "missing_npz"})
            continue
        if path.parent != canonical.resolve():
            raise ValueError(f"Feature path disagrees with its label: {row['sample_uid']}")
        match = re.fullmatch(r"sample_([0-9a-fA-F]{10})\.npz", path.name)
        if not match:
            raise ValueError(f"Unsupported sample filename: {path.name}")
        actual_uid = match.group(1)
        if actual_uid != row["sample_uid"]:
            if not re.fullmatch(r"[\d,.]+[eE][+-]?\d+", row["sample_uid"]):
                raise ValueError(f"Unexplained UID mismatch for {path.name}")
            corrections.append({"field": "sample_uid", "before": row["sample_uid"],
                                "after": actual_uid, "evidence": key})
            row["sample_uid"] = actual_uid
        with np.load(path, allow_pickle=False) as archive:
            sequence = archive["sequence"]
            if sequence.shape != (60, 126) or not np.issubdtype(sequence.dtype, np.number):
                raise ValueError(f"Invalid sequence: {path}")
            if not np.isfinite(sequence).all():
                raise ValueError(f"Non-finite sequence: {path}")
            digest = hashlib.sha256(sequence.astype(np.float32).tobytes()).hexdigest()
            if digest in fingerprints:
                raise ValueError(f"Duplicate sequence: {path} and {fingerprints[digest]}")
            fingerprints[digest] = path.name
        if path in referenced:
            raise ValueError(f"Multiple CSV rows reference {path}")
        referenced.add(path)
        for field in ("class_idx", "folder_name", "language", "dialect", "slug",
                      "label_original", "vocabulary_scope", "recognition_profile",
                      "semantic_label", "vocabulary_group", "motion_type", "region"):
            row[field] = label.get(field, "")
        row.update({"sample_id": actual_uid, "file": path.name,
                    "file_path": path.relative_to(ROOT).as_posix(),
                    "label_slug": label["slug"],
                    "canonical_signer_id": canonical_signer(row)})
        clean.append(row)
        if (index + 1) % 500 == 0:
            print(f"Validated {index + 1}/{len(samples)} rows", flush=True)
    if not clean or len({r['sample_uid'] for r in clean}) != len(clean):
        raise ValueError("Prepared data is empty or contains duplicate sample IDs")
    active_uids = {row["class_uid"] for row in clean}
    active_labels = [row for row in labels if row["class_uid"] in active_uids]
    sample_fields += sorted(set().union(*(row.keys() for row in clean)) - set(sample_fields))
    write_csv(prepared / "samples.csv", clean, sample_fields)
    write_csv(prepared / "labels.csv", active_labels, label_fields)
    write_csv(prepared / "excluded_samples.csv", excluded,
              list(dict.fromkeys([*sample_fields, "exclusion_reason"])))
    write_json(prepared / "corrections.json", corrections)
    write_json(prepared / "unreferenced_npz.json",
               sorted(path.relative_to(ROOT).as_posix() for path in available - referenced))

    registry = ROOT / "dataset" / "vocabulary_registry.json"
    if not registry.exists():
        subprocess.run([sys.executable, str(ROOT / "backend/app/cli/export_registry_snapshot.py"),
                        "--bootstrap"], check=True, cwd=ROOT)
    # Import the repository's existing splitter and explicitly pin NEW inputs.
    spec = importlib.util.spec_from_file_location("local_make_splits", ROOT / "processed/splits/make_splits.py")
    splitter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(splitter)
    splitter.SAMPLES_CSV = prepared / "samples.csv"
    splitter.LABELS_CSV = prepared / "labels.csv"
    tenants = {row.get("tenant_id", "").strip() for row in clean}
    if len(tenants) != 1 or not next(iter(tenants)):
        raise ValueError("Prepare separate splits for each explicit tenant")
    tenant = next(iter(tenants))
    scopes = {"all": "", **{dialect: dialect for dialect in sorted({r['dialect'] for r in clean})}}
    split_results = {}
    for scope, dialect in scopes.items():
        rows_scope = [r for r in clean if not dialect or r["dialect"] == dialect]
        if len({r["class_uid"] for r in rows_scope}) < 2:
            continue
        split_id = f"{args.run_id}-{scope}"
        splitter.OUT_DIR = ROOT / "processed/splits"
        sys.argv = ["make_splits.py", "--operational_split_id", split_id,
                    "--tenant_id", tenant, "--split_mode", "sample",
                    "--min_samples_per_class", "25", "--seed", "42"]
        if dialect:
            sys.argv += ["--dialects", dialect]
        splitter.main()
        directory = ROOT / "processed/splits/operational" / split_id
        meta = json.loads((directory / "split_metadata.json").read_text(encoding="utf-8"))
        mapping = consume_declared(meta)
        partitions = {name: read_csv(directory / f"{name}.csv")[0] for name in ("train", "val", "test")}
        partitions_agree(partitions, mapping)
        sets = [{row["sample_uid"] for row in part} for part in partitions.values()]
        if any(sets[i] & sets[j] for i, j in ((0, 1), (0, 2), (1, 2))):
            raise ValueError("Sample overlap between partitions")
        if set.union(*sets) != {row["sample_uid"] for row in rows_scope}:
            raise ValueError("Split membership differs from prepared scope")
        if any({row["class_uid"] for row in part} != set(mapping) for part in partitions.values()):
            raise ValueError("A partition is missing classes")
        inverse = {idx: {**lookup[uid], "label_key": f"{lookup[uid]['language']}/{lookup[uid]['dialect']}/{lookup[uid]['slug']}",
                         "target_idx": idx} for uid, idx in mapping.items()}
        write_json(directory / "class_uid_to_index.json", mapping)
        write_json(directory / "index_to_label.json", inverse)
        write_json(directory / "label_to_index.json", {entry["label_key"]: idx for idx, entry in inverse.items()})
        # This is deliberately a sample-level split. Do not claim that signers
        # are disjoint or that these results measure generalization to new people.
        signer_sets = {name: {r["canonical_signer_id"] for r in part} for name, part in partitions.items()}
        split_results[scope] = {
            "split_id": split_id, "directory": directory.relative_to(ROOT).as_posix(),
            "num_classes": len(mapping), "counts": {name: len(part) for name, part in partitions.items()},
            "class_coverage": "complete in all partitions", "sample_overlap": 0,
            "signer_overlap": {f"{a}_{b}": len(signer_sets[a] & signer_sets[b])
                               for a, b in (("train", "val"), ("train", "test"), ("val", "test"))},
        }

    if source_hashes != {name: sha256(path) for name, path in source_paths.items()}:
        raise ValueError("Source CSVs changed during preprocessing")
    report = {
        "run_id": args.run_id, "source_hashes": source_hashes,
        "source_label_rows": len(labels), "source_sample_rows": len(samples),
        "available_npz": len(available), "prepared_samples": len(clean),
        "prepared_classes": len(active_labels), "excluded_samples": len(excluded),
        "exclusion_reasons": dict(Counter(r["exclusion_reason"] for r in excluded)),
        "corrections": corrections, "unreferenced_npz": len(available - referenced),
        "labels_without_samples": [row for row in labels if row["class_uid"] not in active_uids],
        "registry_source": json.loads(registry.read_text(encoding="utf-8")).get("source"),
        "npz_policy": "Validate only; retain stored sequence without renormalization",
        "split_policy": "Stratified sample-level 70/15/15, seed 42, floor 25; signers may overlap",
        "splits": split_results,
    }
    write_json(prepared / "preprocessing_report.json", report)
    print(json.dumps({key: value for key, value in report.items() if key != "labels_without_samples"},
                     indent=2, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()

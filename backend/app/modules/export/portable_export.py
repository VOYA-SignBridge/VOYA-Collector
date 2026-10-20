"""Write a complete portable feature bundle; never silently skip samples."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np


def write_feature_bundle(bundle, rows, paths, dataset_root: Path, fields, labels=()):
    allowed = {Path(path).resolve() for path in paths}
    exported, checksums, names = [], {}, set()
    mapping = {uid: index for index, uid in enumerate(sorted({str(r["class_uid"]) for r in rows}))}
    for row in rows:
        source = Path(str(row.get("file_path") or "").replace("\\", "/"))
        if not source.is_absolute():
            source = dataset_root / source
        source = source.resolve()
        if source not in allowed or not source.is_file():
            raise ValueError(f"Missing or out-of-scope NPZ for sample {row.get('sample_uid')}; export aborted")
        name = f"files/{source.name}"
        if name in names:
            raise ValueError("Duplicate feature filename; refusing an ambiguous export")
        names.add(name)
        content = source.read_bytes()
        with np.load(io.BytesIO(content), allow_pickle=False) as data:
            sequence = data["sequence"]
            if sequence.ndim != 2 or sequence.shape[0] == 0 or sequence.shape[1] != 126 or not np.isfinite(sequence).all():
                raise ValueError(f"Invalid (T,126) sequence for sample {row.get('sample_uid')}")
        checksum = hashlib.sha256(content).hexdigest()
        if row.get("checksum") and str(row["checksum"]).lower() != checksum:
            raise ValueError(f"Checksum mismatch for sample {row.get('sample_uid')}")
        bundle.writestr(name, content)
        checksums[name] = checksum
        exported.append({**row, "file_path": name, "storage_key": "", "storage_url": "",
                         "checksum": checksum, "seq_len": int(sequence.shape[0])})

    def write_csv(name, items, columns):
        buffer = io.StringIO(newline="")
        writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(items)
        bundle.writestr(name, buffer.getvalue())

    write_csv("samples.csv", exported, fields)
    bundle.writestr("samples.json", json.dumps(exported, ensure_ascii=False, indent=2))
    selected_labels = [r for r in labels if str(r.get("class_uid")) in mapping]
    bundle.writestr("labels.json", json.dumps(selected_labels, ensure_ascii=False, indent=2, default=str))
    bundle.writestr("manifest.json", json.dumps({
        "format": "voya-features-v1", "feature_dim": 126, "sample_count": len(exported),
        "class_uid_to_target_idx": mapping, "sha256": checksums,
        "paths_relative_to": "bundle_root", "contains_training_splits": False,
    }, ensure_ascii=False, indent=2))
    return len(exported)

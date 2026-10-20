"""Ad-hoc report on dataset/samples.csv — signer vs account ownership, dialects,
sessions. Read-only: it never writes to the dataset.

Usage:
    python scripts/analyze_data.py [DATASET_DIR]

DATASET_DIR defaults to the `dataset/` next to this repo, so the script works
from any checkout. Pass a path to point it at a different dump.
"""

import csv
import sys
import io
# The Windows console is cp1252; printing Vietnamese labels without this raises
# UnicodeEncodeError before a single row is reported.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from collections import Counter, defaultdict
from pathlib import Path

# Derived from this file's own location (same trick as scripts/test_nginx_voya.sh)
# so the script is portable; argv[1] overrides it for other dumps.
REPO_ROOT = Path(__file__).resolve().parent.parent
DATASET = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else REPO_ROOT / "dataset"

if not (DATASET / "samples.csv").is_file():
    sys.exit(f"No samples.csv under {DATASET} — pass the dataset dir as argv[1].")

print("=" * 80)
print("1. SAMPLES.CSV ANALYSIS")
print("=" * 80)

samples = []
with open(DATASET / "samples.csv", newline="", encoding="utf-8") as f:
    samples = list(csv.DictReader(f))

print(f"\nTotal samples: {len(samples)}")

# user_id analysis
user_ids = Counter(r.get("user_id", "") for r in samples)
print(f"\nUnique user_id values: {len(user_ids)}")
for uid, cnt in user_ids.most_common():
    print(f"  user_id='{uid}': {cnt} samples")

# signer_id analysis
signer_ids = Counter(r.get("signer_id", "") for r in samples)
print(f"\nUnique signer_id values: {len(signer_ids)}")
for sid, cnt in signer_ids.most_common():
    print(f"  signer_id='{sid}': {cnt} samples")

# Cross-reference: signer_id vs user_id
print("\nSigner-to-User mapping:")
signer_users = defaultdict(set)
for r in samples:
    signer_users[r.get("signer_id", "")].add(r.get("user_id", ""))
for sid, users in sorted(signer_users.items()):
    print(f"  signer_id='{sid}' -> user_ids={users}")

# Samples WITHOUT signer_id
no_signer = [r for r in samples if not (r.get("signer_id") or "").strip()]
print(f"\nSamples WITHOUT signer_id: {len(no_signer)} ({100*len(no_signer)/len(samples):.1f}%)")

# Samples with UUID in user_id vs display name
import re
uuid_pattern = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)
uuid_users = [r for r in samples if uuid_pattern.search(r.get("user_id", ""))]
print(f"Samples with UUID in user_id: {len(uuid_users)}")

print("\n" + "=" * 80)
print("2. ORPHAN DATA ANALYSIS")
print("=" * 80)

# Check file_path points to existing files
features_root = DATASET / "features"
orphan_samples = []
missing_files = []
for r in samples:
    fp = r.get("file_path", "")
    if fp:
        full_path = DATASET / fp
        if not full_path.exists():
            missing_files.append(r)

print(f"\nSamples with missing file on disk: {len(missing_files)} / {len(samples)}")
if missing_files:
    by_class = Counter(r.get("label_original", "") for r in missing_files)
    print("  Missing files by class:")
    for cls, cnt in by_class.most_common(10):
        print(f"    '{cls}': {cnt} missing")

# Files on disk NOT in samples.csv
sample_paths = set(r.get("file_path", "") for r in samples)
disk_npz = []
if features_root.exists():
    for npz in features_root.rglob("*.npz"):
        try:
            rel = str(npz.relative_to(DATASET)).replace("\\", "/")
        except ValueError:
            rel = str(npz)
        if rel not in sample_paths:
            disk_npz.append(rel)

print(f"\n.npz files on disk NOT in samples.csv (orphan files): {len(disk_npz)}")
if disk_npz[:10]:
    for p in disk_npz[:10]:
        print(f"  {p}")
    if len(disk_npz) > 10:
        print(f"  ... and {len(disk_npz) - 10} more")

print("\n" + "=" * 80)
print("3. HAND DATA QUALITY ANALYSIS")
print("=" * 80)

# left_hand_ratio analysis
no_left = [r for r in samples if r.get("left_hand_ratio", "") == "0.0"]
no_right = [r for r in samples if r.get("right_hand_ratio", "") == "0.0"]
no_both = [r for r in samples if r.get("both_hands_ratio", "") == "0.0"]
print(f"\nSamples with left_hand_ratio=0.0: {len(no_left)}")
print(f"Samples with right_hand_ratio=0.0: {len(no_right)}")
print(f"Samples with both_hands_ratio=0.0: {len(no_both)}")

# Samples that require 2 hands but have 0 for one hand
labels = {}
with open(DATASET / "labels.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        labels[r.get("class_uid", "")] = r

two_hand_missing = []
for r in samples:
    cls = labels.get(r.get("class_uid", ""), {})
    hands_req = cls.get("hands_required", "")
    if hands_req == "2":
        lr = r.get("left_hand_ratio", "")
        rr = r.get("right_hand_ratio", "")
        if lr == "0.0" or rr == "0.0":
            two_hand_missing.append(r)

print(f"\nSamples requiring 2 hands but missing one hand entirely: {len(two_hand_missing)}")
if two_hand_missing:
    by_class = Counter(r.get("label_original", "") for r in two_hand_missing)
    print("  By class:")
    for cls, cnt in by_class.most_common():
        print(f"    '{cls}': {cnt}")

# Quality flags analysis
flagged = [r for r in samples if (r.get("quality_flags") or "").strip()]
print(f"\nSamples with quality flags: {len(flagged)}")
flag_counts = Counter()
for r in flagged:
    for flag in (r.get("quality_flags") or "").split(","):
        flag = flag.strip()
        if flag:
            flag_counts[flag] += 1
for flag, cnt in flag_counts.most_common():
    print(f"  {flag}: {cnt}")

# Legacy samples (no QC fields at all)
no_qc = [r for r in samples if not (r.get("quality_status") or "").strip()]
print(f"\nLegacy samples (no quality_status): {len(no_qc)} ({100*len(no_qc)/len(samples):.1f}%)")

# No normalization info
no_norm = [r for r in samples if not (r.get("normalization_version") or "").strip()]
print(f"Legacy samples (no normalization_version): {len(no_norm)} ({100*len(no_norm)/len(samples):.1f}%)")

no_raw = [r for r in samples if (r.get("raw_landmarks_available") or "") != "1"]
print(f"Samples WITHOUT raw landmarks: {len(no_raw)} ({100*len(no_raw)/len(samples):.1f}%)")

print("\n" + "=" * 80)
print("4. CLASS/LABEL CONSISTENCY CHECK")
print("=" * 80)

# Check if samples reference class_uids that don't exist in labels.csv
label_uids = set(labels.keys())
sample_class_uids = set(r.get("class_uid", "") for r in samples)
orphan_class_uids = sample_class_uids - label_uids
print(f"\nclass_uids in samples.csv but NOT in labels.csv: {len(orphan_class_uids)}")
for uid in orphan_class_uids:
    cnt = sum(1 for r in samples if r.get("class_uid") == uid)
    sample_label = next((r.get("label_original","") for r in samples if r.get("class_uid") == uid), "")
    print(f"  class_uid='{uid}' ({sample_label}): {cnt} samples")

# Duplicate class_idx
idx_counts = Counter(r.get("class_idx", "") for r in labels.values() if r.get("class_idx"))
dups = {idx: cnt for idx, cnt in idx_counts.items() if cnt > 1}
if dups:
    print(f"\nDuplicate class_idx values in labels.csv:")
    for idx, cnt in dups.items():
        print(f"  class_idx={idx}: {cnt} times")
else:
    print("\nNo duplicate class_idx in labels.csv")

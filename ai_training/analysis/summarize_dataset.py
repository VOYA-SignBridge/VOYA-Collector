import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

try:
    from train_model.dataset_versioning import get_code_root, get_data_root, get_features_dir, get_labels_csv, get_samples_csv, get_analysis_dir
except Exception:
    get_code_root = None  # type: ignore
    get_data_root = None  # type: ignore
    get_features_dir = None  # type: ignore
    get_labels_csv = None  # type: ignore
    get_samples_csv = None  # type: ignore
    get_analysis_dir = None  # type: ignore

ROOT = get_code_root() if get_code_root else Path(__file__).resolve().parents[2]
DATA_ROOT = get_data_root() if get_data_root else ROOT
FEATURES = get_features_dir(DATA_ROOT) if get_features_dir else DATA_ROOT / 'features'
LABELS_CSV = get_labels_csv(DATA_ROOT) if get_labels_csv else DATA_ROOT / 'labels.csv'
SAMPLES_CSV = get_samples_csv(DATA_ROOT) if get_samples_csv else DATA_ROOT / 'samples.csv'
OUT_DIR = get_analysis_dir() if get_analysis_dir else ROOT / 'processed' / 'analysis'
OUT_DIR.mkdir(parents=True, exist_ok=True)


def read_labels():
    labels = {}
    with LABELS_CSV.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                idx = int(row['class_idx'])
            except Exception:
                continue
            labels[idx] = {
                'label_original': row.get('label_original', ''),
                'slug': row.get('slug', ''),
                'folder_name': row.get('folder_name', ''),
                'created_at': row.get('created_at', ''),
                'dataset_version': row.get('dataset_version', ''),
            }
    return labels


def read_samples():
    rows = []
    with SAMPLES_CSV.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "K", "M", "G", "T", "P", "E", "Z"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Y{suffix}"


def scan_features():
    per_class = {}
    total_npz = total_json = 0
    total_npz_bytes = total_json_bytes = 0
    mismatches = []

    # Hierarchy: features/<language>/<dialect>/<class_folder>/...
    class_dirs = [p for p in FEATURES.rglob('class_*') if p.is_dir()]
    for class_dir in sorted(class_dirs):
        npz_files = list(class_dir.glob('*.npz'))
        json_files = list(class_dir.glob('*.json'))
        total_npz += len(npz_files)
        total_json += len(json_files)
        npz_bytes = sum(p.stat().st_size for p in npz_files)
        json_bytes = sum(p.stat().st_size for p in json_files)
        total_npz_bytes += npz_bytes
        total_json_bytes += json_bytes

        npz_bases = {p.stem for p in npz_files}
        json_bases = {p.stem for p in json_files}
        only_npz = sorted(list(npz_bases - json_bases))
        only_json = sorted(list(json_bases - npz_bases))
        if only_npz or only_json:
            mismatches.append({
                'class_folder': class_dir.name,
                'only_npz': only_npz,
                'only_json': only_json,
            })

        try:
            rel_key = str(class_dir.relative_to(FEATURES)).replace('\\', '/')
        except Exception:
            rel_key = class_dir.name

        per_class[rel_key] = {
            'npz_count': len(npz_files),
            'json_count': len(json_files),
            'npz_size_bytes': npz_bytes,
            'json_size_bytes': json_bytes,
        }

    return {
        'per_class': per_class,
        'totals': {
            'npz_files': total_npz,
            'json_files': total_json,
            'npz_size_bytes': total_npz_bytes,
            'json_size_bytes': total_json_bytes,
        },
        'mismatches': mismatches,
    }


def check_samples_files(samples):
    missing = []
    present = 0
    for r in samples:
        folder = r.get('folder_name')
        file = r.get('file')
        if not folder or not file:
            continue
        dialect = (r.get('dialect') or '').strip()
        language = (r.get('language') or 'vn').strip()  # samples.csv typically lacks language
        # Prefer hierarchical layout
        path = FEATURES / language / dialect / folder / file if dialect else FEATURES / folder / file
        if path.exists():
            present += 1
        else:
            # fallback to old flat layout if present
            alt = FEATURES / folder / file
            if alt.exists():
                present += 1
                continue
            missing.append({
                'sample_id': r.get('sample_id'),
                'class_idx': r.get('class_idx'),
                'expected_path': str(path.relative_to(DATA_ROOT)),
            })
    return {'present_count': present, 'missing': missing}


def summarize(samples, labels):
    # Basic counts
    n_rows = len(samples)
    class_counts = Counter(int(r['class_idx']) for r in samples if r.get('class_idx'))
    folder_counts = Counter(r['folder_name'] for r in samples if r.get('folder_name'))
    users = Counter(r['user'] for r in samples if r.get('user'))
    dialects = Counter(r['dialect'] for r in samples if r.get('dialect'))
    sources = Counter(r['source'] for r in samples if r.get('source'))
    frames = Counter(r['frames'] for r in samples if r.get('frames'))

    # Per-class mapping with labels
    class_summary = []
    for idx, count in sorted(class_counts.items()):
        lbl = labels.get(idx, {})
        class_summary.append({
            'class_idx': idx,
            'label': lbl.get('label_original', ''),
            'slug': lbl.get('slug', ''),
            'folder_name': lbl.get('folder_name', ''),
            'samples': count,
        })

    feat = scan_features()
    consistency = check_samples_files(samples)

    now = datetime.utcnow().isoformat() + 'Z'
    summary = {
        'generated_at': now,
        'paths': {
            'root': str(ROOT),
            'features': str(FEATURES),
            'labels_csv': str(LABELS_CSV),
            'samples_csv': str(SAMPLES_CSV),
        },
        'counts': {
            'classes_in_labels': len(labels),
            'classes_in_features': len([p for p in FEATURES.rglob('class_*') if p.is_dir()]),
            'samples_csv_rows': n_rows,
        },
        'class_summary': class_summary,
        'csv_distributions': {
            'by_folder_name': folder_counts,
            'by_user': users,
            'by_dialect': dialects,
            'by_source': sources,
            'by_frames': frames,
        },
        'features': feat,
        'consistency': consistency,
    }
    return summary


def write_markdown(summary):
    md = []
    md.append(f"# Dataset Summary\n")
    md.append(f"Generated at: {summary['generated_at']}\n")
    md.append("\n## Overview\n")
    counts = summary['counts']
    md.append(f"- Classes (labels.csv): {counts['classes_in_labels']}\n")
    md.append(f"- Classes (features/): {counts['classes_in_features']}\n")
    md.append(f"- Samples (rows in samples.csv): {counts['samples_csv_rows']}\n")

    md.append("\n## Classes\n")
    md.append("class_idx | label | slug | folder | samples\n")
    md.append(":-:|:-|:-|:-|:-:\n")
    for c in summary['class_summary']:
        md.append(f"{c['class_idx']} | {c['label']} | {c['slug']} | {c['folder_name']} | {c['samples']}\n")

    feat = summary['features']
    md.append("\n## Features on Disk\n")
    totals = feat['totals']
    md.append(f"- NPZ files: {totals['npz_files']} ({sizeof_fmt(totals['npz_size_bytes'])})\n")
    md.append(f"- JSON files: {totals['json_files']} ({sizeof_fmt(totals['json_size_bytes'])})\n")

    md.append("\n### Per-class (features)\n")
    md.append("class_folder | npz | json | npz_size | json_size\n")
    md.append(":-|-:|-:|-:|-:\n")
    for folder, stats in sorted(feat['per_class'].items()):
        md.append(
            f"{folder} | {stats['npz_count']} | {stats['json_count']} | "
            f"{sizeof_fmt(stats['npz_size_bytes'])} | {sizeof_fmt(stats['json_size_bytes'])}\n"
        )

    mis = feat['mismatches']
    if mis:
        md.append("\n### Mismatched pairs (npz/json)\n")
        for m in mis:
            md.append(f"- {m['class_folder']}: only_npz={len(m['only_npz'])}, only_json={len(m['only_json'])}\n")
    else:
        md.append("\n_No mismatched npz/json pairs detected._\n")

    cons = summary['consistency']
    md.append("\n## CSV ↔ Files Consistency\n")
    md.append(f"- Present files referenced by CSV: {cons['present_count']}\n")
    md.append(f"- Missing files referenced by CSV: {len(cons['missing'])}\n")

    # Distributions
    md.append("\n## Distributions (samples.csv)\n")
    for key, counter in summary['csv_distributions'].items():
        md.append(f"\n### {key}\n")
        md.append("value | count\n")
        md.append(":-|-:\n")
        for k, v in Counter(counter).most_common():
            kk = '(blank)' if (k is None or str(k) == '' ) else str(k)
            md.append(f"{kk} | {v}\n")

    (OUT_DIR / 'dataset_summary.md').write_text(''.join(md), encoding='utf-8')


def main():
    labels = read_labels()
    samples = read_samples()
    summary = summarize(samples, labels)

    # Write JSON
    (OUT_DIR / 'dataset_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    # Write Markdown
    write_markdown(summary)
    print('Summary written to:', (OUT_DIR / 'dataset_summary.md'))


if __name__ == '__main__':
    main()

import csv, json
from collections import defaultdict
from pathlib import Path

try:
    from train_model.dataset_versioning import get_code_root, get_data_root, get_labels_csv, get_analysis_dir
except Exception:
    get_code_root = None  # type: ignore
    get_data_root = None  # type: ignore
    get_labels_csv = None  # type: ignore
    get_analysis_dir = None  # type: ignore

ROOT = get_code_root() if get_code_root else Path(__file__).resolve().parents[2]
DATA_ROOT = get_data_root() if get_data_root else ROOT
LABELS = get_labels_csv(DATA_ROOT) if get_labels_csv else DATA_ROOT / 'dataset' /'labels.csv'
OUT = get_analysis_dir() if get_analysis_dir else ROOT / 'processed' / 'analysis'
OUT.mkdir(parents=True, exist_ok=True)

index_to_label = {}
label_to_index = {}
classes_ordered = []

# For analysis/back-compat: slug -> [indices]
slug_to_indices = defaultdict(list)

with LABELS.open('r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        idx = int(row['class_idx']) - 1  # Convert to 0-based index
        slug = row['slug']
        orig = row['label_original']

        language = (row.get('language') or 'vn').strip()
        dialect = (row.get('dialect') or '').strip()
        class_uid = (row.get('class_uid') or '').strip()
        folder_name = (row.get('folder_name') or '').strip()

        # Unique label key to avoid collisions across dialects/languages.
        # Example: vn/bac/dia-chi
        label_key = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"

        index_to_label[idx] = {
            'slug': slug,
            'label_original': orig,
            'language': language,
            'dialect': dialect,
            'class_idx': int(row['class_idx']),
            'class_uid': class_uid,
            'folder_name': folder_name,
            'label_key': label_key,
        }

        label_to_index[label_key] = idx
        slug_to_indices[slug].append(idx)
        classes_ordered.append((idx, label_key, slug, orig))

(index_to_label_path := OUT / 'index_to_label.json').write_text(
    json.dumps(index_to_label, ensure_ascii=False, indent=2), encoding='utf-8')
(label_to_index_path := OUT / 'label_to_index.json').write_text(
    json.dumps(label_to_index, ensure_ascii=False, indent=2), encoding='utf-8')

(slug_to_indices_path := OUT / 'slug_to_indices.json').write_text(
    json.dumps({k: v for k, v in slug_to_indices.items()}, ensure_ascii=False, indent=2),
    encoding='utf-8'
)

# Backward-compat convenience: only write slug_to_index.json if slugs are unique.
all_unique = all(len(v) == 1 for v in slug_to_indices.values())
if all_unique:
    (slug_to_index_path := OUT / 'slug_to_index.json').write_text(
        json.dumps({k: v[0] for k, v in slug_to_indices.items()}, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )
(classes_txt_path := OUT / 'classes.txt').write_text(
    '\n'.join(label_key for _, label_key, _, _ in sorted(classes_ordered)), encoding='utf-8')

print('Wrote:', index_to_label_path)
print('Wrote:', label_to_index_path)
print('Wrote:', slug_to_indices_path)
if all_unique:
    print('Wrote:', slug_to_index_path)
print('Wrote:', classes_txt_path)

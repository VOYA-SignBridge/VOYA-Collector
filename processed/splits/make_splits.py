import csv
import random
import argparse
from pathlib import Path
from collections import defaultdict, Counter
import csv as _csv
import json

try:
    from train_model.dataset_versioning import get_code_root, get_data_root, get_samples_csv, get_labels_csv, get_splits_dir
except Exception:
    get_code_root = None  # type: ignore
    get_data_root = None  # type: ignore
    get_samples_csv = None  # type: ignore
    get_labels_csv = None  # type: ignore
    get_splits_dir = None  # type: ignore

ROOT = get_code_root() if get_code_root else Path(__file__).resolve().parents[2]
DATA_ROOT = get_data_root() if get_data_root else ROOT
if get_samples_csv:
    SAMPLES_CSV = get_samples_csv(DATA_ROOT)
else:
    # Backward-compat: older layout used <data_root>/samples.csv
    # Current app layout uses <data_root>/samples/samples.csv
    cand = DATA_ROOT / 'samples' / 'samples.csv'
    SAMPLES_CSV = cand if cand.exists() else (DATA_ROOT / 'dataset' / 'samples' / 'samples.csv')
OUT_DIR = get_splits_dir() if get_splits_dir else ROOT / 'processed' / 'splits'
if get_labels_csv:
    LABELS_CSV = get_labels_csv(DATA_ROOT)
else:
    # Backward-compat: older layout used <data_root>/labels.csv
    LABELS_CSV = DATA_ROOT / 'dataset' / 'labels.csv'
OUT_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 42
TRAIN_RATIO = 0.70
VAL_RATIO = 0.15  # test will be the remainder


def _load_labels_by_uid_and_idx():
    """Load labels.csv and return two dicts:

    - by_uid: class_uid -> label row
    - by_idx: class_idx(int) -> label row
    """
    by_uid = {}
    by_idx = {}
    with LABELS_CSV.open('r', encoding='utf-8') as f:
        reader = _csv.DictReader(f)
        for r in reader:
            class_uid = (r.get('class_uid') or '').strip()
            ci_raw = (r.get('class_idx') or '').strip()
            try:
                ci = int(ci_raw)
            except Exception:
                continue
            by_idx[ci] = r
            if class_uid:
                by_uid[class_uid] = r
    return by_uid, by_idx


def _derive_file_from_row(r: dict) -> str:
    fp = (r.get('file') or '').strip()
    if fp:
        return fp
    file_path = (r.get('file_path') or '').strip()
    if file_path:
        try:
            return Path(file_path).name
        except Exception:
            pass
    storage_key = (r.get('storage_key') or '').strip()
    if storage_key:
        try:
            return Path(storage_key).name
        except Exception:
            pass
    return ''


def read_samples():
    """Read samples from CSV.

    Supports two schemas:
    1) Legacy trainer schema: has class_idx + sample_id + folder_name + file
    2) Current app schema: has class_uid + sample_uid + file_path (+ language/dialect)
       We enrich rows with class_idx/sample_id/folder_name/file for training.
    """
    label_by_uid, _ = _load_labels_by_uid_and_idx()

    rows = []
    fieldnames = []
    with SAMPLES_CSV.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for r in reader:
            # If already has a valid class_idx, keep as-is.
            ci = (r.get('class_idx') or '').strip()
            if ci:
                try:
                    int(ci)
                    # Ensure sample_id exists for deterministic sorting.
                    if not (r.get('sample_id') or '').strip():
                        r['sample_id'] = (r.get('sample_uid') or '').strip()
                    rows.append(r)
                    continue
                except Exception:
                    pass

            # App schema path: map class_uid -> class_idx + folder_name
            class_uid = (r.get('class_uid') or '').strip()
            label_row = label_by_uid.get(class_uid) if class_uid else None
            if not label_row:
                continue

            ci2 = (label_row.get('class_idx') or '').strip()
            try:
                int(ci2)
            except Exception:
                continue

            r['class_idx'] = ci2
            r['sample_id'] = (r.get('sample_uid') or '').strip()
            r['folder_name'] = (label_row.get('folder_name') or '').strip()
            r['file'] = _derive_file_from_row(r)

            # Trainer expects label_slug/label_original for analysis/logging.
            if not (r.get('label_slug') or '').strip():
                r['label_slug'] = (r.get('slug') or '').strip()
            if not (r.get('label_original') or '').strip():
                r['label_original'] = (r.get('label_original') or label_row.get('label_original') or '').strip()
            if not (r.get('language') or '').strip():
                r['language'] = (label_row.get('language') or 'vn').strip() or 'vn'
            if not (r.get('dialect') or '').strip():
                r['dialect'] = (label_row.get('dialect') or '').strip()

            # Must have folder_name + file to locate features on disk.
            if not (r.get('folder_name') or '').strip() or not (r.get('file') or '').strip():
                continue

            rows.append(r)

    # Ensure output fieldnames include training-required columns.
    extra = ['sample_id', 'class_idx', 'folder_name', 'file', 'label_slug', 'label_original', 'dialect', 'language']
    for c in extra:
        if c not in fieldnames:
            fieldnames.append(c)
    return rows, fieldnames


def _labels_lookup():
    """Return dicts for class_idx -> {slug,label_original}."""
    by_idx = {}
    with LABELS_CSV.open('r', encoding='utf-8') as f:
        reader = _csv.DictReader(f)
        for r in reader:
            idx = int(r['class_idx'])
            by_idx[idx] = {
                'slug': r.get('slug', ''),
                'label_original': r.get('label_original', ''),
                'language': r.get('language', 'vn'),
                'dialect': r.get('dialect', ''),
            }
    return by_idx


def stratified_split(rows):
    grouped = defaultdict(list)
    for r in rows:
        ci = (r.get('class_idx') or '').strip()
        if ci == '':
            continue
        grouped[ci].append(r)

    train, val, test = [], [], []
    for class_idx, items in grouped.items():
        # deterministic order then shuffle
        items.sort(key=lambda x: (x.get('sample_id') or x.get('sample_uid') or ''))
        random.Random(RANDOM_SEED).shuffle(items)
        n = len(items)
        if n >= 3:
            n_train = max(1, int(round(n * TRAIN_RATIO)))
            n_val = max(1, int(round(n * VAL_RATIO)))
        else:
            n_train = max(1, n - 1)
            n_val = 0

        n_test = n - n_train - n_val

        if n_test < 1 and n >= 3:
            n_test = 1

            if n_train > n_val:
                n_train -= 1
            else:
                n_val -= 1
        # adjust if rounding causes overflow
        if n_test < 0:
            n_test = 0
            while n_train + n_val > n:
                if n_val > 0:
                    n_val -= 1
                elif n_train > 0:
                    n_train -= 1
        train.extend(items[:n_train])
        val.extend(items[n_train:n_train+n_val])
        test.extend(items[n_train+n_val:])
    return train, val, test


def _per_class_counts(rows):
    c = Counter(int((r.get('class_idx') or '0')) for r in rows if (r.get('class_idx') or '').strip() != '')
    return c


def _targets_per_split(rows):
    totals = _per_class_counts(rows)
    targets = {
        'train': {},
        'val': {},
        'test': {},
    }
    for k, n in totals.items():
        if n >= 3:
            n_train = max(1, int(round(n * TRAIN_RATIO)))
            n_val = max(1, int(round(n * VAL_RATIO)))
        else:
            n_train = max(1, n - 1)
            n_val = 0

        n_test = n - n_train - n_val

        if n_test < 1 and n >= 3:
            n_test = 1

            if n_train > n_val:
                n_train -= 1
            else:
                n_val -= 1
        targets['train'][k] = n_train
        targets['val'][k] = n_val
        targets['test'][k] = n_test
    return targets


def stratified_group_split_by(rows, group_col: str):
    """Assign entire groups (e.g., users or dialects) to a split (train/val/test)
    while matching per-class targets.

    Greedy heuristic: iterate users (largest first), place user into split that minimizes
    global squared error to targets across splits.
    """
    # group rows by group_col
    groups = defaultdict(list)
    for r in rows:
        key = r.get(group_col) or ''
        groups[key].append(r)

    # compute per-user class vectors
    user_vec = {}
    for u, lst in groups.items():
        c = Counter(int(r['class_idx']) for r in lst)
        user_vec[u] = c

    # targets and current counts per split
    targets = _targets_per_split(rows)
    counts = {
        'train': Counter(),
        'val': Counter(),
        'test': Counter(),
    }

    # deterministic order: users sorted by total samples desc, then name
    rng = random.Random(RANDOM_SEED)
    ordered_users = sorted( groups.keys(), key=lambda u: ( min(user_vec[u].values()), -sum(user_vec[u].values()), str(u) ) )

    assign = {}
    for u in ordered_users:
        vec = user_vec[u]
        # compute deficits per split
        deficits = {}
        for s in ('train','val','test'):
            classes = set(targets[s].keys()) | set(counts[s].keys())
            deficits[s] = Counter({cls: max(0, targets[s].get(cls, 0) - counts[s].get(cls, 0)) for cls in classes})

        candidate_scores = []
        for split in ('train','val','test'):
            # overflow if we add this user to split
            overflow = sum(max(0, (counts[split].get(cls, 0) + vec.get(cls, 0)) - targets[split].get(cls, 0)) for cls in set(list(vec.keys()) + list(targets[split].keys())))
            # squared error cost after assignment
            cost = 0
            for s in ('train','val','test'):
                for cls in set(list(targets[s].keys()) + list(counts[s].keys()) + list(vec.keys())):
                    c = counts[s].get(cls, 0) + (vec.get(cls, 0) if s == split else 0)
                    t = targets[s].get(cls, 0)
                    diff = c - t
                    cost += diff * diff
            # total remaining deficit in that split (before assignment), larger means we prefer to fill it
            deficit_sum = sum(deficits[split].values())
            candidate_scores.append((overflow, cost, -deficit_sum, split))

        # prefer zero-overflow; then lower cost; then larger deficit fill
        candidate_scores.sort()
        chosen_split = candidate_scores[0][3]
        assign[u] = chosen_split
        counts[chosen_split] += vec  # type: ignore

    # build row lists
    train, val, test = [], [], []
    for u, lst in groups.items():
        s = assign[u]
        if s == 'train':
            train.extend(lst)
        elif s == 'val':
            val.extend(lst)
        else:
            test.extend(lst)
    return train, val, test


def write_split(name, rows, fieldnames):
    path = OUT_DIR / f'{name}.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_split_to_dir(out_dir: Path, name: str, rows, fieldnames):
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f'{name}.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def summarize(rows, label):
    # count by class_idx (string), then sort stably by numeric value when possible
    c = Counter((r.get('class_idx') or '').strip() for r in rows if (r.get('class_idx') or '').strip() != '')
    def _key(kv):
        k = kv[0]
        try:
            return int(k)
        except Exception:
            return 10**9  # push non-numeric to the end
    return {label: dict(sorted(c.items(), key=_key)), 'total': len(rows)}

def _assert_no_overlap(a, b):
    sa = set(r["sample_id"] for r in a)
    sb = set(r["sample_id"] for r in b)

    overlap = sa & sb

    if overlap:
        raise RuntimeError(
            f"Split leakage detected: {len(overlap)} overlapping samples"
        )

def main():
    parser = argparse.ArgumentParser(description='Make dataset splits')
    parser.add_argument('--user_disjoint', action='store_true', help='Ensure no group appears in multiple splits', default=True)
    parser.add_argument('--group_col', type=str, default='user', help='Grouping column to keep disjoint (e.g., user, dialect)')
    parser.add_argument('--by_language', action='store_true', help='Write separate split CSVs per language under splits/<language>/')
    parser.add_argument('--languages', type=str, default='', help='Optional comma-separated whitelist of languages when using --by_language')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    global RANDOM_SEED
    RANDOM_SEED = args.seed
    rows, fieldnames = read_samples()
    # enrich rows with label info
    lookup = _labels_lookup()
    if 'label_slug' not in fieldnames:
        fieldnames = fieldnames + ['label_slug', 'label_original']
    if 'language' not in fieldnames:
        fieldnames = fieldnames + ['language']
    if 'dialect' not in fieldnames:
        fieldnames = fieldnames + ['dialect']
    if 'label_key' not in fieldnames:
        fieldnames = fieldnames + ['label_key']
    enriched = []
    for r in rows:
        try:
            idx = int(r['class_idx'])
        except Exception:
            idx = None
        meta = lookup.get(idx, {'slug': '', 'label_original': '', 'language': 'vn', 'dialect': ''})
        r = dict(r)
        r['label_slug'] = meta['slug']
        r['label_original'] = meta['label_original']
        language = (meta.get('language') or 'vn').strip()
        dialect = (meta.get('dialect') or '').strip()
        slug = (meta.get('slug') or '').strip()
        r['language'] = language
        r['dialect'] = dialect
        r['label_key'] = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"
        enriched.append(r)
    rows = enriched
    def _do_split(rows_subset):
        if args.user_disjoint:
            if args.group_col not in fieldnames:
                raise SystemExit(f"samples.csv has no '{args.group_col}' column; cannot perform group-disjoint split.")
            return stratified_group_split_by(rows_subset, args.group_col)
        return stratified_split(rows_subset)

    if not args.by_language:
        train, val, test = _do_split(rows)
        _assert_no_overlap(train, val) 
        _assert_no_overlap(train, test) 
        _assert_no_overlap(val, test)
        paths = {
            'train': write_split('train', train, fieldnames),
            'val': write_split('val', val, fieldnames),
            'test': write_split('test', test, fieldnames),
        }
        summary = {
            'train': summarize(train, 'train'),
            'val': summarize(val, 'val'),
            'test': summarize(test, 'test'),
        }
        print('Split summary:')
        for k, v in summary.items():
            print(k, v)
        for k, p in paths.items():
            print(f'{k} file -> {p}')
        return

    # Per-language mode: write splits into OUT_DIR/<language>/*.csv
    wanted = {x.strip() for x in str(args.languages or '').split(',') if x.strip()}
    by_lang = defaultdict(list)
    for r in rows:
        lang = (r.get('language') or 'vn').strip() or 'vn'
        if wanted and lang not in wanted:
            continue
        by_lang[lang].append(r)

    manifest = {
        'seed': RANDOM_SEED,
        'train_ratio': TRAIN_RATIO,
        'val_ratio': VAL_RATIO,
        'user_disjoint': bool(args.user_disjoint),
        'group_col': args.group_col,
        'languages': {},
    }

    for lang, rows_l in sorted(by_lang.items(), key=lambda kv: kv[0]):
        if not rows_l:
            continue
        train, val, test = _do_split(rows_l)
        out_dir = OUT_DIR / lang
        paths = {
            'train': write_split_to_dir(out_dir, 'train', train, fieldnames),
            'val': write_split_to_dir(out_dir, 'val', val, fieldnames),
            'test': write_split_to_dir(out_dir, 'test', test, fieldnames),
        }
        summary = {
            'train': summarize(train, 'train'),
            'val': summarize(val, 'val'),
            'test': summarize(test, 'test'),
        }
        manifest['languages'][lang] = {
            'total_rows': len(rows_l),
            'paths': {k: str(p) for k, p in paths.items()},
            'summary': summary,
        }
        print(f'Language={lang} summary:')
        for k, v in summary.items():
            print(k, v)
        for k, p in paths.items():
            print(f'{k} file -> {p}')

    (OUT_DIR / 'by_language_manifest.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(f"Wrote manifest -> {OUT_DIR / 'by_language_manifest.json'}")


if __name__ == '__main__':
    main()

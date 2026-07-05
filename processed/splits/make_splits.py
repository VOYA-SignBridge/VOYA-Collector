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
    cand = DATA_ROOT / 'samples.csv'
    SAMPLES_CSV = cand if cand.exists() else (DATA_ROOT / 'dataset' / 'samples.csv')
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
    """
    Derive actual .npz filename from dataset row.

    Priority:
    1. explicit file column
    2. file_path basename
    3. storage_key basename

    Reject non-.npz filenames.
    """

    candidates = [
        (r.get('file') or '').strip(),
        (r.get('file_path') or '').strip(),
        (r.get('storage_key') or '').strip(),
    ]

    for c in candidates:
        if not c:
            continue

        try:
            name = Path(c).name.strip()

            if name.lower().endswith('.npz'):
                return name

        except Exception:
            continue

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
            file_name = (r.get('file') or '').strip()

            if (
                not (r.get('folder_name') or '').strip()
                or not file_name
                or not file_name.lower().endswith('.npz')
            ):
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


# ---------------------------------------------------------------------------
# New: signer-redundancy analysis, coverage validation, coverage-preserving split
# ---------------------------------------------------------------------------

def analyze_class_signer_redundancy(rows, group_col='user'):
    """Return per-class signer statistics.

    Detects which classes have only 1 unique signer (strict group-disjoint
    isolation is impossible for those classes).

    Returns:
        dict: {class_idx(int): {
            'signer_count': int,
            'signers': list[str],
            'total_samples': int,
            'dominance': float,            # max-signer share in [0, 1]
            'strict_isolation_feasible': bool  # True iff signer_count >= 2
        }}
    """
    class_signer_counts: dict = defaultdict(Counter)
    for r in rows:
        ci = (r.get('class_idx') or '').strip()
        group = (r.get(group_col) or '').strip()
        try:
            ci_int = int(ci)
        except Exception:
            continue
        class_signer_counts[ci_int][group] += 1

    result = {}
    for ci, signer_c in class_signer_counts.items():
        total = sum(signer_c.values())
        max_count = max(signer_c.values()) if signer_c else 0
        result[ci] = {
            'signer_count': len(signer_c),
            'signers': sorted(signer_c.keys()),
            'total_samples': total,
            'dominance': max_count / total if total > 0 else 1.0,
            'strict_isolation_feasible': len(signer_c) >= 2,
        }
    return result


def validate_split_coverage(train, val, test, all_rows, label_by_idx=None):
    """Verify class coverage across splits after generation.

    Prints warnings for missing classes and returns a coverage report.
    Called after every split regardless of mode.

    Returns:
        dict with keys: all_classes, train/val/test coverage fractions,
        missing_from_{train,val,test} lists, and label_space_consistent bool.
    """
    def _classes(rows_):
        out = set()
        for r in rows_:
            ci = (r.get('class_idx') or '').strip()
            try:
                out.add(int(ci))
            except Exception:
                pass
        return out

    all_classes = _classes(all_rows)
    train_classes = _classes(train)
    val_classes = _classes(val)
    test_classes = _classes(test)

    missing_from_train = sorted(all_classes - train_classes)
    missing_from_val = sorted(all_classes - val_classes)
    missing_from_test = sorted(all_classes - test_classes)

    n = max(len(all_classes), 1)
    report = {
        'all_classes': len(all_classes),
        'train_coverage': len(train_classes) / n,
        'val_coverage': len(val_classes) / n,
        'test_coverage': len(test_classes) / n,
        'missing_from_train': missing_from_train,
        'missing_from_val': missing_from_val,
        'missing_from_test': missing_from_test,
        'label_space_consistent': not missing_from_train and not missing_from_val,
    }

    def _name(ci):
        if label_by_idx and ci in label_by_idx:
            slug = (label_by_idx.get(ci) or {}).get('slug') or ''
            return f"{ci}({slug})" if slug else str(ci)
        return str(ci)

    if missing_from_train:
        print(f"[WARN] validate_split_coverage: {len(missing_from_train)} class(es) missing "
              f"from train: {[_name(c) for c in missing_from_train]}")
    if missing_from_val:
        print(f"[WARN] validate_split_coverage: {len(missing_from_val)} class(es) missing "
              f"from val: {[_name(c) for c in missing_from_val]}")
    if missing_from_test:
        print(f"[INFO] validate_split_coverage: {len(missing_from_test)} class(es) missing "
              f"from test (acceptable for rare classes): {[_name(c) for c in missing_from_test]}")
    if report['label_space_consistent']:
        print(f"[OK] validate_split_coverage: train/val label-space consistent "
              f"({len(all_classes)} classes in each).")
    return report


def _check_signer_leakage(train, val, test, group_col='user'):
    """Report which signers appear in more than one split (informational).

    In strict_user_disjoint mode this should always be empty.
    In coverage_preserving mode, singleton-class signers may appear in
    multiple splits — that is expected and logged elsewhere.
    """
    def _groups(rows_):
        return {(r.get(group_col) or '').strip()
                for r in rows_ if (r.get(group_col) or '').strip()}

    tg = _groups(train)
    vg = _groups(val)
    eg = _groups(test)
    tv = sorted(tg & vg)
    te = sorted(tg & eg)
    ve = sorted(vg & eg)
    return {
        'train_val': tv,
        'train_test': te,
        'val_test': ve,
        'total_leaking': len((tg & vg) | (tg & eg) | (vg & eg)),
    }


def _group_split_coverage_first(rows, group_col, seed):
    """Group-disjoint split with a coverage-first objective (internal).

    Identical structure to stratified_group_split_by, but the sort tuple
    prepends a coverage_penalty term so that assignments that would leave a
    class absent from train or val are strongly avoided.

    Used by coverage_preserving_group_split for multi-signer classes only.
    """
    groups = defaultdict(list)
    for r in rows:
        key = (r.get(group_col) or '').strip()
        groups[key].append(r)

    user_vec = {}
    for u, lst in groups.items():
        c = Counter(int(r['class_idx']) for r in lst)
        user_vec[u] = c

    all_classes = set()
    for vec in user_vec.values():
        all_classes.update(vec.keys())

    targets = _targets_per_split(rows)
    counts = {
        'train': Counter(),
        'val': Counter(),
        'test': Counter(),
    }

    ordered_users = sorted(
        groups.keys(),
        key=lambda u: (min(user_vec[u].values()), -sum(user_vec[u].values()), str(u))
    )

    assign = {}
    for u in ordered_users:
        vec = user_vec[u]
        deficits = {}
        for s in ('train', 'val', 'test'):
            classes = set(targets[s].keys()) | set(counts[s].keys())
            deficits[s] = Counter({
                cls: max(0, targets[s].get(cls, 0) - counts[s].get(cls, 0))
                for cls in classes
            })

        candidate_scores = []
        for split in ('train', 'val', 'test'):
            # Coverage-first: strongly prefer assignments that keep every class
            # represented in both train and val.
            new_covered_train = set(counts['train'].keys()) | (
                set(vec.keys()) if split == 'train' else set()
            )
            new_covered_val = set(counts['val'].keys()) | (
                set(vec.keys()) if split == 'val' else set()
            )
            coverage_penalty = (
                len(all_classes - new_covered_train) * 1000 +
                len(all_classes - new_covered_val) * 1000
            )

            overflow = sum(
                max(0, (counts[split].get(cls, 0) + vec.get(cls, 0)) - targets[split].get(cls, 0))
                for cls in set(list(vec.keys()) + list(targets[split].keys()))
            )
            cost = 0
            for s in ('train', 'val', 'test'):
                for cls in set(list(targets[s].keys()) + list(counts[s].keys()) + list(vec.keys())):
                    c = counts[s].get(cls, 0) + (vec.get(cls, 0) if s == split else 0)
                    t = targets[s].get(cls, 0)
                    diff = c - t
                    cost += diff * diff
            deficit_sum = sum(deficits[split].values())
            candidate_scores.append((coverage_penalty, overflow, cost, -deficit_sum, split))

        candidate_scores.sort()
        chosen_split = candidate_scores[0][4]
        assign[u] = chosen_split
        counts[chosen_split] += vec

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


def coverage_preserving_group_split(rows, group_col='user', seed=42):
    """Coverage-first group split for live-capture closed-set classifiers.

    Guarantees every class appears in both train and val.

    Strategy:
    - Singleton-signer classes (only 1 unique signer for that class):
      strict group-disjoint isolation is impossible.  A sample-level
      stratified split is applied for those rows and a warning is printed.
    - Multi-signer classes: group-disjoint split with coverage-first
      objective (coverage_penalty added before balance terms).

    Unlike strict_user_disjoint, this mode may allow minimal signer leakage
    for singleton-signer classes.  The diagnostics dict records which classes
    triggered the sample-level fallback.

    Returns:
        (train, val, test, diagnostics)
    """
    redundancy = analyze_class_signer_redundancy(rows, group_col)

    singleton_classes = frozenset(
        ci for ci, info in redundancy.items()
        if not info['strict_isolation_feasible']
    )

    for ci in sorted(singleton_classes):
        info = redundancy[ci]
        signer = info['signers'][0] if info['signers'] else '(unknown)'
        print(
            f"[WARN] coverage_preserving_group_split: "
            f"class {ci} has only 1 unique {group_col} ({signer!r}). "
            f"Strict {group_col} isolation impossible for this class. "
            f"Applying sample-level fallback to preserve train/val coverage."
        )

    def _ci(r):
        try:
            return int((r.get('class_idx') or '').strip())
        except Exception:
            return None

    singleton_rows = [r for r in rows if _ci(r) in singleton_classes]
    multi_rows = [r for r in rows if _ci(r) is not None and _ci(r) not in singleton_classes]

    # Singleton classes: sample-level split (coverage guaranteed, no signer isolation)
    train_s, val_s, test_s = stratified_split(singleton_rows) if singleton_rows else ([], [], [])

    # Multi-signer classes: group-disjoint with coverage-first objective
    if multi_rows:
        train_m, val_m, test_m = _group_split_coverage_first(multi_rows, group_col, seed)
    else:
        train_m, val_m, test_m = [], [], []

    train = train_s + train_m
    val = val_s + val_m
    test = test_s + test_m

    diagnostics = {
        'mode': 'coverage_preserving',
        'singleton_classes': sorted(singleton_classes),
        'singleton_class_count': len(singleton_classes),
        'multi_signer_class_count': len(redundancy) - len(singleton_classes),
        'sample_level_fallback_applied': len(singleton_classes) > 0,
    }
    return train, val, test, diagnostics


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
    parser.add_argument('--user_disjoint', action='store_true', help='Ensure no group appears in multiple splits')
    parser.add_argument('--group_col', type=str, default='user_id', help='Grouping column to keep disjoint (e.g., user_id, dialect)')
    parser.add_argument(
        '--split_mode', type=str, default='sample',
        choices=['sample', 'coverage_preserving', 'strict_user_disjoint'],
        help=(
            'Split strategy. '
            '"sample": sample-level stratified (default, no signer constraints). '
            '"coverage_preserving": guarantees every class in train+val; '
            'uses group-disjoint for multi-signer classes and sample-level fallback '
            'for singleton-signer classes. Recommended for live-capture classifiers. '
            '"strict_user_disjoint": maximises signer isolation; may break coverage '
            'for singleton-signer classes. Equivalent to --user_disjoint. '
            'Recommended for embedding/representation-learning experiments.'
        ),
    )
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
    def _active_mode():
        # --user_disjoint is the legacy flag; it maps to strict_user_disjoint
        # but only if --split_mode was not explicitly set away from 'sample'.
        if args.user_disjoint and args.split_mode == 'sample':
            return 'strict_user_disjoint'
        return args.split_mode

    def _do_split(rows_subset):
        mode = _active_mode()
        if mode in ('strict_user_disjoint', 'coverage_preserving'):
            if args.group_col not in fieldnames:
                raise SystemExit(
                    f"samples.csv has no '{args.group_col}' column; "
                    f"cannot perform {mode} split."
                )
        if mode == 'strict_user_disjoint':
            t, v, e = stratified_group_split_by(rows_subset, args.group_col)
            return t, v, e, None
        if mode == 'coverage_preserving':
            return coverage_preserving_group_split(
                rows_subset, args.group_col, seed=RANDOM_SEED
            )
        t, v, e = stratified_split(rows_subset)
        return t, v, e, None

    if not args.by_language:
        train, val, test, split_diag = _do_split(rows)
        _assert_no_overlap(train, val)
        _assert_no_overlap(train, test)
        _assert_no_overlap(val, test)
        validate_split_coverage(train, val, test, rows, lookup)
        if _active_mode() == 'coverage_preserving':
            leakage = _check_signer_leakage(train, val, test, args.group_col)
            if leakage['total_leaking']:
                print(
                    f"[INFO] Signer leakage report (coverage_preserving mode): "
                    f"train/val={len(leakage['train_val'])} signers, "
                    f"train/test={len(leakage['train_test'])} signers, "
                    f"val/test={len(leakage['val_test'])} signers"
                )
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
        'split_mode': _active_mode(),
        'user_disjoint': bool(args.user_disjoint),
        'group_col': args.group_col,
        'languages': {},
    }

    for lang, rows_l in sorted(by_lang.items(), key=lambda kv: kv[0]):
        if not rows_l:
            continue
        train, val, test, split_diag = _do_split(rows_l)
        validate_split_coverage(train, val, test, rows_l, lookup)
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

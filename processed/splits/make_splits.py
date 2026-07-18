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

# ---------------------------------------------------------------------------
# Vocabulary schema v2: manifest-based, profile-filtered, signer-disjoint splits
# ---------------------------------------------------------------------------

def _load_manifest_rows(manifest_path: Path):
    with Path(manifest_path).open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader), list(reader.fieldnames or [])


def _assert_signer_disjoint(train, val, test, group_col='signer_id'):
    """Hard requirement for strict_signer_disjoint mode."""
    def _g(rows_):
        return {(r.get(group_col) or '').strip() for r in rows_ if (r.get(group_col) or '').strip()}
    train_signers, val_signers, test_signers = _g(train), _g(val), _g(test)
    assert train_signers.isdisjoint(val_signers), f"signer leakage train/val: {train_signers & val_signers}"
    assert train_signers.isdisjoint(test_signers), f"signer leakage train/test: {train_signers & test_signers}"
    assert val_signers.isdisjoint(test_signers), f"signer leakage val/test: {val_signers & test_signers}"
    return train_signers, val_signers, test_signers


def split_from_manifest(
    manifest_rows,
    *,
    split_mode: str,
    recognition_profile: str = '',
    include_common: bool = True,
    unified: bool = False,
    seed: int = 42,
    group_col: str = 'signer_id',
    fail_on_missing_eval: bool = False,
    exclude_unresolved_signers: bool = False,
):
    """Profile-filtered split over an immutable dataset manifest.

    Returns (train, val, test, report). Raises SystemExit on hard failures
    (empty subset, class with no train sample, signer leakage in strict mode,
    unresolved signer_id in strict mode).
    """
    import sys as _sys
    _repo_root = Path(__file__).resolve().parents[2]
    if str(_repo_root) not in _sys.path:
        _sys.path.insert(0, str(_repo_root))
    from processed.shared.vocabulary import (
        check_label_collisions, label_key_v2, select_rows_for_profile,
    )

    # 1. Profile subset (v2 rule: common + selected profile, or unified)
    if unified or recognition_profile:
        rows = select_rows_for_profile(
            manifest_rows,
            recognition_profile=recognition_profile or None,
            include_common=include_common,
            unified=unified,
        )
    else:
        rows = list(manifest_rows)
    if not rows:
        raise SystemExit("Profile subset is empty — nothing to split. "
                         "(Are vocabulary_scope/recognition_profile assigned in the manifest?)")

    collisions = check_label_collisions(rows)
    if collisions:
        raise SystemExit(f"Label collision between common and profile-specific sets: {collisions}. "
                         f"Resolve (rename/reassign) before splitting.")

    # 2. Stable v2 label keys + synthetic class ids for the split machinery
    for r in rows:
        r['label_key'] = label_key_v2(
            r.get('language') or 'vn', r.get('vocabulary_scope') or '',
            r.get('recognition_profile') or '', r.get('slug') or r.get('label_slug') or '')
        if not (r.get('sample_id') or '').strip():
            r['sample_id'] = (r.get('sample_uid') or '').strip()
        if not (r.get('label_slug') or '').strip():
            r['label_slug'] = (r.get('slug') or '').strip()
    unique_keys = sorted({r['label_key'] for r in rows})
    key_to_idx = {k: i + 1 for i, k in enumerate(unique_keys)}
    for r in rows:
        r['class_idx'] = str(key_to_idx[r['label_key']])

    # 3. Split
    excluded_unresolved = []
    if split_mode == 'strict_signer_disjoint':
        unresolved = [r['sample_id'] for r in rows if not (r.get(group_col) or '').strip()]
        if unresolved and exclude_unresolved_signers:
            print(f"[WARN] excluding {len(unresolved)} sample(s) with no {group_col} "
                  f"(explicit --exclude_unresolved_signers): {unresolved[:10]}")
            excluded_unresolved = unresolved
            rows = [r for r in rows if (r.get(group_col) or '').strip()]
        elif unresolved:
            raise SystemExit(
                f"{len(unresolved)} sample(s) have no {group_col} — strict signer-disjoint "
                f"splitting is impossible until signer migration resolves them "
                f"(or pass --exclude_unresolved_signers to drop them explicitly). "
                f"Examples: {unresolved[:5]}")
        train, val, test = stratified_group_split_by(rows, group_col)
        train_s, val_s, test_s = _assert_signer_disjoint(train, val, test, group_col)
    elif split_mode == 'sample':
        train, val, test = stratified_split(rows)
        train_s = val_s = test_s = set()
    else:
        raise SystemExit(f"split_mode '{split_mode}' not supported in manifest mode "
                         f"(use 'sample' or 'strict_signer_disjoint').")

    _assert_no_overlap(train, val)
    _assert_no_overlap(train, test)
    _assert_no_overlap(val, test)

    # 4. Coverage rules: every class MUST have train samples; val/test configurable
    def _classes(rows_):
        return {r['label_key'] for r in rows_}
    all_c, tr_c, va_c, te_c = _classes(rows), _classes(train), _classes(val), _classes(test)
    missing_train = sorted(all_c - tr_c)
    if missing_train:
        raise SystemExit(f"{len(missing_train)} class(es) have no TRAIN sample: {missing_train}")
    missing_eval = sorted((all_c - va_c) | (all_c - te_c))
    if missing_eval:
        msg = f"{len(missing_eval)} class(es) missing from val and/or test: {missing_eval}"
        if fail_on_missing_eval:
            raise SystemExit(msg)
        print(f"[WARN] {msg}")

    report = {
        'split_mode': split_mode,
        'recognition_profile': recognition_profile or ('unified' if unified else 'all'),
        'include_common': include_common,
        'seed': seed,
        'group_col': group_col,
        'num_classes': len(unique_keys),
        'label_keys': unique_keys,
        'counts': {'train': len(train), 'val': len(val), 'test': len(test)},
        'signers': {'train': sorted(train_s), 'val': sorted(val_s), 'test': sorted(test_s)},
        'class_coverage': {
            'train': len(tr_c) / max(1, len(all_c)),
            'val': len(va_c) / max(1, len(all_c)),
            'test': len(te_c) / max(1, len(all_c)),
        },
        'profile_composition': {
            'common': sum(1 for r in rows if (r.get('vocabulary_scope') or '') == 'common'),
            'profile_specific': sum(1 for r in rows if (r.get('vocabulary_scope') or '') == 'profile_specific'),
        },
        'excluded_unresolved_signers': excluded_unresolved,
    }
    return train, val, test, report


def run_manifest_mode(args) -> None:
    """Manifest-based versioned split. NEVER touches the frozen legacy split
    files at processed/splits/{train,val,test}.csv."""
    global RANDOM_SEED
    RANDOM_SEED = args.seed
    manifest_rows, fieldnames = _load_manifest_rows(args.dataset_manifest)
    for col in ('sample_id', 'class_idx', 'label_key', 'label_slug'):
        if col not in fieldnames:
            fieldnames.append(col)

    train, val, test, report = split_from_manifest(
        manifest_rows,
        split_mode=args.split_mode,
        recognition_profile=(args.recognition_profile or ''),
        include_common=args.include_common,
        unified=args.unified,
        seed=args.seed,
        group_col=args.group_col,
        fail_on_missing_eval=args.fail_on_missing_eval,
        exclude_unresolved_signers=args.exclude_unresolved_signers,
    )

    out_dir = OUT_DIR / 'versions' / args.output_version
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit(f"Split version already exists: {out_dir} — split versions are "
                         f"immutable; choose a new --output_version.")
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, rows_ in (('train', train), ('val', val), ('test', test)):
        write_split_to_dir(out_dir, name, rows_, fieldnames)

    import hashlib
    manifest_bytes = Path(args.dataset_manifest).read_bytes()
    report['dataset_manifest'] = str(args.dataset_manifest)
    report['dataset_manifest_checksum'] = hashlib.sha256(manifest_bytes).hexdigest()
    report['output_version'] = args.output_version
    (out_dir / 'split_metadata.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f"Split '{args.output_version}' -> {out_dir}")
    print(f"  mode={report['split_mode']} profile={report['recognition_profile']} "
          f"classes={report['num_classes']} counts={report['counts']}")
    print(f"  signers: train={len(report['signers']['train'])} "
          f"val={len(report['signers']['val'])} test={len(report['signers']['test'])}")
    print(f"  coverage: {report['class_coverage']}")


def main():
    parser = argparse.ArgumentParser(description='Make dataset splits')
    parser.add_argument('--user_disjoint', action='store_true', help='Ensure no group appears in multiple splits')
    parser.add_argument('--group_col', type=str, default='user_id', help='Grouping column to keep disjoint (e.g., user_id, dialect, signer_id)')
    parser.add_argument(
        '--split_mode', type=str, default='sample',
        choices=['sample', 'coverage_preserving', 'strict_user_disjoint', 'strict_signer_disjoint'],
        help=(
            'Split strategy. '
            '"sample": sample-level stratified (default, no signer constraints). '
            '"coverage_preserving": guarantees every class in train+val; '
            'uses group-disjoint for multi-signer classes and sample-level fallback '
            'for singleton-signer classes. Recommended for live-capture classifiers. '
            '"strict_user_disjoint": maximises signer isolation; may break coverage '
            'for singleton-signer classes. Equivalent to --user_disjoint. '
            '"strict_signer_disjoint": manifest mode only — group-disjoint on the '
            'normalized signer_id with hard disjointness asserts.'
        ),
    )
    # --- Vocabulary schema v2 (manifest mode) ---
    parser.add_argument('--dataset_manifest', type=Path, default=None,
                        help='Immutable dataset manifest CSV. Enables v2 manifest mode '
                             '(splits reference sample_id; legacy split files untouched).')
    parser.add_argument('--recognition_profile', type=str, default='',
                        help='Profile subset: north|central|south|hoa_de (manifest mode)')
    parser.add_argument('--include_common', dest='include_common', action='store_true', default=True,
                        help='Include common vocabulary in the profile subset (default true)')
    parser.add_argument('--no_include_common', dest='include_common', action='store_false')
    parser.add_argument('--unified', action='store_true',
                        help='Unified baseline: common + every validly-assigned profile')
    parser.add_argument('--output_version', type=str, default='',
                        help='Version name for the split (written under processed/splits/versions/<name>/)')
    parser.add_argument('--fail_on_missing_eval', action='store_true',
                        help='Fail (instead of warn) when a class has no val/test sample')
    parser.add_argument('--exclude_unresolved_signers', action='store_true',
                        help='Explicitly drop samples whose signer_id is unresolved '
                             '(otherwise strict mode fails). Exclusions are recorded in split_metadata.json')
    parser.add_argument('--by_language', action='store_true', help='Write separate split CSVs per language under splits/<language>/')
    parser.add_argument('--languages', type=str, default='', help='Optional comma-separated whitelist of languages when using --by_language')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    # v2 manifest mode: fully separate path; never touches legacy split files.
    if args.dataset_manifest is not None:
        if not args.output_version:
            raise SystemExit('--dataset_manifest requires --output_version')
        if args.split_mode == 'strict_signer_disjoint' and args.group_col == 'user_id':
            args.group_col = 'signer_id'
        run_manifest_mode(args)
        return
    if args.split_mode == 'strict_signer_disjoint':
        raise SystemExit('strict_signer_disjoint requires --dataset_manifest (v2 mode).')

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

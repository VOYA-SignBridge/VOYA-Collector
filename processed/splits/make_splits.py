import csv
import itertools
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
    # Canonical layout: <repo>/dataset/samples.csv (the interim
    # dataset/samples/samples.csv path was retired 2026-07-20)
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
                # `region` là nửa còn lại của khoá duy nhất trong CSDL
                # `(tenant_id, slug, language, dialect, region)`. Không mang nó
                # theo thì `ăn|bac` và `ăn|nam` trông y hệt nhau trong split.
                'region': r.get('region', ''),
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


#: Sàn mặc định khi `--min_samples_per_class` không được truyền: 0 = tắt.
#: Giá trị dùng thật nằm ở `MIN_SAMPLES_PER_CLASS_FOR_TRAINING` phía backend
#: (mặc định 25 ≈ 5 lần quay live-capture). Chủ ý KHÔNG đọc biến môi trường đó
#: ở đây: split là hiện vật, và sàn nó đã dùng phải nằm trong chính hiện vật
#: chứ không phụ thuộc vào môi trường của lần chạy sau.
DEFAULT_MIN_SAMPLES_PER_CLASS = 0


def _class_key(r: dict) -> str:
    """Định danh lớp bền nhất có trong hàng: class_uid, rồi mới tới class_idx."""
    return (r.get('class_uid') or '').strip() or (r.get('class_idx') or '').strip()


def filter_classes_below_floor(rows, floor: int, *, key_fn=_class_key):
    """Loại HẲN các lớp có ít hơn `floor` mẫu. Trả về (rows_giữ_lại, đã_loại).

    Vì sao lọc ở ĐÂY chứ không ở lúc huấn luyện: `_consent_preflight` phía
    backend đã chốt nguyên tắc này rồi, và nó đúng cho cả hai trường hợp — một
    checkpoint huấn luyện trên tập nhỏ hơn tệp split khai báo là một checkpoint
    NÓI DỐI về nguồn gốc của nó. Split là đầu vào đã đóng băng; ai muốn đổi tập
    lớp thì dựng lại split, không lọc lén lúc chạy.

    Loại cả lớp chứ không cắt bớt mẫu, và đó là chủ ý: một lớp 5 mẫu chia
    70/15/15 còn 3 mẫu huấn luyện. Nó không học được, nhưng nó vẫn chiếm một
    chiều trong tầng softmax và vẫn hiện ra ở danh sách lớp thời gian thực —
    tức là kéo tụt số đo mà không đóng góp gì. Giữ nó lại chỉ để bảng tổng kết
    trông nhiều lớp hơn là tự lừa mình.

    `floor <= 0` là TẮT, và khi tắt thì không loại gì cả — để lượt chạy cũ và
    các đường gọi chưa khai báo sàn giữ nguyên hành vi.
    """
    if floor <= 0:
        return list(rows), []

    dem = Counter()
    nhan = {}
    for r in rows:
        k = key_fn(r)
        if not k:
            continue
        dem[k] += 1
        nhan.setdefault(k, (r.get('label_original') or r.get('label_slug')
                            or r.get('slug') or '').strip())

    loai = {k for k, n in dem.items() if n < floor}
    da_loai = sorted(
        ({'class': k, 'label': nhan.get(k, ''), 'samples': dem[k]} for k in loai),
        key=lambda d: (-d['samples'], d['class']),
    )
    giu = [r for r in rows if key_fn(r) not in loai]
    return giu, da_loai


def enforce_min_classes(class_keys, min_classes: int, *, ten_tap: str = '',
                        so_ung_vien: int = 0, da_loai=()) -> None:
    """Dừng hẳn nếu sau khi lọc còn quá ít lớp. KHÔNG ghi split.

    Vì sao cổng này phải nằm ở ĐÂY chứ không chỉ ở API tạo phiên huấn luyện:
    `make_splits.py` chạy được thẳng từ dòng lệnh, ngoài mọi cổng của backend.
    Một cổng chỉ bảo vệ được đường đi qua nó.

    Ca thật ngày 14/08: `can-tho` có 8 lớp, sàn 25 mẫu loại 7, còn ĐÚNG MỘT.
    Ghi ra một tập chia một lớp là ghi ra một hiện vật vô nghĩa mà mọi thứ phía
    sau sẽ đối xử như thật.
    """
    if min_classes <= 0:
        return
    n = len(set(class_keys))
    if n >= min_classes:
        return
    boi_canh = f" cho {ten_tap}" if ten_tap else ''
    chi_tiet = ''
    if da_loai:
        vi_du = ', '.join(f"{d.get('label') or d.get('class')} ({d['samples']} mẫu)"
                          for d in list(da_loai)[:5])
        chi_tiet = f" Đã loại vì chưa đủ mẫu: {vi_du}."
    raise SystemExit(
        f"Không đủ lớp để chia{boi_canh}: còn {n} lớp, cần ≥{min_classes}."
        f"{chi_tiet}"
        f" {so_ung_vien or n} lớp ứng viên ban đầu."
        f" KHÔNG ghi tập chia — một tập chia dưới hai lớp không có bài toán "
        f"phân loại nào để học, nhưng mọi thứ phía sau sẽ đối xử với nó như thật."
    )


def _report_floor(floor: int, da_loai, con_lai_lop: int) -> None:
    if floor <= 0:
        return
    if not da_loai:
        print(f"[floor] min_samples_per_class={floor}: mọi lớp đều đạt "
              f"({con_lai_lop} lớp giữ nguyên).")
        return
    print(f"[floor] min_samples_per_class={floor}: loại {len(da_loai)} lớp "
          f"chưa đủ mẫu, còn {con_lai_lop} lớp.")
    for d in da_loai[:20]:
        ten = f" {d['label']}" if d['label'] else ''
        print(f"         - {d['class']}{ten}: {d['samples']} mẫu")
    if len(da_loai) > 20:
        print(f"         … và {len(da_loai) - 20} lớp nữa")


#: Số lớp tối thiểu để một tập chia có nghĩa. Dưới hai lớp thì không có bài
#: toán phân loại nào để học. Đây là CHÍNH SÁCH, nên nó phải nằm trong hiện vật
#: cùng với sàn số mẫu — xem `write_legacy_snapshot`.
DEFAULT_MIN_CLASSES = 2


def class_set_checksum(class_keys) -> str:
    """Băm TẬP lớp — không phụ thuộc thứ tự.

    Chuẩn hoá trước khi băm: bỏ trùng, bỏ khoảng trắng thừa, SẮP XẾP, nối bằng
    xuống dòng. Nhờ vậy `[A, B, C]` và `[C, A, B]` cho cùng một mã, đúng nghĩa
    "tập lớp". Không chuẩn hoá thì mã sẽ băm cả thứ tự trả về ngẫu nhiên của
    CSDL và mất hết ý nghĩa.
    """
    import hashlib

    canon = '\n'.join(sorted({str(k).strip() for k in class_keys if str(k).strip()}))
    return hashlib.sha256(canon.encode('utf-8')).hexdigest()


def class_mapping_checksum(mapping) -> str:
    """Băm ÁNH XẠ lớp→chỉ số. Khác hẳn `class_set_checksum`, và cần cả hai.

    `A→0 B→1 C→2` và `A→2 B→0 C→1` có CÙNG tập lớp nhưng KHÔNG cùng ánh xạ
    nhãn. Một checkpoint dùng ánh xạ thứ hai mà đọc nhãn theo ánh xạ thứ nhất
    sẽ đoán sai toàn bộ, âm thầm, với độ chính xác báo cáo vẫn đẹp.

    Chuyện này không phải giả định: `_build_subset_label_maps` trong
    `train_tcn.py` dựng `label_to_index` bằng `enumerate` trên các nhãn gom
    theo THỨ TỰ HÀNG XUẤT HIỆN trong CSV. Nghĩa là lớp 0 của mô hình hiện nay
    là "nhãn nào nằm ở dòng đầu tiên", và không có gì ghim nó lại. Mã băm này
    là thứ để phát hiện khi nó trượt.

    `mapping` là dãy cặp `(class_key, idx)`. Sắp theo `class_key` trước khi
    băm, nên thứ tự đưa vào không đổi kết quả.

    UỶ QUYỀN cho `label_mapping.canonical_mapping_hash`, và đó là điểm chính.
    Bản trước tự băm `k=i`, trong khi bên tiêu thụ băm `k<TAB>i`. Hai bản cài
    đặt của cùng một quy ước, lệch nhau đúng một ký tự phân tách, nên MỌI hiện
    vật do `make_splits` ghi ra đều bị `consume_declared` từ chối với thông báo
    "hiện vật đã bị sửa sau khi ghi" — trong khi không ai sửa gì cả.

    Bộ kiểm không thấy được vì cả hai phía đều được kiểm bằng CHÍNH hàm của
    mình (`rep[...] == class_mapping_checksum(...)`), và fixture của smoke tự
    tính metadata bằng `canonical_mapping_hash` thay vì chạy qua `make_splits`.
    Một quy ước chỉ có một định nghĩa thì không có gì để lệch.
    """
    from processed.train_utils.label_mapping import canonical_mapping_hash

    return canonical_mapping_hash({str(k): int(i) for k, i in mapping})


def assign_target_indices(class_keys):
    """{class_key: target_idx} liên tục 0..K-1, thứ tự TẤT ĐỊNH theo khoá.

    Vì sao là một trường RIÊNG chứ không ghi đè `class_idx`: hai thứ đó là hai
    khái niệm khác nhau và trộn chúng là một lỗi đắt.

      `class_idx`   ĐỊNH DANH toàn cục, lấy từ `labels.csv`, bền qua mọi lượt
                    chia. Một nhãn giữ nguyên số này kể cả khi nó không nằm
                    trong tập chia nào. Đây là thứ không được để trống.
      `target_idx`  vị trí trong tầng đầu ra CỦA RIÊNG lượt chia này, luôn
                    0..K-1 không thủng lỗ. Loại một lớp thì mọi lớp sau nó
                    dịch xuống — nên nó KHÔNG phải định danh.

    Ghi đè `class_idx` thành 0..K-1 sẽ làm mọi hiện vật trỏ vào nó (mẫu, npz,
    checkpoint cũ) trỏ nhầm chỗ ở lần chia kế tiếp.
    """
    return {k: i for i, k in enumerate(sorted(class_keys))}


def write_split(name, rows, fieldnames):
    # `mkdir` ở ĐÂY chứ không lúc phân giải `OUT_DIR`: các cổng (sàn số mẫu,
    # số lớp tối thiểu) chạy trước khi có gì được ghi, và một lượt bị cổng
    # chặn không được để lại thư mục nào. Thư mục rỗng vẫn là một hiện vật với
    # người đọc sau — nó qua được phép kiểm "chỉ-tạo-mới" (rỗng nên không coi
    # là đã tồn tại) và làm resolver báo "có hiện vật nhưng thiếu bản khai".
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f'{name}.csv'
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


#: Tên tệp khai báo của split legacy. Chế độ manifest đã có
#: `versions/<tên>/split_metadata.json` riêng; đường legacy trước đây KHÔNG khai
#: báo gì cả, nên không ai kiểm được một checkpoint đã huấn luyện trên tập lớp
#: nào. Đây là chỗ vá khoảng trống đó.
LEGACY_SNAPSHOT_NAME = 'split_metadata.json'


def write_legacy_snapshot(out_dir: Path, *, class_keys, floor: int, excluded,
                          mode: str, seed: int, counts: dict,
                          min_classes: int = DEFAULT_MIN_CLASSES,
                          sample_counts=None, split_id=None, extra=None,
                          class_meta=None, tenant_id=None) -> Path:
    """Ghi HỢP ĐỒNG của tập chia cạnh train/val/test.csv.

    Hợp đồng chứ không phải ghi chú, và khác biệt nằm ở chỗ có ai ĐỌC nó rồi
    hành động hay không: cổng huấn luyện đọc tệp này, đối chiếu với nội dung
    CSV thật, và từ chối chạy khi hai thứ không khớp.

    Ba thứ bắt buộc, không được lược:

      `policy`              sàn số mẫu VÀ số lớp tối thiểu. Ghi mỗi con số 25
                            là chưa đủ — người đọc sau sẽ không biết tập chia
                            này đã được kiểm điều kiện thứ hai hay chưa.
      `classes`             ánh xạ ĐẦY ĐỦ class_uid → target_idx. Thiếu nó thì
                            không ai dựng lại được ý nghĩa của tầng đầu ra.
      `*_hash`              hai mã băm, xem `class_mapping_checksum` để biết vì
                            sao một cái là không đủ.

    `sample_counts` là {class_key: số mẫu TRƯỚC khi chia} — chứng cứ để đối
    chiếu về sau, và là thứ cho biết một lớp đạt sàn sát nút hay dư dả.

    `class_meta` là {class_key: {class_idx, slug, dialect, region, ...}} — nhãn
    ĐỌC, không phải định danh. Chúng đi kèm vì `build_checkpoint_mapping` chép
    chúng vào checkpoint và giao diện thời gian thực dựng tên hiển thị từ đó;
    thiếu chúng thì màn hình hiện `class_uid` thô, vì `normalize_idx_to_label`
    tra từ vựng theo `label_key` mà UID không khớp gì cả. Không trường nào
    trong đây tham gia quyết định `target_idx`.
    """
    from datetime import datetime, timezone

    keys = sorted(set(class_keys))
    mapping = assign_target_indices(keys)
    dem = dict(sample_counts or {})
    mo_ta = dict(class_meta or {})

    payload = {
        'schema_version': 2,
        # Hiện vật phải TỰ KHAI nó thuộc hợp đồng nào. Chính vì hai hợp đồng bị
        # nhập làm một mà ba tệp `processed/splits/*.csv` vừa là mốc nghiên cứu
        # đóng băng vừa là đầu vào vận hành. `train_tcn.py` chỉ đi đường
        # `class_uid → target_idx` khi đọc thấy đúng chữ này; thiếu nó thì mọi
        # thứ giữ nguyên hành vi cũ.
        'purpose': 'operational',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'split_mode': mode,
        'seed': seed,
        'ratios': {'train': TRAIN_RATIO, 'val': VAL_RATIO,
                   'test': round(1.0 - TRAIN_RATIO - VAL_RATIO, 10)},
        'policy': {
            'min_samples_per_class': int(floor),
            'min_classes': int(min_classes),
        },
        'num_classes': len(keys),
        'classes': [
            {'class_uid': k, 'target_idx': mapping[k],
             'sample_count_before_split': int(dem.get(k, 0)),
             **{c: v for c, v in (mo_ta.get(k) or {}).items() if v not in (None, '')}}
            for k in keys
        ],
        'class_set_hash': class_set_checksum(keys),
        'class_mapping_hash': class_mapping_checksum(mapping.items()),
        'excluded_below_floor': excluded,
        'counts': counts,
        # Giữ tên cũ để bản đọc trước đó không vỡ. `schema_version` mới là thứ
        # người đọc nên nhìn.
        'min_samples_per_class': int(floor),
        'class_set': keys,
        'class_set_checksum': class_set_checksum(keys),
    }
    if split_id:
        # `split_id` nằm TRONG bản khai, không chỉ ở tên thư mục: chép ba CSV
        # từ hiện vật Y vào một thư mục đặt tên X phải bị phát hiện.
        payload['split_id'] = str(split_id)
        # Mã băm từng tệp, tính SAU khi ba CSV đã ghi xong. Đây là thứ biến
        # "tìm được tệp" thành "đã xác minh hiện vật".
        from processed.train_utils.split_artifact import (
            OWNER_BINDING_KEY, OWNER_KEY, file_hashes, owner_binding)

        # ★ C2b — hiện vật vận hành PHẢI có chủ, và chủ chỉ do bên tạo đặt.
        #
        # Điều kiện là `split_id`, tức "tôi đang ghi một hiện vật vận hành CÓ
        # ĐỊA CHỈ" — thứ mà `resolve_operational` có thể trả về cho một lượt
        # huấn luyện. Bản khai ở gốc `processed/splits/` và ở nhánh
        # `--by_language` cũng mang `purpose: operational`, nhưng chúng không có
        # `split_id` nên không hiện vật nào phân giải tới được; ở đó chữ
        # `operational` đang làm nhiệm vụ khác — cờ báo cho `train_tcn.py` biết
        # đi đường `class_uid → target_idx`. Hai nghĩa chồng lên một trường là
        # nợ kỹ thuật có thật, ghi ở docs/10-issues/KNOWN_ISSUES.md.
        chu = str(tenant_id or '').strip()
        if not chu:
            raise ValueError(
                f'hiện vật vận hành {split_id!r} không có `{OWNER_KEY}`. Chủ sở '
                f'hữu phải đến từ ngữ cảnh tạo, và không có ngữ cảnh thì DỪNG — '
                f'không lấy tenant của lượt huấn luyện đầu tiên muốn dùng nó, '
                f'không rơi về tenant khởi tạo. Truyền --tenant_id=<ID>.')
        # Kiểm hợp đồng TRƯỚC khi làm việc — cùng khuôn đã dùng ở C1. Đặt sau
        # `file_hashes` thì một hiện vật thiếu chủ sẽ nổ bằng FileNotFoundError
        # của tệp CSV, và người đọc log sẽ đi sửa nhầm chỗ.
        payload['files'] = file_hashes(out_dir)
        payload[OWNER_KEY] = chu
        payload[OWNER_BINDING_KEY] = owner_binding(
            split_id=str(split_id), tenant_id=chu, files=payload['files'])
    elif str(tenant_id or '').strip():
        # Bản khai không-có-địa-chỉ mà lại mang chủ sở hữu là một lời khai không
        # ai cưỡng chế được: `resolve_operational` không bao giờ chạm tới nó.
        # Ghi vào chỉ tạo cảm giác an toàn giả.
        raise ValueError(
            'tenant_id chỉ có nghĩa với hiện vật vận hành có `split_id`. '
            'Bản khai ở gốc splits/ hoặc theo ngôn ngữ không phải hiện vật có '
            'địa chỉ, nên không mang quyền sở hữu.')
    if extra:
        payload.update(extra)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / LEGACY_SNAPSHOT_NAME
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
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


#: Above this many distinct groups the exhaustive search is skipped. 3**14 is
#: ~4.8M partitions, already a few seconds; real signer counts are far smaller.
_EXACT_PARTITION_MAX_GROUPS = 13


def _exact_group_partition(rows, group_col: str):
    """Best coverage-complete group partition, or None if none exists.

    stratified_group_split_by only matches per-class SAMPLE COUNTS; it has no
    notion of class coverage, so with a few dominant signers it happily empties
    a whole split. That is how hoa_de_signer_disjoint_v1/_v3 reached disk with
    val=0/test=0, and it is why alphabet failed here at first: 7 signers, of
    which S001 (987 samples) and S002 (708) dominate, and the count-matching
    objective put none of them in val.

    A valid partition did exist. With a handful of groups the assignment space
    is tiny (3**7 = 2187), so search it exactly instead of hoping a greedy pass
    lands on it: keep only partitions where every class appears in all three
    splits, then pick the one closest to the 70/15/15 sample ratio.

    Returns (train, val, test) row lists, or None when no valid partition
    exists (genuinely too few groups) or there are too many groups to enumerate
    — the caller then falls back to the greedy path and the validity gate still
    refuses to write an unusable split.
    """
    groups = defaultdict(list)
    for r in rows:
        groups[(r.get(group_col) or '').strip()].append(r)
    names = sorted(groups)
    if not names or len(names) > _EXACT_PARTITION_MAX_GROUPS:
        return None

    classes_of = {n: {r['label_key'] for r in groups[n]} for n in names}
    size_of = {n: len(groups[n]) for n in names}
    all_classes = set().union(*classes_of.values())
    total = sum(size_of.values()) or 1
    want = (TRAIN_RATIO, VAL_RATIO, 1.0 - TRAIN_RATIO - VAL_RATIO)

    best = None
    for assign in itertools.product(range(3), repeat=len(names)):
        parts = [[n for n, a in zip(names, assign) if a == i] for i in range(3)]
        if any(not p for p in parts):
            continue
        if any(all_classes - set().union(*(classes_of[n] for n in p)) for p in parts):
            continue
        sizes = [sum(size_of[n] for n in p) for p in parts]
        score = sum(abs(s / total - w) for s, w in zip(sizes, want))
        # `assign` breaks ties so the result never depends on dict ordering.
        if best is None or (score, assign) < (best[0], best[1]):
            best = (score, assign, parts)

    if best is None:
        return None
    parts = best[2]
    return tuple([r for n in p for r in groups[n]] for p in parts)


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
    include_common: bool = False,
    unified: bool = False,
    seed: int = 42,
    group_col: str = 'signer_id',
    fail_on_missing_eval: bool | None = None,
    exclude_unresolved_signers: bool = False,
    min_samples_per_class: int = DEFAULT_MIN_SAMPLES_PER_CLASS,
    min_classes: int = DEFAULT_MIN_CLASSES,
):
    """Profile-filtered split over an immutable dataset manifest.

    Returns (train, val, test, report). Raises SystemExit on hard failures
    (empty subset, empty train/val/test, class with no train coverage, signer
    leakage or unresolved signer_id in strict mode).

    fail_on_missing_eval defaults to True in strict_signer_disjoint mode: a
    split whose val/test cannot evaluate the label space is worthless for
    research, and silently writing one is how hoa_de_signer_disjoint_v1/_v3
    ended up on disk with val=0/test=0. Pass False explicitly (CLI:
    --allow_invalid_split) only for debugging; the report is then stamped
    valid_for_research=false.
    """
    if fail_on_missing_eval is None:
        fail_on_missing_eval = (split_mode == 'strict_signer_disjoint')
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
    # Sàn số mẫu, áp NGAY SAU khi có label_key và TRƯỚC khi đánh chỉ số: đánh số
    # trước rồi loại sau sẽ để lại lỗ trong dãy.
    #
    # ĐÍNH CHÍNH cho bản trước của chú thích này: trainer KHÔNG lấy số lớp bằng
    # `max(class_idx)`. `_build_subset_label_maps` (train_tcn.py) tự dựng
    # `label_to_index` bằng `enumerate(unique_keys)` với `unique_keys` gom theo
    # THỨ TỰ HÀNG XUẤT HIỆN trong CSV. Điều đó nguy hơn cái tôi đã tưởng: lớp 0
    # của mô hình là "nhãn nào nằm ở dòng đầu", nên cùng một tập lớp mà thứ tự
    # hàng khác nhau sẽ cho ánh xạ nhãn khác nhau — và không có gì hiện nay ghim
    # nó lại. Đó là lý do `class_mapping_hash` phải tồn tại, không chỉ
    # `class_set_hash`.
    rows, excluded_below_floor = filter_classes_below_floor(
        rows, min_samples_per_class, key_fn=lambda r: r.get('label_key') or '')
    _report_floor(min_samples_per_class, excluded_below_floor,
                  len({r['label_key'] for r in rows}))
    if not rows:
        raise SystemExit(
            f"Sàn {min_samples_per_class} mẫu/lớp loại hết mọi lớp của tập con này "
            f"— không còn gì để chia.")

    unique_keys = sorted({r['label_key'] for r in rows})
    enforce_min_classes(unique_keys, min_classes,
                        ten_tap=(recognition_profile or 'tập con này'),
                        da_loai=excluded_below_floor)

    # `class_idx` giữ nguyên quy ước 1-based đã có, vì các split đã versioned
    # trên đĩa được ghi bằng nó và chúng là hiện vật BẤT BIẾN. `target_idx` là
    # trường mới, 0-based liên tục, và là thứ tầng đầu ra nên dùng. Xem
    # `assign_target_indices` để biết vì sao hai trường chứ không một.
    key_to_idx = {k: i + 1 for i, k in enumerate(unique_keys)}
    target_idx = assign_target_indices(unique_keys)
    sample_counts = Counter(r['label_key'] for r in rows)
    for r in rows:
        r['class_idx'] = str(key_to_idx[r['label_key']])
        r['target_idx'] = str(target_idx[r['label_key']])

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
        # Exact first: the greedy below optimises sample counts only and will
        # empty a split rather than lose count accuracy. Falls back to it when
        # there are too many groups to enumerate or no valid partition exists.
        exact = _exact_group_partition(rows, group_col)
        if exact is not None:
            train, val, test = exact
            print(f"[split] exact {group_col}-disjoint partition found "
                  f"({len({(r.get(group_col) or '').strip() for r in rows})} groups)")
        else:
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

    # 4. Split-validity gate.
    #
    # A degenerate split is the dangerous failure mode here: with too few
    # signers the greedy group assignment puts EVERY signer in train, leaving
    # val/test empty. _assert_signer_disjoint then passes vacuously (the empty
    # set is disjoint from everything) and, before this gate existed, the
    # split version was still written to disk and looked successful. Both
    # hoa_de_signer_disjoint_v1 and _v3 were produced that way (val=0, test=0).
    #
    # Empty val/test / missing train coverage are therefore HARD failures in
    # strict mode. They can only be downgraded to warnings via the explicit
    # compatibility flag, and the resulting artifact is permanently stamped
    # valid_for_research=false so no aggregator can pick it up.
    def _classes(rows_):
        return {r['label_key'] for r in rows_}
    all_c, tr_c, va_c, te_c = _classes(rows), _classes(train), _classes(val), _classes(test)

    invalid_reasons: list = []
    if not train:
        invalid_reasons.append('train split is empty')
    if not val:
        invalid_reasons.append('validation split is empty')
    if not test:
        invalid_reasons.append('test split is empty')

    missing_train = sorted(all_c - tr_c)
    if missing_train:
        invalid_reasons.append(
            f'{len(missing_train)} class(es) have no TRAIN sample: {missing_train[:5]}')
    missing_val = sorted(all_c - va_c)
    missing_test = sorted(all_c - te_c)
    if missing_val:
        invalid_reasons.append(
            f'{len(missing_val)} class(es) missing from val: {missing_val[:5]}')
    if missing_test:
        invalid_reasons.append(
            f'{len(missing_test)} class(es) missing from test: {missing_test[:5]}')

    if split_mode == 'strict_signer_disjoint':
        overlap = (train_s & val_s) | (train_s & test_s) | (val_s & test_s)
        if overlap:
            invalid_reasons.append(f'signer overlap between splits: {sorted(overlap)}')
        for name, sset in (('train', train_s), ('val', val_s), ('test', test_s)):
            if not sset:
                invalid_reasons.append(f'{name} split has no signer assigned')

    valid_for_research = not invalid_reasons
    if invalid_reasons:
        detail = '\n  - '.join(invalid_reasons)
        if fail_on_missing_eval:
            raise SystemExit(
                f"Split is not usable for research:\n  - {detail}\n"
                f"Refusing to write a split version that cannot be evaluated. "
                f"With {len(train_s | val_s | test_s)} signer(s) available, strict "
                f"signer-disjoint splitting needs more signer coverage (>= 3 signers "
                f"per class). Pass --allow_invalid_split ONLY for debugging: the "
                f"artifact will be stamped valid_for_research=false.")
        print(f"[WARN] split is NOT valid for research:\n  - {detail}")
        print("[WARN] --allow_invalid_split was given; artifact will be stamped "
              "valid_for_research=false and MUST NOT be used for paper results.")

    signer_counts = {
        'train': len(train_s), 'val': len(val_s), 'test': len(test_s),
        'total_distinct': len(train_s | val_s | test_s),
    }

    report = {
        'split_mode': split_mode,
        'recognition_profile': recognition_profile or ('unified' if unified else 'all'),
        'include_common': include_common,
        'seed': seed,
        'group_col': group_col,
        'valid_for_research': valid_for_research,
        'invalid_reasons': invalid_reasons,
        'num_classes': len(unique_keys),
        'label_keys': unique_keys,
        'class_set_hash': class_set_checksum(unique_keys),
        'class_mapping_hash': class_mapping_checksum(target_idx.items()),
        'policy': {
            'min_samples_per_class': int(min_samples_per_class),
            'min_classes': int(min_classes),
        },
        'classes': [
            {'class_uid': k, 'class_idx': key_to_idx[k], 'target_idx': target_idx[k],
             'sample_count_before_split': int(sample_counts.get(k, 0))}
            for k in unique_keys
        ],
        'excluded_below_floor': excluded_below_floor,
        # Tên cũ, giữ cho bản đọc trước đó không vỡ.
        'class_set_checksum': class_set_checksum(unique_keys),
        'min_samples_per_class': int(min_samples_per_class),
        'counts': {'train': len(train), 'val': len(val), 'test': len(test)},
        'sample_counts': {'train': len(train), 'val': len(val), 'test': len(test),
                          'total': len(rows)},
        'signers': {'train': sorted(train_s), 'val': sorted(val_s), 'test': sorted(test_s)},
        'signer_counts': signer_counts,
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
        # --allow_invalid_split is the ONLY way to downgrade the validity gate
        # to a warning; otherwise strict mode defaults to failing hard.
        fail_on_missing_eval=(False if args.allow_invalid_split
                              else (True if args.fail_on_missing_eval else None)),
        exclude_unresolved_signers=args.exclude_unresolved_signers,
        min_samples_per_class=args.min_samples_per_class,
        min_classes=args.min_classes,
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
    if report.get('valid_for_research'):
        print("  valid_for_research: TRUE")
    else:
        print("  valid_for_research: FALSE — this split MUST NOT be used for paper "
              "results; the aggregator will refuse runs trained on it.")
        for reason in report.get('invalid_reasons', []):
            print(f"    - {reason}")


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
    parser.add_argument('--include_common', dest='include_common', action='store_true', default=False,
                        help='EXPLICITLY include common vocabulary in the profile subset '
                             '(default false — profiles train independently)')
    parser.add_argument('--no_include_common', dest='include_common', action='store_false',
                        help='[compatibility no-op — default is already false]')
    parser.add_argument('--unified', action='store_true',
                        help='Unified baseline: common + every validly-assigned profile')
    parser.add_argument('--output_version', type=str, default='',
                        help='Version name for the split (written under processed/splits/versions/<name>/)')
    parser.add_argument('--fail_on_missing_eval', action='store_true',
                        help='Fail when a class has no val/test sample. Already the '
                             'DEFAULT in strict_signer_disjoint mode; use this to opt in '
                             'for sample mode too.')
    parser.add_argument('--allow_invalid_split', action='store_true',
                        help='COMPATIBILITY/DEBUG ONLY. Downgrade the split-validity gate '
                             '(empty train/val/test, missing class coverage, signer overlap) '
                             'from an error to a warning and write the split anyway. The '
                             'artifact is stamped valid_for_research=false and is rejected '
                             'by aggregate_experiment_results.py.')
    parser.add_argument('--exclude_unresolved_signers', action='store_true',
                        help='Explicitly drop samples whose signer_id is unresolved '
                             '(otherwise strict mode fails). Exclusions are recorded in split_metadata.json')
    parser.add_argument('--min_samples_per_class', type=int,
                        default=DEFAULT_MIN_SAMPLES_PER_CLASS,
                        help='Loại HẲN khỏi split những lớp có ít hơn N mẫu (0 = tắt). '
                             'Đặt bằng MIN_SAMPLES_PER_CLASS_FOR_TRAINING của backend '
                             '(mặc định 25 ≈ 5 lần quay) để split khớp với cổng huấn '
                             'luyện; lệch nhau thì backend từ chối lượt chạy và yêu '
                             'cầu chia lại.')
    parser.add_argument('--operational_split_id', type=str, default='',
                        help='Dựng HIỆN VẬT VẬN HÀNH bất biến tại '
                             'processed/splits/operational/<ID>/ thay vì ghi đè ba '
                             'tệp nghiên cứu đóng băng ở gốc. Chỉ-tạo-mới: thư mục '
                             'đã tồn tại thì DỪNG. Không có khái niệm "split mới '
                             'nhất" — một lượt chạy ghim đúng một ID.')
    parser.add_argument('--tenant_id', type=str, default='',
                        help='Tổ chức SỞ HỮU hiện vật vận hành. BẮT BUỘC cùng '
                             '--operational_split_id. Giá trị này đến từ ngữ '
                             'cảnh tạo split và được ghim vào bản khai; nó '
                             'KHÔNG suy ra được về sau từ lượt huấn luyện đầu '
                             'tiên muốn dùng hiện vật, vì như vậy là ai hỏi '
                             'trước thì thành chủ. Không có mặc định.')
    parser.add_argument('--min_classes', type=int, default=DEFAULT_MIN_CLASSES,
                        help=f'Số lớp tối thiểu SAU khi lọc; dưới ngưỡng thì DỪNG và '
                             f'không ghi split (mặc định {DEFAULT_MIN_CLASSES}, 0 = tắt). '
                             f'Cổng này nằm trong chính CLI vì make_splits chạy được '
                             f'ngoài API — một cổng chỉ bảo vệ đường đi qua nó.')
    parser.add_argument('--dialects', type=str, default='',
                        help='Chỉ giữ các phương ngữ này (phân tách bằng dấu '
                             'phẩy), áp TRƯỚC sàn số mẫu. Bắt buộc khi dựng '
                             'hiện vật vận hành cho một phương ngữ: bản khai '
                             'của hiện vật phải chứa ĐÚNG tập lớp mà trainer '
                             'sẽ đọc, vì `num_classes` lấy thẳng từ bản khai.')
    parser.add_argument('--by_language', action='store_true', help='Write separate split CSVs per language under splits/<language>/')
    parser.add_argument('--languages', type=str, default='', help='Optional comma-separated whitelist of languages when using --by_language')
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()

    # ★ C2b — cổng này đứng TRƯỚC mọi lượt ghi, và vị trí của nó là nội dung.
    #
    # `write_legacy_snapshot` cũng từ chối hiện vật không chủ, nhưng nó chạy SAU
    # khi ba tệp CSV đã nằm trên đĩa: đỏ ở đó để lại một thư mục có ba CSV và
    # không có bản khai — một hiện vật nửa chừng, mà quy tắc chỉ-tạo-mới lại
    # khiến không ai ghi đè lên nó được nữa. Chặn ở đây thì không byte nào được
    # ghi. Cổng kia là lưới thứ hai, cho người gọi hàm trực tiếp.
    if args.operational_split_id and not str(args.tenant_id or '').strip():
        raise SystemExit(
            'Hiện vật vận hành phải có chủ: thiếu --tenant_id.\n'
            'Chủ sở hữu đến từ ngữ cảnh tạo split. Không tìm được ngữ cảnh thì '
            'DỪNG — không dùng tenant khởi tạo, không dùng tenant của lượt '
            'huấn luyện sẽ tiêu thụ nó.')
    if str(args.tenant_id or '').strip() and not args.operational_split_id:
        raise SystemExit(
            '--tenant_id chỉ dùng với --operational_split_id. Bản khai ở gốc '
            'processed/splits/ không phải hiện vật có địa chỉ nên không mang '
            'được quyền sở hữu, và ghi một trường không ai cưỡng chế vào đó chỉ '
            'tạo cảm giác an toàn giả.')

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

    global RANDOM_SEED, OUT_DIR
    RANDOM_SEED = args.seed
    if args.operational_split_id:
        # KHÔNG đụng ba tệp ở gốc. Bất biến, chỉ-tạo-mới: ghi đè một hiện
        # vật đã có sẽ làm mọi checkpoint trỏ vào nó nói sai nguồn gốc,
        # trong khi split_id trong checkpoint vẫn trông hợp lệ.
        OUT_DIR = OUT_DIR / 'operational' / args.operational_split_id
        if OUT_DIR.exists() and any(OUT_DIR.iterdir()):
            raise SystemExit(
                f'Hiện vật vận hành đã tồn tại: {OUT_DIR}. Hiện vật là BẤT '
                f'BIẾN — chọn --operational_split_id khác, đừng ghi đè.')
        # KHÔNG tạo thư mục ở đây — xem `write_split`.
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
    if 'region' not in fieldnames:
        fieldnames = fieldnames + ['region']
    enriched = []
    for r in rows:
        try:
            idx = int(r['class_idx'])
        except Exception:
            idx = None
        meta = lookup.get(idx, {'slug': '', 'label_original': '', 'language': 'vn',
                                'dialect': '', 'region': ''})
        r = dict(r)
        r['label_slug'] = meta['slug']
        r['label_original'] = meta['label_original']
        language = (meta.get('language') or 'vn').strip()
        dialect = (meta.get('dialect') or '').strip()
        slug = (meta.get('slug') or '').strip()
        r['language'] = language
        r['dialect'] = dialect
        r['region'] = (meta.get('region') or '').strip()
        r['label_key'] = f"{language}/{dialect}/{slug}" if dialect else f"{language}/{slug}"
        enriched.append(r)
    rows = enriched

    # Bộ lọc phương ngữ, áp TRƯỚC sàn — và thứ tự đó là bắt buộc.
    #
    # Trainer nhận `--dialect` và tự lọc lại lúc chạy, nên thoạt nhìn lọc ở đây
    # là thừa. Không thừa: `consume_declared` lấy `num_classes` từ mục `classes`
    # của bản khai, còn `partitions_agree` chỉ từ chối class_uid LẠ chứ không
    # đòi mọi lớp đã khai phải có mặt. Một hiện vật khai 60 lớp mà trainer chỉ
    # đọc 7 sẽ dựng tầng đầu ra 60 chiều với 53 chiều không bao giờ thấy một
    # mẫu nào — chạy trót lọt, không cảnh báo, và checkpoint nói dối về tập lớp
    # nó đã học.
    #
    # Áp trước sàn vì sàn phải tính trên đúng tập con: `can-tho` có 1 lớp đạt
    # trên 9, nhưng nếu sàn chạy trên toàn bộ 60 lớp rồi mới cắt phương ngữ thì
    # `enforce_min_classes` đếm 41 lớp và cho qua.
    pn_muon = [x.strip() for x in str(args.dialects or '').split(',') if x.strip()]
    if pn_muon:
        co_that = sorted({(r.get('dialect') or '').strip() for r in rows
                          if (r.get('dialect') or '').strip()})
        khong_co = [d for d in pn_muon if d not in co_that]
        if khong_co:
            raise SystemExit(
                f"Không có phương ngữ {khong_co} trong dữ liệu. "
                f"Hiện có: {co_that}. Gõ sai tên phương ngữ mà vẫn chạy tiếp sẽ "
                f"cho ra một hiện vật rỗng hoặc một tập con ngoài ý muốn.")
        rows = [r for r in rows if (r.get('dialect') or '').strip() in pn_muon]
        print(f"[scope] dialects={pn_muon}: giữ {len(rows)} mẫu, "
              f"{len({_class_key(r) for r in rows if _class_key(r)})} lớp.")

    # Sàn số mẫu, áp TRƯỚC khi chia. Sau khi chia là quá muộn: tỉ lệ 70/15/15
    # tính trên từng lớp, nên loại một lớp sau đó sẽ làm ba tập lệch tỉ lệ.
    truoc = len({_class_key(r) for r in rows if _class_key(r)})
    rows, da_loai = filter_classes_below_floor(rows, args.min_samples_per_class)
    tap_lop = sorted({_class_key(r) for r in rows if _class_key(r)})
    _report_floor(args.min_samples_per_class, da_loai, len(tap_lop))
    enforce_min_classes(tap_lop, args.min_classes,
                        ten_tap=('+'.join(pn_muon) if pn_muon else ''),
                        so_ung_vien=truoc, da_loai=da_loai)

    # Số mẫu TRƯỚC khi chia, và `target_idx` gắn vào từng hàng. Gắn ở đây —
    # trước khi chia — nên cả ba tệp mang cùng một ánh xạ; tính lại ở mỗi tệp
    # là ba cơ hội để chúng lệch nhau.
    dem_mau = Counter(_class_key(r) for r in rows if _class_key(r))
    # Nhãn ĐỌC cho từng lớp, gom từ chính các hàng sẽ được ghi ra. Lấy ở đây
    # thay vì tra `labels.csv` lúc nạp checkpoint, vì từ vựng đổi được sau khi
    # huấn luyện xong và không có gì báo — đúng lỗi thứ ba đã tìm ra 14/08.
    mo_ta_lop: dict = {}
    for r in rows:
        k = _class_key(r)
        if not k or k in mo_ta_lop:
            continue
        mo_ta_lop[k] = {
            'class_idx': (r.get('class_idx') or '').strip(),
            'slug': (r.get('label_slug') or r.get('slug') or '').strip(),
            'label_original': (r.get('label_original') or '').strip(),
            'language': (r.get('language') or '').strip(),
            'dialect': (r.get('dialect') or '').strip(),
            'region': (r.get('region') or '').strip(),
        }
    anh_xa = assign_target_indices(tap_lop)
    for r in rows:
        k = _class_key(r)
        if k in anh_xa:
            r['target_idx'] = str(anh_xa[k])
    if 'target_idx' not in fieldnames:
        fieldnames = fieldnames + ['target_idx']

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
        snap = write_legacy_snapshot(
            OUT_DIR, class_keys=tap_lop, floor=args.min_samples_per_class,
            excluded=da_loai, mode=_active_mode(), seed=RANDOM_SEED,
            counts={'train': len(train), 'val': len(val), 'test': len(test)},
            min_classes=args.min_classes, sample_counts=dem_mau,
            class_meta=mo_ta_lop,
            split_id=args.operational_split_id or None,
            tenant_id=args.tenant_id or None,
            # Phạm vi phải nằm TRONG hiện vật: đọc lại sau ba tháng, "7 lớp"
            # một mình không nói được đây là 7 lớp của hoa-de hay 7 lớp còn
            # sót của toàn bộ từ vựng.
            extra={'scope': {'dialects': pn_muon}} if pn_muon else None,
        )
        print('Split summary:')
        for k, v in summary.items():
            print(k, v)
        for k, p in paths.items():
            print(f'{k} file -> {p}')
        print(f'class-set snapshot -> {snap}')
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
        lop_l = sorted({_class_key(r) for r in rows_l if _class_key(r)})
        enforce_min_classes(lop_l, args.min_classes, ten_tap=f"ngôn ngữ {lang}",
                            so_ung_vien=len(lop_l), da_loai=da_loai)
        write_legacy_snapshot(
            out_dir, class_keys=lop_l, floor=args.min_samples_per_class,
            min_classes=args.min_classes,
            sample_counts=Counter(_class_key(r) for r in rows_l if _class_key(r)),
            # `da_loai` là danh sách toàn cục: sàn đã áp trước khi tách ngôn
            # ngữ, nên một lớp bị loại thuộc về đúng một ngôn ngữ và lọc lại
            # theo ngôn ngữ ở đây sẽ cần tra ngược thông tin đã bỏ. Ghi cả danh
            # sách và nói rõ phạm vi còn thật thà hơn là ghi một tập con đoán mò.
            excluded=da_loai, mode=_active_mode(), seed=RANDOM_SEED,
            counts={'train': len(train), 'val': len(val), 'test': len(test)},
            extra={'language': lang, 'excluded_scope': 'toàn bộ split, mọi ngôn ngữ'},
        )
        manifest['languages'][lang] = {
            'total_rows': len(rows_l),
            'paths': {k: str(p) for k, p in paths.items()},
            'summary': summary,
            'class_set_hash': class_set_checksum(lop_l),
            'class_mapping_hash': class_mapping_checksum(
                assign_target_indices(lop_l).items()),
            'num_classes': len(lop_l),
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


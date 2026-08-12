"""Sinh cac fold leave-one-performer-out (giu nguoi ky ra ngoai) tu mot manifest mau.

Vi sao can script nay: make_splits.py chia theo signer nhung chia NGAU NHIEN —
no khong chi dinh duoc "lan nay giu H03 ra lam test". Bai bao lai danh gia theo
tung nguoi: moi nguoi du dieu kien tro thanh mot fold, va nguoi do phai vang mat
o CA train LAN val, khong chi vang mat o test:

    P_train ∩ P_test = P_val ∩ P_test = ∅        (Eq. performer_disjoint)

Rang buoc do ap len TAP NGUOI, khong phai tap mau. Chia theo mau van co the cho
cung mot nguoi nam o hai phia — do dung la ket qua ma bai bao dem ra do.

Hai giao thuc:

  protocol A (mac dinh)  test = toan bo mau cua nguoi muc tieu; train/val lay tu
                         nhung nguoi con lai. Day la bang "held-out-performer".

  matched                test = mot nua mau cua nguoi muc tieu, can bang lop, CO
                         DINH cho ca hai dieu kien. A giu nguoi muc tieu ngoai
                         train/val; B day mau tu nua con lai (roi khoi test) vao
                         train va val, DOI CHO mau cung lop cua nguoi khac nen
                         kich thuoc train va so mau moi lop khong doi. Chenh lech
                         doc duoc khi do la do phoi nhiem nguoi ky, khong phai do
                         train nhieu du lieu hon.

Ten that cua nguoi ky KHONG bao gio di vao CSV: script thay bang but danh
(H01, H02, ...) va ghi anh xa ra performer_map.json rieng, de artifact chia se
duoc ma khong lo danh tinh.

Dung:
    python scripts/make_loso_splits.py --manifest dataset/samples.csv \
        --dialect hoa-de --out_dir processed/splits/loso/hoa_de
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Giu nguyen thu tu cot cua cac split CSV cu — dataset_loader doc folder_name/file
# de dung lai duong dan .npz, con lai la provenance.
COLUMNS = [
    'sample_uid', 'class_uid', 'slug', 'label_original', 'language', 'dialect',
    'source_type', 'user_id', 'session_id', 'fps_original', 'fps_processed',
    'seq_len', 'augment_id', 'completeness', 'file_path', 'storage_key',
    'storage_url', 'checksum', 'created_at', 'folder_name', 'file',
    'sample_id', 'class_idx', 'label_slug', 'label_key',
]


def npz_basename(row: dict) -> str:
    for col in ('file', 'storage_key', 'file_path'):
        v = (row.get(col) or '').strip()
        if v.endswith('.npz'):
            return v.rsplit('/', 1)[-1]
    return ''


def index_features(features_root: Path) -> dict[str, Path]:
    return {p.name: p for p in features_root.rglob('*.npz')}


def norm_name(name: str, fold_case: bool) -> str:
    """Chuan hoa nhe: NFC + bo khoang trang thua. Chi ha chu khi duoc yeu cau —
    'Tran' va 'Trân' co the la hai nguoi, script khong tu quyet dinh ho la mot."""
    n = unicodedata.normalize('NFC', (name or '').strip())
    return n.casefold() if fold_case else n


def load_rows(manifest: Path, dialect: str, profile: str, features: dict[str, Path],
              alias: dict[str, str], fold_case: bool) -> tuple[list[dict], dict]:
    with manifest.open(encoding='utf-8', errors='ignore') as f:
        raw = list(csv.DictReader(f))

    stats = {'manifest_rows': len(raw)}
    rows = [r for r in raw if not (r.get('deleted_at') or '').strip()]
    stats['after_deleted_filter'] = len(rows)

    if dialect:
        rows = [r for r in rows if (r.get('dialect') or '').strip() == dialect]
    if profile:
        rows = [r for r in rows if (r.get('recognition_profile') or '').strip() == profile]
    stats['after_profile_filter'] = len(rows)

    kept, missing = [], 0
    for r in rows:
        base = npz_basename(r)
        path = features.get(base)
        if path is None:
            missing += 1
            continue
        raw_name = (r.get('user_id') or '').strip()
        name = norm_name(raw_name, fold_case)
        r['_performer'] = alias.get(name, name)
        r['_npz'] = path
        r['_class'] = (r.get('slug') or r.get('label_slug') or '').strip()
        kept.append(r)
    stats['dropped_no_npz'] = missing
    stats['resolved'] = len(kept)
    return kept, stats


def select_classes_and_performers(rows, min_samples, min_class_performers, log):
    """Chon dong thoi tap lop va tap nguoi du dieu kien.

    Bai bao doi "phu het lop" moi duoc lam fold. Nhung dieu kien do phu thuoc vao
    tap lop, ma tap lop lai phu thuoc vao ai duoc tinh — vong tron. Cach go: bo
    dan lop nao dang chan nhieu nguoi nhat, cho den khi con it nhat 2 nguoi phu
    het. Moi buoc deu duoc ghi lai de nguoi doc kiem tra duoc, thay vi bien mat
    trong mot con so cuoi cung.
    """
    counts = Counter(r['_performer'] for r in rows)
    candidates = {p for p, n in counts.items() if n >= min_samples and p}
    for p, n in sorted(counts.items(), key=lambda x: -x[1]):
        if p not in candidates:
            log.append(f'performer {p!r} excluded: {n} samples < --min_samples {min_samples}')

    rows = [r for r in rows if r['_performer'] in candidates]
    cov = defaultdict(set)
    for r in rows:
        cov[r['_performer']].add(r['_class'])

    classes = set(r['_class'] for r in rows)
    # lop chi mot nguoi dong gop thi khong the danh gia held-out — bo truoc
    per_class = defaultdict(set)
    for r in rows:
        per_class[r['_class']].add(r['_performer'])
    for c in sorted(classes):
        if len(per_class[c]) < min_class_performers:
            log.append(f'class {c!r} dropped: only {len(per_class[c])} performer(s) '
                       f'< --min_class_performers {min_class_performers}')
    classes = {c for c in classes if len(per_class[c]) >= min_class_performers}

    while True:
        eligible = {p for p in candidates if classes <= cov[p]}
        if len(eligible) >= 2 or not classes:
            break
        blocked = Counter()
        for p in candidates:
            for c in classes - cov[p]:
                blocked[c] += 1
        worst, n = blocked.most_common(1)[0]
        log.append(f'class {worst!r} dropped: blocks {n} otherwise-complete performer(s)')
        classes.discard(worst)

    rows = [r for r in rows if r['_class'] in classes]
    return rows, sorted(classes), sorted(eligible)


def assign_pseudonyms(rows, eligible, prefix, order):
    if order:
        ordered = [p for p in order if p in eligible]
        ordered += [p for p in eligible if p not in ordered]
    else:
        first_seen = {}
        for r in rows:
            first_seen.setdefault(r['_performer'], r.get('created_at') or '')
        ordered = sorted(eligible, key=lambda p: (first_seen.get(p, ''), p))
    mapping = {p: f'{prefix}{i:02d}' for i, p in enumerate(ordered, 1)}
    # nguoi khong du dieu kien nhung con trong pool van can but danh
    others = sorted({r['_performer'] for r in rows} - set(mapping))
    for i, p in enumerate(others, 1):
        mapping[p] = f'{prefix}X{i:02d}'
    return mapping


def to_out_row(r: dict, class_idx: dict[str, int], pseudo: dict[str, str]) -> dict:
    key = (r.get('storage_key') or '').strip()
    parts = key.split('/')
    folder = parts[-2] if len(parts) >= 2 else ''
    fname = parts[-1] if parts else ''
    if not fname.endswith('.npz'):
        fname = r['_npz'].name
        folder = r['_npz'].parent.name
    lang = (r.get('language') or 'vn').strip() or 'vn'
    dial = (r.get('dialect') or '').strip()
    out = {c: (r.get(c) or '') for c in COLUMNS}
    out.update({
        'language': lang,
        'dialect': dial,
        'user_id': pseudo[r['_performer']],
        'file_path': '',            # de trong: loader se dung folder_name + file
        'folder_name': folder,
        'file': fname,
        'sample_id': (r.get('sample_uid') or '').strip(),
        'class_idx': str(class_idx[r['_class']]),
        'label_slug': r['_class'],
        'label_key': f'{lang}/{dial}/{r["_class"]}' if dial else f'{lang}/{r["_class"]}',
    })
    return out


def stratified_val(pool: list[dict], val_ratio: float, seed: int):
    """Tach val khoi pool, giu ti le lop. Moi lop bao dam it nhat 1 mau val neu
    con du 2 mau — val rong o mot lop nghia la checkpoint chon mu o lop do."""
    rng = random.Random(seed)
    by_class = defaultdict(list)
    for r in pool:
        by_class[r['_class']].append(r)
    train, val = [], []
    for c in sorted(by_class):
        items = sorted(by_class[c], key=lambda r: r.get('sample_uid') or '')
        rng.shuffle(items)
        k = max(1, round(len(items) * val_ratio)) if len(items) >= 2 else 0
        val += items[:k]
        train += items[k:]
    return train, val


def balanced_test_half(target_rows, seed, ratio=0.5):
    """Nua mau cua nguoi muc tieu lam test co dinh, can bang lop."""
    rng = random.Random(seed)
    by_class = defaultdict(list)
    for r in target_rows:
        by_class[r['_class']].append(r)
    test, pool = [], []
    for c in sorted(by_class):
        items = sorted(by_class[c], key=lambda r: r.get('sample_uid') or '')
        rng.shuffle(items)
        k = max(1, int(len(items) * ratio))
        test += items[:k]
        pool += items[k:]
    return test, pool


def write_fold(out_dir: Path, name: str, train, val, test, meta: dict,
               class_idx, pseudo, manifest_sha):
    d = out_dir / name
    d.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split, rows_ in (('train', train), ('val', val), ('test', test)):
        with (d / f'{split}.csv').open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=COLUMNS)
            w.writeheader()
            for r in rows_:
                w.writerow(to_out_row(r, class_idx, pseudo))
        counts[split] = len(rows_)

    all_classes = set(class_idx)
    cov = {s: len({r['_class'] for r in rows_}) / max(1, len(all_classes))
           for s, rows_ in (('train', train), ('val', val), ('test', test))}
    perf = {s: sorted({pseudo[r['_performer']] for r in rows_})
            for s, rows_ in (('train', train), ('val', val), ('test', test))}

    reasons = []
    if not train:
        reasons.append('train partition is empty')
    if not val:
        reasons.append('val partition is empty')
    if not test:
        reasons.append('test partition is empty')
    if cov['train'] < 1.0:
        reasons.append(f'train covers only {cov["train"]:.0%} of the label space')
    if cov['test'] == 0:
        reasons.append('test covers no class')
    if meta.get('protocol') == 'A':
        leak = (set(perf['train']) | set(perf['val'])) & set(perf['test'])
        if leak:
            reasons.append(f'performer leakage into development: {sorted(leak)}')

    report = dict(meta)
    report.update({
        'valid_for_research': not reasons,
        'invalid_reasons': reasons,
        'num_classes': len(all_classes),
        'label_keys': sorted(all_classes),
        'counts': counts,
        'sample_counts': dict(counts, total=sum(counts.values())),
        'class_coverage': cov,
        'signers': perf,
        'signer_counts': {s: len(v) for s, v in perf.items()},
        'group_col': 'user_id',
        'dataset_manifest_checksum': manifest_sha,
    })
    (d / 'split_metadata.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--features_root', type=Path, default=REPO / 'dataset' / 'features')
    ap.add_argument('--dialect', type=str, default='')
    ap.add_argument('--recognition_profile', type=str, default='')
    ap.add_argument('--out_dir', type=Path, required=True)
    ap.add_argument('--protocol', choices=['A', 'matched'], default='A')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--val_ratio', type=float, default=0.15)
    ap.add_argument('--min_samples', type=int, default=20,
                    help='nguoi ky duoi nguong nay khong duoc lam fold')
    ap.add_argument('--min_class_performers', type=int, default=2)
    ap.add_argument('--prefix', type=str, default='H')
    ap.add_argument('--performer_order', type=str, default='',
                    help='danh sach ten that, phan cach dau phay, quyet dinh H01..H0N')
    ap.add_argument('--alias', action='append', default=[], metavar='RAW=CANONICAL',
                    help='gop hai ten thu thap ve mot nguoi that (lap lai duoc)')
    ap.add_argument('--fold_case', action='store_true',
                    help='coi "Minh" va "minh" la mot nguoi')
    ap.add_argument('--split_version', type=str, default='')
    ap.add_argument('--expect_classes', type=int, default=0,
                    help='so lop bat buoc phai con lai sau khi chon. Khac la dung '
                         'ngay. Dat bang con so trong bai bao thi mot snapshot du '
                         'lieu thieu nguoi ky khong the am tham cho ra bang khac.')
    # --- cong dong thuan -------------------------------------------------
    #
    # Mac dinh 'research_release' chu khong phai 'internal_training': dau ra cua
    # script nay la artifact cua bai bao, va bang so lieu trong bai la mot hinh
    # thuc cong bo du lieu. Mau khong truy duoc nguoi ky bi loai o day, va do la
    # y dinh — khong chung minh duoc da xin phep ai thi khong dua vao bai.
    ap.add_argument('--consent-scope', default='research_release',
                    choices=['internal_training', 'research_release', 'public_library'])
    ap.add_argument('--consent-snapshot', type=Path,
                    default=REPO / 'dataset' / 'consent_snapshot.json')
    ap.add_argument('--skip-consent-gate', action='store_true',
                    help='Bo qua cong dong thuan. Ghi vao performer_map.json.')
    args = ap.parse_args()

    alias = {}
    for a in args.alias:
        if '=' not in a:
            raise SystemExit(f'--alias phai co dang RAW=CANONICAL, nhan duoc {a!r}')
        k, v = a.split('=', 1)
        alias[norm_name(k, args.fold_case)] = norm_name(v, args.fold_case)

    features = index_features(args.features_root)
    if not features:
        raise SystemExit(f'Khong tim thay .npz nao duoi {args.features_root}')
    print(f'[data] {len(features)} .npz duoi {args.features_root}')

    log: list[str] = []
    rows, stats = load_rows(args.manifest, args.dialect, args.recognition_profile,
                            features, alias, args.fold_case)
    if not rows:
        raise SystemExit('Khong con mau nao sau khi loc — kiem tra --dialect/--recognition_profile.')

    consent_note: dict = {'scope': args.consent_scope}
    if args.skip_consent_gate:
        consent_note.update({'enforced': False, 'reason': '--skip-consent-gate'})
        print('[consent] BI BO QUA theo yeu cau — ghi vao performer_map.json')
    else:
        import sys as _s
        if str(REPO / 'backend') not in _s.path:
            _s.path.insert(0, str(REPO / 'backend'))
        from app.consent_gate import (  # noqa: E402
            SnapshotUnusable, filter_rows, load_snapshot,
        )
        try:
            consents, aliases_map, snap_meta = load_snapshot(args.consent_snapshot)
        except SnapshotUnusable as exc:
            raise SystemExit(
                f'[consent] {exc}\n'
                f'          Neu that su muon chia split KHONG loc thi truyen '
                f'--skip-consent-gate.') from None
        gated = filter_rows(rows, scope=args.consent_scope,
                            consents=consents, aliases=aliases_map)
        print(f'[consent] {gated.summary()}')
        consent_note.update({
            'enforced': True,
            'snapshot_hash': snap_meta.get('content_hash'),
            'kept': len(gated.kept),
            'withheld': len(gated.withheld),
            'withheld_reasons': gated.reasons,
        })
        rows = gated.kept
        stats['after_consent_gate'] = len(rows)
        if not rows:
            raise SystemExit(
                f"[consent] khong con mau nao du dieu kien cho muc "
                f"'{args.consent_scope}'. Day la hanh vi dung khi chua thu dong "
                f"thuan, nhung khong chia split duoc.")
    print(f'[data] manifest {stats["manifest_rows"]} rows -> {stats["resolved"]} resolved '
          f'({stats["dropped_no_npz"]} khong tim thay .npz)')

    classes_before = len({r['_class'] for r in rows})
    performers_before = len({r['_performer'] for r in rows})
    rows, classes, eligible = select_classes_and_performers(
        rows, args.min_samples, args.min_class_performers, log)
    for line in log:
        print(f'[select] {line}')
    print(f'[select] classes {classes_before} -> {len(classes)}, '
          f'performers {performers_before} -> {len(eligible)} eligible')
    if len(eligible) < 2:
        raise SystemExit(f'Chi co {len(eligible)} nguoi du dieu kien — khong lam LOSO duoc.')
    if args.expect_classes and len(classes) != args.expect_classes:
        raise SystemExit(
            f'--expect_classes {args.expect_classes} nhung chon ra {len(classes)} lop '
            f'({", ".join(classes) or "khong con lop nao"}).\n'
            f'Snapshot du lieu nay khong sinh lai duoc bo lop da cong bo. Xem log '
            f'[select] o tren de biet lop nao bi bo va vi ai. Dung --expect_classes 0 '
            f'de chay tren bo lop rut gon, nhung ket qua KHONG so sanh duoc voi bang cu.')

    pseudo = assign_pseudonyms(
        rows, eligible,
        args.prefix,
        [norm_name(x, args.fold_case) for x in args.performer_order.split(',') if x.strip()])
    class_idx = {c: i + 1 for i, c in enumerate(classes)}

    print(f'[select] {len(classes)} classes: {", ".join(classes)}')
    print(f'[select] {len(eligible)} eligible performers: '
          + ', '.join(f'{pseudo[p]}' for p in eligible))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    manifest_sha = hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    version = args.split_version or f'{args.out_dir.name}_protocol{args.protocol}'

    # anh xa danh tinh nam RIENG, khong nam trong CSV
    (args.out_dir / 'performer_map.json').write_text(json.dumps({
        'note': 'Chua ten that. KHONG phat hanh kem artifact.',
        'pseudonym_to_source': {v: k for k, v in pseudo.items()},
        'eligible_folds': [pseudo[p] for p in eligible],
        # Di theo artifact: sau nay doc lai mot bang so lieu, cau hoi "tap nay
        # da qua cong dong thuan chua, o muc nao" phai tra loi duoc tu chinh
        # artifact chu khong phai tu tri nho cua nguoi chay lenh.
        'consent_gate': consent_note,
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    reports = {}
    for p in eligible:
        tag = pseudo[p]
        target = [r for r in rows if r['_performer'] == p]
        others = [r for r in rows if r['_performer'] != p]
        base_meta = {
            'split_mode': 'leave_one_performer_out',
            # Only the real thing, never args.dialect as a stand-in: dialect is
            # a storage directory, recognition_profile decides which model gets
            # trained, and the two are not interchangeable. Writing one into the
            # other put the non-existent profile "spa" on 7 classes. A manifest
            # that leaves this empty is honest; one that guesses describes an
            # experiment that never ran.
            'recognition_profile': args.recognition_profile or '',
            # Trainer can cai nay de dung label map rieng cua fold. Thieu no thi
            # dataset_loader roi ve labels.csv toan cuc va model mo ra 42 lop cho
            # mot fold 7 lop: accuracy van dep, macro-F1 bi 35 lop vang mat keo
            # xuong con mot phan sau.
            'dialect': args.dialect,
            'seed': args.seed,
            'held_out_performer': tag,
            'split_version': version,
            'source_manifest': str(args.manifest),
        }

        if args.protocol == 'A':
            train, val = stratified_val(others, args.val_ratio, args.seed)
            reports[f'test_{tag}'] = write_fold(
                args.out_dir, f'test_{tag}', train, val, target,
                dict(base_meta, protocol='A'), class_idx, pseudo, manifest_sha)
        else:
            test, exposure = balanced_test_half(target, args.seed)
            train_a, val_a = stratified_val(others, args.val_ratio, args.seed)
            reports[f'test_{tag}_A'] = write_fold(
                args.out_dir, f'test_{tag}_A', train_a, val_a, test,
                dict(base_meta, protocol='A', matched_pair=tag),
                class_idx, pseudo, manifest_sha)

            # Protocol B: mau nguoi muc tieu DOI CHO mau cung lop cua nguoi khac,
            # nen |train| va so mau moi lop giu nguyen. Khong doi cho thi chenh
            # lech doc duoc se lan voi "train nhieu du lieu hon".
            rng = random.Random(args.seed + 1)
            ex_by_class = defaultdict(list)
            for r in exposure:
                ex_by_class[r['_class']].append(r)
            for c in ex_by_class:
                ex_by_class[c].sort(key=lambda r: r.get('sample_uid') or '')
                rng.shuffle(ex_by_class[c])

            n_val_add = {c: min(1, len(v)) for c, v in ex_by_class.items()}
            val_add, train_add = [], []
            for c, items in ex_by_class.items():
                k = n_val_add[c]
                val_add += items[:k]
                train_add += items[k:]

            def displace(base, add):
                by_class = defaultdict(list)
                for r in base:
                    by_class[r['_class']].append(r)
                for c in by_class:
                    by_class[c].sort(key=lambda r: r.get('sample_uid') or '')
                    rng.shuffle(by_class[c])
                need = Counter(r['_class'] for r in add)
                kept = []
                for c, items in by_class.items():
                    drop = min(need.get(c, 0), max(0, len(items) - 1))
                    kept += items[drop:]
                return kept + add

            train_b = displace(train_a, train_add)
            val_b = displace(val_a, val_add)
            reports[f'test_{tag}_B'] = write_fold(
                args.out_dir, f'test_{tag}_B', train_b, val_b, test,
                dict(base_meta, protocol='B', matched_pair=tag),
                class_idx, pseudo, manifest_sha)

    summary = {
        'split_version': version,
        'protocol': args.protocol,
        'classes': classes,
        'folds': {k: {'counts': v['counts'], 'valid_for_research': v['valid_for_research'],
                      'invalid_reasons': v['invalid_reasons']}
                  for k, v in reports.items()},
        'selection_log': log,
        'stats': stats,
        'dataset_manifest_checksum': manifest_sha,
    }
    (args.out_dir / 'loso_summary.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    print()
    bad = 0
    for name in sorted(reports):
        r = reports[name]
        ok = 'OK ' if r['valid_for_research'] else 'BAD'
        bad += 0 if r['valid_for_research'] else 1
        print(f'  [{ok}] {name:16s} train={r["counts"]["train"]:4d} '
              f'val={r["counts"]["val"]:3d} test={r["counts"]["test"]:4d}  '
              f'dev_performers={r["signer_counts"]["train"]}')
        for why in r['invalid_reasons']:
            print(f'         ! {why}')
    print(f'\n-> {args.out_dir}  ({len(reports)} fold, {bad} khong hop le)')
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())

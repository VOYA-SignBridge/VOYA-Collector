from __future__ import annotations

import argparse
import numpy as np
import sys
from pathlib import Path
from typing import List

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.modules.dataset.balancing import build_balance_plan
from app.modules.dataset.catalog import ClassMetadata, load_labels
from app.tenancy import tenant_id_of
from app.modules.dataset.samples import save_sequence_npz
from app.processing.augmenter import generate_augmented_sequences

def get_class_dirs(tenant_id: str) -> dict[str, Path]:
    # Công cụ này SINH mẫu tăng cường rồi ghi xuống cây dữ liệu. Đường ghi
    # bám theo chủ sở hữu của lớp, nên đọc toàn kho ở đây sẽ đổ mẫu mới vào
    # cây của tổ chức khởi tạo — xem chú thích ở `balancer.load_class_meta_map`.
    rows = load_labels(tenant_id)
    out = {}
    for r in rows:
        meta = ClassMetadata(
            class_uid=r['class_uid'], slug=r['slug'], label_original=r['label_original'],
            language=r['language'], dialect=r['dialect'],
            is_common_global=bool(int(r['is_common_global'])),
            is_common_language=bool(int(r['is_common_language'])),
            tenant_id=tenant_id_of(r),
        )
        out[meta.class_uid] = meta.hierarchy_path()
    return out

def load_sequences_for_class(class_uid: str, limit: int | None = None) -> List[np.ndarray]:
    dirs = get_class_dirs()
    path = dirs.get(class_uid)
    if not path or not path.exists():
        return []
    seqs = []
    for f in path.glob('*.npz'):
        try:
            with np.load(f, allow_pickle=True) as data:
                seq = data.get('sequence')
                if seq is not None and seq.ndim == 2:
                    seqs.append(seq.astype(np.float32))
        except Exception:
            continue
        if limit and len(seqs) >= limit:
            break
    return seqs

def execute(tenant_id: str, target: int | None = None,
            per_sequence_aug: int = 2):
    plan = build_balance_plan(tenant_id, target=target)
    dirs = get_class_dirs(tenant_id)
    rows = load_labels(tenant_id)
    uid_to_meta = {r['class_uid']: ClassMetadata(
        class_uid=r['class_uid'], slug=r['slug'], label_original=r['label_original'],
        language=r['language'], dialect=r['dialect'],
        is_common_global=bool(int(r['is_common_global'])),
        is_common_language=bool(int(r['is_common_language'])),
        tenant_id=tenant_id_of(r),
    ) for r in rows}
    performed = []
    for item in plan.get('plan', []):
        cid = item['class_uid']
        deficit = item['deficit']
        meta = uid_to_meta.get(cid)
        if not meta:
            continue
        existing = load_sequences_for_class(cid)
        if not existing:
            continue
        # cycle through existing sequences
        idx = 0
        created = 0
        while created < deficit:
            base_seq = existing[idx % len(existing)]
            aug_list = generate_augmented_sequences(base_seq, config={'n': per_sequence_aug})
            for i, aseq in enumerate(aug_list):
                if created >= deficit:
                    break
                save_sequence_npz(meta, aseq, meta={'oversampled': True}, augment_id=i, source_type='oversample')
                created += 1
            idx += 1
        performed.append({'class_uid': cid, 'added': created})
    return {'performed': performed}

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Lập kế hoạch hoặc tạo mẫu augment để cân bằng class."
    )
    parser.add_argument("--target", type=int, default=None, help="Số mẫu mục tiêu cho mỗi class")
    parser.add_argument("--per-sequence-aug", type=int, default=2)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Thực sự tạo file NPZ; mặc định chỉ in kế hoạch",
    )
    args = parser.parse_args()

    if not args.apply:
        print({"dry_run": True, **build_balance_plan(target=args.target)})
        return
    print(execute(target=args.target, per_sequence_aug=args.per_sequence_aug))


if __name__ == '__main__':
    main()

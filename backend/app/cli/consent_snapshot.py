"""Xuất trạng thái đồng thuận của người ký ra một tệp mà script offline đọc được.

Chạy TRONG container (chỗ duy nhất nối được Postgres):

    docker exec voya_backend python -m app.cli.consent_snapshot \\
        --out /dataset/consent_snapshot.json

Rồi các script dựng manifest / chia split trên máy chủ đọc tệp đó. Xem phần
"ảnh chụp" trong `app/consent_gate.py` để biết vì sao phải đi vòng qua tệp thay
vì hỏi thẳng cơ sở dữ liệu.

`--check` không ghi gì, chỉ in tình trạng và thoát khác 0 khi ảnh chụp hiện có
đã quá hạn — dùng được trong kiểm tra sau triển khai hoặc một tác vụ định kỳ.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("/dataset/consent_snapshot.json"))
    ap.add_argument("--tenant", default=None,
                    help="Mặc định: tenant đang có phạm vi, nếu không thì public_tenant_id")
    ap.add_argument("--check", action="store_true",
                    help="Chỉ kiểm tra ảnh chụp hiện có, không ghi đè")
    args = ap.parse_args(argv)

    from app.consent_gate import (
        SNAPSHOT_MAX_AGE_DAYS, SnapshotUnusable, build_snapshot, load_snapshot,
    )
    from app.tenant_context import system_scope

    if args.check:
        try:
            consents, _aliases, meta = load_snapshot(args.out)
        except SnapshotUnusable as exc:
            print(f"[FAIL] {exc}")
            return 1
        print(f"[OK] {args.out} — {len(consents)} nguoi ky, "
              f"tao luc {meta.get('generated_at')}, "
              f"hash {str(meta.get('content_hash'))[:12]}")
        return 0

    # `system_scope` vì ảnh chụp phải nhìn thấy cả tenant khi được gọi từ dòng
    # lệnh, nơi không có request nào đặt phạm vi.
    with system_scope("consent snapshot: doc toan bo dong thuan cua mot tenant"):
        data = build_snapshot(args.tenant)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Ghi qua tệp tạm rồi đổi tên: một script offline đọc đúng lúc lệnh này
    # đang ghi sẽ thấy tệp cụt, và một ảnh chụp cụt là một cổng mở toang.
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
                   encoding="utf-8")
    tmp.replace(args.out)

    signers = data.get("signers") or {}
    live = sum(1 for s in signers.values() if s.get("highest_live_rank") is not None)
    print(f"[OK] {args.out}")
    print(f"     tenant       : {data.get('tenant_id')}")
    print(f"     nguoi ky     : {len(signers)} co ho so, {live} con hieu luc")
    print(f"     bi danh      : {len(data.get('aliases') or {})}")
    print(f"     content_hash : {data.get('content_hash')}")
    print(f"     han dung     : {SNAPSHOT_MAX_AGE_DAYS} ngay")
    if not signers:
        print("     [CANH BAO] khong co dong thuan nao duoc ghi nhan. Moi duong")
        print("                phat hanh/cong bo se tra ve RONG — dung y cua co che.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

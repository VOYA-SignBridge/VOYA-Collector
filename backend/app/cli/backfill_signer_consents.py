"""Phản chiếu lại chấp thuận tài khoản → đồng thuận người ký, cho dữ liệu cũ.

Chạy TRONG container:

    docker exec voya_backend python -m app.cli.backfill_signer_consents --dry-run
    docker exec voya_backend python -m app.cli.backfill_signer_consents --confirm

Vì sao cần: cầu nối `consent_gate.sync_signer_consent` chỉ chạy từ lúc nó tồn
tại (2026-08-09). Ai đã ký `data_contribution` TRƯỚC đó, hoặc ký lúc chưa có hồ
sơ người ký, thì chấp thuận nằm nguyên trong `user_consents` mà chưa có dòng
tương ứng trong `signer_consents` — và cổng dữ liệu chỉ đọc bảng thứ hai.

Lệnh này KHÔNG tạo đồng thuận mới. Nó chỉ chép sang những chấp thuận **đã có
thật** và **còn hiệu lực**. Không có chấp thuận thì không có gì để chép, và đó
là kết quả đúng chứ không phải việc cần sửa.

Mặc định là `--dry-run`: in ra sẽ làm gì rồi dừng. Phải `--confirm` mới ghi.
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--confirm", action="store_true",
                    help="Thật sự ghi. Không có cờ này thì chỉ in.")
    ap.add_argument("--dry-run", action="store_true", help="(mặc định)")
    args = ap.parse_args(argv)
    write = bool(args.confirm)

    from app.consent_gate import CONSENT_DOCUMENT_SCOPE, sync_signer_consent
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    kinds = tuple(CONSENT_DOCUMENT_SCOPE)
    with system_scope("backfill: tim chap thuan chua duoc phan chieu"):
        rows = _fetch_all(
            """
            SELECT uc.user_id, uc.kind, s.signer_id
            FROM user_consents uc
            JOIN signers s ON s.external_user_id::text = uc.user_id::text
            WHERE uc.kind = ANY(%s)
              AND uc.withdrawn_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM signer_consents sc
                  WHERE sc.tenant_id = s.tenant_id
                    AND sc.signer_id = s.signer_id
                    AND sc.withdrawn_at IS NULL
              )
            """,
            (list(kinds),),
        )

    if not rows:
        print("[OK] khong co chap thuan nao can phan chieu.")
        print("     Neu ban mong doi co, kiem hai dieu: da ai ky "
              f"{'/'.join(kinds)} chua, va ho da co ho so nguoi ky chua")
        print("     (`SELECT count(*) FROM signers WHERE external_user_id IS NOT NULL`).")
        return 0

    print(f"[{'GHI' if write else 'THU'}] {len(rows)} chap thuan can phan chieu:")
    for r in rows:
        print(f"  {r['kind']:<20} user={r['user_id']}  ->  signer={r['signer_id']} "
              f"({CONSENT_DOCUMENT_SCOPE[r['kind']]})")

    if not write:
        print("\nChua ghi gi. Chay lai voi --confirm de thuc hien.")
        return 0

    done = 0
    for r in rows:
        if sync_signer_consent(str(r["user_id"]), r["kind"]):
            done += 1
    print(f"\n[OK] da phan chieu {done}/{len(rows)}.")
    # Khác 0 khi có cái không chép được: người gọi trong script cần biết.
    return 0 if done == len(rows) else 1


if __name__ == "__main__":
    sys.exit(main())

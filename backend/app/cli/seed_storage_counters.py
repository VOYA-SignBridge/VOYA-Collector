"""Đặt bộ đếm dung lượng khớp với đĩa, cho các tenant đã có dữ liệu từ trước v8.

Vì sao cần một lệnh riêng
--------------------------
`tenant_storage.bytes_used` mặc định 0. Trên một bản triển khai vừa bật v8,
mọi tổ chức bắt đầu ở 0 trong khi đĩa của họ đã có dữ liệu — nên hạn mức hỏng
theo hướng **MỞ**: một tổ chức đang chiếm 3 GB được ghi thêm trọn 2 GB nữa
trước khi bị chặn.

Lượt đối chiếu hằng ngày sẽ sửa việc đó, nhưng "hằng ngày" nghĩa là hạn mức
không có hiệu lực trong tối đa một ngày kể từ lúc bật. Đó là thứ phải đóng
TRƯỚC khi bật cưỡng chế, không phải sau.

Nó làm gì
---------
Đúng những gì `reconcile()` làm, và cố ý dùng chính hàm ấy chứ không viết lại:
hai phép đo cho cùng một câu hỏi thì sớm muộn cũng lệch nhau. Bảng hiện vật
tính phí ở `docs/07-business/BILLABLE_STORAGE_INVENTORY.md`.

An toàn khi chạy lại
--------------------
Lượt đối chiếu GHI ĐÈ bộ đếm theo số trên đĩa, nên chạy bao nhiêu lần cũng ra
một kết quả. Không cần kiểm trạng thái trước khi chạy.

    docker exec voya_backend python -m app.cli.seed_storage_counters --check
    docker exec voya_backend python -m app.cli.seed_storage_counters
"""

from __future__ import annotations

import argparse
import sys


def _bao_cao() -> int:
    """In bộ đếm hiện tại so với số trên đĩa. KHÔNG ghi gì."""
    from app import storage_quota as sq
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("cli: doi chieu thu bo dem dung luong"):
        rows = _fetch_all(
            "SELECT t.tenant_id, COALESCE(s.bytes_used, -1) AS dem "
            "  FROM tenants t LEFT JOIN tenant_storage s USING (tenant_id) "
            " WHERE t.deleted_at IS NULL ORDER BY t.tenant_id"
        )
        print(f"{'tenant':<24} {'bộ đếm':>14} {'đĩa':>14} {'lệch':>14}")
        print("-" * 70)
        lech = 0
        for r in rows:
            dem = int(r["dem"])
            that = sq._billable_bytes(r["tenant_id"])
            # -1 là "chưa có dòng nào", khác hẳn 0 là "đã đo và bằng không".
            nhan = "(chưa có)" if dem < 0 else f"{dem:,}"
            if dem != that:
                lech += 1
            print(f"{r['tenant_id']:<24} {nhan:>14} {that:>14,} "
                  f"{(that - max(dem, 0)):>+14,}")
        print("-" * 70)
        print(f"{len(rows)} tenant, {lech} lệch")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="chỉ báo cáo, không ghi gì")
    args = ap.parse_args(argv)

    if args.check:
        return _bao_cao()

    from app import storage_quota as sq

    ket = sq.reconcile()
    print(f"đã xét {ket['da_xet']} tenant, sửa {ket['lech']}, lỗi {ket['loi']}, "
          f"đang vượt trần {ket['vuot_tran']}")
    return 1 if ket["loi"] else 0


if __name__ == "__main__":
    sys.exit(main())

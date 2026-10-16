"""Lấp bảng `tenant_usage_daily` từ dữ liệu đã có.

Vì sao cần một lệnh riêng
--------------------------
Tác vụ nền `rollup_usage_daily` chỉ gộp NGÀY HÔM QUA. Trên một bản triển khai
vừa bật v4, bảng số đo trống trơn trong khi `samples` đã có 3.860 hàng trải
suốt nhiều tháng — nên trang "Mức dùng" sẽ hiện một biểu đồ rỗng và trông như
tính năng hỏng.

Cũng dùng để lấp khoảng trống sau một sự cố làm celery-beat nghỉ vài ngày.

An toàn khi chạy lại
--------------------
Mọi câu gộp là `INSERT ... ON CONFLICT DO UPDATE`, nên chạy hai lần cho ra đúng
một kết quả. Không cần kiểm trạng thái trước khi chạy.

Dung lượng chỉ đo cho NGÀY CUỐI, có chủ ý: dung lượng là trạng thái hiện tại,
và gán con số hôm nay cho chín mươi ngày trước là bịa ra một lịch sử phẳng chưa
từng tồn tại. Những ngày trước đó sẽ không có điểm dung lượng nào — đúng, vì ta
thật sự không biết.

    docker exec voya_backend python -m app.cli.backfill_usage --days 90
    docker exec voya_backend python -m app.cli.backfill_usage --check
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone


def _report_coverage() -> int:
    """In ra bảng số đo đang phủ tới đâu. Không ghi gì."""
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("cli: report usage coverage"):
        rows = _fetch_all(
            "SELECT metric, count(*) AS n, min(usage_date) AS earliest, "
            "max(usage_date) AS latest FROM tenant_usage_daily "
            "GROUP BY metric ORDER BY metric"
        )
        tenants = _fetch_all(
            "SELECT count(DISTINCT tenant_id) AS n FROM tenant_usage_daily"
        )

    if not rows:
        print("tenant_usage_daily TRỐNG — chạy lại lệnh này không kèm --check.")
        return 1

    print(f"{'chỉ số':<26} {'dòng':>7}  {'từ':<12} {'đến':<12}")
    print("-" * 62)
    for row in rows:
        print(
            f"{row['metric']:<26} {row['n']:>7}  "
            f"{str(row['earliest']):<12} {str(row['latest']):<12}"
        )
    print("-" * 62)
    print(f"số tenant có số đo: {tenants[0]['n'] if tenants else 0}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--days", type=int, default=90,
        help="số ngày lùi về quá khứ để gộp lại (mặc định 90)",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="chỉ báo cáo bảng số đo đang phủ tới đâu, không ghi gì",
    )
    args = parser.parse_args(argv)

    from app.storage.metadata_db import ensure_tables

    ensure_tables()

    if args.check:
        return _report_coverage()

    if args.days < 1:
        print("--days phải ≥ 1", file=sys.stderr)
        return 2

    from app.usage import backfill

    since = (datetime.now(timezone.utc) - timedelta(days=args.days)).date()
    print(f"Đang gộp số đo từ {since} tới hôm nay ({args.days} ngày)...")
    totals = backfill(days=args.days)

    print()
    for metric, written in sorted(totals.items()):
        print(f"  {metric:<26} {written:>7} dòng")
    print()
    return _report_coverage()


if __name__ == "__main__":
    raise SystemExit(main())

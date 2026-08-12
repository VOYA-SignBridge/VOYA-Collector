"""Ghi hộ chấp thuận cho những tài khoản có trước ngày công bố văn bản.

Vấn đề nó giải
---------------
Cưỡng chế bật bằng cách công bố. Nghĩa là mọi tài khoản tạo TRƯỚC lần công bố
đầu tiên không có dòng chấp thuận nào, và sẽ mãi không có: đường duy nhất tạo
ra một dòng là biểu mẫu đăng ký, mà họ thì đã đăng ký xong rồi.

Kết quả là bảng độ phủ đứng ở "0/N đã đồng ý" vĩnh viễn, và con số đó không
phân biệt được "chưa ai ký" với "tính năng mới bật hôm qua".

Vì sao những dòng này KHÔNG phải chữ ký
----------------------------------------
Chúng được ghi với ``source='backfill'`` và một ``note`` bắt buộc. Đó không
phải chi tiết kế toán — đó là ranh giới đạo đức của lệnh này. Người vận hành
khẳng định một điều ("những tài khoản này là của chúng tôi, do chúng tôi tạo,
và chúng tôi chấp nhận điều khoản thay chúng"); người dùng bấm nút khẳng định
một điều khác. Ghi cả hai vào cùng một hình dạng dữ liệu là làm giả bằng chứng,
kể cả khi lời khẳng định đầu hoàn toàn đúng sự thật.

Bản ghi sống lâu hơn hoàn cảnh biết được sự khác nhau đó. ``consent_coverage()``
vì thế trả về cả ``accepted`` lẫn ``accepted_by_user``, và hai con số ấy phải
được đọc như hai con số.

Dùng
----
    # Xem sẽ ghi cho ai — KHÔNG ghi gì. Đây là mặc định.
    python -m app.cli.backfill_consents --note "tài khoản nội bộ, ..."

    # Ghi thật.
    python -m app.cli.backfill_consents --note "..." --apply

    # Chỉ một loại, hoặc chỉ một tài khoản.
    python -m app.cli.backfill_consents --kind terms --username minh --note "..." --apply

Exit: 0 xong · 2 thiếu tham số · 3 chưa công bố văn bản bắt buộc.
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Dict, List, Optional

from app.tenant_context import platform_command


def _accounts_missing(kind: str, username: Optional[str]) -> List[Dict[str, Any]]:
    """Tài khoản đang hoạt động chưa có chấp thuận CÒN HIỆU LỰC cho loại này.

    `NOT EXISTS` chứ không `LEFT JOIN ... IS NULL`: chỉ mục duy nhất bộ phận
    `uq_consent_live` cho phép nhiều dòng đã-rút cho cùng một cặp (người, loại),
    nên phép nối sẽ nhân bản hàng và đếm sai.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    sql = """
        SELECT u.id, u.username, u.email, u.created_at
        FROM users u
        WHERE u.is_active
          AND NOT EXISTS (
                SELECT 1 FROM user_consents c
                 WHERE c.user_id = u.id AND c.kind = %s
                   AND c.withdrawn_at IS NULL)
    """
    params: tuple = (kind,)
    if username:
        sql += " AND u.username = %s"
        params += (username,)
    sql += " ORDER BY u.created_at"

    with system_scope("cli: tìm tài khoản chưa có chấp thuận"):
        return [dict(r) for r in _fetch_all(sql, params)]


@platform_command("cli: ghi hộ chấp thuận cho tài khoản có sẵn")
def main(argv: List[str] | None = None) -> int:
    from app import legal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=legal.KINDS, action="append",
                        help="lặp lại được. Bỏ trống = hai loại bắt buộc.")
    parser.add_argument("--username", help="chỉ một tài khoản")
    parser.add_argument("--note", default="",
                        help="BẮT BUỘC khi --apply: vì sao ghi hộ")
    parser.add_argument("--recorded-by", default=None,
                        help="UUID người vận hành chịu trách nhiệm")
    parser.add_argument("--apply", action="store_true",
                        help="ghi thật. Không có cờ này thì chỉ liệt kê.")
    args = parser.parse_args(argv)

    kinds = args.kind or list(legal.REQUIRED_AT_REGISTRATION)

    unpublished = [k for k in kinds if legal.current_document(k) is None]
    if unpublished:
        print(f"ERROR: chưa công bố {', '.join(unpublished)}. "
              f"Không thể đồng ý với một văn bản không tồn tại.")
        return 3

    if args.apply and not args.note.strip():
        print("ERROR: --apply cần --note. Một dòng ghi hộ không giải thích "
              "được sẽ bị đọc nhầm thành chữ ký thật.")
        return 2

    total_written = 0
    for kind in kinds:
        doc = legal.current_document(kind)
        assert doc is not None  # đã lọc ở trên
        targets = _accounts_missing(kind, args.username)

        print(f"\n=== {kind} bản {doc['version']} ===")
        if not targets:
            print("  không có tài khoản nào thiếu. Không làm gì.")
            continue

        print(f"  {len(targets)} tài khoản thiếu chấp thuận:")
        for row in targets[:20]:
            print(f"    {row['username']:<24} {row['email']:<36} "
                  f"tạo {row['created_at']:%Y-%m-%d}")
        if len(targets) > 20:
            print(f"    … và {len(targets) - 20} tài khoản nữa")

        if not args.apply:
            print("  (thử nghiệm — chưa ghi gì. Thêm --apply để ghi thật.)")
            continue

        for row in targets:
            legal.record_consent(
                str(row["id"]), kind, str(doc["version"]),
                source="backfill", note=args.note.strip(),
                recorded_by=args.recorded_by,
            )
            total_written += 1
        print(f"  đã ghi {len(targets)} dòng, source='backfill'.")

    if args.apply:
        print(f"\nTổng: {total_written} dòng chấp thuận ghi hộ.")
        print("Chúng KHÔNG phải chữ ký người dùng và không được đếm như chữ ký; "
              "xem cột `accepted_by_user` ở bảng độ phủ.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

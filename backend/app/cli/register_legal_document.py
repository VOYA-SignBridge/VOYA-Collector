"""Công bố một bản Điều khoản / Quyền riêng tư / Đồng ý đóng góp.

Công bố CHÍNH LÀ hành động bật cưỡng chế: khi chưa có bản nào, đăng ký không
đòi chấp thuận; ngay khi có, mọi tài khoản mới phải đồng ý và số hiệu được đối
chiếu ở server.

    python -m app.cli.register_legal_document \\
        --kind terms --version 2026-08-08 \\
        --file docs/04-legal/published/terms-2026-08-08.md \\
        --url /legal/terms

    python -m app.cli.register_legal_document --list

Nội dung được LƯU NGUYÊN VĂN và băm cùng bản ghi. Sửa file mà giữ nguyên số
hiệu phiên bản sẽ bị từ chối (exit 4) — vì mọi chấp thuận đã thu trỏ tới số
hiệu đó, và đổi nội dung dưới chân chúng làm bằng chứng trở nên vô nghĩa. Muốn
sửa thì tăng phiên bản.

`--requires-reconsent` dành cho thay đổi làm đổi phạm vi xử lý dữ liệu. Sửa lỗi
chính tả thì đừng bật: nó đá mọi người đang dùng ra màn hình đồng ý.

`--effective-from` ở tương lai là cách LÊN LỊCH: bản mới nằm sẵn trong bảng,
đường đọc công khai chưa thấy nó, và tới đúng thời điểm nó tự thay bản cũ mà
không cần ai chạy lệnh gì lúc nửa đêm.

Exit: 0 xong · 2 thiếu tham số · 3 không đọc được file · 4 xung đột nội dung.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from app.tenant_context import platform_command


@platform_command("cli: công bố văn bản pháp lý")
def main(argv: List[str] | None = None) -> int:
    from app import legal

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", action="store_true",
                        help="liệt kê bản đang hiệu lực của từng loại")
    parser.add_argument("--history", action="store_true",
                        help="liệt kê MỌI bản, kèm số chấp thuận trỏ tới")
    parser.add_argument("--kind", choices=legal.KINDS)
    parser.add_argument("--version", help="ví dụ 2026-08-07 hoặc 1.2")
    parser.add_argument("--file", help="đường dẫn tới bản văn (md hoặc txt)")
    parser.add_argument("--url", help="đường người dùng đọc bản văn")
    parser.add_argument("--title", default="")
    parser.add_argument("--language", default="vi")
    parser.add_argument("--change-summary", default="",
                        help="bản này khác bản trước ở chỗ nào")
    parser.add_argument("--effective-from", default=None,
                        help="ISO 8601, ví dụ 2026-09-01T00:00:00+07:00. "
                             "Bỏ trống = hiệu lực ngay.")
    parser.add_argument("--requires-reconsent", action="store_true",
                        help="buộc người đã đồng ý bản cũ phải đồng ý lại")
    args = parser.parse_args(argv)

    if args.list:
        for kind in legal.KINDS:
            doc = legal.current_document(kind)
            if doc is None:
                print(f"  {kind:<20} (chưa công bố)")
            else:
                print(f"  {kind:<20} {doc['version']:<14} {doc['url']}")
        missing = legal.missing_for_registration()
        if missing:
            print(f"\nCHƯA công bố (đăng ký sẽ KHÔNG thu chấp thuận): "
                  f"{', '.join(missing)}")
        return 0

    if args.history:
        print(f"  {'loại':<20} {'bản':<14} {'hiệu lực':<12} {'chữ ký':>7}  tiêu đề")
        for row in legal.list_documents(args.kind):
            state = "đang dùng" if row["is_effective"] else "hẹn giờ"
            print(f"  {row['kind']:<20} {row['version']:<14} {state:<12} "
                  f"{row['consent_count']:>7}  {row['title']}")
        return 0

    if not (args.kind and args.version and args.file and args.url):
        print("ERROR: cần --kind, --version, --file, --url "
              "(hoặc dùng --list / --history)")
        return 2

    effective_from = None
    if args.effective_from:
        try:
            effective_from = datetime.fromisoformat(args.effective_from)
        except ValueError:
            print(f"ERROR: --effective-from không phải ISO 8601: "
                  f"{args.effective_from!r}")
            return 2

    path = Path(args.file)
    try:
        body = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: không đọc được {path}: {exc}")
        return 3
    if not body.strip():
        print(f"ERROR: {path} rỗng. Một văn bản rỗng không phải văn bản.")
        return 3

    try:
        legal.register_document(
            args.kind, args.version, url=args.url, body=body,
            title=args.title, requires_reconsent=args.requires_reconsent,
            language=args.language, change_summary=args.change_summary,
            effective_from=effective_from,
        )
    except legal.ConsentError as exc:
        print(f"ERROR: {exc}")
        return 4

    print(f"Đã công bố {args.kind} bản {args.version}")
    print(f"  hash nội dung: {legal.content_hash(body)[:16]}…")
    print(f"  dài:           {len(body):,} ký tự")
    print(f"  đọc tại:       {args.url}")
    if effective_from is not None:
        print(f"  HẸN GIỜ:       {effective_from.isoformat()} "
              f"(chưa áp dụng cho tới lúc đó)")
    if args.kind in legal.REQUIRED_AT_REGISTRATION:
        still = legal.missing_for_registration()
        if still:
            print(f"\nCòn thiếu để cưỡng chế đầy đủ: {', '.join(still)}")
        elif effective_from is None:
            print("\nTừ giờ mọi tài khoản mới phải đồng ý trước khi tạo được.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

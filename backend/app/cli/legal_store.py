"""Kho tài liệu pháp lý: kiểm toàn vẹn, đưa dữ liệu cũ vào kho, dọn rác.

    python -m app.cli.legal_store --status
    python -m app.cli.legal_store --verify
    python -m app.cli.legal_store --backfill          # ghi bản đã công bố vào kho
    python -m app.cli.legal_store --gc                # liệt kê rác, KHÔNG xoá
    python -m app.cli.legal_store --gc --apply        # xoá thật

`--verify` là phép kiểm quan trọng nhất ở đây, và nó kiểm HAI chiều:

1. mỗi hàng có `storage_key` phải trỏ tới một tệp CÓ THẬT;
2. tệp đó phải có nội dung trùng **từng byte** với cột `body` trong bảng.

Chiều thứ hai là lý do việc lưu hai nơi không phải hai nguồn sự thật. Bản trong
bảng là bản hồ sơ — đóng băng, nằm cùng `pg_dump` với những chấp thuận trỏ tới
nó. Bản trong kho là tài liệu — sửa được ở dạng nháp, so sánh được, sao chép
được. Một phép kiểm chứng minh chúng bằng nhau là thứ giữ cho chúng không trôi.

Exit: 0 mọi thứ khớp · 1 có sai lệch · 2 sai tham số.
"""

from __future__ import annotations

import argparse
import sys
from typing import List

from app.tenant_context import platform_command


@platform_command("cli: kho tài liệu pháp lý")
def main(argv: List[str] | None = None) -> int:
    from app import legal, legal_store
    from app.storage.metadata_db import _cursor, _fetch_all
    from app.tenant_context import system_scope

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true", help="tóm tắt kho")
    parser.add_argument("--verify", action="store_true",
                        help="đối chiếu từng hàng với tệp của nó")
    parser.add_argument("--backfill", action="store_true",
                        help="ghi vào kho những bản đã công bố mà chưa có tệp")
    parser.add_argument("--gc", action="store_true",
                        help="tìm blob không còn ai trỏ tới")
    parser.add_argument("--apply", action="store_true",
                        help="với --gc: xoá thật thay vì chỉ liệt kê")
    args = parser.parse_args(argv)

    if not any((args.status, args.verify, args.backfill, args.gc)):
        print("ERROR: cần một trong --status / --verify / --backfill / --gc")
        return 2

    root = legal_store.store_root()

    if args.status:
        with system_scope("cli: tóm tắt kho"):
            docs = _fetch_all(
                "SELECT kind, version, storage_key, byte_size FROM legal_documents "
                "ORDER BY kind, effective_from")
            drafts = _fetch_all(
                "SELECT kind, status, storage_key FROM legal_document_drafts "
                "ORDER BY updated_at DESC")
            events = _fetch_all("SELECT count(*) AS c FROM legal_document_events")
        on_disk = list(legal_store.iter_keys())
        print(f"gốc kho:        {root}")
        print(f"tệp trên đĩa:   {len(on_disk)}")
        print(f"bản đã công bố: {len(docs)}  "
              f"({sum(1 for d in docs if d['storage_key'])} có tệp)")
        print(f"bản nháp:       {len(drafts)}")
        print(f"dòng sổ đăng bạ:{events[0]['c']:>4}")
        for d in docs:
            mark = "" if d["storage_key"] else "   <== CHUA CO TEP"
            print(f"  {d['kind']:<20} {d['version']:<14} "
                  f"{(d['storage_key'] or '-')[:46]}{mark}")
        return 0

    if args.backfill:
        # Đưa những bản công bố dưới thời v5 (chỉ có `body`, chưa có tệp) vào
        # kho. Idempotent: tên tệp là băm nội dung, nên chạy lại không ghi thêm.
        with system_scope("cli: đưa bản đã công bố vào kho"):
            rows = _fetch_all(
                "SELECT doc_id, kind, version, body, content_hash "
                "FROM legal_documents WHERE storage_key IS NULL "
                "  AND body IS NOT NULL AND body <> ''")
        if not rows:
            print("Không có bản nào thiếu tệp. Không làm gì.")
            return 0
        for row in rows:
            key, digest, size = legal_store.write(row["kind"], row["body"])
            if digest != row["content_hash"]:
                print(f"ERROR: {row['kind']} bản {row['version']} — băm nội dung "
                      f"trong bảng ({row['content_hash'][:12]}…) khác băm tính "
                      f"lại ({digest[:12]}…). KHÔNG ghi con trỏ.")
                return 1
            # Trigger `legal_documents_freeze` cho phép ĐIỀN con trỏ khi nó còn
            # trống, và cấm ĐỔI nó về sau. Câu này là lượt điền duy nhất.
            with system_scope("cli: gắn con trỏ kho"):
                with _cursor() as cur:
                    cur.execute(
                        "UPDATE legal_documents SET storage_key = %s, byte_size = %s "
                        " WHERE doc_id = %s AND storage_key IS NULL",
                        (key, size, row["doc_id"]))
            print(f"  {row['kind']:<20} {row['version']:<14} -> {key}")
            legal.record_event("document.stored", kind=row["kind"],
                               version=row["version"], storage_key=key,
                               content_hash_value=digest,
                               detail={"byte_size": size, "source": "backfill"})
        print(f"\nĐã đưa {len(rows)} bản vào kho.")
        return 0

    if args.verify:
        with system_scope("cli: đối chiếu kho với bảng"):
            rows = _fetch_all(
                "SELECT kind, version, body, content_hash, storage_key "
                "FROM legal_documents ORDER BY kind, effective_from")
        problems = []
        for row in rows:
            key = row["storage_key"]
            if not key:
                problems.append(f"{row['kind']}:{row['version']} — chưa có tệp "
                                f"(chạy --backfill)")
                continue
            if not legal_store.exists(key):
                problems.append(f"{row['kind']}:{row['version']} — tệp {key} "
                                f"KHÔNG tồn tại")
                continue
            if not legal_store.verify(key, row["content_hash"]):
                problems.append(f"{row['kind']}:{row['version']} — tệp {key} "
                                f"không khớp băm trong bảng")
                continue
            if legal_store.read(key) != row["body"]:
                problems.append(f"{row['kind']}:{row['version']} — tệp và cột "
                                f"`body` KHÁC NHAU")
                continue
            print(f"  OK  {row['kind']:<20} {row['version']:<14} {key[:46]}")
        if problems:
            print("\nSAI LECH:")
            for p in problems:
                print(f"  {p}")
            return 1
        print(f"\n{len(rows)}/{len(rows)} bản khớp giữa bảng và kho.")
        return 0

    # --gc
    referenced = legal.referenced_storage_keys()
    orphans = legal_store.collect_garbage(referenced, dry_run=not args.apply)
    if not orphans:
        print("Không có blob mồ côi nào đủ tuổi để dọn.")
        return 0
    for key in orphans:
        print(f"  {'xoa' if args.apply else 'se xoa'}  {key}")
    if not args.apply:
        print(f"\n{len(orphans)} blob mồ côi. Thêm --apply để xoá thật.")
    else:
        print(f"\nĐã xoá {len(orphans)} blob mồ côi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

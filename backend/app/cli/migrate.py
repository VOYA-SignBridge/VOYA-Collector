"""Lệnh migration RÕ RÀNG. Cái duy nhất được phép đổi hình dạng cơ sở dữ liệu.

    python -m app.cli.migrate --to 5            # migrate that DB to v5
    python -m app.cli.migrate --status          # hỏi, không đổi gì
    python -m app.cli.migrate --adopt           # đóng dấu lược đồ đã đúng sẵn
    python -m app.cli.migrate --dry-run --to 5  # in ra sẽ chạy những gì

Vì sao có tệp này
=================
Trước 12/08/2026, migration là một tác dụng phụ của việc khởi động backend.
`ensure_tables()` chạy toàn bộ DDL, kể cả phần bỏ bảng và chép dữ liệu — nên
mọi `docker compose up` đều là một lượt migration mà không ai gọi tên. Hôm đó
một lệnh kiểm chứng vô hại đã dùng chính đường đó để đổi lược đồ sản xuất.

Bây giờ ranh giới là:

    ensure_tables()          THÊM và bổ khuyết, chạy mỗi lần khởi động
    app.cli.migrate          ĐỔI và BỎ, chạy khi có người gõ ra nó

Ba chốt chặn, theo thứ tự
=========================
1. **Đúng đích.** `EXPECTED_DATABASE` bắt buộc ở đây, khác với ở
   `ensure_tables()` nơi nó là tuỳ chọn. Lý do khác nhau: `ensure_tables()`
   chạy hợp lệ ở mỗi lần khởi động nên chốt chặn luôn-bật sẽ chặn cả đường
   đúng; còn lệnh này thì mỗi lần chạy đều là một quyết định, và một quyết định
   luôn nói được nó nhắm vào đâu. Đây chính xác là thứ đã thiếu hôm 12/08.
2. **Đúng chiều.** Không migration lùi. Lược đồ đang ở v6 mà lệnh yêu cầu v5
   thì huỷ — cách quay lui duy nhất là khôi phục từ sao lưu.
3. **Đúng phiên bản đích.** `--to` phải khớp `APP_SCHEMA_VERSION` của ẢNH đang
   chạy lệnh. Không có chốt này thì `--to 5` chạy từ một ảnh v6 sẽ để lại lược
   đồ v6 mang dấu v5.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

from app.logging_config import configure_logging
from app.storage.metadata_db import EXPECTED_DATABASE_ENV
from app.storage.schema_version import (
    APP_SCHEMA_VERSION,
    MIN_SUPPORTED_SCHEMA_VERSION,
    SchemaVersionError,
    compatibility_error,
    read_schema_version,
    stamp_schema_version,
)

logger = logging.getLogger("cli.migrate")


def _current_version() -> tuple[int | None, str]:
    """(phiên bản, tên cơ sở dữ liệu). Đọc bằng vai DDL."""
    from app.storage.metadata_db import _migration_cursor

    with _migration_cursor() as cur:
        cur.execute("SELECT current_database()")
        database = cur.fetchone()[0]
        return read_schema_version(cur), database


def _schema_looks_complete() -> list[str]:
    """Những đối tượng của lược đồ hiện hành còn THIẾU. Rỗng = đã đủ."""
    from app.storage.authz_schema import missing_objects
    from app.storage.metadata_db import _migration_cursor

    with _migration_cursor() as cur:
        # `missing_objects` nhận CONNECTION, không phải cursor: nó tự mở cursor
        # riêng để người gọi chọn được vai. Ở đây vai đó là vai DDL.
        return list(missing_objects(cur.connection))


def cmd_status() -> int:
    from app.storage.metadata_db import _migration_cursor
    from app.storage.schema_version import (
        checksum_problem, migration_checksum, migration_payload,
        read_recorded_checksum,
    )

    version, database = _current_version()
    missing = _schema_looks_complete()
    error = compatibility_error(version)

    with _migration_cursor() as cur:
        _, recorded, has_column = read_recorded_checksum(cur)
        ck_problem = checksum_problem(cur)
    current_ck = migration_checksum()

    print(f"co so du lieu    : {database}")
    print(f"phien ban luoc do: "
          f"{version if version is not None else '(chua dong dau)'}")
    print(f"anh nay ho tro   : v{MIN_SUPPORTED_SCHEMA_VERSION}..v{APP_SCHEMA_VERSION}")
    print(f"payload mot chieu: {len(migration_payload())} cau")
    print(f"checksum hien tai: {current_ck}")
    print(f"checksum da ghi  : "
          f"{recorded if recorded else ('(NULL)' if has_column else '(chua co cot)')}")
    print(f"doi tuong thieu  : {len(missing)}")
    for name in missing[:20]:
        print(f"    - {name}")
    if len(missing) > 20:
        print(f"    ... con {len(missing) - 20} muc nua")

    if error is None and ck_problem is None:
        print("\nKET LUAN: khop — backend khoi dong duoc tren co so du lieu nay.")
        return 0

    print("\nKET LUAN: KHONG KHOP")
    if error:
        print(error)
    if ck_problem:
        print(ck_problem)
    return 1


def cmd_adopt_checksum() -> int:
    """Xác nhận MỘT LẦN checksum cho một phiên bản đã đóng dấu trước khi có cột.

    Vì sao phải là một lệnh riêng thay vì tự điền khi thấy NULL
    -----------------------------------------------------------
    Vì "nếu NULL thì điền giá trị hiện tại" hợp thức hoá mọi thứ. Một migration
    đã bị sửa cũng cho ra NULL trên máy chưa nâng cấp, và lượt khởi động kế tiếp
    sẽ ghi nội dung ĐÃ SỬA vào sổ như thể đó là bản gốc. Từ đó không ai còn phát
    hiện được gì — chính là điều checksum sinh ra để ngăn.

    Nên lệnh này kiểm ba điều trước khi ghi, và từ chối nếu bất kỳ điều nào sai:

      1. Đã có một phiên bản được đóng dấu (không phải cơ sở dữ liệu trắng).
      2. Phiên bản đó nằm trong khoảng ảnh này hỗ trợ — nếu không thì checksum
         của ảnh này không mô tả lượt biến đổi mà cơ sở dữ liệu đã đi qua.
      3. Lược đồ ĐẦY ĐỦ: `missing_objects()` rỗng. Đây là bằng chứng gián tiếp
         nhưng thật rằng migration đã chạy trọn vẹn, chứ không dừng giữa chừng.

    Và nó chỉ ghi khi checksum đang NULL. Đã có giá trị thì KHÔNG ghi đè, kể cả
    khi lệch — ghi đè lúc lệch chính là xoá bằng chứng.
    """
    from app.storage.metadata_db import _migration_cursor
    from app.storage.schema_version import (
        SCHEMA_VERSION_TABLE, migration_checksum, read_recorded_checksum,
    )

    version, database = _current_version()
    if version is None:
        print(f"TU CHOI: {database!r} chua dong dau phien ban nao. "
              f"Day khong phai viec cua --adopt-checksum.\n"
              f"    Chay:  python -m app.cli.migrate --to {APP_SCHEMA_VERSION}")
        return 2

    if not (MIN_SUPPORTED_SCHEMA_VERSION <= version <= APP_SCHEMA_VERSION):
        print(f"TU CHOI: luoc do o v{version}, anh nay ho tro "
              f"v{MIN_SUPPORTED_SCHEMA_VERSION}..v{APP_SCHEMA_VERSION}. "
              f"Checksum cua anh nay khong mo ta lan bien doi ma co so du lieu "
              f"nay da di qua.")
        return 2

    missing = _schema_looks_complete()
    if missing:
        print(f"TU CHOI: luoc do con thieu {len(missing)} doi tuong, nen khong "
              f"the khang dinh migration v{version} da chay tron ven:")
        for name in missing[:20]:
            print(f"    - {name}")
        return 2

    with _migration_cursor() as cur:
        _, recorded, has_column = read_recorded_checksum(cur)
        if not has_column:
            print("TU CHOI: cot `migration_checksum` chua ton tai. Chay backend "
                  "mot lan (hoac `--to`) de `ensure_tables()` them cot, roi thu lai.")
            return 2

        current = migration_checksum()
        if recorded is not None:
            if recorded == current:
                print(f"v{version} da co checksum va KHOP — khong can lam gi.")
                return 0
            print(f"TU CHOI: v{version} DA co checksum va no LECH.\n"
                  f"    da ghi   : {recorded}\n"
                  f"    hien tai : {current}\n"
                  f"Lenh nay khong ghi de. Ghi de luc lech chinh la xoa bang chung.\n"
                  f"Hoac hoan nguyen noi dung migration ve dung ban da ap dung, "
                  f"hoac tao phien ban v{version + 1}.")
            return 2

        cur.execute(
            f"UPDATE {SCHEMA_VERSION_TABLE} SET migration_checksum = %s, "
            f"note = coalesce(note || ' | ', '') || %s "
            f"WHERE version = %s AND migration_checksum IS NULL",
            (current, "checksum adopted (one-time)", version))
        touched = cur.rowcount

    print(f"Da ghi checksum cho v{version} tren {database!r}: {current}")
    print(f"    so dong duoc xac nhan: {touched}")
    print("Tu gio noi dung migration v%d la BAT BIEN: sua no se lam gate do." % version)
    return 0


def cmd_adopt(force: bool = False) -> int:
    """Đóng dấu một lược đồ đã ĐÚNG SẴN nhưng chưa từng được đóng dấu.

    Tồn tại vì một lý do có thật và chỉ xảy ra một lần cho mỗi máy: sản xuất
    đã ở v5 TỪ TRƯỚC khi sổ đăng bạ ra đời. Không có lệnh này thì lượt triển
    khai đầu tiên sau khi có cổng phiên bản sẽ từ chối khởi động trên một cơ sở
    dữ liệu hoàn toàn đúng.

    Nó KHÔNG đổi gì trong lược đồ. Và nó từ chối chạy khi lược đồ còn thiếu đối
    tượng — đóng dấu một lược đồ dở dang là cách biến cổng này thành đồ trang
    trí, và một cổng trang trí còn tệ hơn không có cổng.
    """
    version, database = _current_version()
    if version is not None:
        print(f"Co so du lieu {database!r} da o v{version} — khong can adopt.")
        return 0

    missing = _schema_looks_complete()
    if missing and not force:
        print(f"TU CHOI: luoc do con thieu {len(missing)} doi tuong, nen no CHUA "
              f"o v{APP_SCHEMA_VERSION}:")
        for name in missing[:20]:
            print(f"    - {name}")
        print(f"\nChay lenh migration that:  "
              f"python -m app.cli.migrate --to {APP_SCHEMA_VERSION}")
        return 2

    from app.storage.metadata_db import _migration_cursor

    with _migration_cursor() as cur:
        stamp_schema_version(
            cur, APP_SCHEMA_VERSION,
            note="adopt: luoc do da dung san truoc khi so dang ba ra doi"
                 + (" (--force, con thieu doi tuong)" if missing else ""),
        )
    print(f"Da dong dau {database!r} o v{APP_SCHEMA_VERSION}.")
    return 0


def cmd_migrate(target: int, dry_run: bool = False, note: str | None = None) -> int:
    from app.storage.metadata_db import (
        DDL_STATEMENTS,
        INDEX_STATEMENTS,
        MIGRATION_STATEMENTS,
        migrate_database,
        one_way_statements,
    )

    if target != APP_SCHEMA_VERSION:
        print(f"TU CHOI: --to {target} nhung anh nay viet ra "
              f"v{APP_SCHEMA_VERSION}.\nTrien khai anh dung phien ban roi chay lai.")
        return 2

    version, database = _current_version()
    if version is not None and version > target:
        print(f"TU CHOI: luoc do dang o v{version}, khong migration lui ve "
              f"v{target}.\nCach quay lui duy nhat la khoi phuc tu sao luu — xem "
              f"docs/BACKUP_RESTORE.md.")
        return 2

    # Checksum, TRƯỚC khi chạy bất kỳ câu nào.
    #
    # Nếu nội dung migration đã đổi so với lúc nó được áp dụng, thì chạy lại nó
    # không phải là "chạy lại" — nó là chạy một lượt biến đổi KHÁC dưới cùng một
    # nhãn phiên bản. Bắt ở đây, trước khi có câu nào chạm vào cơ sở dữ liệu.
    #
    # Trường hợp NULL cũng dừng ở đây, và đây là chỗ ĐÚNG để dừng: `deploy.sh`
    # chạy lệnh này trước khi dựng stack, nên một lượt triển khai lên máy chưa
    # xác nhận checksum sẽ dừng lại sạch sẽ — container cũ vẫn chạy mã cũ — kèm
    # đúng lệnh cần gõ.
    from app.storage.metadata_db import _migration_cursor
    from app.storage.schema_version import (
        MigrationChecksumMismatch, MigrationChecksumMissing, checksum_problem,
    )

    with _migration_cursor() as cur:
        problem = checksum_problem(cur)

    if isinstance(problem, MigrationChecksumMismatch):
        print(f"TU CHOI: {problem}")
        return 2

    if isinstance(problem, MigrationChecksumMissing):
        # KHÔNG chặn ở đây, và lý do là một vòng chết có thật.
        #
        # Cột `migration_checksum` do chính lượt migration này tạo ra (nó nằm
        # trong `SCHEMA_VERSION_DDL`). Nếu "chưa có checksum" là điều kiện chặn
        # thì trên mọi cơ sở dữ liệu đóng dấu trước khi cột ra đời — tức là
        # sản xuất — lệnh sẽ từ chối chạy chính lượt migration duy nhất có thể
        # thêm cột đó. Không lệnh nào thoát ra được.
        #
        # Bỏ chặn ở đây KHÔNG mở đường cho việc tự hợp thức hoá, vì hai lẽ:
        # lượt chạy này kết thúc bằng `stamp_schema_version`, ghi một dòng MỚI
        # kèm checksum hiện tại — một hành động do người gõ ra, có
        # `EXPECTED_DATABASE`, và có kiểm `missing_objects()` ngay sau đó. Còn
        # nếu payload ĐÃ bị sửa mà dòng cũ CÓ checksum, nhánh trên đã chặn rồi.
        print(f"LUU Y: {' '.join(str(problem).split())[:200]}")
        print("       Lenh nay se ghi mot dong moi kem checksum hien tai.\n")

    one_way = one_way_statements()
    if dry_run:
        from app.storage.authz_schema import AUTHZ_DDL_STATEMENTS

        # Quét cả bốn danh sách, kể cả `INDEX_STATEMENTS` nơi hôm nay không có
        # câu một chiều nào: bản xem trước phải soi đúng tập mà `_apply_schema`
        # lọc, nếu không thì nó sẽ im lặng bỏ sót đúng câu vừa được thêm.
        will_run = [
            s for s in (*DDL_STATEMENTS, *MIGRATION_STATEMENTS,
                        *INDEX_STATEMENTS, *AUTHZ_DDL_STATEMENTS)
            if s in one_way
        ]
        print(f"co so du lieu : {database}")
        print(f"tu v{version if version is not None else '?'} -> v{target}")
        print(f"\n{len(will_run)} cau MOT CHIEU se chay (phan con lai la them/bo "
              f"khuyet, chay o moi lan khoi dong):\n")
        for stmt in will_run:
            print(f"  --- {' '.join(stmt.split())[:160]}")
        print("\n(--dry-run: khong chay gi)")
        return 0

    logger.warning(
        "[MIGRATE] bat dau database=%s tu v%s -> v%s",
        database, version if version is not None else "(chua dong dau)", target,
    )
    migrate_database(note=note)

    after, _ = _current_version()
    missing = _schema_looks_complete()
    logger.warning("[MIGRATE] xong database=%s v%s doi_tuong_thieu=%d",
                   database, after, len(missing))

    if missing:
        # Không ném lỗi: lược đồ đã đổi rồi, và bỏ chạy giữa chừng không lấy lại
        # được gì. Nhưng mã thoát phải khác 0, vì `deploy.sh` đọc nó và một lượt
        # migration dở dang KHÔNG được đi tiếp sang bước triển khai.
        print(f"CANH BAO: migration chay xong nhung con {len(missing)} doi tuong "
              f"thieu:")
        for name in missing[:20]:
            print(f"    - {name}")
        return 1

    print(f"Da migrate {database!r} len v{after}.")
    return 0


def main(argv: list[str] | None = None) -> int:
    configure_logging()

    parser = argparse.ArgumentParser(
        description="Migration ro rang cho luoc do VOYA. "
                    "Dat EXPECTED_DATABASE de khoa dich.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--status", action="store_true",
                       help="In phien ban hien tai va ket luan tuong thich. Khong doi gi.")
    group.add_argument("--to", type=int, metavar="N",
                       help=f"Migrate len phien ban N (anh nay: {APP_SCHEMA_VERSION}).")
    group.add_argument("--adopt", action="store_true",
                       help="Dong dau mot luoc do da dung san nhung chua co dau.")
    group.add_argument("--adopt-checksum", action="store_true",
                       help="Xac nhan MOT LAN checksum cho phien ban da dong dau "
                            "truoc khi cot checksum ton tai. Co kiem chung, va "
                            "khong bao gio ghi de mot checksum da co.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Voi --to: in ra cac cau mot chieu se chay, roi thoat.")
    parser.add_argument("--force", action="store_true",
                        help="Voi --adopt: dong dau ke ca khi luoc do con thieu doi tuong.")
    parser.add_argument("--note", help="Ghi vao so dang ba cung voi lan dong dau nay.")
    args = parser.parse_args(argv)

    try:
        if args.status:
            return cmd_status()

        # Chốt chặn 1, và nó nằm ở ĐÂY chứ không ở `_assert_expected_database`.
        #
        # Hàm kia chỉ kiểm khi biến ĐƯỢC ĐẶT, và phải như vậy: nó cũng chạy ở
        # mỗi lần backend khởi động, nơi một chốt chặn luôn-bật sẽ chặn cả
        # đường đúng. Nhưng lệnh này thì khác — mỗi lần chạy là một quyết định,
        # và cái thiếu hôm 12/08 không phải là một phép so sánh, mà là việc
        # người gõ lệnh phải NÓI RA họ đang nhắm vào cơ sở dữ liệu nào.
        #
        # `--dry-run` cũng phải khai đích: nó in ra "sẽ chạy gì trên DB nào", và
        # một bản xem trước của nhầm cơ sở dữ liệu là thứ trấn an sai.
        missing_target = not (os.getenv(EXPECTED_DATABASE_ENV) or "").strip()
        if missing_target:
            print(
                f"TU CHOI: chua dat {EXPECTED_DATABASE_ENV}.\n"
                f"Lenh nay doi luoc do, nen no phai biet ban NHAM VAO dau:\n"
                f"    {EXPECTED_DATABASE_ENV}=signdb python -m app.cli.migrate "
                f"--to {APP_SCHEMA_VERSION}\n"
                f"(dung --status de chi hoi ma khong doi gi — lenh do khong can bien nay)"
            )
            return 2

        if args.adopt_checksum:
            return cmd_adopt_checksum()
        if args.adopt:
            return cmd_adopt(force=args.force)
        return cmd_migrate(args.to, dry_run=args.dry_run, note=args.note)
    except SchemaVersionError as exc:
        print(f"TU CHOI: {exc}")
        return 2
    except Exception as exc:
        logger.exception("[MIGRATE][THAT BAI] %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

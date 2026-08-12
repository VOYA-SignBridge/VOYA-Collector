"""Post-deploy check: is this machine's data actually consistent and protected?

Run it inside the backend container after a `git pull` + rebuild + restore:

    docker exec voya_backend python -m app.cli.verify_deployment

Exit code 0 = everything green, 1 = at least one FAIL. Read-only: it changes
nothing, so it is safe to run against production at any time.

Why this exists rather than "it started, so it worked":

  * ensure_tables() swallows every DDL failure by design, so one bad statement
    cannot block startup. The cost is that a missing table or an unapplied
    constraint looks identical to success in the logs. A missing comma in the
    classes DDL once produced a database with no classes table at all, and
    nothing in the boot sequence said so.

  * Postgres will not add a CHECK/FK/unique index that existing rows already
    violate. On a database with pre-existing bad rows the integrity constraints
    silently never apply -- measured: 4 of 5 absent on a dirty database.

  * sync_missing_data_on_startup() copies CSV -> Postgres whenever the DB has
    FEWER rows than the CSV. If the CSV mirrors are stale, the next restart
    resurrects rows that were deliberately deleted. Row counts drifting apart
    is therefore not cosmetic; it is a pending rollback of your cleanup.

  * file_path points at .npz files on disk. A database restored without its
    dataset/ tree looks perfectly healthy in SQL and fails on every preview,
    download and training run.
"""

from __future__ import annotations

import csv
import sys

from app.tenant_context import platform_command

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


@platform_command("cli: verify deployment")
def main() -> int:
    try:
        from app.storage.metadata_db import _fetch_all, verify_integrity_constraints
    except Exception as exc:  # pragma: no cover - import guard
        print(f"FAIL  khong import duoc app.storage.metadata_db: {exc}")
        print("      Chay trong container backend voi PYTHONPATH=/app.")
        return 1

    def scalar(sql: str):
        return list(_fetch_all(sql)[0].values())[0]

    # ---- 0. phien ban luoc do vs ANH DANG CHAY ---------------------------
    #
    # Kiểm ĐẦU TIÊN, vì nó quyết định mọi kết luận bên dưới có nghĩa hay không.
    # Mọi mục còn lại đọc lược đồ và so với thứ mã này kỳ vọng — nếu hai bên
    # không cùng phiên bản thì một dòng "PASS" chỉ có nghĩa "khớp với kỳ vọng
    # SAI", và đó tệ hơn một dòng FAIL.
    #
    # Câu hỏi ở đây không phải "cơ sở dữ liệu đã migrate chưa" mà là **ảnh này
    # có chạy được trên lược đồ này không**, hai chiều. Sự cố 12/08/2026 nằm ở
    # chiều ít ai nghĩ tới: lược đồ MỚI hơn ảnh.
    try:
        from app.storage.metadata_db import _migration_cursor
        from app.storage.schema_version import (
            APP_SCHEMA_VERSION, MIN_SUPPORTED_SCHEMA_VERSION,
            compatibility_error, read_schema_version,
        )

        with _migration_cursor() as cur:
            db_version = read_schema_version(cur)
        problem = compatibility_error(db_version)
        window = f"anh ho tro v{MIN_SUPPORTED_SCHEMA_VERSION}..v{APP_SCHEMA_VERSION}"
        shown = db_version if db_version is not None else "chua dong dau"

        if problem is None:
            record(PASS, "phien ban luoc do", f"DB v{db_version}, {window}")
        else:
            record(FAIL, "phien ban luoc do",
                   f"DB {shown}, {window} — "
                   f"{' '.join(str(problem).split())[:160]}")
    except Exception as exc:
        record(WARN, "phien ban luoc do", f"khong kiem tra duoc: {exc}")

    # ---- 0b. noi dung migration co con nguyen nhu luc ap dung -------------
    #
    # Phiên bản khớp KHÔNG có nghĩa nội dung khớp. Hai máy cùng mang nhãn v5 mà
    # đi qua hai payload khác nhau sẽ giống hệt nhau ở mọi phép kiểm cấu trúc
    # bên dưới — số bảng, ràng buộc, trigger đều đúng — trong khi dữ liệu đã
    # được biến đổi khác nhau. Đây là chỗ duy nhất trong toàn bộ báo cáo này
    # nhìn thấy sự khác biệt đó.
    try:
        from app.storage.metadata_db import _migration_cursor
        from app.storage.schema_version import (
            MigrationChecksumMismatch, checksum_problem, migration_checksum,
            migration_payload, read_recorded_checksum,
        )

        with _migration_cursor() as cur:
            _, recorded, has_column = read_recorded_checksum(cur)
            ck_problem = checksum_problem(cur)
        current = migration_checksum()
        n_stmt = len(migration_payload())

        if ck_problem is None:
            record(PASS, "checksum migration",
                   f"{n_stmt} cau mot chieu, {current[:16]}… khop")
        elif isinstance(ck_problem, MigrationChecksumMismatch):
            record(FAIL, "checksum migration",
                   f"NOI DUNG DA DOI sau khi ap dung — ghi {str(recorded)[:16]}… "
                   f"nhung hien tai {current[:16]}…")
        else:
            record(FAIL, "checksum migration",
                   "chua xac nhan — chay `python -m app.cli.migrate --adopt-checksum`")
    except Exception as exc:
        record(WARN, "checksum migration", f"khong kiem tra duoc: {exc}")

    # ---- 1. tables ------------------------------------------------------
    expected_tables = {
        "users", "classes", "samples", "raw_uploads", "training_jobs",
        "training_metrics", "google_sheets_sync_status", "password_reset_tokens",
        "refresh_tokens", "sot_authorized_keys",
    }
    have = {r["table_name"] for r in _fetch_all(
        "SELECT table_name FROM information_schema.tables WHERE table_schema='public'")}
    missing_tables = sorted(expected_tables - have)
    record(FAIL if missing_tables else PASS, "bang du",
           f"thieu: {', '.join(missing_tables)}" if missing_tables
           else f"{len(expected_tables)}/{len(expected_tables)}")

    # ---- 2. integrity constraints in force ------------------------------
    missing = verify_integrity_constraints()
    record(FAIL if missing else PASS, "rang buoc toan ven",
           f"thieu {len(missing)}: {', '.join(missing)}" if missing else "5/5 co hieu luc")

    # ---- 2b. tenant_id actually references a tenant ----------------------
    # The migration that adds these is wrapped in a warning-and-continue, so
    # "ensure_tables ran" does not mean "the constraint is here". Ask the
    # catalogue instead of trusting the boot log.
    try:
        from app.storage.metadata_db import (
            TENANT_SCOPED_TABLES, missing_tenant_foreign_keys,
        )
        unguarded = missing_tenant_foreign_keys()
        record(FAIL if unguarded else PASS, "khoa ngoai tenant_id",
               f"thieu {len(unguarded)}: {', '.join(unguarded)}" if unguarded
               else f"{len(TENANT_SCOPED_TABLES)}/{len(TENANT_SCOPED_TABLES)} bang duoc bao ve")
    except Exception as exc:
        record(WARN, "khoa ngoai tenant_id", f"khong kiem tra duoc: {exc}")

    # ---- 2c. row-level security actually in force ------------------------
    # A foreign key on tenant_id proves the column points somewhere real. It
    # proves NOTHING about whether a query is filtered by it — that is the
    # policy, and until this check existed the deploy verifier reported a green
    # tenant posture while every query returned every tenant's rows.
    #
    # Two separate failures, deliberately reported apart:
    #   - policies missing  -> nothing is enforced
    #   - policies present but the connected role bypasses them -> worse, because
    #     pg_policies and pg_tables.rowsecurity both say isolation is active
    try:
        from app.storage.metadata_db import _cursor
        from app.storage.rls import RLS_TABLES, isolation_posture

        with _cursor() as cur:
            posture = isolation_posture(cur.connection)

        enabled = set(posture["rls_tables"])
        absent = sorted(set(RLS_TABLES) - enabled)
        record(FAIL if absent else PASS, "RLS bat tren bang",
               f"thieu {len(absent)}: {', '.join(absent)}" if absent
               else f"{len(RLS_TABLES)}/{len(RLS_TABLES)} bang")

        record(FAIL if posture["policies_are_theatre"] else PASS, "RLS co hieu luc",
               f"role {posture['role']} bo qua policy (superuser={posture['is_superuser']}, "
               f"bypassrls={posture['bypasses_rls']}) - doi DATABASE_URL sang voya_app"
               if posture["policies_are_theatre"]
               else f"role {posture['role']} bi rang buoc")
    except Exception as exc:
        record(WARN, "RLS", f"khong kiem tra duoc: {exc}")

    # ---- 2c-bis. mặt phẳng phân quyền (PDM v1.0 + Casbin) ---------------
    #
    # Ba phép kiểm cho ba cách nó có thể "chạy" mà không bảo vệ gì:
    #
    #   schema thiếu   `_run_ddl` nuốt lỗi, nên một bảng hay trigger không ra
    #                  đời chỉ để lại một dòng WARNING lúc khởi động. Thiếu
    #                  trigger dominance nghĩa là role phạm vi PROJECT cầm
    #                  được quyền phạm vi TENANT — leo thang, im lặng.
    #
    #   chưa backfill  Schema đủ nhưng không ai có assignment nào. Ở chế độ
    #                  `casbin` thì đó là toàn bộ hệ thống trả 403; ở `shadow`
    #                  thì đó là một biển mismatch ALLOW->DENY.
    #
    #   policy chưa nạp  Ở chế độ `casbin` là hỏng-thì-đóng (tiến trình đáng lẽ
    #                  không khởi động nổi). Kiểm lại ở đây vì lệnh này chạy
    #                  trong một tiến trình KHÁC tiến trình API.
    try:
        from app.config import settings
        from app.storage.authz_schema import missing_objects
        from app.storage.metadata_db import _cursor, _fetch_all
        from app.tenant_context import system_scope

        with _cursor() as cur:
            missing_authz = missing_objects(cur.connection)
        record(FAIL if missing_authz else PASS, "schema phan quyen",
               f"thieu {len(missing_authz)}: {'; '.join(missing_authz[:4])}"
               if missing_authz else "day du")

        with system_scope("verify: dem assignment phan quyen"):
            counts = _fetch_all(
                "SELECT (SELECT count(*) FROM permissions WHERE is_active) AS perms, "
                "       (SELECT count(*) FROM roles WHERE is_builtin AND is_active) AS roles, "
                # v5: MỘT bảng gán, phạm vi đọc từ membership nó trỏ tới.
                # `membership_id IS NULL` = phạm vi hệ thống.
                "       (SELECT count(*) FROM role_assignments "
                "         WHERE revoked_at IS NULL AND membership_id IS NOT NULL) "
                "         AS tenant_grants, "
                "       (SELECT count(*) FROM role_assignments "
                "         WHERE revoked_at IS NULL AND membership_id IS NULL) "
                "         AS system_grants, "
                "       (SELECT count(*) FROM users WHERE is_admin AND is_active) AS legacy_admins, "
                # `role IS NOT NULL`, và đó là cả nội dung của phép đếm này.
                # Thành viên không vai (tư cách có, vai ở tầng tenant không —
                # xem `catalog.RETIRED_BUILTIN_ROLES`) KHÔNG sinh assignment
                # nào, đúng thiết kế. Đếm họ vào vế "quyền cũ" làm phép so sánh
                # bên dưới báo "backfill chưa chạy" vĩnh viễn, và lời khuyên
                # kèm theo — chạy lại backfill — không bao giờ làm con số khớp.
                "       (SELECT count(*) FROM tenant_members "
                "         WHERE status = 'ACTIVE' AND removed_at IS NULL "
                "           AND role IS NOT NULL) AS legacy_members"
            )[0]

        # So HAI vế của cùng một sự thật. Một hệ đã backfill phải có ít nhất
        # một assignment cho mỗi quyền cũ; lệch nghĩa là backfill chưa chạy
        # hoặc chạy dở.
        behind = (counts["system_grants"] < counts["legacy_admins"]
                  or counts["tenant_grants"] < counts["legacy_members"])
        record(FAIL if behind else PASS, "backfill phan quyen",
               f"RBAC moi: {counts['system_grants']} he thong / "
               f"{counts['tenant_grants']} tenant; quyen cu: "
               f"{counts['legacy_admins']} is_admin / {counts['legacy_members']} thanh vien co vai"
               + (" - chay `python -m app.cli.backfill_authz --actor <ai do> --apply`"
                  if behind else ""),
               )

        record(PASS, "danh muc quyen",
               f"{counts['perms']} quyen, {counts['roles']} role dung san")

        mode = getattr(settings, "authz_mode", "shadow")
        if mode == "legacy":
            record(WARN, "che do phan quyen",
                   "AUTHZ_MODE=legacy - Casbin khong chay, khong co du lieu so sanh")
        else:
            from app.authorization import enforcer as authz_enforcer

            authz_enforcer.reload_policy(reason="verify_deployment")
            state = authz_enforcer.status()
            ok = state["ready"]
            record(FAIL if (not ok and mode == "casbin") else (PASS if ok else WARN),
                   "policy Casbin",
                   f"mode={mode} " + (
                       f"the he {state['generation']}, {state['policy']}" if ok
                       else f"CHUA NAP: {state['error']}"))
    except Exception as exc:
        record(WARN, "phan quyen", f"khong kiem tra duoc: {exc}")

    # ---- 2d. văn bản pháp lý đã công bố ---------------------------------
    # Cưỡng chế chấp thuận BẬT bằng cách công bố văn bản (xem
    # routers/auth.py:_validate_consents). Nghĩa là "quên công bố" trông giống
    # hệt "chạy bình thường" — tài khoản vẫn tạo được, chỉ là không thu chấp
    # thuận nào. Phép kiểm này là chỗ duy nhất tình trạng đó lộ ra trước khi có
    # người hỏi bằng chứng.
    try:
        from app import legal

        missing_legal = legal.missing_for_registration()
        record(FAIL if missing_legal else PASS, "van ban phap ly",
               f"chua cong bo: {', '.join(missing_legal)} - dang ky KHONG thu "
               f"chap thuan. Chay: python -m app.cli.register_legal_document"
               if missing_legal
               else f"{len(legal.REQUIRED_AT_REGISTRATION)}/"
                    f"{len(legal.REQUIRED_AT_REGISTRATION)} da cong bo")
    except Exception as exc:
        record(WARN, "van ban phap ly", f"khong kiem tra duoc: {exc}")

    # ---- 2d-bis. kho văn bản đọc lại được (v5) --------------------------
    #
    # Công bố xong chưa đủ. Một dòng chấp thuận trỏ tới `(kind, version)`, nên
    # nếu bản văn ứng với cặp đó không đọc lại được thì dòng ấy chỉ là một con
    # số. Đúng tình trạng đó đã tồn tại suốt thời v1..v4: `register_document`
    # băm nội dung rồi vứt, và `url` trỏ tới một file tĩnh chưa từng tồn tại.
    #
    # Hai phép kiểm dưới đây bắt hai kiểu hỏng khác nhau: dòng có mà thân rỗng
    # (di sản v1, hoặc một lần công bố đi vòng qua `register_document`), và
    # thân có mà băm không khớp (bảng đã bị sửa tay).
    try:
        from app import legal
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        with system_scope("verify: kho van ban phap ly"):
            rows = _fetch_all(
                "SELECT kind, version, body, content_hash FROM legal_documents")

        empty = [f"{r['kind']}:{r['version']}" for r in rows if not (r["body"] or "").strip()]
        mismatched = [
            f"{r['kind']}:{r['version']}" for r in rows
            if (r["body"] or "").strip()
            and legal.content_hash(r["body"]) != r["content_hash"]
        ]

        if not rows:
            record(WARN, "than van ban", "chua co ban nao de kiem")
        elif empty:
            record(FAIL, "than van ban",
                   f"{len(empty)} ban KHONG co noi dung: {', '.join(empty[:3])}"
                   f" - nguoi dung khong doc lai duoc ban ho da ky")
        elif mismatched:
            record(FAIL, "than van ban",
                   f"{len(mismatched)} ban co hash KHONG khop noi dung: "
                   f"{', '.join(mismatched[:3])} - bang da bi sua tay")
        else:
            record(PASS, "than van ban",
                   f"{len(rows)} ban, than day du va hash khop")
    except Exception as exc:
        record(WARN, "than van ban", f"khong kiem tra duoc: {exc}")

    # ---- 2d-ter. kho tài liệu trên đĩa (v6) -----------------------------
    #
    # Phép kiểm RIÊNG, không gộp vào chuỗi trên: nó hỏi một câu khác. Ở trên là
    # "bản hồ sơ trong bảng có nguyên vẹn không"; ở đây là "bản tài liệu trên
    # đĩa có còn không, và có đúng là cùng một thứ không".
    #
    # Kiểu hỏng mà nó bắt: khôi phục một `pg_dump` mà quên mang theo thư mục
    # `dataset/legal`. Bảng đầy đủ, mọi con trỏ đều có, và không đường nào trong
    # ứng dụng phát hiện ra cho tới khi có người bấm vào một tài liệu.
    try:
        from app import legal_store
        from app.storage.metadata_db import _fetch_all
        from app.tenant_context import system_scope

        with system_scope("verify: kho tai lieu tren dia"):
            docs = _fetch_all(
                "SELECT kind, version, storage_key, content_hash "
                "FROM legal_documents")

        pointed = [r for r in docs if r["storage_key"]]
        broken = [f"{r['kind']}:{r['version']}" for r in pointed
                  if not legal_store.verify(r["storage_key"], r["content_hash"])]

        if not docs:
            record(WARN, "kho tai lieu", "chua co ban nao de kiem")
        elif broken:
            record(FAIL, "kho tai lieu",
                   f"{len(broken)} ban co con tro HONG: {', '.join(broken[:3])} "
                   f"- thieu thu muc {legal_store.store_root()}?")
        elif len(pointed) < len(docs):
            record(WARN, "kho tai lieu",
                   f"{len(docs) - len(pointed)}/{len(docs)} ban chua co tep - "
                   f"chay: python -m app.cli.legal_store --backfill")
        else:
            record(PASS, "kho tai lieu",
                   f"{len(pointed)}/{len(docs)} ban co tep va khop hash")
    except Exception as exc:
        record(WARN, "kho tai lieu", f"khong kiem tra duoc: {exc}")

    # ---- 2e. mặt phẳng thương mại (v4) ----------------------------------
    #
    # Ba phép kiểm, mỗi phép cho một kiểu hỏng KHÔNG tự lộ ra:
    #
    #   * Bảng giá trống → `plan_for_tenant` rơi về nhánh dự phòng và áp hạn
    #     mức bằng 0 cho tất cả. Mọi đường ghi đóng lại, và thông báo cho người
    #     dùng là "gói Không xác định" — không ai đoán được nguyên nhân thật.
    #   * Tenant không gói → nó đi qua MỌI cổng hạn mức mà không bị hỏi gì.
    #     Ngược lại với trường hợp trên, và tệ hơn: không có triệu chứng nào.
    #   * Tenant không có đăng ký đang mở → lịch sử gói bắt đầu từ hư không, và
    #     một tranh chấp hoá đơn không trả lời được.
    try:
        n_plans = scalar("SELECT count(*) FROM plans")
        record(FAIL if n_plans == 0 else PASS, "bang gia",
               "TRONG - moi tenant se bi ap han muc 0" if n_plans == 0
               else f"{n_plans} goi")

        no_plan = scalar(
            "SELECT count(*) FROM tenants WHERE deleted_at IS NULL AND plan_code IS NULL"
        )
        record(FAIL if no_plan else PASS, "tenant co goi",
               f"{no_plan} tenant khong co goi - di qua moi cong han muc"
               if no_plan else "tat ca deu co goi")

        no_sub = scalar(
            "SELECT count(*) FROM tenants t WHERE t.deleted_at IS NULL AND NOT EXISTS ("
            "  SELECT 1 FROM tenant_subscriptions s"
            "  WHERE s.tenant_id = t.tenant_id AND s.ended_at IS NULL)"
        )
        record(WARN if no_sub else PASS, "lich su goi",
               f"{no_sub} tenant khong co dang ky dang mo" if no_sub
               else "moi tenant co dung mot dang ky dang mo")
    except Exception as exc:
        record(WARN, "mat phang thuong mai", f"khong kiem tra duoc: {exc}")

    # ---- 2f. số đo mức dùng đã được lấp chưa -----------------------------
    #
    # WARN chứ không FAIL: bảng trống không làm hỏng gì, nhưng nó khiến trang
    # "Mức dùng" hiện biểu đồ rỗng và trông như tính năng hỏng. Đây cũng là
    # triệu chứng của một lỗi thật đã gặp — `_upsert` chạy ngoài `system_scope`
    # bị RLS từ chối, và tác vụ nền ghi ra số không mỗi giờ mà chỉ để lại một
    # dòng log không ai đọc.
    try:
        n_usage = scalar("SELECT count(*) FROM tenant_usage_daily")
        record(WARN if n_usage == 0 else PASS, "so do muc dung",
               "TRONG - chay: python -m app.cli.backfill_usage --days 400"
               if n_usage == 0 else f"{n_usage} hang")
    except Exception as exc:
        record(WARN, "so do muc dung", f"khong kiem tra duoc: {exc}")

    # ---- 3. data quality -------------------------------------------------
    # left(...) rather than LIKE 'http%': _fetch_all always hands psycopg2 a
    # params tuple, which turns on placeholder parsing, and a bare % in the SQL
    # then dies as a malformed placeholder.
    checks = [
        ("uid sai dinh dang", "SELECT count(*) FROM samples WHERE sample_uid !~ '^[0-9a-f]{10}$'"),
        ("file_path la URL", "SELECT count(*) FROM samples WHERE left(file_path, 4) = 'http'"),
        ("mau mo coi",
         "SELECT count(*) FROM samples s LEFT JOIN classes c ON c.class_uid=s.class_uid "
         "WHERE s.class_uid IS NOT NULL AND c.class_uid IS NULL"),
        ("thieu created_at", "SELECT count(*) FROM samples WHERE created_at IS NULL"),
    ]
    for label, sql in checks:
        n = scalar(sql)
        record(PASS if n == 0 else FAIL, label, f"{n} hang")

    # ---- 4. CSV mirrors vs DB (startup sync would undo cleanup) ----------
    n_classes = scalar("SELECT count(*) FROM classes")
    n_samples = scalar("SELECT count(*) FROM samples")
    for label, path, db_n in (
        ("labels.csv vs classes", "/dataset/labels.csv", n_classes),
        ("samples.csv vs samples", "/dataset/samples.csv", n_samples),
    ):
        try:
            with open(path, newline="", encoding="utf-8-sig") as fh:
                csv_n = sum(1 for _ in csv.DictReader(fh))
        except FileNotFoundError:
            record(WARN, label, f"khong thay {path}")
            continue
        if csv_n == db_n:
            record(PASS, label, f"{csv_n} = {db_n}")
        elif csv_n > db_n:
            record(FAIL, label,
                   f"CSV {csv_n} > DB {db_n} — startup sync se NAP LAI {csv_n - db_n} hang da xoa")
        else:
            record(WARN, label, f"CSV {csv_n} < DB {db_n} — CSV thieu du lieu, export lai")

    # ---- 4b. vocabulary registry vs the data (T1 / T2 / T5) --------------
    # Runs HERE and not only in CI because this is the machine where the two
    # drift apart: a merge task that stopped halfway leaves the catalogue
    # pointing one way and the directories another, and nobody spots that by eye.
    try:
        known = {r["dialect_id"] for r in _fetch_all("SELECT dialect_id FROM dialects")}
        known |= {r["old_dialect_id"] for r in _fetch_all(
            "SELECT old_dialect_id FROM dialect_aliases")}
        used = {r["dialect"] for r in _fetch_all(
            "SELECT DISTINCT dialect FROM classes WHERE dialect IS NOT NULL AND dialect <> ''")}
        orphan = sorted(used - known)
        record(PASS if not orphan else FAIL, "phuong ngu mo coi",
               "khong co" if not orphan else f"{orphan} — co trong du lieu, khong co trong danh muc")

        # `%%`, không phải `%`. `_fetch_all` truyền `params=()` mặc định, và một
        # dãy rỗng vẫn KHÁC `None`, nên psycopg2 vẫn chạy bước nội suy chuỗi và
        # nghẹn ở dấu `%` của `LIKE` với `IndexError: tuple index out of range`.
        #
        # Ngoại lệ đó rơi vào `except` bên dưới và biến thành một dòng WARN
        # "chua kiem duoc" — nên phép kiểm này CHƯA TỪNG chạy, và không ai biết
        # vì báo cáo vẫn có một dòng cho nó.
        mism = _fetch_all(
            "SELECT count(*) AS c FROM samples WHERE file_path LIKE 'features/%%' "
            "AND file_path NOT LIKE '%%/' || dialect || '/%%'")
        bad = int(mism[0]["c"]) if mism else 0
        record(PASS if bad == 0 else FAIL, "duong dan khop phuong ngu",
               "khop het" if bad == 0 else f"{bad} hang co file_path khong khop cot dialect "
                                           f"— task gop co the da dung giua chung")
    except Exception as exc:
        record(WARN, "danh muc phuong ngu", f"chua kiem duoc: {exc}")

    # ---- 5. do the .npz actually exist on this machine? ------------------
    #
    # `file_path` trong bảng là đường TƯƠNG ĐỐI so với gốc dataset
    # (`features/vn/…/sample.npz`), không phải đường tuyệt đối. Bản đầu của phép
    # kiểm này gọi thẳng `os.path.exists(file_path)`, tức là phân giải theo thư
    # mục làm việc của tiến trình — trong container là `/app`, nơi không có
    # `features/` nào. Kết quả: nó báo ĐỎ "3860/3860 thiếu" trên một máy có đủ
    # 3860 tệp.
    #
    # Đó là kiểu hỏng tệ hơn cả không kiểm: một cổng triển khai báo động giả ở
    # quy mô đó sẽ dạy người vận hành bỏ qua nó, và lần nó nói thật thì cũng bị
    # bỏ qua nốt.
    #
    # Dùng `resolve_absolute_path` chứ không tự nối `DATASET_ROOT / file_path`:
    # bản có sẵn ấy đã xử lý cả dữ liệu CŨ mang đường tuyệt đối, và một bản thứ
    # hai chỉ chờ ngày trôi ra khỏi bản gốc.
    from app.storage.metadata_db import resolve_absolute_path

    rows = _fetch_all("SELECT file_path FROM samples WHERE file_path IS NOT NULL AND file_path <> ''")
    gone = [r["file_path"] for r in rows
            if not resolve_absolute_path(r["file_path"]).exists()]
    if not rows:
        record(WARN, "file .npz tren dia", "khong co hang nao de kiem")
    elif gone:
        record(FAIL, "file .npz tren dia",
               f"{len(gone)}/{len(rows)} thieu — vd: {gone[0]}. Copy thu muc dataset/features sang may nay.")
    else:
        record(PASS, "file .npz tren dia", f"{len(rows)}/{len(rows)} co mat")

    # ---- 6. class_idx sane for training ----------------------------------
    n_idx = scalar("SELECT count(DISTINCT class_idx) FROM classes WHERE class_idx IS NOT NULL")
    n_cls = scalar("SELECT count(*) FROM classes")
    record(PASS if n_idx == n_cls else FAIL, "class_idx duy nhat", f"{n_idx} idx / {n_cls} lop")

    empty = scalar(
        "SELECT count(*) FROM (SELECT c.class_uid FROM classes c "
        "LEFT JOIN samples s ON s.class_uid = c.class_uid "
        "GROUP BY c.class_uid HAVING count(s.sample_uid) = 0) d")
    record(WARN if empty else PASS, "lop rong",
           f"{empty} lop khong co mau — moi lop van chiem 1 o dau ra cua model" if empty else "0")

    # ---- 7. room left on the data volume ---------------------------------
    #
    # `sync_tasks._disk_over_watermark()` stops downloading missing files at
    # 95%, deliberately, to protect the database and the filesystem. Nothing
    # told the operator that had happened: the task returns `stopped_disk_full`
    # into a Celery result nobody reads, and the symptom that reaches a human
    # is "some previews are broken".
    #
    # Measured 2026-08-09: the data volume was at 96% and the sweep had been
    # refusing to download for an unknown length of time. It surfaced only
    # because two unrelated tests went red.
    #
    # The threshold here is the SAME constant the backpressure uses — two
    # numbers that mean "the disk is full" will drift, and the day they do, the
    # check that says green is the one the operator will believe.
    try:
        import shutil

        from app.config import settings as _settings
        from app.monitoring import DISK_CRIT_PCT, DISK_WARN_PCT

        usage = shutil.disk_usage(str(_settings.dataset_root))
        pct = 100.0 * usage.used / usage.total if usage.total else 0.0
        free_gb = usage.free / (1024 ** 3)
        detail = f"{pct:.1f}% da dung, con {free_gb:.1f} GB"
        if pct >= DISK_CRIT_PCT:
            record(FAIL, "cho trong o du lieu",
                   f"{detail} — dong bo Drive DA NGUNG tai file (backpressure)")
        elif pct >= DISK_WARN_PCT:
            record(WARN, "cho trong o du lieu",
                   f"{detail} — qua nguong canh bao {DISK_WARN_PCT:.0f}%, "
                   f"dong bo dung o {DISK_CRIT_PCT:.0f}%")
        else:
            record(PASS, "cho trong o du lieu", detail)
    except Exception as exc:
        record(WARN, "cho trong o du lieu", f"khong kiem tra duoc: {exc}")

    # ---- 8. the stack was brought up WITH its production overlay ----------
    #
    # `docker-compose.yml` mot minh KHONG dat mem_limit cho dich vu nao;
    # `docker-compose.prod.yml` moi dat. Tren may 12 GB nay, mot container
    # khong tran bo nho la dieu da tung giet dockerd mot lan (xem
    # docs/KNOWN_ISSUES.md), va no khong de lai trieu chung nao cho toi luc do.
    #
    # Do bang cgroup CUA CHINH MINH thay vi hoi docker: container nay khong co
    # docker socket, va mot phep do tu ben trong khong the bi lech so voi thuc
    # te dang chay. cgroup v2 ghi "max" khi khong gioi han; v1 ghi mot so rat
    # lon (thuong 2^63 lam tron theo page size).
    def _self_mem_limit_bytes():
        for path in ("/sys/fs/cgroup/memory.max",
                     "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
            try:
                with open(path) as fh:
                    raw = fh.read().strip()
            except OSError:
                continue
            if raw == "max":
                return None
            try:
                value = int(raw)
            except ValueError:
                continue
            # Nguong 1 PB: bat ca "max" cua v2 lan so khong-tuong cua v1.
            return None if value >= (1 << 50) else value
        return 0  # khong doc duoc cgroup nao — khong ket luan duoc

    limit = _self_mem_limit_bytes()
    if limit is None:
        record(FAIL, "gioi han bo nho container",
               "backend chay KHONG gioi han bo nho — stack duoc dung thieu "
               "docker-compose.prod.yml. Trien khai lai bang scripts/deploy.sh")
    elif limit == 0:
        record(WARN, "gioi han bo nho container", "khong doc duoc cgroup")
    else:
        record(PASS, "gioi han bo nho container", f"{limit / (1024 ** 2):.0f} MB")

    # ---- 9. GPU: noi RO nguyen nhan, khong chi noi "khong co" -------------
    #
    # Canh bao cu gui di mot cau duy nhat cho moi nguyen nhan — "Nvidia GPU is
    # missing or unreadable" — nen ngay 2026-08-09 no bao di tim cai card dang
    # nam yen trong may, trong khi loi that la stack dung thieu overlay GPU.
    try:
        from app.monitoring import read_gpu_snapshot

        snap = read_gpu_snapshot()
        if not snap.get("available"):
            record(WARN, "GPU", f"{snap.get('reason')}: {snap.get('hint', '')}")
        else:
            head = (f"{snap.get('name') or 'GPU'} — "
                    f"{snap.get('vram_total_mb', 0):.0f} MB VRAM, "
                    f"{snap.get('compute_capability') or '?'}")
            supported = snap.get("torch_supports_this_gpu")
            if supported is False:
                # Con duong hong am tham nhat: card co that, driver co that,
                # `nvidia-smi` dep de — va lan phong kernel dau tien chet giua
                # buoi huan luyen. `pick_device` lui ve CPU nen job VAN chay,
                # chi la cham gap nhieu lan va khong ai duoc bao.
                record(FAIL, "GPU",
                       f"{head} — torch {snap.get('torch_version')} KHONG co kernel "
                       f"cho chip nay (co: {snap.get('torch_arch_list')}). Huan luyen "
                       f"se lui ve CPU. Cai wheel torch co "
                       f"{snap.get('compute_capability')}.")
            elif supported is None:
                record(WARN, "GPU", f"{head} — chua xac dinh duoc torch co dung "
                                    f"duoc chip nay khong")
            else:
                record(PASS, "GPU", f"{head}, torch {snap.get('torch_version')} OK")
    except Exception as exc:
        record(WARN, "GPU", f"khong kiem tra duoc: {exc}")

    # ---- 10. quy ket nguoi dong gop ---------------------------------------
    #
    # Mot mau khong co `signer_id` la mot mau khong truy duoc ve nguoi co ban
    # tay trong do. Hai he qua, va ca hai deu that:
    #
    #   * Ai do noi "toi rut phan dong gop cua toi" thi he thong khong xac dinh
    #     noi do la nhung dong nao.
    #   * Cong dong thuan (app/consent_gate.py) loai HET nhung dong do khoi moi
    #     ban phat hanh — dung y, nhung nghia la con so duoi day chinh la phan
    #     kho du lieu khong bao gio ra khoi nha duoc.
    #
    # Do 2026-08-09: 1.674/3.860 mau co signer_id (43,4%), 4 nguoi ky phan biet.
    # Con so nay khong tu tot len; no chi tot len khi co nguoi di dien lai. Dat
    # o day de no duoc nhin thay moi lan trien khai thay vi nam trong mot ban
    # bao cao doc mot lan roi thoi.
    total_samples = scalar("SELECT count(*) FROM samples")
    with_signer = scalar("SELECT count(*) FROM samples WHERE signer_id IS NOT NULL AND signer_id <> ''")
    n_signers = scalar("SELECT count(DISTINCT signer_id) FROM samples "
                       "WHERE signer_id IS NOT NULL AND signer_id <> ''")
    if not total_samples:
        record(PASS, "quy ket nguoi dong gop", "chua co mau nao")
    else:
        pct = 100.0 * with_signer / total_samples
        detail = (f"{with_signer}/{total_samples} mau co signer_id ({pct:.1f}%), "
                  f"{n_signers} nguoi ky phan biet")
        if pct < 60.0:
            record(WARN, "quy ket nguoi dong gop",
                   f"{detail} — phan con lai KHONG phat hanh duoc va khong thi "
                   f"hanh duoc loi rut dong thuan")
        else:
            record(PASS, "quy ket nguoi dong gop", detail)

    # ---- 11. anh chup dong thuan con han ----------------------------------
    #
    # Script offline TU CHOI chay khi anh chup qua han, nen mot anh chup het han
    # khong lam hong gi ca — no lam DUNG mot viec: chan lai. Nhung no chan luc
    # nguoi ta dang chuan bi phat hanh, va do la luc te nhat de phat hien.
    try:
        from pathlib import Path as _Path

        from app.config import settings as _settings
        from app.consent_gate import SnapshotUnusable, load_snapshot

        snap_path = _Path(_settings.dataset_root) / "consent_snapshot.json"
        try:
            consents, _al, meta = load_snapshot(snap_path)
            record(PASS, "anh chup dong thuan",
                   f"{len(consents)} nguoi ky, tao luc {meta.get('generated_at')}")
        except SnapshotUnusable as exc:
            record(WARN, "anh chup dong thuan", str(exc).split(".")[0])
    except Exception as exc:
        record(WARN, "anh chup dong thuan", f"khong kiem tra duoc: {exc}")

    # ---- report ----------------------------------------------------------
    width = max(len(n) for _, n, _ in results)
    print()
    for status, name, detail in results:
        print(f"  {status:5} {name:<{width}}  {detail}")
    n_fail = sum(1 for s, _, _ in results if s == FAIL)
    n_warn = sum(1 for s, _, _ in results if s == WARN)
    print(f"\n  {len(results) - n_fail - n_warn} PASS / {n_warn} WARN / {n_fail} FAIL")
    if n_fail:
        print("  -> Con loi phai xu ly truoc khi tin vao trien khai nay.")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())

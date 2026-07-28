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
import os
import sys

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
results: list[tuple[str, str, str]] = []


def record(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def main() -> int:
    try:
        from app.storage.metadata_db import _fetch_all, verify_integrity_constraints
    except Exception as exc:  # pragma: no cover - import guard
        print(f"FAIL  khong import duoc app.storage.metadata_db: {exc}")
        print("      Chay trong container backend voi PYTHONPATH=/app.")
        return 1

    def scalar(sql: str):
        return list(_fetch_all(sql)[0].values())[0]

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
        ("samples.csv vs samples", "/dataset/samples/samples.csv", n_samples),
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

    # ---- 5. do the .npz actually exist on this machine? ------------------
    rows = _fetch_all("SELECT file_path FROM samples WHERE file_path IS NOT NULL AND file_path <> ''")
    gone = [r["file_path"] for r in rows if not os.path.exists(r["file_path"])]
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

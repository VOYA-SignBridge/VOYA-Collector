"""Reconstruct samples.auth_user_id for rows that arrived through a CSV.

WHY THIS EXISTS
---------------
`samples.csv` had no `auth_user_id` column until 2026-08-01. Every row imported
from another machine's CSV therefore reached Postgres with a NULL owner, and
`/dataset/samples/trash` — which scopes a contributor to their own rows by
`auth_user_id` — showed them nothing. Only `samples.user_id` survived the trip,
and that column holds either an account UUID (older builds wrote the UUID) or a
display name (newer builds write the name).

WHY IT DOES NOT MATCH ON NAMES
-----------------------------
The obvious idea — `user_id` "Khoa" means the account named "Khoa" — is WRONG
here, and the database proves it. Measured on the dev database, 2026-08-01,
across the 3692 rows that do have an owner:

    user_id 'Khoa'  ->  account Khoa 340 rows,  account Minh 129 rows
    user_id 'Trân'  ->  account Minh 620 rows   (the Trân ACCOUNT owns none)
    user_id 'Ảnh'   ->  account Minh 405 rows
    user_id 'Minh'  ->  account Minh 1530,      account Minh6868 5

`user_id` is who SIGNED; `auth_user_id` is the account that ran the capture
station. One account records many signers. Name-matching would have handed 620
of Minh's recordings to Trân — and then let Trân delete them.

So the only proposals this tool will make are:

  * the value already IS an account id (older builds wrote the UUID into
    `user_id` — 998 such rows exist in the historical dump), or
  * every row already carrying that same `user_id` agrees on one account
    ("observed"), or
  * the data owner named it explicitly in an overrides file.

Anything else is printed for a human and left alone. `Trâm` vs `Trân` — one
diacritic apart, two different people (owner-confirmed 2026-07-31) — is the
reason no fuzzy tier is ever applied automatically.

USAGE
-----
    python -m app.cli.backfill_sample_owners                 # report only
    python -m app.cli.backfill_sample_owners --apply         # write auto-safe matches
    python -m app.cli.backfill_sample_owners --apply --include-folded
    python -m app.cli.backfill_sample_owners --apply --write-csv

`--write-csv` copies the resolved owners back into samples.csv so the next
machine-to-machine transfer keeps them. Must run in a container that can reach
Postgres (the host cannot: the postgres service publishes no ports).
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.tenant_context import platform_command

logger = logging.getLogger("backfill.owners")

# Tiers a proposal can come from. Only AUTO_TIERS are ever written.
TIER_UUID = "uuid"            # user_id IS the account id
TIER_OBSERVED = "observed"    # every owned row with this user_id agrees on one account
TIER_OVERRIDE = "override"    # named explicitly by the data owner
TIER_SPLIT = "split"          # existing rows disagree -- REPORT ONLY
TIER_NAMESAKE = "namesake"    # an account is spelled like this -- REPORT ONLY, unsound
AUTO_TIERS = (TIER_OVERRIDE, TIER_UUID, TIER_OBSERVED)

OVERRIDES_PATH = Path("config/sample_owner_overrides.json")


def _fold(text: str) -> str:
    """Lowercase, strip diacritics, collapse whitespace. Deliberately lossy —
    used only to PROPOSE a match, never to commit one."""
    s = unicodedata.normalize("NFKD", (text or "").strip().lower().replace("đ", "d"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.split())


def _load_overrides() -> Dict[str, str]:
    """{user_id_value: account_uuid_or_username} confirmed by the data owner."""
    try:
        if OVERRIDES_PATH.exists():
            data = json.loads(OVERRIDES_PATH.read_text(encoding="utf-8"))
            return {str(k): str(v) for k, v in (data.get("owners") or {}).items()}
    except Exception as exc:
        logger.warning("Không đọc được %s: %s", OVERRIDES_PATH, exc)
    return {}


def _resolve(
    user_key: str,
    users: List[Dict[str, Any]],
    overrides: Dict[str, str],
    observed: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Tuple[Optional[str], str, str]:
    """(auth_user_id, tier, note). auth_user_id is None when unresolved.

    `observed` maps a user_id value to {"accounts": n, "only_account": uuid,
    "n": rows} built from rows that ALREADY have an owner — see
    metadata_db.observed_owner_by_user_id. Unanimity is the whole test: the
    moment two accounts appear for one name, the name carries no information
    about ownership and the value is reported instead of written.
    """
    key = (user_key or "").strip()
    observed = observed or {}
    if not key or key == "(trống)":
        return None, "none", "user_id trống — không suy ra được chủ sở hữu"

    by_id = {str(u["id"]): u for u in users}
    name_of = lambda uid: str(by_id.get(uid, {}).get("username") or uid)  # noqa: E731

    ov = overrides.get(key)
    if ov:
        if ov in by_id:
            return ov, TIER_OVERRIDE, f"chủ dữ liệu chỉ định -> {name_of(ov)}"
        hit = [u for u in users if str(u["username"]) == ov]
        if len(hit) == 1:
            return str(hit[0]["id"]), TIER_OVERRIDE, f"chủ dữ liệu chỉ định -> {ov}"
        return None, "none", f"override '{ov}' không khớp tài khoản nào"

    if key in by_id:
        return key, TIER_UUID, f"user_id chính là id tài khoản ({name_of(key)})"

    ev = observed.get(key)
    if ev:
        accounts = int(ev.get("accounts") or 0)
        rows = int(ev.get("n") or 0)
        if accounts == 1 and ev.get("only_account"):
            acct = str(ev["only_account"])
            return acct, TIER_OBSERVED, (
                f"{rows} mẫu cùng user_id này đều thuộc tài khoản {name_of(acct)}"
            )
        if accounts > 1:
            return None, TIER_SPLIT, (
                f"{rows} mẫu cùng user_id này chia cho {accounts} tài khoản — "
                "tên không quyết định được chủ sở hữu"
            )

    # A same-spelled account is NOT evidence (measured: 620 rows with user_id
    # 'Trân' are owned by the Minh account, not the Trân account). Reported so a
    # human can decide, never applied.
    namesake = [u for u in users if _fold(str(u["username"])) == _fold(key)]
    if namesake:
        names = ", ".join(sorted(str(u["username"]) for u in namesake))
        return None, TIER_NAMESAKE, (
            f"có tài khoản trùng tên ({names}) nhưng KHÔNG có bằng chứng nào — "
            "cần chủ dữ liệu xác nhận"
        )

    return None, "none", "không có tài khoản nào khớp và không có mẫu cùng tên đã có chủ"


def _write_csv_owners(owners_by_uid: Dict[str, str], samples_csv: Path) -> int:
    """Copy resolved owners into samples.csv. Only fills BLANK cells."""
    from app.dataset_samples import ensure_samples_column

    ensure_samples_column("auth_user_id")
    from filelock import FileLock

    lock = FileLock(str(samples_csv) + ".lock")
    filled = 0
    with lock:
        with open(samples_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        for row in rows:
            if row.get("auth_user_id"):
                continue
            found = owners_by_uid.get(row.get("sample_uid") or "")
            if found:
                row["auth_user_id"] = found
                filled += 1
        if filled:
            tmp = str(samples_csv) + ".tmp"
            with open(tmp, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore", restval="")
                w.writeheader()
                w.writerows(rows)
                f.flush()
            import os

            os.replace(tmp, samples_csv)
    return filled


@platform_command("cli: backfill sample owners")
def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Gắn lại chủ sở hữu cho mẫu thiếu auth_user_id")
    parser.add_argument("--apply", action="store_true", help="Ghi thật (mặc định chỉ báo cáo)")
    parser.add_argument("--write-csv", action="store_true", help="Ghi ngược auth_user_id vào samples.csv")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    from app.config import settings
    from app.storage.metadata_db import (
        backfill_sample_owner,
        list_users_basic,
        observed_owner_by_user_id,
        sample_owner_gap_report,
    )

    users = list_users_basic()
    gaps = sample_owner_gap_report()
    overrides = _load_overrides()
    observed = {str(r["user_key"]): r for r in observed_owner_by_user_id()}

    if not gaps:
        logger.info("Không có mẫu nào thiếu auth_user_id.")
        return 0

    total = sum(int(g["n"]) for g in gaps)
    logger.info("%d tài khoản/tên khác nhau, %d mẫu chưa có chủ sở hữu.", len(gaps), total)
    logger.info("%d tài khoản trong bảng users.", len(users))
    logger.info("")
    logger.info("%-38s %7s  %-9s %s", "user_id trong samples", "số mẫu", "mức", "kết luận")
    logger.info("%s", "-" * 110)

    planned: List[Tuple[str, str, int]] = []
    needs_human = 0
    for g in gaps:
        key = str(g["user_key"])
        n = int(g["n"])
        auth, tier, note = _resolve(key, users, overrides, observed)
        logger.info("%-38s %7d  %-9s %s", key[:38], n, tier, note)
        if auth and tier in AUTO_TIERS:
            planned.append((key, auth, n))
        else:
            needs_human += n

    logger.info("%s", "-" * 110)
    logger.info(
        "Sẽ gắn được: %d mẫu — còn lại %d mẫu cần chủ dữ liệu xác nhận.",
        sum(n for _, _, n in planned), needs_human,
    )
    if needs_human:
        logger.info(
            "Cách xác nhận: tạo %s dạng {\"owners\": {\"<user_id>\": \"<username hoặc uuid>\"}}",
            OVERRIDES_PATH,
        )

    if not args.apply:
        logger.info("")
        logger.info("(chế độ báo cáo — thêm --apply để ghi)")
        return 0

    written = 0
    for key, auth, _ in planned:
        try:
            written += backfill_sample_owner(key, auth)
        except Exception as exc:
            logger.error("Gắn chủ sở hữu cho '%s' thất bại: %s", key, exc)
    logger.info("Đã cập nhật %d dòng trong Postgres.", written)

    if args.write_csv and written:
        from app.storage.metadata_db import _fetch_all

        rows = _fetch_all("SELECT sample_uid, auth_user_id FROM samples WHERE auth_user_id IS NOT NULL")
        mapping = {str(r["sample_uid"]): str(r["auth_user_id"]) for r in rows}
        filled = _write_csv_owners(mapping, Path(settings.dataset_root) / "samples.csv")
        logger.info("Đã ghi %d ô auth_user_id vào samples.csv.", filled)

    return 0


if __name__ == "__main__":
    sys.exit(main())

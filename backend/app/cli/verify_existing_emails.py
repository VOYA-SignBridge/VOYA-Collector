"""Grandfather the accounts that existed before email verification was required.

WHY THIS EXISTS
---------------
`REQUIRE_EMAIL_VERIFICATION` refuses a session to any account whose address was
never verified. Switching it on without running this first locks out every
account on the deployment — on this one, all of them, including the operator
who flipped the flag and now cannot log in to flip it back.

That sequence is easy to describe and easy to skip, so it is a command instead
of a paragraph. `--check` reports how many accounts would be locked out, which
is the number worth knowing BEFORE the change rather than after.

WHAT IT DOES NOT DO
-------------------
It does not verify anything. It records that these addresses are accepted
as-is, which is a decision about existing data, not a proof about it — the
addresses were never confirmed and marking them does not confirm them. What it
buys is that the requirement applies from now on, to accounts created from now
on, which is the only place it can honestly apply.

New accounts are unaffected: they register with `email_verified_at` NULL and
must go through `/auth/verify/*` like the policy intends.

USAGE
-----
    python -m app.cli.verify_existing_emails --check
    python -m app.cli.verify_existing_emails --apply
    python -m app.cli.verify_existing_emails --apply --before 2026-08-07
    python -m app.cli.verify_existing_emails --apply --email-like '%@student.ctu.edu.vn'

`--apply` with no filter touches EVERY unverified account. That is the intended
one-shot cutover, and it is also a wide blast radius for a command someone runs
while exploring — the filters exist so a narrower intent can be expressed
directly instead of approximated.

Exit codes: 0 nothing to do / applied, 2 accounts would be locked out (--check),
3 refused.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import List

from app.tenant_context import platform_command


def _unverified(cutoff: datetime | None, email_like: str | None) -> List[dict]:
    from app.storage.metadata_db import _fetch_all

    sql = (
        "SELECT id, username, email, created_at FROM users "
        "WHERE email_verified_at IS NULL"
    )
    params: list = []
    if cutoff is not None:
        sql += " AND created_at < %s"
        params.append(cutoff)
    if email_like:
        sql += " AND email ILIKE %s"
        params.append(email_like)
    return _fetch_all(sql + " ORDER BY created_at", tuple(params))


def _mark(ids: List[str]) -> int:
    from app.storage.metadata_db import _cursor

    # `_cursor` rather than `_execute`, which returns None — the caller reports
    # how many rows changed, and that number is the only evidence the statement
    # did anything.
    #
    # `%s::uuid[]` because psycopg2 adapts a list of Python strings to `text[]`
    # and `users.id` is `uuid`; Postgres has no `uuid = text` operator, so the
    # uncast version fails outright rather than matching nothing.
    #
    # `email_verified_at IS NULL` is repeated here rather than trusted from the
    # SELECT: between the two statements someone may have verified their
    # address for real, and overwriting that timestamp would replace a genuine
    # proof with this bulk decision.
    with _cursor() as cur:
        cur.execute(
            "UPDATE users SET email_verified_at = now() "
            "WHERE id = ANY(%s::uuid[]) AND email_verified_at IS NULL",
            (ids,),
        )
        return cur.rowcount


@platform_command("cli: grandfather pre-existing email addresses")
def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true",
                       help="report who would be locked out; change nothing")
    group.add_argument("--apply", action="store_true",
                       help="mark those accounts as accepted")
    parser.add_argument("--before", metavar="YYYY-MM-DD",
                        help="only accounts created before this date "
                             "(default: all existing accounts)")
    parser.add_argument("--email-like", metavar="PATTERN",
                        help="only addresses matching this SQL ILIKE pattern, "
                             "e.g. '%%@student.ctu.edu.vn'")
    args = parser.parse_args(argv)

    cutoff = None
    if args.before:
        try:
            cutoff = datetime.strptime(args.before, "%Y-%m-%d").replace(
                tzinfo=timezone.utc)
        except ValueError:
            print(f"ERROR: --before must be YYYY-MM-DD, got {args.before!r}")
            return 3

    rows = _unverified(cutoff, args.email_like)
    if not rows:
        print("No unverified accounts. REQUIRE_EMAIL_VERIFICATION is safe to enable.")
        return 0

    print(f"{len(rows)} account(s) would be refused a session:\n")
    for row in rows:
        created = row["created_at"].date() if row.get("created_at") else "?"
        print(f"  {str(row['id'])[:8]}  {row['username']:<16} {row['email']:<38} {created}")

    if args.check:
        print(f"\nEnabling REQUIRE_EMAIL_VERIFICATION now would lock out {len(rows)}.")
        print("Run again with --apply to accept these addresses as-is.")
        return 2

    changed = _mark([str(row["id"]) for row in rows])
    print(f"\nMarked {changed} account(s) as accepted.")
    print("REQUIRE_EMAIL_VERIFICATION can now be enabled; accounts created from")
    print("now on must verify through /auth/verify/*.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

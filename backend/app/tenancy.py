"""Tenant identity — one definition, imported everywhere.

Why this module exists
----------------------
Before A1, the string ``'default'`` appeared as a bare literal in 13 places in
``storage/metadata_db.py`` and nowhere else in the codebase. That is workable
while the DDL is the only thing that mentions a tenant, but A1 puts ``tenant_id``
into the CSV source of truth as well, which would have pushed the count past
twenty across four modules.

A tenant id spelled out inline has two concrete problems:

1. It cannot be audited. "Does every writer agree on the bootstrap tenant?"
   becomes a grep across string literals rather than a fact about one symbol.
2. It cannot be asserted on. Tests that hardcode ``== "default"`` bake the
   answer into the test suite, so the suite stops being able to detect the very
   drift it exists to catch.

So: one symbol, one spelling, and a validator that fails at import time rather
than emitting malformed SQL.

Why this is NOT an environment variable
---------------------------------------
It is deliberately a constant and not a setting. ``tenant_id`` is a foreign key
into ``tenants`` and it is written into ``dataset/samples.csv``, which is the
source of truth and is mirrored to Google Drive and Sheets. If an operator
changed the value through the environment after data existed, every subsequent
write would land under a tenant that the old rows do not share — splitting the
corpus in two with no error, because both halves are individually valid.

The rename path for the bootstrap tenant is a data migration (insert the new
tenant row, repoint the children, retire the old row), not a config edit. Making
it look like a config edit would invite exactly the silent split this module is
meant to prevent.

Related: :doc:`docs/needFix/MULTITENANT_ARCHITECTURE.md`,
``docs/needFix/BACKEND_WORK_PLAN.md`` (item A1).
"""

from __future__ import annotations

import re
from typing import Any, Mapping

#: Column name carrying the tenant key. Named so callers building CSV headers,
#: SQL column lists and payload dicts all agree without repeating the string.
TENANT_COLUMN = "tenant_id"

#: The bootstrap tenant every pre-multi-tenant row belongs to.
#:
#: Every one of the 3.860 samples / 63 classes / 9 users that existed when A1
#: landed is this tenant. That is what makes the backfill a constant and
#: therefore cheap — a property that stops holding the moment a second tenant
#: exists, which is why A1 is sequenced first.
DEFAULT_TENANT_ID = "default"

#: A tenant id names a Postgres row, a CSV cell, and (from A4) a storage
#: directory. Restricting the alphabet keeps all three safe at once: no quoting
#: surprises in SQL, no delimiter collisions in CSV, no path traversal on disk.
#:
#: \A and \Z, NOT ^ and $. In Python `$` also matches immediately before a
#: trailing newline, so `^...$` accepted "truong-b\n" as a valid id — which
#: would break the CSV row it was written into, name a directory with a newline
#: in it, and read as a SEPARATE partition that is indistinguishable from
#: "truong-b" in any log. \Z matches only at the true end of the string.
_TENANT_ID_RE = re.compile(r"\A[a-z0-9][a-z0-9_-]{0,62}\Z")


def is_valid_tenant_id(value: Any) -> bool:
    """True when `value` is a well-formed tenant id."""
    return isinstance(value, str) and bool(_TENANT_ID_RE.match(value))


# Fail at import, not at first write. DEFAULT_TENANT_ID is interpolated into DDL
# (`DEFAULT '<id>'`), so a malformed value would produce SQL that either fails
# obscurely at boot or — worse — succeeds with the wrong default. This assert
# costs one regex at startup and removes that whole class of outcome.
if not is_valid_tenant_id(DEFAULT_TENANT_ID):  # pragma: no cover - import guard
    raise ValueError(
        f"DEFAULT_TENANT_ID {DEFAULT_TENANT_ID!r} is not a valid tenant id; "
        f"it must match {_TENANT_ID_RE.pattern}"
    )


def _reject_non_string(value: Any) -> None:
    """Refuse anything that is not a `str`.

    The values that reach these helpers come from CSV cells (always str),
    psycopg2 rows (str or None) and JSON request bodies (anything at all). Only
    the last can hand over an int, a bool or a list, and silently stringifying
    those is how a partition gets created by accident rather than by decision.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"tenant_id must be a string or None, got {type(value).__name__}: {value!r}"
        )


def normalize_tenant_id(value: Any, *, fallback: str = DEFAULT_TENANT_ID) -> str:
    """Coerce `value` to a usable tenant id, falling back when it is absent.

    The fallback exists because every row that predates A1 has no tenant of its
    own: the CSV mirror hands over ``None``, and older files hand over ``""``
    (``csv.DictReader``'s ``restval``). Both mean "written before tenants
    existed", and the honest answer for both is the bootstrap tenant.

    A value that is present but MALFORMED is a different situation and is not
    silently repaired — that would let a typo quietly become a new tenant
    partition. It raises.

    A value of the wrong TYPE raises too, and that check is not pedantry:
    ``str(123)`` is ``"123"``, which matches the allowed alphabet, so without it
    an integer arriving from a JSON body would silently become tenant "123" —
    a real partition, created by a type confusion, with no error anywhere.
    """
    if value is None:
        return fallback
    _reject_non_string(value)
    text = value.strip()
    if not text:
        return fallback
    if not is_valid_tenant_id(text):
        raise ValueError(
            f"invalid tenant_id {text!r}: must match {_TENANT_ID_RE.pattern}"
        )
    return text


def optional_tenant_id(value: Any) -> str | None:
    """Validate `value` as a tenant id, or return None when it is absent.

    This is the primitive the Postgres upserts need, and it is deliberately NOT
    ``normalize_tenant_id``. The difference decides whether A1 works.

    Consider a mirror CSV written by a machine that predates the tenant column,
    synced into a database that already holds rows for tenant "truong-b". Every
    row dict arrives without a tenant key:

      * With a ``'default'`` fallback, the upsert would write ``tenant_id =
        'default'`` over each existing row — silently reassigning tenant B's
        corpus to the bootstrap tenant. That is precisely the data-partition
        loss A1 exists to prevent, reintroduced one layer lower.
      * Returning None instead lets the SQL distinguish "no opinion" from "this
        row belongs to X": the INSERT arm substitutes the bootstrap tenant for a
        genuinely new row, and the ON CONFLICT arm keeps whatever the database
        already had.

    So: absent means absent. Only the CSV WRITE path, where a new row must be
    stamped with a concrete owner, uses the fallback form.
    """
    if value is None:
        return None
    _reject_non_string(value)
    text = value.strip()
    if not text:
        return None
    if not is_valid_tenant_id(text):
        raise ValueError(
            f"invalid tenant_id {text!r}: must match {_TENANT_ID_RE.pattern}"
        )
    return text


def tenant_id_of(row: Mapping[str, Any], *, fallback: str = DEFAULT_TENANT_ID) -> str:
    """Read the tenant id out of a CSV row / payload mapping.

    Single accessor so that CSV readers, the Postgres upserts and the backfill
    CLI cannot disagree about which key holds the tenant or what a blank means.
    """
    return normalize_tenant_id(row.get(TENANT_COLUMN), fallback=fallback)

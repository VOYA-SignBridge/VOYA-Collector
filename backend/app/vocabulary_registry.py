"""Dialects and recognition profiles — Postgres is the source of truth.

Unlike labels/samples (CSV is authoritative, Postgres mirrors), this registry is
DB-first, because only a foreign key can refuse a bad value at write time. A
convention can be forgotten; `RECOGNITION_PROFILES` was hardcoded in six places
that disagreed with each other, and a sync script still managed to write the
non-existent profile "spa" into 7 classes.

dialect_id is IMMUTABLE and ASCII: it names a directory (features/<lang>/<dialect>/),
a checkpoint file, and published split manifests. display_name carries the
accents and is the only part anyone renames.

NAMING — read before touching the `community_*` tables
------------------------------------------------------
The tables `community_dialects`, `community_profiles` and `community_versions`
hold the SYSTEM CATALOG: system-managed configuration templates (which dialects
and recognition profiles exist by default) that a new tenant is cloned from.
They contain no contributed data — no video, no landmarks, no consent record,
no attribution, no licence.

That is NOT what "Community" means in CTU-SignBridge. The Community Data
Commons is data people contributed plus the governance around it: submission,
rights and consent review, immutable releases, licences, access grants,
attribution, withdrawal. It does not exist yet; see
docs/01-architecture/COMMUNITY_DATA_COMMONS.md.

The functions here are therefore named `*_catalog_*`. The table names still say
`community_*` because renaming them is a migration with a deploy window, and the
domain name is what had to stop being wrong first. Do not "fix" the function
names back to match the tables.

See docs/02-data/DIALECT_LIFECYCLE.md and REGISTRY_ARCHITECTURE.md §2.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from psycopg2.extras import Json

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_TENANT = "default"
SNAPSHOT_PATH: Path = settings.dataset_root / "vocabulary_registry.json"
_CACHE_TTL = 30.0
_cache: Dict[str, Tuple[float, Any]] = {}


class RegistryPinError(Exception):
    """An artifact pins a registry version that is missing or does not match.

    Always fatal by design: continuing with the CURRENT registry would silently
    reinterpret old data under a new vocabulary, which is the failure the whole
    pinning scheme exists to prevent.
    """


class TenantRegistryUnavailable(Exception):
    """A tenant's registry could not be read. Never degrades to the system catalogue."""


class DialectConflict(Exception):
    """Slug already taken by a different display name — caller must decide."""

    def __init__(self, dialect_id: str, existing_display_name: str):
        self.dialect_id = dialect_id
        self.existing_display_name = existing_display_name
        super().__init__(
            f"Slug '{dialect_id}' đã thuộc về phương ngữ '{existing_display_name}'. "
            f"Dùng phương ngữ đó, hoặc đặt tên khác."
        )


def slugify_dialect(text: str) -> str:
    """'Miền Bắc' -> 'mien-bac'. ASCII only: this becomes a directory name.

    Accents are folded because a Unicode directory name breaks Drive sync and
    Windows/Linux round-trips — not because Postgres cannot store them (it can,
    and display_name does).
    """
    s = unicodedata.normalize("NFKD", (text or "").strip().lower().replace("đ", "d"))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:40]


def _invalidate() -> None:
    _cache.clear()


def _cached(key: str, loader):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    value = loader()
    _cache[key] = (time.time(), value)
    return value


# --------------------------------------------------------------------------- read


def list_dialects(
    tenant_id: str = DEFAULT_TENANT,
    *,
    viewer_id: Optional[str] = None,
    include_inactive: bool = False,
) -> List[Dict[str, Any]]:
    """Approved dialects, plus the viewer's OWN pending ones.

    A pending dialect is usable immediately by whoever asked for it — that is the
    point of the button — but stays invisible to everyone else until an admin
    approves it.
    """
    from app.storage.metadata_db import _fetch_all

    where = ["tenant_id = %s"]
    params: List[Any] = [tenant_id]
    visible = "status = 'approved'"
    if viewer_id:
        visible = f"({visible} OR created_by = %s)"
        params.append(viewer_id)
    where.append(visible)
    if not include_inactive:
        where.append("is_active = TRUE")
    return _fetch_all(
        f"SELECT * FROM dialects WHERE {' AND '.join(where)} ORDER BY display_order, display_name",
        tuple(params),
    )


def list_profiles(tenant_id: str = DEFAULT_TENANT) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all

    return _fetch_all(
        "SELECT * FROM recognition_profiles WHERE tenant_id = %s AND is_active = TRUE "
        "ORDER BY display_order, profile_id",
        (tenant_id,),
    )


def list_regions() -> List[Dict[str, Any]]:
    """Các vùng miền dùng được, đọc từ bảng `regions`.

    Đọc từ bảng chứ không từ `VALID_REGIONS` trong `dataset_manager`: tuple đó
    tự nói nó chỉ là bộ lọc đầu vào ở tầng ứng dụng, còn nguồn sự thật là bảng
    này. Cứng hoá danh sách vào giao diện là lặp lại đúng lỗi mà bảng tra
    phương ngữ viết tay đã mắc — nó không bao giờ học được một giá trị mới
    thêm sau khi mã được viết.

    `regions` KHÔNG có `tenant_id`: đây là danh mục tham chiếu toàn nền tảng,
    vai ứng dụng chỉ được đọc (xem `REFERENCE_TABLES`).
    """
    from app.storage.metadata_db import _fetch_all

    return _fetch_all(
        "SELECT code, name_vi, name_en, sort_order FROM regions "
        "WHERE is_active = TRUE AND status = 'approved' "
        "ORDER BY sort_order, code"
    )


def known_dialect_ids(tenant_id: str = DEFAULT_TENANT) -> set:
    """Every dialect_id that may appear on a row, aliases included.

    Aliases count: a merged-away id still appears in checkpoints and published
    split manifests, which are never rewritten.
    """

    def load() -> set:
        from app.storage.metadata_db import _fetch_all

        rows = _fetch_all("SELECT dialect_id FROM dialects WHERE tenant_id = %s", (tenant_id,))
        alias = _fetch_all(
            "SELECT old_dialect_id AS dialect_id FROM dialect_aliases WHERE tenant_id = %s",
            (tenant_id,),
        )
        return {r["dialect_id"] for r in rows + alias}

    return _cached(f"dialects:{tenant_id}", load)


def known_profile_ids(tenant_id: str = DEFAULT_TENANT) -> set:
    def load() -> set:
        return {r["profile_id"] for r in list_profiles(tenant_id)}

    return _cached(f"profiles:{tenant_id}", load)


def dialect_owner(dialect_id: str, tenant_id: str = DEFAULT_TENANT) -> Optional[str]:
    """Who a not-yet-approved dialect belongs to; None once it is public.

    Everything derived from a pending dialect inherits this scope — the classes,
    the samples, and any model trained on it. A model built from one person's
    unapproved vocabulary must not appear in the shared realtime list: its label
    set describes a vocabulary nobody else has agreed exists yet.

    Enforcement points (call this, do not re-derive the rule):
      - training: refuse to start / to list a job whose dialect is owned by
        someone else, and never promote such a model to the global registry;
      - realtime: a promoted model must have owner None.
    """
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT status, created_by FROM dialects WHERE tenant_id = %s AND dialect_id = %s",
        (tenant_id, dialect_id),
    )
    if not rows or rows[0]["status"] == "approved":
        return None
    return str(rows[0]["created_by"] or "") or None


def can_use_dialect(dialect_id: str, user_id: Optional[str],
                    tenant_id: str = DEFAULT_TENANT) -> bool:
    owner = dialect_owner(dialect_id, tenant_id)
    return owner is None or (user_id is not None and str(user_id) == owner)


def assert_can_use_dialect(dialect_id: str, user_id: Optional[str],
                           tenant_id: str = DEFAULT_TENANT) -> None:
    if not can_use_dialect(dialect_id, user_id, tenant_id):
        raise PermissionError(
            f"Phương ngữ '{dialect_id}' đang chờ admin duyệt và chỉ người tạo dùng được."
        )


def resolve_dialect(dialect_id: str, tenant_id: str = DEFAULT_TENANT) -> str:
    """Follow one merge hop: 'mien-bac' -> 'bac'. Unknown ids pass through."""
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT new_dialect_id FROM dialect_aliases WHERE tenant_id = %s AND old_dialect_id = %s",
        (tenant_id, dialect_id),
    )
    return rows[0]["new_dialect_id"] if rows else dialect_id


def registry_version(tenant_id: str = DEFAULT_TENANT) -> int:
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT version FROM vocabulary_registry_meta WHERE tenant_id = %s", (tenant_id,)
    )
    return int(rows[0]["version"]) if rows else 0


# --------------------------------------------------------------------------- write


def _canonical_json(payload: Dict[str, Any]) -> str:
    """Stable serialisation, so the same content always hashes the same."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(payload: Dict[str, Any]) -> str:
    """sha256 over the canonical form, minus the fields that describe the
    snapshot rather than its content — otherwise the hash would change on every
    export even when nothing about the vocabulary did."""
    body = {k: v for k, v in payload.items()
            if k not in ("registry_version", "content_hash", "generated", "exported_at")}
    return hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()


def _bump(tenant_id: str, created_by: Optional[str] = None, note: str = "") -> int:
    """Close the current registry state into a NEW immutable version.

    The old code incremented a counter and overwrote one snapshot file, which
    made `pin version N` unhonourable: N's contents vanished as soon as N+1 was
    written. Here the row in registry_versions is written once and never
    updated, and the per-version snapshot file is written alongside it, so an
    artifact that pinned N can still be checked against N years later.

    Returns the new version number.
    """
    from app.storage.metadata_db import _cursor

    _invalidate()
    payload = _build_snapshot(tenant_id)
    digest = content_hash(payload)

    with _cursor() as cur:
        # Serialise per tenant for the whole read-then-write. The dedup check
        # used to run in its OWN transaction before this block, so two backends
        # starting together both read "latest = v4", both saw a change, and
        # produced v5 and v6 carrying identical content — precisely the version
        # churn the check exists to prevent. The ON CONFLICT below stops a
        # duplicate key, not a duplicate STATE.
        #
        # Advisory lock rather than SELECT ... FOR UPDATE: on the very first
        # bump for a tenant there is no row to lock.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"registry:{tenant_id}",))

        # A version identifies a distinct CONTENT state, not a number of runs.
        # init_db() re-clones on every backend start, so without this the
        # version would climb forever while nothing changed.
        cur.execute(
            "SELECT version, content_hash FROM registry_versions WHERE tenant_id = %s "
            "ORDER BY version DESC LIMIT 1",
            (tenant_id,),
        )
        latest = cur.fetchone()
        if latest and str(latest[1]) == digest:
            version = int(latest[0])
            payload["registry_version"] = version
            payload["content_hash"] = digest
            unchanged = True
        else:
            unchanged = False
            cur.execute(
                "UPDATE vocabulary_registry_meta SET version = version + 1, updated_at = NOW() "
                "WHERE tenant_id = %s RETURNING version",
                (tenant_id,),
            )
            row = cur.fetchone()
            if row is None:
                cur.execute(
                    "INSERT INTO vocabulary_registry_meta(tenant_id, version) VALUES(%s, 1) "
                    "RETURNING version",
                    (tenant_id,),
                )
                row = cur.fetchone()
            version = int(row[0])
            payload["registry_version"] = version
            payload["content_hash"] = digest
            cur.execute(
                "INSERT INTO registry_versions(tenant_id, version, content_hash, snapshot, note, created_by) "
                "VALUES(%s, %s, %s, %s, %s, %s) ON CONFLICT (tenant_id, version) DO NOTHING",
                (tenant_id, version, digest, Json(payload), note or None, created_by or None),
            )

    if unchanged:
        logger.debug("[VOCAB] %s: nội dung không đổi, giữ v%s", tenant_id, version)
    try:
        export_snapshot(tenant_id, payload=payload)
    except Exception as exc:  # a stale snapshot is detectable; a failed write is not fatal
        logger.warning("[VOCAB] snapshot export failed: %s", exc)
    return version


def get_registry_version(tenant_id: str, version: int) -> Optional[Dict[str, Any]]:
    """The exact snapshot a dataset pinned. None if that version was never
    written — which a caller must treat as an error, never as 'use current'."""
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT version, content_hash, snapshot, created_at, note FROM registry_versions "
        "WHERE tenant_id = %s AND version = %s",
        (tenant_id, int(version)),
    )
    return rows[0] if rows else None


def verify_pinned_snapshot(tenant_id: str, version: int, expected_hash: str) -> None:
    """Raise unless the stored version matches what the artifact pinned.

    Both halves matter: a missing version means the artifact references a
    vocabulary that no longer exists, and a hash mismatch means the row was
    tampered with or restored from a different database. Neither may degrade
    into 'carry on with the current registry'.
    """
    row = get_registry_version(tenant_id, version)
    if row is None:
        raise RegistryPinError(
            f"registry version {version} của tenant '{tenant_id}' không tồn tại — "
            "artifact đang trỏ tới một danh mục không còn. DỪNG."
        )
    if expected_hash and str(row["content_hash"]) != str(expected_hash):
        raise RegistryPinError(
            f"hash không khớp cho registry v{version} của '{tenant_id}': "
            f"artifact ghi {expected_hash}, DB có {row['content_hash']}. DỪNG."
        )


def create_dialect(
    display_name: str,
    *,
    language: str = "vn",
    created_by: Optional[str] = None,
    tenant_id: str = DEFAULT_TENANT,
    auto_approve: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    """Return (row, created). Raises DialectConflict when the slug is taken by
    a DIFFERENT display name — never merges two names silently."""
    from app.storage.metadata_db import _execute, _fetch_all

    display_name = (display_name or "").strip()
    dialect_id = slugify_dialect(display_name)
    if not dialect_id:
        raise ValueError("Tên phương ngữ không hợp lệ (rỗng sau khi chuẩn hoá).")

    existing = _fetch_all(
        "SELECT * FROM dialects WHERE tenant_id = %s AND dialect_id = %s",
        (tenant_id, dialect_id),
    )
    if existing:
        row = existing[0]
        # Same name modulo case -> idempotent, hand back what is already there.
        if (row["display_name"] or "").strip().lower() == display_name.lower():
            return row, False
        raise DialectConflict(dialect_id, row["display_name"])

    status = "approved" if auto_approve else "pending"
    _execute(
        "INSERT INTO dialects(tenant_id, dialect_id, display_name, language, status, "
        "created_by, approved_by, approved_at) VALUES(%s, %s, %s, %s, %s, %s, %s, "
        "CASE WHEN %s THEN NOW() END)",
        (tenant_id, dialect_id, display_name, language, status, created_by,
         created_by if auto_approve else None, auto_approve),
    )
    _bump(tenant_id)
    logger.info("[VOCAB] dialect %s (%s) created status=%s by=%s",
                dialect_id, display_name, status, created_by)
    return _fetch_all(
        "SELECT * FROM dialects WHERE tenant_id = %s AND dialect_id = %s",
        (tenant_id, dialect_id),
    )[0], True


def approve_dialect(dialect_id: str, approved_by: str, tenant_id: str = DEFAULT_TENANT) -> None:
    from app.storage.metadata_db import _execute

    _execute(
        "UPDATE dialects SET status = 'approved', approved_by = %s, approved_at = NOW() "
        "WHERE tenant_id = %s AND dialect_id = %s",
        (approved_by, tenant_id, dialect_id),
    )
    _bump(tenant_id)
    logger.info("[VOCAB] dialect %s approved by %s", dialect_id, approved_by)


def rename_dialect(dialect_id: str, display_name: str, tenant_id: str = DEFAULT_TENANT) -> None:
    """The cheap rename: one row, one column. dialect_id itself never changes."""
    from app.storage.metadata_db import _execute

    _execute(
        "UPDATE dialects SET display_name = %s WHERE tenant_id = %s AND dialect_id = %s",
        ((display_name or "").strip(), tenant_id, dialect_id),
    )
    _bump(tenant_id)


def set_dialect_active(dialect_id: str, active: bool, tenant_id: str = DEFAULT_TENANT) -> None:
    """Retire a dialect without deleting it — test junk leaves the dropdowns
    while its historical rows stay queryable."""
    from app.storage.metadata_db import _execute

    _execute(
        "UPDATE dialects SET is_active = %s WHERE tenant_id = %s AND dialect_id = %s",
        (bool(active), tenant_id, dialect_id),
    )
    _bump(tenant_id)


def record_merge(old_id: str, new_id: str, merged_by: Optional[str] = None,
                 tenant_id: str = DEFAULT_TENANT) -> None:
    """Catalogue half of a merge: alias + retire. Moving files is a separate,
    resumable task — see docs/02-data/DIALECT_LIFECYCLE.md §3.5."""
    from app.storage.metadata_db import _execute

    _execute(
        "INSERT INTO dialect_aliases(tenant_id, old_dialect_id, new_dialect_id, merged_by) "
        "VALUES(%s, %s, %s, %s) ON CONFLICT (tenant_id, old_dialect_id) DO UPDATE "
        "SET new_dialect_id = EXCLUDED.new_dialect_id",
        (tenant_id, old_id, new_id, merged_by),
    )
    _execute(
        "UPDATE dialects SET is_active = FALSE, status = 'rejected', merged_into = %s "
        "WHERE tenant_id = %s AND dialect_id = %s",
        (new_id, tenant_id, old_id),
    )
    _bump(tenant_id)
    logger.info("[VOCAB] dialect %s merged into %s by %s", old_id, new_id, merged_by)


# --------------------------------------------------------------------------- export


def _build_snapshot(tenant_id: str) -> Dict[str, Any]:
    """The registry's content, with no version/hash yet — those are assigned by
    _bump when the state is frozen into a version."""
    from app.storage.metadata_db import _fetch_all

    return {
        "source": "tenant",
        "tenant_id": tenant_id,
        "generated": "app.vocabulary_registry — do not edit by hand",
        "dialects": [
            {k: r[k] for k in ("dialect_id", "display_name", "language", "is_alphabet",
                               "is_active", "status")}
            for r in list_dialects(tenant_id, include_inactive=True)
        ],
        "profiles": [
            {k: r[k] for k in ("profile_id", "display_name", "is_trainable")}
            for r in list_profiles(tenant_id)
        ],
        "aliases": {
            r["old_dialect_id"]: r["new_dialect_id"]
            for r in _fetch_all(
                "SELECT old_dialect_id, new_dialect_id FROM dialect_aliases WHERE tenant_id = %s",
                (tenant_id,),
            )
        },
    }


def version_snapshot_path(tenant_id: str, version: int) -> Path:
    """Where version N's immutable copy lives. Per-version files are what make
    `pin v2` survive the arrival of v3 — the current-pointer file is overwritten
    every export, these never are."""
    return SNAPSHOT_PATH.parent / "registry_versions" / f"{tenant_id}_v{int(version)}.json"


def export_snapshot(
    tenant_id: str = DEFAULT_TENANT,
    path: Optional[Path] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write the registry where DB-less consumers can read it.

    Scripts run straight on the host cannot reach Postgres — the compose service
    publishes no port. They read this file and compare `registry_version` +
    `content_hash` with what their own manifest recorded; a mismatch is an
    error, not a silent fallback to a stale list.

    Two files are written: the current-pointer (overwritten) and version N's own
    copy (written once, never touched again).
    """
    if payload is None:
        payload = _build_snapshot(tenant_id)
        payload["registry_version"] = registry_version(tenant_id)
        payload["content_hash"] = content_hash(payload)

    body = json.dumps(payload, ensure_ascii=False, indent=2)
    target = path or SNAPSHOT_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")

    if path is None:
        _freeze_version_file(tenant_id, int(payload.get("registry_version") or 0), body)
    return target


def _freeze_version_file(tenant_id: str, version: int, body: str) -> None:
    """Write version N's copy exactly once, atomically.

    `if not exists(): write()` was neither: two processes could both pass the
    check, and a plain write leaves a truncated file if the process dies
    mid-way — a half-written snapshot is worse than a missing one, because it
    parses as JSON far too often to be caught by chance.

    Write to a temp file, fsync, then os.link to claim the name: link fails if
    the target exists, so the winner is decided by the filesystem. If the name
    is already taken, the existing content must MATCH — a published version
    that disagrees with what we just computed means two different states were
    published under one number, and that is a fatal integrity problem, not
    something to overwrite.
    """
    import os
    import tempfile

    frozen = version_snapshot_path(tenant_id, version)
    frozen.parent.mkdir(parents=True, exist_ok=True)

    if frozen.exists():
        if frozen.read_text(encoding="utf-8") != body:
            raise RegistryPinError(
                f"snapshot v{version} của '{tenant_id}' đã tồn tại với nội dung KHÁC. "
                "Hai trạng thái khác nhau cùng mang một số version — dừng, không ghi đè."
            )
        return

    fd, tmp = tempfile.mkstemp(dir=str(frozen.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
            fh.flush()
            os.fsync(fh.fileno())
        try:
            os.link(tmp, frozen)  # fails if another process got there first
        except FileExistsError:
            if Path(frozen).read_text(encoding="utf-8") != body:
                raise RegistryPinError(
                    f"snapshot v{version} của '{tenant_id}' bị ghi đồng thời với nội dung khác."
                )
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


# --------------------------------------------------------------------------- seed


# --------------------------------------------------------------------------- access

EDITOR_ROLES = ("admin", "editor")


def tenant_role(tenant_id: str, user_id: Optional[str]) -> Optional[str]:
    """This user's role IN THIS TENANT, or None if they have none.

    `None` gộp HAI trạng thái, và đó là chủ ý
    ------------------------------------------
    Hàm trả `None` cho cả "không phải thành viên" lẫn "là thành viên đang hoạt
    động nhưng chưa có vai nào ở tầng tenant" (`tenant_members.role IS NULL` —
    trạng thái ra đời khi `tenant_viewer` nghỉ hưu, xem
    `authorization/catalog.py::RETIRED_BUILTIN_ROLES`).

    Gộp được vì mọi chỗ gọi đều hỏi cùng một câu: *vai này có cấp thứ tôi cần
    không*. Với cả hai trạng thái, câu trả lời là không — `can_edit_registry`
    từ chối, `require_tenant_admin` từ chối, `_legacy_decision` trả False. Trả
    về hai giá trị khác nhau chỉ để rồi xử lý giống nhau là mời gọi chỗ gọi thứ
    tư xử lý khác đi mà không có lý do.

    Chỗ nào THẬT SỰ cần phân biệt thì hỏi tư cách thành viên trực tiếp —
    `authorization_service._membership_active` làm đúng thế, và nó cố ý không
    đi qua hàm này.

    Runs in system scope, for the same reason `auth.py` does — this is the
    authorisation plane, and it has the same circularity as the identity plane.
    The ambient scope of a request is the caller's HOME tenant
    (`users.tenant_id`); the question here is about a DIFFERENT tenant named in
    the path. Filtering the answer by the home scope makes the answer always
    "not a member", so a person who is an admin of tenant B while living in
    tenant A can never act on B. `tenant_members` gained a row-level policy on
    2026-08-07 and that is exactly what happened: 403 on their own tenant.

    Safe to widen because of the shape of the query, not because of trust: it
    is a point lookup keyed by BOTH ids, returning one role. The caller already
    knows both values. Nothing here can list members, discover tenants, or
    answer a question the caller did not already ask about themselves.

    Vì sao lọc theo `status` / `removed_at`
    ---------------------------------------
    Hai cột đó vào cùng PDM v1.0 và **chưa có mã nào ghi chúng**: gỡ thành viên
    hôm nay là `DELETE FROM tenant_members` (xem `tenant_admin.remove_member`),
    tức là xoá cứng, nên không dòng nào mang `status = 'REMOVED'`.

    Nghĩa là mệnh đề này KHÔNG đổi hành vi nào hôm nay. Nó có mặt vì thời điểm
    duy nhất thêm nó mà không rủi ro là BÂY GIỜ — trước khi luồng gỡ mềm tồn
    tại. Ngày ai đó đổi `remove_member` sang `UPDATE ... status = 'REMOVED'`,
    hàm này đã đúng sẵn; nếu để sau, cái đúng phải nhớ sửa ở đây, và quên thì
    hậu quả là **người đã bị gỡ khỏi tổ chức vẫn giữ nguyên quyền biên tập** —
    im lặng, vì `can_edit_registry` chỉ hỏi "có role không".

    Cùng vị từ mà `authorization/adapter.py` dùng khi chiếu policy sang Casbin.
    Hai bên phải khớp: lệch nhau là shadow mode báo bất đồng cho một khác biệt
    do chính hai truy vấn tạo ra, chứ không phải khác biệt thật.

    Phụ thuộc lược đồ: hai cột này do `storage/authz_schema` thêm, và
    `missing_objects()` canh chúng — một lần `ALTER` thất bại lặng lẽ sẽ làm
    hàm này ném lỗi ở MỌI lời gọi, nên nó phải bị bắt ở kiểm tra triển khai chứ
    không phải ở request đầu tiên.
    """
    if not user_id:
        return None
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("authz: role lookup names its own tenant, not the caller's"):
        rows = _fetch_all(
            "SELECT role FROM tenant_members "
            " WHERE tenant_id = %s AND user_id = %s "
            "   AND status = 'ACTIVE' AND removed_at IS NULL",
            (tenant_id, str(user_id)),
        )
    if not rows:
        return None
    # `str()` chỉ khi có giá trị. Bản trước viết `str(rows[0]["role"])` vô điều
    # kiện, và từ ngày cột `role` nhận NULL, câu đó biến một thành viên không
    # vai thành chuỗi `"None"` — một vai không tồn tại, đi thẳng vào
    # `LEGACY_TENANT_ROLE_MAP.get(...)`, và đẻ ra một dòng log mức ERROR
    # ("role cũ không có trong bản đồ") ở MỖI request của người đó.
    role = rows[0]["role"]
    return str(role) if role is not None else None


def can_edit_registry(tenant_id: str, user_id: Optional[str],
                      is_system_admin: bool = False) -> bool:
    """Only an admin/editor OF THIS TENANT may change its registry.

    Tenant membership and the system-admin flag are two different authorities,
    checked separately on purpose: being an editor of tenant A must never grant
    anything in tenant B, which is the whole point of the tenant plane. The
    system admin is an operator escape hatch, not a tenant role.
    """
    if is_system_admin:
        return True
    return tenant_role(tenant_id, user_id) in EDITOR_ROLES


def assert_can_edit_registry(tenant_id: str, user_id: Optional[str],
                             is_system_admin: bool = False) -> None:
    if not can_edit_registry(tenant_id, user_id, is_system_admin):
        raise PermissionError(
            f"Chỉ admin hoặc editor của tenant '{tenant_id}' mới sửa được danh mục của tenant đó."
        )


def assert_system_admin(is_system_admin: bool) -> None:
    """Guard for the COMMUNITY plane. Kept as its own function so that no
    tenant-scoped check can ever be mistaken for authority over the template —
    the system catalogue must not be readable or writable by tenant users."""
    if not is_system_admin:
        raise PermissionError("Danh mục hệ thống (System Catalog) chỉ admin hệ thống mới xem/sửa được.")


CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"


def _read_seed(name: str) -> List[Dict[str, str]]:
    import csv as _csv

    src = CONFIG_DIR / name
    if not src.is_file():
        return []
    with src.open(newline="", encoding="utf-8-sig") as fh:
        return [r for r in _csv.DictReader(fh)]


def _flag(row: Dict[str, str], key: str, default: str = "1") -> bool:
    return (row.get(key) or default).strip() == "1"


def seed_system_catalog(created_by: Optional[str] = None) -> Dict[str, int]:
    """Load the system catalogue from config/*.seed.csv — FIRST INSTALL ONLY.

    After this, the system catalogue lives in Postgres and a system admin
    edits it in the app; the CSVs are not re-read over the top (ON CONFLICT DO
    NOTHING), so an admin's edit is never reverted by a redeploy. That is what
    makes "admin có quyền tùy chỉnh ban đầu" work without a code change.

    The tenant-facing tables are NOT touched here. Tenants get their catalogue
    by cloning (clone_catalog_to_tenant), never by reading this one.
    """
    from app.storage.metadata_db import _execute

    counts = {"dialects": 0, "profiles": 0}
    for i, row in enumerate(_read_seed("dialects.seed.csv")):
        did = (row.get("dialect_id") or "").strip()
        if not did:
            continue
        _execute(
            "INSERT INTO community_dialects(dialect_id, display_name, language, is_alphabet, "
            "display_order, is_active, note, updated_by) "
            "VALUES(%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (dialect_id) DO NOTHING",
            (did, (row.get("display_name") or did).strip(),
             (row.get("language") or "vn").strip(), _flag(row, "is_alphabet", "0"),
             int(row.get("display_order") or i), _flag(row, "is_active"),
             (row.get("note") or "").strip() or None, created_by),
        )
        counts["dialects"] += 1

    # Profiles come from their OWN seed file, never from the data they validate:
    # deriving the allow-list from the rows it checks is circular — that is how
    # the bogus profile "spa" would have legitimised itself. The file also ends
    # the drift that had this list hardcoded here AND in processed/shared.
    for i, row in enumerate(_read_seed("profiles.seed.csv")):
        pid = (row.get("profile_id") or "").strip()
        if not pid:
            continue
        _execute(
            "INSERT INTO community_profiles(profile_id, display_name, is_trainable, "
            "display_order, note, updated_by) VALUES(%s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (profile_id) DO NOTHING",
            (pid, (row.get("display_name") or pid).strip(), _flag(row, "is_trainable"),
             int(row.get("display_order") or i), (row.get("note") or "").strip() or None,
             created_by),
        )
        counts["profiles"] += 1
    return counts


# `dialect_id` / `profile_id` are deliberately absent from both lists. They name
# directories on disk, checkpoint files and published split manifests; renaming
# one would silently orphan every artifact that cites it. Display names are the
# editable surface — that separation is the whole reason the id is a slug.
_COMMUNITY_DIALECT_COLUMNS = ("display_name", "language", "is_alphabet",
                              "display_order", "is_active", "note")
_COMMUNITY_PROFILE_COLUMNS = ("display_name", "is_trainable", "display_order",
                              "is_active", "note")


def _update_catalog_row(table: str, key_column: str, key: str,
                          allowed: Tuple[str, ...], changes: Dict[str, Any],
                          updated_by: Optional[str]) -> Dict[str, Any]:
    """Patch one system-catalogue row. Column names come from `allowed`, never from the
    caller's keys, so an unexpected key is a 400 rather than injected SQL.

    Editing does NOT publish. A version is a deliberate act with a note attached
    (see publish_catalog_version); auto-publishing on every keystroke would
    fill the history with versions nobody chose to make and destroy the one
    property that makes a version worth pinning — that somebody meant it.
    """
    from app.storage.metadata_db import _fetch_all

    unknown = sorted(k for k in changes if k not in allowed)
    if unknown:
        raise ValueError(f"Không sửa được trường: {', '.join(unknown)}")
    fields = {k: v for k, v in changes.items() if k in allowed}
    if not fields:
        raise ValueError("Không có trường nào để sửa.")

    assignments = ", ".join(f"{col} = %s" for col in fields)
    rows = _fetch_all(
        f"UPDATE {table} SET {assignments}, updated_by = %s, updated_at = NOW() "
        f"WHERE {key_column} = %s RETURNING *",
        (*fields.values(), updated_by, key),
    )
    if not rows:
        raise KeyError(key)
    return rows[0]


def update_catalog_dialect(dialect_id: str, changes: Dict[str, Any],
                             updated_by: Optional[str] = None) -> Dict[str, Any]:
    """Edit the system catalogue's dialect. System-admin plane only.

    This is what makes `seed_system_catalog`'s ON CONFLICT DO NOTHING honest: the CSVs
    are read once, and from then on the admin edits here without a redeploy ever
    reverting them.
    """
    return _update_catalog_row("community_dialects", "dialect_id", dialect_id,
                                 _COMMUNITY_DIALECT_COLUMNS, changes, updated_by)


def update_catalog_profile(profile_id: str, changes: Dict[str, Any],
                             updated_by: Optional[str] = None) -> Dict[str, Any]:
    """Edit the system catalogue's recognition profile. System-admin plane only."""
    return _update_catalog_row("community_profiles", "profile_id", profile_id,
                                 _COMMUNITY_PROFILE_COLUMNS, changes, updated_by)


def system_catalog_snapshot() -> Dict[str, Any]:
    from app.storage.metadata_db import _fetch_all

    return {
        # Stored VALUE, not prose — it feeds content_hash, and every published
        # community_versions row was hashed with this exact spelling. Changing
        # it would mint a new version that differs from the last one by a word.
        # Rename it in the same migration that renames the tables, not before.
        "source": "community",
        "tenant_id": None,
        "generated": "app.vocabulary_registry.system_catalog_snapshot — do not edit by hand",
        "dialects": [
            {"dialect_id": r["dialect_id"], "display_name": r["display_name"],
             "language": r["language"], "is_alphabet": r["is_alphabet"],
             "is_active": r["is_active"], "status": "approved"}
            for r in _fetch_all(
                "SELECT * FROM community_dialects ORDER BY display_order, dialect_id")
        ],
        "profiles": [
            {"profile_id": r["profile_id"], "display_name": r["display_name"],
             "is_trainable": r["is_trainable"]}
            for r in _fetch_all(
                "SELECT * FROM community_profiles WHERE is_active = TRUE "
                "ORDER BY display_order, profile_id")
        ],
        "aliases": {},
    }


def publish_catalog_version(created_by: Optional[str] = None, note: str = "") -> int:
    """Freeze the system catalogue into an immutable version.

    A tenant records which catalogue version it was cloned from, so "what did
    the template look like when this tenant started" stays answerable after the
    admin edits the template again.
    """
    from app.storage.metadata_db import _cursor

    payload = system_catalog_snapshot()
    digest = content_hash(payload)

    # Same rule as _bump, and deliberately the same SHAPE of rule: compare only
    # against the LATEST version, not all of history.
    #
    # clone_catalog_to_tenant publishes before every clone, so without this a
    # tenant created today would record "cloned from v37" where v1..v37 are all
    # byte-identical — noise that makes the provenance trail useless.
    #
    # Matching against all of history instead would make version numbers
    # non-monotonic in time: edit then revert would resurrect v1 as "current",
    # and "pinned an old version" would become indistinguishable from "pinned
    # the current one". A version is a point on the timeline, not a content hash.
    with _cursor() as cur:
        # Read-then-write under one lock, same reason as _bump: the check and
        # the insert must not straddle two transactions or concurrent boots
        # publish two versions from one state.
        cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", ("registry:__community__",))
        cur.execute(
            "SELECT version, content_hash FROM community_versions ORDER BY version DESC LIMIT 1"
        )
        latest = cur.fetchone()
        if latest and str(latest[1]) == digest:
            return int(latest[0])

        cur.execute("SELECT COALESCE(MAX(version), 0) + 1 FROM community_versions")
        version = int(cur.fetchone()[0])
        payload["registry_version"] = version
        payload["content_hash"] = digest
        cur.execute(
            "INSERT INTO community_versions(version, content_hash, snapshot, note, created_by) "
            "VALUES(%s, %s, %s, %s, %s) ON CONFLICT (version) DO NOTHING",
            (version, digest, Json(payload), note or None, created_by),
        )
    logger.info("[VOCAB] catalog version %s published (%s)", version, digest[:12])
    return version


def list_catalog_versions(limit: int = 50) -> List[Dict[str, Any]]:
    """Version history WITHOUT the snapshot bodies.

    Each snapshot is a full catalogue; returning them all turns a history list
    into a multi-megabyte response. Callers who want a body ask for one version.
    """
    from app.storage.metadata_db import _fetch_all

    return _fetch_all(
        "SELECT v.version, v.content_hash, v.note, v.created_at, u.username AS created_by_username "
        "FROM community_versions v LEFT JOIN users u ON u.id = v.created_by "
        "ORDER BY v.version DESC LIMIT %s",
        (max(1, min(int(limit), 500)),),
    )


def get_catalog_version(version: int) -> Optional[Dict[str, Any]]:
    """One frozen system-catalogue snapshot, or None. Mirrors get_registry_version on
    the tenant plane so "what did the template look like at v3" is answerable
    with the same call shape on both planes."""
    from app.storage.metadata_db import _fetch_all

    rows = _fetch_all(
        "SELECT version, content_hash, snapshot, note, created_at "
        "FROM community_versions WHERE version = %s",
        (int(version),),
    )
    return rows[0] if rows else None


def clone_catalog_to_tenant(tenant_id: str, created_by: Optional[str] = None) -> Dict[str, int]:
    """Bootstrap a tenant's own registry from the system catalogue. ONCE.

    This is the only place the system catalogue is read on a tenant's behalf.
    Everything afterwards reads the tenant's own tables — there is deliberately
    no runtime path back to the catalogue, because a tenant that lost its registry
    must fail loudly rather than silently adopt somebody else's vocabulary.

    Idempotent by ON CONFLICT DO NOTHING, so re-running never clobbers edits the
    tenant has since made to its clone.
    """
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenant_context import tenant_scope

    catalog_version = publish_catalog_version(created_by, note=f"clone -> {tenant_id}")
    # `regions` KHÔNG được nhân bản ở đây: nó là bảng toàn cục, cùng hình dạng
    # với `languages`. Xem khối v3.19 trong metadata_db để biết vì sao bản theo
    # tenant bị bỏ.
    counts = {"dialects": 0, "profiles": 0}

    # Phạm vi của TENANT ĐÍCH, không phải phạm vi nền tảng.
    #
    # Mọi phép ghi dưới đây đều mang `tenant_id` của đúng tenant ấy, nên đây là
    # thao tác "hành động NHÂN DANH tenant đích" — hẹp hơn hẳn `system_scope`,
    # và đủ để thoả vế WITH CHECK của `dialects`, `recognition_profiles`,
    # `vocabulary_registry_meta` lẫn `tenants`.
    #
    # Hai bảng NGUỒN (`community_dialects`, `community_profiles`) không mang cột
    # `tenant_id` nên không thuộc diện RLS — chúng đọc được dưới mọi phạm vi.
    #
    # Trước 15/08/2026 hàm này KHÔNG có phạm vi nào. Vì `dialects` đã bật RLS từ
    # lâu, endpoint `POST /vocabulary/catalog/clone` đã hỏng từ trước:
    #
    #     psycopg2.errors.InsufficientPrivilege:
    #     new row violates row-level security policy for table "dialects"
    #
    # Lỗi ấy sống sót qua mọi lượt kiểm cho tới khi có một bài kiểm gọi ĐÚNG
    # endpoint. Bài kiểm dựng lại khuôn `system_scope` rồi kiểm chính khuôn ấy
    # thì không bao giờ chạm tới hàm này.
    with tenant_scope(tenant_id):
        for r in _fetch_all("SELECT * FROM community_dialects ORDER BY display_order, dialect_id"):
            _execute(
                "INSERT INTO dialects(tenant_id, dialect_id, display_name, language, is_alphabet, "
                "is_active, status, note, approved_at) "
                "VALUES(%s, %s, %s, %s, %s, %s, 'approved', %s, NOW()) "
                "ON CONFLICT (tenant_id, dialect_id) DO NOTHING",
                (tenant_id, r["dialect_id"], r["display_name"], r["language"],
                 r["is_alphabet"], r["is_active"], r.get("note")),
            )
            counts["dialects"] += 1

        for r in _fetch_all("SELECT * FROM community_profiles WHERE is_active = TRUE "
                            "ORDER BY display_order, profile_id"):
            _execute(
                "INSERT INTO recognition_profiles(tenant_id, profile_id, display_name, is_trainable, display_order) "
                "VALUES(%s, %s, %s, %s, %s) ON CONFLICT (tenant_id, profile_id) DO NOTHING",
                (tenant_id, r["profile_id"], r["display_name"], r["is_trainable"], r["display_order"]),
            )
            counts["profiles"] += 1

        _execute(
            "INSERT INTO vocabulary_registry_meta(tenant_id, version) VALUES(%s, 0) "
            "ON CONFLICT (tenant_id) DO NOTHING",
            (tenant_id,),
        )
        _execute(
            "UPDATE tenants SET cloned_from_community_version = %s, cloned_at = NOW() "
            "WHERE tenant_id = %s AND cloned_from_community_version IS NULL",
            (catalog_version, tenant_id),
        )
        _bump(tenant_id, created_by=created_by,
              note=f"clone từ system catalog v{catalog_version}")
    logger.info("[VOCAB] tenant %s cloned from system catalog v%s: %s",
                tenant_id, catalog_version, counts)
    return counts


def seed_from_csv(csv_path: Optional[Path] = None, tenant_id: str = DEFAULT_TENANT) -> int:
    """Back-compat entry point used by init_db: seed the system catalogue, then bootstrap
    the default tenant from it. Idempotent at both steps."""
    counts = seed_system_catalog()
    clone_catalog_to_tenant(tenant_id)
    return counts["dialects"]


# ---------------------------------------------------------------------------
# Phân loại vùng: chuyển một lớp từ `unclassified` sang vùng đã xác minh
# ---------------------------------------------------------------------------

class RegionReclassifyError(Exception):
    """Không chuyển được, kèm lý do đọc được cho người vận hành."""

    def __init__(self, message: str, *, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def reclassify_class_region(
    class_uid: str,
    target_region: str,
    *,
    tenant_id: Optional[str] = None,
    actor: Optional[Dict[str, Any]] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Đổi vùng của MỘT lớp, giữ nguyên mọi thứ khác.

    Đây là trường hợp TỐT: bản ghi `unclassified` hoá ra chính là biến thể của
    một miền cụ thể, nên chỉ cần đổi phân loại. `class_uid` giữ nguyên, nên
    mẫu, tệp npz, video và lịch sử đều đi theo mà không phải chép hay dời gì.

    Trường hợp KHÔNG xử lý được ở đây: một bản ghi `unclassified` thực chất
    chứa dữ liệu lẫn của nhiều vùng. Lúc đó đổi phân loại là nói dối về phần
    dữ liệu còn lại — phải TÁCH thành nhiều lớp rồi chia mẫu về đúng chỗ, và
    việc đó cần người quyết định từng mẫu chứ không phải một hàm. Hàm này cố ý
    KHÔNG đoán: nó chỉ đổi nhãn, và người gọi phải biết mình đang đổi cái gì.

    Hai cửa chặn, và cả hai đều cần thiết:

      * Đích phải có trong `regions` của ĐÚNG tenant và đang bật. Khoá ngoại
        đã chặn mã không tồn tại, nhưng nó không phân biệt được "chưa có" với
        "đã nghỉ hưu" — chuyển vào một vùng đã tắt là tạo dữ liệu không hiện ra
        ở đâu cả.
      * Không được đụng một lớp đã tồn tại ở đúng (slug, language, dialect,
        vùng đích). Khoá duy nhất sẽ ném, nhưng thông báo của Postgres không
        nói được cho người vận hành rằng việc cần làm là GỘP chứ không phải
        đổi. Bắt trước để trả lời đúng câu hỏi đó.
    """
    from app import audit
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenancy import DEFAULT_TENANT_ID, normalize_tenant_id

    tid = normalize_tenant_id(tenant_id) if tenant_id else DEFAULT_TENANT_ID
    dich = (target_region or "").strip().lower()
    if not dich:
        raise RegionReclassifyError("thiếu vùng đích")

    rows = _fetch_all(
        "SELECT slug, language, dialect, region, label_original FROM classes "
        "WHERE tenant_id = %s AND class_uid = %s AND deleted_at IS NULL",
        (tid, class_uid),
    )
    if not rows:
        raise RegionReclassifyError(f"không có lớp {class_uid!r}", status_code=404)
    lop = rows[0]
    nguon = (lop.get("region") or "").strip()
    if nguon == dich:
        return {"class_uid": class_uid, "from": nguon, "to": dich, "changed": False}

    hop_le = _fetch_all("SELECT is_active FROM regions WHERE code = %s", (dich,))
    if not hop_le:
        raise RegionReclassifyError(f"vùng {dich!r} không có trong danh mục")
    if not hop_le[0].get("is_active", True):
        raise RegionReclassifyError(f"vùng {dich!r} đã nghỉ hưu, không nhận lớp mới")

    dung = _fetch_all(
        "SELECT class_uid FROM classes WHERE tenant_id = %s AND slug = %s "
        "AND language = %s AND dialect = %s AND region = %s "
        "AND deleted_at IS NULL AND class_uid <> %s",
        (tid, lop["slug"], lop["language"], lop["dialect"], dich, class_uid),
    )
    if dung:
        raise RegionReclassifyError(
            f"đã có lớp {dung[0]['class_uid']!r} cho {lop['slug']!r} ở vùng "
            f"{dich!r} — việc cần làm là GỘP hai lớp, không phải đổi phân loại",
            status_code=409,
        )

    _execute(
        "UPDATE classes SET region = %s WHERE tenant_id = %s AND class_uid = %s",
        (dich, tid, class_uid),
    )
    audit.record(
        "class.region.reclassify",
        actor=actor,
        target_type="class",
        target_id=class_uid,
        detail={"from": nguon, "to": dich, "label": lop.get("label_original"),
                "note": note},
        tenant_id=tid,
    )
    return {"class_uid": class_uid, "from": nguon, "to": dich, "changed": True}

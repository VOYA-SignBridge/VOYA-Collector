"""Admin API for managing SOT (Source of Truth) machines + inspecting the catalog.

Backs the SOT admin page. All endpoints require an admin session. Machine
registration is DB-backed (metadata_db.sot_authorized_keys) and unioned into the
reader's verify path by reader_sync.effective_authorized_keys, so a machine
registered here is trusted by THIS deployment immediately — no git commit /
redeploy. The committed authorized_keys.json stays the read-only baseline.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app.auth import require_admin
from app.sot import catalog_schema, keys
from app.sot import manifest as m
from app.storage import metadata_db as db

router = APIRouter(prefix="/admin/sot", tags=["admin", "sot"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_ed25519_pubkey(public_b64: str) -> bool:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

    try:
        Ed25519PublicKey.from_public_bytes(base64.b64decode((public_b64 or "").strip()))
        return True
    except Exception:
        return False


def _list_machines() -> List[Dict[str, Any]]:
    """Committed baseline (read-only) + active DB registrations (revocable)."""
    out: List[Dict[str, Any]] = []
    committed_pks = set()
    for e in keys.load_authorized_keys():
        pk = e.get("public_key")
        committed_pks.add(pk)
        out.append({
            "name": e.get("name"),
            "fingerprint": e.get("fingerprint") or (keys.fingerprint(pk) if pk else None),
            "public_key": pk,
            "added_at": e.get("added_at"),
            "added_by": None,
            "note": None,
            "source": "committed",
            "revocable": False,
        })
    for row in db.sot_list_authorized_keys(include_revoked=False):
        pk = row.get("public_key")
        if pk in committed_pks:
            continue  # a key that is also committed is shown once, as committed
        out.append({
            "name": row.get("name"),
            "fingerprint": row.get("fingerprint"),
            "public_key": pk,
            "added_at": row.get("added_at"),
            "added_by": row.get("added_by"),
            "note": row.get("note"),
            "source": "db",
            "revocable": True,
        })
    return out


def _db_counts() -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for table in ("classes", "samples", "raw_uploads"):
        try:
            rows = db._fetch_all(f"SELECT COUNT(*) AS c FROM {table} WHERE deleted_at IS NULL")
            counts[table] = int(rows[0]["c"]) if rows else 0
        except Exception:
            counts[table] = -1  # -1 => query failed (table missing / DB down)
    return counts


def _this_machine() -> Dict[str, Any]:
    """Whether THIS deployment holds a writer private key (servers do not)."""
    try:
        pk = keys.load_private_key()
        pub = keys.public_key_b64(pk)
        return {"is_writer": True, "fingerprint": keys.fingerprint(pub), "public_key": pub}
    except Exception:
        return {"is_writer": False, "fingerprint": None, "public_key": None}


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get("/overview")
def sot_overview(current_user: Dict[str, Any] = Depends(require_admin)):
    """Fast, DB-side snapshot — no Drive round-trip (see /remote for that)."""
    return {
        "machines": _list_machines(),
        "db_counts": _db_counts(),
        "schema_version": catalog_schema.schema_version(),
        "this_machine": _this_machine(),
    }


@router.get("/schema")
def sot_schema(current_user: Dict[str, Any] = Depends(require_admin)):
    """Schema shape, without the DDL.

    This used to return export_schema_sql() and the page rendered the whole
    CREATE TABLE listing — column types, defaults, constraints and all. Admin
    auth guards who can call it, but it does not guard where the output ends up:
    the DDL was on screen for anyone behind the operator, in any screenshot, in
    any screen share. The table/column inventory below answers the question the
    page actually asks ("is this deployment's schema the expected shape?")
    without publishing the blueprint of the database.
    """
    return {
        "schema_version": catalog_schema.schema_version(),
        "required_columns": catalog_schema.REQUIRED_COLUMNS,
    }


@router.get("/remote")
def sot_remote(current_user: Dict[str, Any] = Depends(require_admin)):
    """The published SOT on Drive (slower — one Drive round-trip). Best-effort:
    returns available=false with an error instead of 500 when Drive is down."""
    from app.sot.reader_sync import effective_authorized_keys
    from app.sot.store import GDriveSotStore, read_text

    try:
        store = GDriveSotStore(read_only=True)
        if not store.exists(m.LATEST_NAME):
            return {"available": True, "published": False}

        latest = json.loads(store.read_bytes(m.LATEST_NAME).decode("utf-8"))
        version = latest.get("version")
        manifest_bytes = store.read_bytes(f"{version}/{m.MANIFEST_NAME}")
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        try:
            sig = read_text(store, f"{version}/{m.MANIFEST_SIG_NAME}")
            signed_by = keys.verify_with_authorized(
                manifest_bytes, sig, effective_authorized_keys()
            )
        except Exception:
            signed_by = None

        row_counts = manifest.get("row_counts", {})
        files = [
            {"name": name, "sha256": h, "rows": row_counts.get(name)}
            for name, h in sorted(manifest.get("files", {}).items())
        ]
        return {
            "available": True,
            "published": True,
            "version": version,
            "machine": manifest.get("machine"),
            "signed_by": signed_by,
            "trusted": signed_by is not None,
            "created_at": manifest.get("created_at"),
            "schema_version": manifest.get("schema_version"),
            "row_counts": row_counts,
            "files": files,
        }
    except Exception as exc:  # network/creds/etc — surface, don't 500
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"}


@router.post("/verify")
def sot_verify(current_user: Dict[str, Any] = Depends(require_admin)):
    """Dry-run verify the published SOT (signatures + checksums). Read-only."""
    from app.sot.reader_sync import (
        CatalogSink, SotSyncRejected, effective_authorized_keys, sync_from_sot,
    )
    from app.sot.store import GDriveSotStore

    noop = CatalogSink(
        apply_schema=lambda _s: None,
        column_exists=lambda _t, _c: True,
        count_rows=lambda _t: 0,
        upsert_class=lambda _r: None,
        upsert_sample=lambda _r: None,
        upsert_raw_upload=lambda _r: None,
    )
    try:
        res = sync_from_sot(GDriveSotStore(read_only=True), noop, authorized_keys=effective_authorized_keys())
        return {"ok": True, "status": res.status, "version": res.version, "signed_by": res.signed_by}
    except SotSyncRejected as exc:
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


# ---------------------------------------------------------------------------
# Machine registration / revocation
# ---------------------------------------------------------------------------

class RegisterMachine(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    note: Optional[str] = Field(None, max_length=500)
    mode: str = Field("public_key", pattern="^(public_key|generate)$")
    public_key: Optional[str] = Field(None, max_length=500)


@router.post("/machines", status_code=status.HTTP_201_CREATED)
def register_machine(payload: RegisterMachine, current_user: Dict[str, Any] = Depends(require_admin)):
    name = payload.name.strip()
    machines = _list_machines()
    if any((mm.get("name") or "").lower() == name.lower() for mm in machines):
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Tên máy '{name}' đã được dùng.")

    private_key_b64: Optional[str] = None
    if payload.mode == "generate":
        pk = keys.generate_private_key()
        public_b64 = keys.public_key_b64(pk)
        private_key_b64 = keys.private_key_to_b64(pk)
    else:
        public_b64 = (payload.public_key or "").strip()
        if not public_b64:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Thiếu public_key.")
        if not _valid_ed25519_pubkey(public_b64):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="public_key không hợp lệ (phải là Ed25519 base64).")

    if any(mm.get("public_key") == public_b64 for mm in machines):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Public key này đã được đăng ký.")

    fp = keys.fingerprint(public_b64)
    try:
        db.sot_add_authorized_key(
            name=name, public_key=public_b64, fingerprint=fp,
            added_by=current_user.get("username"), note=payload.note,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Không thể đăng ký: {exc}")

    result: Dict[str, Any] = {
        "machine": {
            "name": name, "fingerprint": fp, "public_key": public_b64,
            "source": "db", "revocable": True, "added_by": current_user.get("username"),
            "note": payload.note,
        }
    }
    if private_key_b64 is not None:
        # Returned exactly ONCE. The admin must save it on the writer machine at
        # SOT_PRIVATE_KEY_PATH (default ~/.voya/sot_private.key); it is never stored here.
        result["private_key"] = private_key_b64
        result["private_key_hint"] = (
            "Lưu chuỗi này vào máy writer tại ~/.voya/sot_private.key (0600). "
            "Server KHÔNG lưu — mất là phải đăng ký máy mới."
        )
    return result


@router.delete("/machines/{fingerprint}")
def revoke_machine(fingerprint: str, current_user: Dict[str, Any] = Depends(require_admin)):
    # A committed-baseline key cannot be revoked from the UI (it lives in git).
    for mm in _list_machines():
        if mm.get("fingerprint") == fingerprint and mm.get("source") == "committed":
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Máy này nằm trong authorized_keys.json (committed) — gỡ bằng cách sửa file + commit, không gỡ qua UI được.",
            )
    if not db.sot_revoke_authorized_key(fingerprint):
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Không tìm thấy máy đang hoạt động với fingerprint này.")
    return {"revoked": True, "fingerprint": fingerprint}

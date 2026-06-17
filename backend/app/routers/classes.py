from typing import Optional, Dict, Any
import json
import unicodedata
from pathlib import Path
from filelock import FileLock
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from app.dataset_manager import get_or_register_class, list_classes, normalize_dialect
from app.dataset_samples import list_samples
from app.balancer import build_balance_plan
from app.api_validation import validate_label, validate_language, validate_dialect
from app.catalog_sync import CatalogSyncError, sync_delete_class, sync_update_class
from app.config import settings
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/classes", tags=["classes"])

# ---------------------------------------------------------------------------
# Preferences file (replaces localStorage on frontend)
# ---------------------------------------------------------------------------
_PREFS_PATH = Path(settings.dataset_root) / "user_preferences.json"
_PREFS_LOCK = str(_PREFS_PATH) + ".lock"


def _load_prefs() -> dict:
    if not _PREFS_PATH.exists():
        return {}
    try:
        with open(_PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_prefs(data: dict) -> None:
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock = FileLock(_PREFS_LOCK)
    with lock:
        with open(_PREFS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Text normalization for prefix matching (remove diacritics)
# ---------------------------------------------------------------------------
def _normalize_search(text: str) -> str:
    """Normalize text for prefix search: lowercase, remove diacritics."""
    if not text:
        return ""
    t = text.strip().lower()
    t = t.replace("\u0111", "d").replace("\u0110", "D")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return t


@router.post("/register")
def register_class(payload: dict = Body(...)):
    label = validate_label(payload.get("label"))
    language = validate_language(payload.get("language", "vn"))
    dialect = validate_dialect(normalize_dialect(payload.get("dialect", "")))
    is_common_global = bool(payload.get("is_common_global", False))
    is_common_language = bool(payload.get("is_common_language", False))
    meta = get_or_register_class(
        label_original=label,
        language=language,
        dialect=dialect,
        is_common_global=is_common_global,
        is_common_language=is_common_language,
    )
    return {
        "success": True,
        "class_uid": meta.class_uid,
        "slug": meta.slug,
        "language": meta.language,
        "dialect": meta.dialect,
    }


@router.get("/list")
def list_endpoint(language: Optional[str] = None, dialect: Optional[str] = None):
    metas = list_classes(language=language, dialect=dialect)
    return {"count": len(metas), "items": [m.to_label_row() for m in metas]}


@router.get("/suggest")
def suggest_labels(
    q: str = Query("", description="Search prefix"),
    language: Optional[str] = None,
    dialect: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
):
    """Autocomplete label suggestions by prefix match.

    Returns labels from the currently selected language+dialect that
    start with the query text (diacritics-insensitive prefix match).
    When q is empty, returns the first `limit` labels sorted A-Z.
    """
    metas = list_classes(language=language, dialect=dialect)

    # Deduplicate by label_original
    seen: set = set()
    unique_labels: list = []
    for m in metas:
        label = m.label_original.strip()
        if label and label not in seen:
            seen.add(label)
            unique_labels.append(label)

    unique_labels.sort()

    query_norm = _normalize_search(q)

    if not query_norm:
        return {"suggestions": unique_labels[:limit]}

    matches = [
        label
        for label in unique_labels
        if _normalize_search(label).startswith(query_norm)
    ]
    return {"suggestions": matches[:limit]}


@router.get("/collectors")
def search_collectors(
    q: str = Query("", description="Search prefix for collector name"),
    language: Optional[str] = None,
    dialect: Optional[str] = None,
    limit: int = Query(10, ge=1, le=50),
):
    """Search unique collectors (user_ids) from sample data.

    Optionally filtered by language and dialect.
    Returns collector names matching the query prefix.
    """
    samples = list_samples()

    seen: set = set()
    collectors: list = []
    for s in samples:
        user_id = (s.get("user_id") or "").strip()
        if not user_id or user_id in seen:
            continue
        if language and s.get("language", "") != language:
            continue
        if dialect and s.get("dialect", "") != dialect:
            continue
        seen.add(user_id)
        collectors.append(user_id)

    collectors.sort()

    query_norm = _normalize_search(q)
    if not query_norm:
        return {"collectors": collectors[:limit]}

    matches = [
        name for name in collectors if _normalize_search(name).startswith(query_norm)
    ]
    return {"collectors": matches[:limit]}


@router.get("/preferences")
def get_preference(key: str = Query(..., description="Preference key")):
    """Get a user preference value by key."""
    prefs = _load_prefs()
    value = prefs.get(key)
    return {"key": key, "value": value}


@router.post("/preferences")
def set_preference(payload: dict = Body(...)):
    """Set a user preference key-value pair."""
    key = payload.get("key", "").strip()
    value = payload.get("value")
    if not key:
        raise HTTPException(status_code=400, detail="Key is required")

    lock = FileLock(_PREFS_LOCK)
    with lock:
        prefs = _load_prefs()
        prefs[key] = value
        _save_prefs(prefs)

    return {"success": True, "key": key, "value": value}


@router.get("/stats")
def stats(language: Optional[str] = None, dialect: Optional[str] = None):
    metas = list_classes(language=language, dialect=dialect)
    samples = list_samples()
    counts = {m.class_uid: 0 for m in metas}
    for s in samples:
        cid = s.get("class_uid")
        if cid in counts:
            counts[cid] += 1
    max_count = max(counts.values(), default=0)
    distribution = []
    for m in metas:
        c = counts[m.class_uid]
        distribution.append(
            {
                "class_uid": m.class_uid,
                "slug": m.slug,
                "label_original": m.label_original,
                "language": m.language,
                "dialect": m.dialect,
                "count": c,
                "imbalance_ratio": round((c / max_count) if max_count else 0.0, 4),
            }
        )
    return {
        "total_classes": len(metas),
        "max_count": max_count,
        "distribution": distribution,
    }


@router.get("/balance")
def balance_plan(target: int | None = None):
    plan = build_balance_plan(target=target)
    return plan


@router.put("/{class_ref}")
def update_class(
    class_ref: str,
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_update_class(class_ref, payload)
        return {
            "success": True,
            "message": f"Nh\u00e3n \u0111\u01b0\u1ee3c c\u1eadp nh\u1eadt th\u00e0nh c\u00f4ng: {result.get('slug', '')}",
            "op_id": result.get("op_id"),
            "operation_logs": result.get("operation_logs"),
            **result,
        }
    except CatalogSyncError as exc:
        return {
            "success": False,
            "message": f"L\u1ed7i c\u1eadp nh\u1eadt nh\u00e3n: {str(exc)}",
            "error_code": exc.error_code,
            "operation_logs": getattr(exc, "logs", None),
        }


@router.delete("/{class_ref}")
def delete_class(
    class_ref: str,
    current_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_delete_class(class_ref)
        return {
            "success": True,
            "message": f"Nh\u00e3n \u0111\u01b0\u1ee3c x\u00f3a th\u00e0nh c\u00f4ng. \u0110\u00e3 x\u00f3a {result.get('sample_count', 0)} m\u1eabu v\u00e0 {result.get('raw_upload_count', 0)} video g\u1ed1c.",
            "op_id": result.get("op_id"),
            "operation_logs": result.get("operation_logs"),
            **result,
        }
    except CatalogSyncError as exc:
        return {
            "success": False,
            "message": f"L\u1ed7i x\u00f3a nh\u00e3n: {str(exc)}",
            "error_code": exc.error_code,
            "operation_logs": getattr(exc, "logs", None),
        }

from typing import Optional
from fastapi import APIRouter, Body, HTTPException
from app.dataset_manager import get_or_register_class, list_classes
from app.dataset_samples import list_samples
from app.balancer import build_balance_plan
from app.dataset_manager import normalize_dialect
from app.api_validation import validate_label, validate_language, validate_dialect
from app.catalog_sync import CatalogSyncError, sync_delete_class, sync_update_class

router = APIRouter(prefix="/classes", tags=["classes"])

@router.post("/register")
def register_class(payload: dict = Body(...)):
    label = validate_label(payload.get("label"))
    language = validate_language(payload.get("language", "vn"))
    dialect = validate_dialect(normalize_dialect(payload.get("dialect", "")))
    is_common_global = bool(payload.get("is_common_global", False))
    is_common_language = bool(payload.get("is_common_language", False))
    meta = get_or_register_class(label_original=label,
                                 language=language,
                                 dialect=dialect,
                                 is_common_global=is_common_global,
                                 is_common_language=is_common_language)
    return {"success": True, "class_uid": meta.class_uid, "slug": meta.slug, "language": meta.language, "dialect": meta.dialect}

@router.get("/list")
def list_endpoint(language: Optional[str] = None, dialect: Optional[str] = None):
    metas = list_classes(language=language, dialect=dialect)
    return {"count": len(metas), "items": [m.to_label_row() for m in metas]}

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
        distribution.append({
            "class_uid": m.class_uid,
            "slug": m.slug,
            "label_original": m.label_original,
            "language": m.language,
            "dialect": m.dialect,
            "count": c,
            "imbalance_ratio": round((c / max_count) if max_count else 0.0, 4)
        })
    return {"total_classes": len(metas), "max_count": max_count, "distribution": distribution}

@router.get("/balance")
def balance_plan(target: int | None = None):
    plan = build_balance_plan(target=target)
    return plan


@router.put("/{class_ref}")
def update_class(class_ref: str, payload: dict = Body(...)):
    try:
        result = sync_update_class(class_ref, payload)
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/{class_ref}")
def delete_class(class_ref: str):
    try:
        result = sync_delete_class(class_ref)
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path

from app.config import settings
from app.modules.dataset.catalog import load_labels
from app.modules.dataset.samples import list_samples as list_samples_v2
from app.modules.dataset import sample_service
from app.modules.dataset.catalog_sync import (
    CatalogSyncError,
    sync_update_class,
    sync_soft_delete_class,
    sync_soft_delete_sample,
    sync_restore_sample,
    sync_purge_sample,
    list_trash_samples,
    bulk_restore_samples,
    bulk_purge_samples,
    empty_sample_trash,
)
from app.modules.identity import get_current_user, get_current_user_optional, require_admin

router = APIRouter(prefix="/dataset", tags=["dataset"])


# ---- Models ----
class LabelOut(BaseModel):
    class_idx: int
    label_original: str
    slug: str
    folder_name: str
    created_at: str
    dataset_version: str
    notes: str

class SampleOut(BaseModel):
    sample_id: str
    class_idx: int
    folder_name: str
    file: str
    user: str
    session_id: str
    frames: str
    duration: str
    source: str
    created_at: str


# ---- Endpoints ----

def _labels_rows() -> List[Dict[str, str]]:
    return load_labels()


def _class_uid_to_label_row_map() -> Dict[str, Dict[str, str]]:
    rows = _labels_rows()
    return {r.get("class_uid"): r for r in rows if r.get("class_uid")}


@router.post("/labels", response_model=LabelOut)
def create_label(
    label: str = Form(...),
    notes: str = Form(""),
    version: str = Form("v0"),
    language: str = Form("vn"),
    dialect: str = Form("common"),
):
    """Compatibility endpoint.

    Creates/returns a class entry in the new hierarchy while keeping the old response shape.
    """
    from app.modules.dataset.catalog import get_or_register_class

    meta = get_or_register_class(
        label_original=label,
        language=(language or "vn").lower().strip(),
        dialect=(dialect or "common").lower().strip(),
        is_common_language=True,
        is_common_global=False,
    )
    # best-effort: `class_idx` may be empty until migration/assignment
    class_idx = int(meta.class_idx or 0)
    return {
        "class_idx": class_idx,
        "label_original": meta.label_original,
        "slug": meta.slug,
        "folder_name": meta.folder_name(),
        "created_at": "",
        "dataset_version": version or getattr(settings, "dataset_version", "v0"),
        "notes": notes or "",
    }


@router.get("/labels", response_model=List[LabelOut])
def list_labels():
    rows = _labels_rows()
    out: List[Dict[str, Any]] = []
    for r in rows:
        try:
            class_idx = int(r.get("class_idx") or 0)
        except Exception:
            class_idx = 0
        out.append({
            "class_idx": class_idx,
            "label_original": r.get("label_original") or "",
            "slug": r.get("slug") or "",
            "folder_name": r.get("folder_name") or f"{r.get('class_uid','')}_{r.get('slug','')}",
            "created_at": r.get("created_at") or "",
            "dataset_version": getattr(settings, "dataset_version", "v0"),
            "notes": "",
        })
    return out


@router.post("/labels/merge")
def merge_labels(src_class_idx: int = Form(...), dst_class_idx: int = Form(...)):
    # This legacy operation is not supported in the new hierarchy.
    # Keep endpoint but return an explicit error.
    raise HTTPException(status_code=400, detail="/dataset/labels/merge is deprecated; use new hierarchy tools")


@router.put("/labels/{class_ref}")
def update_label(
    class_ref: str,
    label: str = Form(...),
    admin_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_update_class(class_ref, {"label_original": label})
        return {"success": True, "op_id": result.get("op_id"), "operation_logs": result.get("operation_logs"), **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc), "operation_logs": getattr(exc, "logs", None)}) from exc


@router.delete("/labels/{class_ref}")
def delete_label(
    class_ref: str,
    admin_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_soft_delete_class(class_ref)
        return {"success": True, "op_id": result.get("op_id"), "operation_logs": result.get("operation_logs"), **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc), "operation_logs": getattr(exc, "logs", None)}) from exc


@router.get("/samples", response_model=List[SampleOut])
def list_samples():
    samples = list_samples_v2()
    labels_by_uid = _class_uid_to_label_row_map()
    out: List[Dict[str, Any]] = []
    for s in samples:
        class_uid = s.get("class_uid")
        label_row = labels_by_uid.get(class_uid) or {}
        try:
            class_idx = int(label_row.get("class_idx") or 0)
        except Exception:
            class_idx = 0
        folder_name = label_row.get("folder_name") or ""
        source_hint = s.get("storage_key") or s.get("file_path") or ""
        out.append({
            "sample_id": s.get("sample_uid") or "",
            "class_idx": class_idx,
            "folder_name": folder_name,
            "file": Path(source_hint).name if source_hint else "",
            "user": s.get("user_id") or "",
            "session_id": s.get("session_id") or "",
            "frames": str(s.get("seq_len") or ""),
            "duration": "",
            "source": s.get("source_type") or "",
            "created_at": s.get("created_at") or "",
        })
    return out

@router.get("/samples/{sample_id}/data")
def get_sample_data(sample_id: str):
    """
    Trả về file npz/json của sample_id
    """
    try:
        path = sample_service.resolve_sample_artifact(sample_id)
    except (
        sample_service.SampleNotFoundError,
        sample_service.SampleArtifactMissingError,
    ) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(str(path), media_type="application/octet-stream")


@router.get("/samples/trash")
def list_sample_trash(current_user: Dict[str, Any] = Depends(require_admin)):
    """List soft-deleted samples (whose class is still active). Admin only."""
    try:
        items = list_trash_samples()
        return {"count": len(items), "items": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không đọc được thùng rác mẫu: {exc}")


@router.post("/samples/trash/restore")
def bulk_restore_samples_endpoint(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Restore several soft-deleted samples. Body: {sample_uids: [...]}."""
    result = bulk_restore_samples(payload.get("sample_uids") or [])
    return {"success": True, "message": f"Đã khôi phục {result['ok_count']} mẫu.", **result}


@router.post("/samples/trash/purge")
def bulk_purge_samples_endpoint(
    payload: dict = Body(default={}),
    current_user: Dict[str, Any] = Depends(require_admin),
):
    """Permanently delete samples. Body: {sample_uids: [...]} for a selection, or
    {all: true} to empty the whole sample trash. Irreversible."""
    if payload.get("all"):
        result = empty_sample_trash()
    else:
        result = bulk_purge_samples(payload.get("sample_uids") or [])
    return {"success": True, "message": f"Đã xóa vĩnh viễn {result['ok_count']} mẫu.", **result}


@router.delete("/samples/{sample_id}")
def delete_sample(
    sample_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Soft-delete a sample to Trash (restorable)."""
    try:
        sample_service.ensure_sample_access(sample_id, current_user)
    except sample_service.SampleAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        result = sync_soft_delete_sample(sample_id)
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/samples/{sample_id}/restore")
def restore_sample_endpoint(
    sample_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Restore a soft-deleted sample from Trash."""
    try:
        sample_service.ensure_sample_access(sample_id, current_user)
    except sample_service.SampleAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        result = sync_restore_sample(sample_id)
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/samples/{sample_id}/purge")
def purge_sample_endpoint(
    sample_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Permanently delete a sample (file + Drive + DB). Irreversible."""
    try:
        sample_service.ensure_sample_access(sample_id, current_user)
    except sample_service.SampleAccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    try:
        result = sync_purge_sample(sample_id)
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

@router.post("/samples/add")
def add_sample(
    class_idx: int = Form(...),
    user: str = Form(""),
    session_id: str = Form(""),
    frames: int = Form(0),
    duration: float = Form(0.0),
    source: str = Form("video"),
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    try:
        saved = sample_service.save_uploaded_npz(
            class_idx=class_idx,
            filename=file.filename,
            file_object=file.file,
            current_user=current_user,
            user=user,
            session_id=session_id,
            frames=frames,
            duration=duration,
            source=source,
        )
    except sample_service.SampleLabelNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except sample_service.InvalidSampleUploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "ok", "path": saved}

@router.get("/sessions")
@router.get("/dataset/sessions")
def list_sessions(user: str = "", session_id: str = ""):
    """List capture sessions from the unified samples CSV."""
    samples = list_samples_v2()
    # lightweight grouping without pandas
    sessions: Dict[str, Dict[str, Any]] = {}
    for s in samples:
        sid = s.get("session_id") or ""
        if session_id and sid != session_id:
            continue
        uid = s.get("user_id") or ""
        if user and uid != user:
            continue
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "user": uid,
                "labels": [],
                "samples_count": 0,
                "created_at": s.get("created_at") or "",
            }
        sessions[sid]["samples_count"] += 1
        label = s.get("label_original") or ""
        if label and label not in sessions[sid]["labels"]:
            sessions[sid]["labels"].append(label)
    return list(sessions.values())

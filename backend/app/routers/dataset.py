from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from app.config import settings
from app.dataset_manager import load_labels, ClassMetadata
from app.dataset_samples import list_samples as list_samples_v2, save_sequence_npz
from app.storage.gdrive_client import materialize_sample_artifacts
from app.catalog_sync import CatalogSyncError, sync_delete_class, sync_delete_sample, sync_update_class
from app.auth import get_current_user, get_current_user_optional, require_admin
from app.storage.metadata_db import get_sample_owner

router = APIRouter(prefix="/dataset", tags=["dataset"])


def _check_sample_ownership(sample_id: str, current_user: Dict[str, Any]) -> None:
    """Raise 403 if current_user is not the owner of the sample and is not admin.

    Legacy samples with auth_user_id=NULL (guest uploads) can only be deleted by admin.
    """
    if current_user.get("is_admin") or current_user.get("role") == "admin":
        return  # Admin bypass
    owner_id = get_sample_owner(sample_id)
    if owner_id is None:
        # Guest sample or sample not found in DB — only admin can touch
        raise HTTPException(
            status_code=403,
            detail="Chỉ admin mới có thể xóa mẫu không có chủ sở hữu",
        )
    if str(owner_id) != str(current_user["id"]):
        raise HTTPException(
            status_code=403,
            detail="Bạn không có quyền thực hiện thao tác này trên mẫu này",
        )

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
    session_uid: str
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


def _class_idx_to_meta() -> Dict[int, ClassMetadata]:
    out: Dict[int, ClassMetadata] = {}
    for r in _labels_rows():
        try:
            idx = int(r.get("class_idx") or 0)
        except Exception:
            continue
        if idx <= 0:
            continue
        out[idx] = ClassMetadata(
            class_uid=r["class_uid"],
            slug=r["slug"],
            label_original=r["label_original"],
            language=r["language"],
            dialect=r["dialect"],
            is_common_global=bool(int(r.get("is_common_global") or 0)),
            is_common_language=bool(int(r.get("is_common_language") or 0)),
            class_idx=idx,
        )
    return out


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
    from app.dataset_manager import get_or_register_class

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
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    from app.dataset_manager import load_labels
    from app.dataset_samples import list_samples as list_samples_v2
    from app.catalog_sync import _find_class_row_by_ref
    
    rows = load_labels()
    target_class = _find_class_row_by_ref(rows, class_ref)
    if not target_class:
        raise HTTPException(status_code=404, detail="Class not found")
        
    class_uid = target_class.get("class_uid")
    all_samples = list_samples_v2()
    class_samples = [s for s in all_samples if s.get("class_uid") == class_uid and not s.get("deleted_at")]
    
    my_samples = [s for s in class_samples if s.get("user_id") == current_user["id"]]
    other_samples = [s for s in class_samples if s.get("user_id") != current_user["id"]]
    
    is_admin = current_user.get("is_admin", False)
    
    if not is_admin and not my_samples:
        raise HTTPException(status_code=403, detail="You do not own any samples in this class.")
        
    if is_admin or not other_samples:
        # Direct update
        try:
            result = sync_update_class(class_ref, {"label_original": label})
            return {"success": True, "op_id": result.get("op_id"), "operation_logs": result.get("operation_logs"), **result}
        except CatalogSyncError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"error": str(exc), "operation_logs": getattr(exc, "logs", None)}) from exc
    else:
        # Forking logic for normal user
        from app.catalog_sync import sync_fork_class_for_user
        try:
            result = sync_fork_class_for_user(class_ref, {"label_original": label}, current_user["id"])
            return {"success": True, "op_id": result.get("op_id"), "operation_logs": result.get("operation_logs"), **result}
        except CatalogSyncError as exc:
            raise HTTPException(status_code=exc.status_code, detail={"error": str(exc), "operation_logs": getattr(exc, "logs", None)}) from exc


@router.delete("/labels/{class_ref}")
def delete_label(
    class_ref: str,
    admin_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_delete_class(class_ref)
        return {"success": True, "op_id": result.get("op_id"), "operation_logs": result.get("operation_logs"), **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc), "operation_logs": getattr(exc, "logs", None)}) from exc


@router.get("/samples", response_model=List[SampleOut])
def list_samples(class_uid: Optional[str] = None):
    samples = list_samples_v2()
    labels_by_uid = _class_uid_to_label_row_map()
    out: List[Dict[str, Any]] = []
    for s in samples:
        if class_uid and s.get("class_uid") != class_uid:
            continue
        c_uid = s.get("class_uid")
        label_row = labels_by_uid.get(c_uid) or {}
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
            "user": s.get("username") or s.get("user_id") or "",
            "session_uid": s.get("session_uid") or s.get("session_id") or "",
            "frames": str(s.get("seq_len") or ""),
            "duration": "",
            "source": s.get("source_type") or "",
            "created_at": s.get("created_at") or "",
            "storage_key": s.get("storage_key") or "",
            "storage_url": s.get("storage_url") or "",
        })
    return out

@router.get("/samples/{sample_id}/data")
def get_sample_data(sample_id: str):
    """
    Trả về file npz/json của sample_id
    """
    samples = list_samples_v2()
    match = next((s for s in samples if (s.get("sample_uid") == sample_id)), None)
    if not match:
        raise HTTPException(status_code=404, detail="Sample not found")
    file_path = match.get("file_path") or ""
    if file_path and Path(file_path).exists():
        return FileResponse(file_path, media_type="application/octet-stream")

    cache_dir = Path(settings.dataset_root) / "cache" / "sample_downloads"
    resolved = materialize_sample_artifacts([match], cache_dir)
    if not resolved:
        raise HTTPException(status_code=404, detail="Sample file missing on disk")
    return FileResponse(str(resolved[0]), media_type="application/octet-stream")


@router.delete("/samples/{sample_id}")
def delete_sample(
    sample_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _check_sample_ownership(sample_id, current_user)
    try:
        result = sync_delete_sample(sample_id)
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put("/samples/{sample_id}")
def update_sample(
    sample_id: str,
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    from app.catalog_sync import sync_update_sample
    _check_sample_ownership(sample_id, current_user)
    try:
        result = sync_update_sample(sample_id, payload)
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

@router.post("/samples/add")
def add_sample(
    class_idx: int = Form(...),
    user: str = Form(""),
    session_uid: str = Form(""),
    frames: int = Form(0),
    duration: float = Form(0.0),
    source: str = Form("video"),
    file: UploadFile = File(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    idx_to_meta = _class_idx_to_meta()
    meta = idx_to_meta.get(int(class_idx))
    if not meta:
        raise HTTPException(status_code=404, detail="label not found (class_idx)")
    if not file.filename.endswith(".npz"):
        raise HTTPException(status_code=400, detail="Only .npz uploads are supported")

    try:
        data = np.load(file.file, allow_pickle=False)
        seq = data.get("sequence")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid npz")
    if seq is None or not isinstance(seq, np.ndarray) or seq.ndim != 2:
        raise HTTPException(status_code=400, detail="npz must contain 2D 'sequence'")

    saved = save_sequence_npz(
        meta,
        seq.astype(np.float32),
        meta={
            "user": user or current_user.get("username", ""),
            "user_id": current_user["id"],
            "session_uid": session_uid,
            "fps_original": "",
            "fps_processed": "",
            "completeness": "",
            "frames": int(frames or seq.shape[0]),
            "duration": str(duration or ""),
            "source": source,
        },
        augment_id=0,
        source_type=source or "upload",
    )
    return {"status": "ok", "path": saved}

@router.get("/sessions")
@router.get("/dataset/sessions")
def list_sessions(user: str = "", session_uid: str = ""):
    """List capture sessions from the unified samples CSV."""
    samples = list_samples_v2()
    # lightweight grouping without pandas
    sessions: Dict[str, Dict[str, Any]] = {}
    for s in samples:
        sid = s.get("session_uid") or s.get("session_id") or ""
        if session_uid and sid != session_uid:
            continue
        uid = s.get("user_id") or ""
        if user and uid != user:
            continue
        if sid not in sessions:
            sessions[sid] = {
                "session_uid": sid,
                "user": uid,
                "samples_count": 0,
                "created_at": s.get("created_at") or "",
            }
        sessions[sid]["samples_count"] += 1
    return list(sessions.values())

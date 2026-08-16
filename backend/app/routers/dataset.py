from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Body, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from pathlib import Path
import numpy as np

from app import audit
from app.config import settings
from app.dataset_manager import load_labels, ClassMetadata
from app.tenancy import tenant_id_of
from app.dataset_samples import list_samples as list_samples_v2, save_sequence_npz
from app.storage.gdrive_client import materialize_sample_artifacts
from app.catalog_sync import (
    CatalogSyncError,
    sync_update_class,
    sync_soft_delete_class,
    sync_soft_delete_sample,
    sync_restore_sample,
    sync_purge_sample,
    list_trash_samples,
    list_trash_samples_for_user,
    bulk_restore_samples,
    bulk_purge_samples,
    empty_sample_trash,
)
from app.auth import get_current_user, get_current_user_optional, require_admin
from app.tenant_context import require_tenant
from app.storage.metadata_db import get_sample_owner, partition_sample_ownership

router = APIRouter(prefix="/dataset", tags=["dataset"])


def _check_sample_ownership(sample_id: str, current_user: Dict[str, Any]) -> None:
    """Raise 403 if current_user is not the owner of the sample and is not admin.

    Legacy samples with auth_user_id=NULL (guest uploads) can only be deleted by admin.
    """
    if current_user.get("is_admin"):
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


_SKIP_REASONS = {
    "foreign": "thuộc về tài khoản khác",
    "unowned": "chưa gắn chủ sở hữu (dữ liệu cũ) — cần admin",
    "missing": "không có trong cơ sở dữ liệu",
}


def _actionable_uids(
    uids: List[str], current_user: Dict[str, Any]
) -> tuple[List[str], Dict[str, Any]]:
    """Keep only the uids this caller may act on, and explain the rest.

    Admin acts on everything. For anyone else this is ONE query for the whole
    batch (partition_sample_ownership), not one per uid — a 200-sample
    selection used to mean 200 round-trips.

    The second return value is merged into the response so the UI can say WHY
    something was left out. Silently shrinking the batch is the failure mode
    worth avoiding: selecting 10 and being told "đã khôi phục 7" with no
    mention of the other 3 reads as data loss.
    """
    uids = [str(u).strip() for u in (uids or []) if str(u or "").strip()]
    if current_user.get("is_admin"):
        return uids, {"skipped_count": 0, "skipped": {}}

    split = partition_sample_ownership(uids, str(current_user.get("id") or ""))
    skipped: Dict[str, Any] = {}
    for bucket in ("foreign", "unowned", "missing"):
        items = getattr(split, bucket)
        if items:
            skipped[bucket] = {
                "count": len(items),
                "reason": _SKIP_REASONS[bucket],
                "sample_uids": items[:20],
            }
    return list(split.owned), {"skipped_count": len(split.skipped), "skipped": skipped}


def _skip_note(info: Dict[str, Any]) -> str:
    n = int(info.get("skipped_count") or 0)
    if not n:
        return ""
    parts = [f"{d['count']} {d['reason']}" for d in info.get("skipped", {}).values()]
    return f" Bỏ qua {n} mẫu: " + "; ".join(parts) + "."

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
    """Nhãn MÀ NGƯỜI GỌI ĐƯỢC THẤY.

    Phạm vi đặt ở HELPER chứ không ở từng chỗ gọi: bốn endpoint dùng chung
    hàm này, và một chỗ quên truyền phạm vi là một lỗ. Đặt ở đây thì không
    có chỗ nào để quên.

    `require_tenant()` ném lỗi khi không có ngữ cảnh — đóng, không mở.
    """
    return load_labels(require_tenant())


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
            tenant_id=tenant_id_of(r),
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
    admin_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_update_class(class_ref, {"label_original": label}, tenant_id=require_tenant())
        return {"success": True, "op_id": result.get("op_id"), "operation_logs": result.get("operation_logs"), **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc), "operation_logs": getattr(exc, "logs", None)}) from exc


@router.delete("/labels/{class_ref}")
def delete_label(
    class_ref: str,
    request: Request,
    admin_user: Dict[str, Any] = Depends(require_admin),
):
    try:
        result = sync_soft_delete_class(class_ref, tenant_id=require_tenant())
        audit.record("data.class.soft_delete", actor=admin_user, request=request,
                     target_type="class", target_id=result.get("class_uid") or class_ref,
                     detail={"sample_count": result.get("sample_count"), "via": "labels"})
        return {"success": True, "op_id": result.get("op_id"), "operation_logs": result.get("operation_logs"), **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"error": str(exc), "operation_logs": getattr(exc, "logs", None)}) from exc


# Requires login, unlike the sibling /labels listing. /labels backs the public
# LabelsPage (that route is deliberately outside ProtectedRoute), but this one
# returns a `user` UUID per sample — i.e. who contributed what — and nothing in
# the repo calls it: the frontend only ever uses the /samples/{id}/... subpaths.
# It was reachable anonymously purely by omission.
@router.get("/samples", response_model=List[SampleOut])
def list_samples(current_user: Dict[str, Any] = Depends(get_current_user)):
    # Phân giải TRONG phạm vi người gọi. Mẫu của tenant khác không lọt vào
    # danh sách, nên `match` là None và endpoint trả 404 — GIỐNG HỆT một
    # `sample_id` không tồn tại. Không có phép kiểm tenant nào sau khi tra cứu,
    # nên cũng không có kênh phụ nào giữa hai câu trả lời.
    #
    # Quan trọng với `/data`: việc kiểm `Path(file_path).exists()` nằm SAU bước
    # này, nên sự tồn tại của tệp không bao giờ được hỏi cho một mẫu ngoài phạm
    # vi. Trước 16/08/2026 đường này đọc toàn kho.
    samples = list_samples_v2(require_tenant())
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
    # Phân giải TRONG phạm vi người gọi. Mẫu của tenant khác không lọt vào
    # danh sách, nên `match` là None và endpoint trả 404 — GIỐNG HỆT một
    # `sample_id` không tồn tại. Không có phép kiểm tenant nào sau khi tra cứu,
    # nên cũng không có kênh phụ nào giữa hai câu trả lời.
    #
    # Quan trọng với `/data`: việc kiểm `Path(file_path).exists()` nằm SAU bước
    # này, nên sự tồn tại của tệp không bao giờ được hỏi cho một mẫu ngoài phạm
    # vi. Trước 16/08/2026 đường này đọc toàn kho.
    samples = list_samples_v2(require_tenant())
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


@router.get("/samples/trash")
def list_sample_trash(current_user: Dict[str, Any] = Depends(get_current_user)):
    """List soft-deleted samples (whose class is still active). An admin sees the
    whole sample trash; a contributor sees ONLY their own (by auth_user_id)."""
    try:
        if current_user.get("is_admin"):
            items = list_trash_samples()
        else:
            items = list_trash_samples_for_user(str(current_user["id"]))
        return {"count": len(items), "items": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Không đọc được thùng rác mẫu: {exc}")


@router.post("/samples/trash/restore")
def bulk_restore_samples_endpoint(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Restore several soft-deleted samples. Body: {sample_uids: [...]}. A
    non-admin may only restore samples they own; the rest are reported back in
    `skipped` with a reason instead of vanishing from the count."""
    uids, skip_info = _actionable_uids(payload.get("sample_uids") or [], current_user)
    result = bulk_restore_samples(uids)
    message = f"Đã khôi phục {result['ok_count']} mẫu." + _skip_note(skip_info)
    return {"success": True, "message": message, **result, **skip_info}


@router.post("/samples/trash/purge")
def bulk_purge_samples_endpoint(
    request: Request,
    payload: dict = Body(default={}),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Permanently delete samples. Body: {sample_uids: [...]} for a selection, or
    {all: true} to empty the trash. Irreversible. A non-admin acts ONLY on their
    own samples: {all: true} empties just their trash; anything else is reported
    in `skipped` with a reason."""
    is_admin = bool(current_user.get("is_admin"))
    skip_info: Dict[str, Any] = {"skipped_count": 0, "skipped": {}}
    if payload.get("all"):
        if is_admin:
            result = empty_sample_trash()
        else:
            own = [s["sample_uid"] for s in list_trash_samples_for_user(str(current_user["id"]))]
            result = bulk_purge_samples(own)
    else:
        uids, skip_info = _actionable_uids(payload.get("sample_uids") or [], current_user)
        result = bulk_purge_samples(uids)
    audit.record("data.sample.purge.bulk", actor=current_user, request=request,
                 target_type="sample", detail={
                     "all": bool(payload.get("all")),
                     "as_admin": is_admin,
                     "ok_count": result.get("ok_count"),
                     "skipped_count": skip_info.get("skipped_count"),
                 })
    message = f"Đã xóa vĩnh viễn {result['ok_count']} mẫu." + _skip_note(skip_info)
    return {"success": True, "message": message, **result, **skip_info}


@router.delete("/samples/{sample_id}")
def delete_sample(
    sample_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Soft-delete a sample to Trash (restorable)."""
    _check_sample_ownership(sample_id, current_user)
    try:
        result = sync_soft_delete_sample(sample_id, tenant_id=require_tenant())
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/samples/{sample_id}/restore")
def restore_sample_endpoint(
    sample_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Restore a soft-deleted sample from Trash."""
    _check_sample_ownership(sample_id, current_user)
    try:
        result = sync_restore_sample(sample_id, tenant_id=require_tenant())
        return {"success": True, **result}
    except CatalogSyncError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete("/samples/{sample_id}/purge")
def purge_sample_endpoint(
    sample_id: str,
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Permanently delete a sample (file + Drive + DB). Irreversible."""
    _check_sample_ownership(sample_id, current_user)
    try:
        result = sync_purge_sample(sample_id, tenant_id=require_tenant())
        audit.record("data.sample.purge", actor=current_user, request=request,
                     target_type="sample", target_id=sample_id,
                     detail={"class_uid": result.get("class_uid")})
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
            "auth_user_id": current_user["id"],
            "session_id": session_id,
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
def list_sessions(user: str = "", session_id: str = ""):
    """List capture sessions from the unified samples CSV."""
    # Phân giải TRONG phạm vi người gọi. Mẫu của tenant khác không lọt vào
    # danh sách, nên `match` là None và endpoint trả 404 — GIỐNG HỆT một
    # `sample_id` không tồn tại. Không có phép kiểm tenant nào sau khi tra cứu,
    # nên cũng không có kênh phụ nào giữa hai câu trả lời.
    #
    # Quan trọng với `/data`: việc kiểm `Path(file_path).exists()` nằm SAU bước
    # này, nên sự tồn tại của tệp không bao giờ được hỏi cho một mẫu ngoài phạm
    # vi. Trước 16/08/2026 đường này đọc toàn kho.
    samples = list_samples_v2(require_tenant())
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

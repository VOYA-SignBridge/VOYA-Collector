from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List
import logging

from app.auth import get_current_user
from app.storage.metadata_db import _execute, _get_conn
from app.storage.gdrive_client import get_gdrive_client
from app.limiter import limiter
from fastapi import Request

router = APIRouter(prefix="/trash", tags=["trash"])
log = logging.getLogger("trash")

def _check_admin_or_owner(owner_id: str, current_user: Dict[str, Any]):
    if current_user.get("is_admin"):
        return True
    if owner_id and str(owner_id) == str(current_user.get("id")):
        return True
    raise HTTPException(status_code=403, detail="Forbidden. Not the owner or admin.")

@router.delete("/samples/{sample_uid}")
@limiter.limit("20/minute")
async def soft_delete_sample(
    request: Request,
    sample_uid: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Soft Delete a single sample. Moves the file to Google Drive trash."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, storage_key FROM samples WHERE sample_uid = %s AND deleted_at IS NULL", (sample_uid,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Sample not found or already deleted")
                
                user_id, storage_key = row
                _check_admin_or_owner(user_id, current_user)
                
                # Soft delete in DB
                cur.execute("UPDATE samples SET deleted_at = NOW(), sheets_synced = FALSE WHERE sample_uid = %s", (sample_uid,))
            conn.commit()
            
        # Trash on Google Drive
        if storage_key:
            try:
                gdrive = get_gdrive_client()
                file_id = gdrive.get_file_id_by_path(storage_key)
                if file_id:
                    gdrive.service.files().update(fileId=file_id, body={'trashed': True}).execute()
            except Exception as e:
                log.warning("[TRASH] Failed to trash file on GDrive for %s: %s", sample_uid, e)

        return {"success": True, "message": f"Sample {sample_uid} soft deleted."}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Soft delete failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.delete("/samples")
@limiter.limit("5/minute")
async def batch_soft_delete_samples(
    request: Request,
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Batch Soft Delete by array of IDs or session_uid."""
    sample_uids = payload.get("sample_uids", [])
    session_uid = payload.get("session_uid")
    
    if not sample_uids and not session_uid:
        raise HTTPException(status_code=400, detail="Provide sample_uids or session_uid")
        
    deleted_count = 0
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                if session_uid:
                    cur.execute("SELECT sample_uid, user_id, storage_key FROM samples WHERE session_uid = %s AND deleted_at IS NULL", (session_uid,))
                else:
                    format_strings = ','.join(['%s'] * len(sample_uids))
                    cur.execute(f"SELECT sample_uid, user_id, storage_key FROM samples WHERE sample_uid IN ({format_strings}) AND deleted_at IS NULL", tuple(sample_uids))
                    
                rows = cur.fetchall()
                if not rows:
                    return {"success": True, "deleted_count": 0, "message": "No valid samples found."}
                
                gdrive = get_gdrive_client()
                for (suid, user_id, storage_key) in rows:
                    try:
                        _check_admin_or_owner(user_id, current_user)
                        cur.execute("UPDATE samples SET deleted_at = NOW(), sheets_synced = FALSE WHERE sample_uid = %s", (suid,))
                        deleted_count += 1
                        
                        # Trash on Google Drive
                        if storage_key:
                            try:
                                file_id = gdrive.get_file_id_by_path(storage_key)
                                if file_id:
                                    gdrive.service.files().update(fileId=file_id, body={'trashed': True}).execute()
                            except Exception as e:
                                log.warning("[TRASH] Failed to trash file on GDrive for %s: %s", suid, e)
                    except HTTPException:
                        continue # skip unauthorized
            conn.commit()
            
        return {"success": True, "deleted_count": deleted_count}
    except Exception as e:
        log.error("Batch soft delete failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.post("/samples/{sample_uid}/restore")
@limiter.limit("20/minute")
async def restore_sample(
    request: Request,
    sample_uid: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Restore a soft deleted sample. Untrashes from Google Drive."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, storage_key FROM samples WHERE sample_uid = %s AND deleted_at IS NOT NULL", (sample_uid,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Sample not found or not deleted")
                
                user_id, storage_key = row
                _check_admin_or_owner(user_id, current_user)
                
                cur.execute("UPDATE samples SET deleted_at = NULL, sheets_synced = FALSE WHERE sample_uid = %s", (sample_uid,))
            conn.commit()
            
        # Untrash on Google Drive
        if storage_key:
            try:
                gdrive = get_gdrive_client()
                file_id = gdrive.get_file_id_by_path(storage_key)
                if file_id:
                    gdrive.service.files().update(fileId=file_id, body={'trashed': False}).execute()
            except Exception as e:
                log.warning("[TRASH] Failed to untrash file on GDrive for %s: %s", sample_uid, e)

        return {"success": True, "message": f"Sample {sample_uid} restored."}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Restore failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.delete("/classes/{class_uid}")
@limiter.limit("5/minute")
async def soft_delete_class(
    request: Request,
    class_uid: str,
    admin_user: Dict[str, Any] = Depends(get_current_user)
):
    """Soft Delete a class and all its samples (Cascade). Only admins."""
    if not admin_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Forbidden. Only admin can delete classes.")
        
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                # Mark class as deleted
                cur.execute("UPDATE classes SET deleted_at = NOW(), is_active = FALSE WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Class not found or already deleted")
                
                # Soft delete all samples belonging to this class
                cur.execute("SELECT storage_key FROM samples WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))
                storage_keys = [row[0] for row in cur.fetchall() if row[0]]
                
                cur.execute("UPDATE samples SET deleted_at = NOW(), sheets_synced = FALSE WHERE class_uid = %s AND deleted_at IS NULL", (class_uid,))
                deleted_samples = cur.rowcount
            conn.commit()
            
        # Trash files on Google Drive
        gdrive = get_gdrive_client()
        for key in storage_keys:
            try:
                file_id = gdrive.get_file_id_by_path(key)
                if file_id:
                    gdrive.service.files().update(fileId=file_id, body={'trashed': True}).execute()
            except Exception as e:
                log.warning("[TRASH] Failed to trash file on GDrive for class cascade: %s", e)

        return {"success": True, "message": f"Class {class_uid} and {deleted_samples} samples soft deleted."}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Soft delete class failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.post("/classes/{class_uid}/restore")
@limiter.limit("5/minute")
async def restore_class(
    request: Request,
    class_uid: str,
    admin_user: Dict[str, Any] = Depends(get_current_user)
):
    """Restore a class and all its samples. Only admins."""
    if not admin_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Forbidden. Only admin can restore classes.")
        
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE classes SET deleted_at = NULL, is_active = TRUE WHERE class_uid = %s AND deleted_at IS NOT NULL", (class_uid,))
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Class not found or not deleted")
                
                cur.execute("SELECT storage_key FROM samples WHERE class_uid = %s AND deleted_at IS NOT NULL", (class_uid,))
                storage_keys = [row[0] for row in cur.fetchall() if row[0]]
                
                cur.execute("UPDATE samples SET deleted_at = NULL, sheets_synced = FALSE WHERE class_uid = %s AND deleted_at IS NOT NULL", (class_uid,))
                restored_samples = cur.rowcount
            conn.commit()
            
        # Untrash files on Google Drive
        gdrive = get_gdrive_client()
        for key in storage_keys:
            try:
                file_id = gdrive.get_file_id_by_path(key)
                if file_id:
                    gdrive.service.files().update(fileId=file_id, body={'trashed': False}).execute()
            except Exception as e:
                log.warning("[TRASH] Failed to untrash file on GDrive for class restore: %s", e)

        return {"success": True, "message": f"Class {class_uid} and {restored_samples} samples restored."}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Restore class failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")


@router.get("/samples")
async def get_trashed_samples(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """List soft-deleted samples. Normal users only see their own. Admins see all."""
    try:
        from app.storage.metadata_db import list_trash_samples
        samples = list_trash_samples()
        if not current_user.get("is_admin"):
            samples = [s for s in samples if str(s.get("user_id")) == str(current_user.get("id"))]
        return {"success": True, "data": samples}
    except Exception as e:
        log.error("Failed to list trash samples: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.get("/classes")
async def get_trashed_classes(
    request: Request,
    admin_user: Dict[str, Any] = Depends(get_current_user)
):
    """List soft-deleted classes. Admins only."""
    if not admin_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Forbidden. Only admin can view trash classes.")
    try:
        from app.storage.metadata_db import list_trash_classes
        classes = list_trash_classes()
        return {"success": True, "data": classes}
    except Exception as e:
        log.error("Failed to list trash classes: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.delete("/samples/{sample_uid}/hard")
@limiter.limit("5/minute")
async def hard_delete_sample(
    request: Request,
    sample_uid: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Hard Delete a single sample."""
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id, storage_key FROM samples WHERE sample_uid = %s AND deleted_at IS NOT NULL", (sample_uid,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Sample not found in trash")
                
                user_id, storage_key = row
                _check_admin_or_owner(user_id, current_user)
                
                cur.execute("DELETE FROM samples WHERE sample_uid = %s", (sample_uid,))
            conn.commit()
            
        if storage_key:
            try:
                gdrive = get_gdrive_client()
                file_id = gdrive.get_file_id_by_path(storage_key)
                if file_id:
                    gdrive.service.files().delete(fileId=file_id).execute()
            except Exception as e:
                log.warning("[TRASH] Failed to hard delete file on GDrive for %s: %s", sample_uid, e)

        return {"success": True, "message": f"Sample {sample_uid} hard deleted."}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Hard delete failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.delete("/classes/{class_uid}/hard")
@limiter.limit("2/minute")
async def hard_delete_class(
    request: Request,
    class_uid: str,
    admin_user: Dict[str, Any] = Depends(get_current_user)
):
    """Hard Delete a class. Only admins."""
    if not admin_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Forbidden. Only admin can hard delete classes.")
        
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT storage_key FROM samples WHERE class_uid = %s AND deleted_at IS NOT NULL", (class_uid,))
                storage_keys = [row[0] for row in cur.fetchall() if row[0]]
                
                cur.execute("DELETE FROM samples WHERE class_uid = %s", (class_uid,))
                cur.execute("DELETE FROM classes WHERE class_uid = %s", (class_uid,))
            conn.commit()
            
        gdrive = get_gdrive_client()
        for key in storage_keys:
            try:
                file_id = gdrive.get_file_id_by_path(key)
                if file_id:
                    gdrive.service.files().delete(fileId=file_id).execute()
            except Exception as e:
                log.warning("[TRASH] Failed to hard delete file on GDrive for class cascade: %s", e)

        return {"success": True, "message": f"Class {class_uid} hard deleted."}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Hard delete class failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")


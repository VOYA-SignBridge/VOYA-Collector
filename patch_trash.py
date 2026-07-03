import re
from pathlib import Path

trash_path = Path("backend/app/routers/trash.py")
content = trash_path.read_text("utf-8")

new_endpoints = """
@router.get("/samples")
async def get_trashed_samples(
    request: Request,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    \"\"\"List soft-deleted samples. Normal users only see their own. Admins see all.\"\"\"
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
    \"\"\"List soft-deleted classes. Admins only.\"\"\"
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
    \"\"\"Hard Delete a single sample.\"\"\"
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
    \"\"\"Hard Delete a class. Only admins.\"\"\"
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

"""

if "def get_trashed_samples" not in content:
    content += "\n" + new_endpoints
    trash_path.write_text(content, "utf-8")
    print("Injected new trash endpoints into trash.py")

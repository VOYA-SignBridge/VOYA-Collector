from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any
from datetime import datetime
import uuid
import logging
import re
from app.auth import get_current_user
from app.storage.metadata_db import _execute, _get_conn
from app.dataset_samples import SAMPLES_CSV, SAMPLE_FIELDS
from app.config import settings

router = APIRouter(prefix="/session", tags=["session"])
log = logging.getLogger("session")

def generate_session_uid(source: str, user_id: str) -> str:
    """Generate Batch ID: [LC/UP]-[YYMMDD-HHMM]-[USER_ID_LAST_6]"""
    prefix = "LC" if source == "camera" else "UP"
    timestamp = datetime.utcnow().strftime("%y%m%d-%H%M")
    
    # Extract last 6 chars of user UUID
    # If not a UUID or too short, fallback to random 6 chars
    if not user_id or len(str(user_id)) < 6:
        user_suffix = uuid.uuid4().hex[-6:].upper()
    else:
        user_suffix = str(user_id).replace("-", "")[-6:].upper()
        
    return f"{prefix}-{timestamp}-{user_suffix}"

@router.post("/init")
async def init_session(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Step 1: Initialize a recording session.
    Payload: { "source": "camera" | "upload" }
    Returns: { "session_uid": "LC-..." }
    """
    source = payload.get("source", "camera")
    if source not in ["camera", "upload"]:
        source = "camera"
        
    session_uid = generate_session_uid(source, current_user.get("id"))
    
    # We could insert into a `collection_sessions` table here as per Phase 2.1
    # if it exists, otherwise just return the ID for the client to use.
    # We'll rely on the client passing this ID to /upload/camera.
    
    return {
        "success": True,
        "session_uid": session_uid,
        "message": "Session initialized"
    }

@router.post("/commit")
async def commit_session(
    payload: dict = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Step 3: Commit the session.
    Verifies that the expected number of samples (usually 5) have been uploaded.
    Payload: { "session_uid": "...", "expected_count": 5 }
    """
    session_uid = payload.get("session_uid")
    expected_count = payload.get("expected_count", 5)
    
    if not session_uid:
        raise HTTPException(status_code=400, detail="Missing session_uid")
        
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT count(*) FROM samples WHERE session_uid = %s AND deleted_at IS NULL",
                    (session_uid,)
                )
                actual_count = cur.fetchone()[0]
                
        if actual_count < expected_count:
            return {
                "success": False,
                "status": "incomplete",
                "actual_count": actual_count,
                "expected_count": expected_count,
                "message": f"Session incomplete. Expected {expected_count}, got {actual_count}."
            }
            
        return {
            "success": True,
            "status": "completed",
            "actual_count": actual_count,
            "expected_count": expected_count,
            "message": "Session completed successfully."
        }
    except Exception as e:
        log.error("Commit session failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.delete("/{session_uid}")
async def delete_session(
    session_uid: str,
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Cancel or delete an entire session (all its samples).
    """
    try:
        # Verify ownership or admin
        with _get_conn() as conn:
            with conn.cursor() as cur:
                # Check if session exists and belongs to user
                cur.execute(
                    "SELECT DISTINCT user_id FROM samples WHERE session_uid = %s",
                    (session_uid,)
                )
                rows = cur.fetchall()
                if not rows:
                    raise HTTPException(status_code=404, detail="Session not found or empty")
                
                # Check ownership if not admin
                if not current_user.get("is_admin"):
                    owners = [r[0] for r in rows if r[0]]
                    if str(current_user.get("id")) not in owners:
                        raise HTTPException(status_code=403, detail="Forbidden. Not your session.")
            
        # Soft delete samples
        with _get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE samples SET deleted_at = NOW() WHERE session_uid = %s AND deleted_at IS NULL",
                    (session_uid,)
                )
                deleted_samples = cur.rowcount
                
                cur.execute(
                    "UPDATE raw_uploads SET deleted_at = NOW() WHERE session_uid = %s AND deleted_at IS NULL",
                    (session_uid,)
                )
                deleted_uploads = cur.rowcount
            conn.commit()
            
        return {
            "success": True,
            "deleted_samples": deleted_samples,
            "deleted_uploads": deleted_uploads,
            "message": "Session deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error("Delete session failed: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

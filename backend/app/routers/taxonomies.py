from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List
import logging

from app.auth import get_current_user
from app.storage.metadata_db import _execute, _get_conn, _cursor

router = APIRouter(prefix="/taxonomies", tags=["taxonomies"])
log = logging.getLogger("taxonomies")

@router.get("/languages")
async def get_languages():
    """Get all languages."""
    try:
        with _cursor() as cur:
            cur.execute("SELECT code, name FROM languages ORDER BY name ASC")
            columns = [desc[0] for desc in cur.description]
            return {"success": True, "data": [dict(zip(columns, row)) for row in cur.fetchall()]}
    except Exception as e:
        log.error("Failed to fetch languages: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.get("/dialects")
async def get_dialects(language_code: str = None):
    """Get all dialects, optionally filtered by language."""
    try:
        with _cursor() as cur:
            if language_code:
                cur.execute("SELECT code, language_code, name FROM dialects WHERE language_code = %s ORDER BY name ASC", (language_code,))
            else:
                cur.execute("SELECT code, language_code, name FROM dialects ORDER BY name ASC")
            columns = [desc[0] for desc in cur.description]
            return {"success": True, "data": [dict(zip(columns, row)) for row in cur.fetchall()]}
    except Exception as e:
        log.error("Failed to fetch dialects: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

@router.post("/dialects")
async def create_dialect(
    payload: dict = Body(...),
    admin_user: Dict[str, Any] = Depends(get_current_user)
):
    """Create a new dialect (Admin only)."""
    if not admin_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Forbidden. Only admin can add dialects.")
    
    code = payload.get("code")
    name = payload.get("name")
    language_code = payload.get("language_code", "vn")
    
    if not code or not name:
        raise HTTPException(status_code=400, detail="Missing code or name")
        
    try:
        with _get_conn() as conn:
            with conn.cursor() as cur:
                # check if language exists
                cur.execute("SELECT 1 FROM languages WHERE code = %s", (language_code,))
                if not cur.fetchone():
                    raise HTTPException(status_code=400, detail=f"Language {language_code} not found")
                
                # Check if dialect code already exists
                cur.execute("SELECT 1 FROM dialects WHERE code = %s", (code,))
                if cur.fetchone():
                    raise HTTPException(status_code=400, detail=f"Dialect code {code} already exists")
                
                cur.execute(
                    "INSERT INTO dialects (code, language_code, name) VALUES (%s, %s, %s) RETURNING code, language_code, name",
                    (code, language_code, name)
                )
                row = cur.fetchone()
                columns = [desc[0] for desc in cur.description]
                new_dialect = dict(zip(columns, row))
            conn.commit()
            
        return {"success": True, "data": new_dialect}
    except HTTPException:
        raise
    except Exception as e:
        log.error("Failed to create dialect: %s", e)
        raise HTTPException(status_code=500, detail="Database error")

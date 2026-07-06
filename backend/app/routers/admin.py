from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import get_current_user, require_admin
from app.storage.postgres_connection import connect_postgres
from psycopg2.extras import RealDictCursor
from app.sync_tasks import download_missing_files_to_local

router = APIRouter(prefix="/admin", tags=["admin"])

class UserRoleUpdate(BaseModel):
    is_admin: bool

@router.get("/users")
def get_all_users(current_user: Dict[str, Any] = Depends(require_admin)):
    """Lấy danh sách tất cả người dùng (Chỉ Admin)"""
    conn = connect_postgres()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, username, email, is_active, is_admin, created_at
                    FROM users
                    ORDER BY created_at DESC
                    """
                )
                users = cur.fetchall()
                # Chuyển đổi UUID/datetime sang string để FastAPI tự serialize
                for u in users:
                    u["id"] = str(u["id"])
                    if u["created_at"]:
                        u["created_at"] = u["created_at"].isoformat()
                return users
    finally:
        conn.close()

@router.put("/users/{user_id}/role")
def update_user_role(
    user_id: str, 
    payload: UserRoleUpdate,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Cập nhật quyền của người dùng (Chỉ Admin)"""
    # Không cho phép tự gỡ quyền admin của chính mình
    if str(user_id) == str(current_user["id"]) and not payload.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thể tự gỡ quyền Admin của chính mình."
        )

    conn = connect_postgres()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "UPDATE users SET is_admin = %s WHERE id = %s RETURNING id, username, is_admin",
                    (payload.is_admin, user_id)
                )
                updated = cur.fetchone()
                if not updated:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Không tìm thấy người dùng"
                    )
                return {"status": "success", "user": {"id": str(updated["id"]), "username": updated["username"], "is_admin": updated["is_admin"]}}
    finally:
        conn.close()

@router.post("/sync-local")
def sync_local_files(current_user: Dict[str, Any] = Depends(require_admin)):
    """Trigger task tải các file feature và raw video thiếu từ Google Drive về local"""
    task = download_missing_files_to_local.delay()
    return {
        "status": "success",
        "message": "Đã bắt đầu quá trình đồng bộ hóa file về server",
        "task_id": task.id
    }

@router.get("/sync-status/{task_id}")
def get_sync_status(task_id: str, current_user: Dict[str, Any] = Depends(require_admin)):
    """Kiểm tra trạng thái tiến trình đồng bộ"""
    from celery.result import AsyncResult
    task = AsyncResult(task_id)
    
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'current': 0,
            'total': 1,
            'status': 'Pending...'
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'downloaded': task.info.get('downloaded', 0),
            'skipped': task.info.get('skipped', 0),
            'errors': task.info.get('errors', 0)
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'current': task.info.get('current', 1),
            'total': task.info.get('total', 1),
            'downloaded': task.info.get('downloaded', 0),
            'skipped': task.info.get('skipped', 0),
            'errors': task.info.get('errors', 0)
        }
    else:
        # FAILURE or others
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    
    return response

"""Phase 2 — Label detail viewer API.

Endpoints backing /admin/labels/:id (LabelDetailPage):

    GET /classes/{class_uid}/sessions
        List the label's recording sessions (grouped sample rows).
    GET /classes/{class_uid}/sessions/{session_id}/frames
        The original (non-augmented) keypoint sequence as JSON — browsers
        can't read .npz (a zip of .npy) natively, so the server unpacks it.
    GET /classes/{class_uid}/sessions/{session_id}/preview
        Tier-3 readiness probe: {status: "ready"|"rendering"}. A miss lazily
        enqueues the Celery render task (render-once-then-cache).
    GET /classes/{class_uid}/sessions/{session_id}/preview.mp4
        The pre-rendered skeleton video itself.

Auth: signed-in users only — the viewer page itself is admin-gated in the
frontend, but reviewers without the admin flag may be granted the URL later.
Responses are immutable per session, so browsers may cache them for 7 days
(private: they sit behind cookie auth, shared caches must not store them).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.auth import get_current_user
from app.preview_render import (
    find_class_meta,
    list_session_rows,
    pick_original_sample,
    preview_filename,
    render_preview_for_session,
    resolve_sample_npz,
    sample_fps,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/classes", tags=["label-sessions"])

# Immutable per-session data behind cookie auth: browser cache yes (7 days),
# shared/proxy caches no.
_CACHE_HEADER = "private, max-age=604800"


def _get_class_or_404(class_uid: str):
    meta = find_class_meta(class_uid)
    if meta is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy nhãn")
    return meta


def _get_session_rows_or_404(class_uid: str, session_id: str) -> list:
    rows = list_session_rows(class_uid).get(session_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần quay (session)")
    return rows


@router.get("/{class_uid}/sessions")
def list_label_sessions(
    class_uid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    meta = _get_class_or_404(class_uid)
    groups = list_session_rows(class_uid)

    # Ownership is decided by auth_user_id (a UUID), NOT by the display name in
    # user_id/username — two people can share a name, so a name-based check would
    # let one edit/delete another's data. samples.csv has no auth_user_id column,
    # so read it from Postgres (get_sample_owner) for the session's original row.
    from app.storage.metadata_db import get_sample_owners

    me = str(current_user.get("id") or "")

    # One batched owner lookup for every session's original sample (avoids an
    # N+1 query when the label has many recordings).
    originals = {key: (pick_original_sample(rows) or {}) for key, rows in groups.items()}
    owners = get_sample_owners([o.get("sample_uid") or "" for o in originals.values()])

    sessions = []
    for key, rows in groups.items():
        original = originals[key]
        preview_exists = (Path(meta.hierarchy_path()) / preview_filename(key)).exists()
        created = min((r.get("created_at") or "" for r in rows), default="")
        owner_id = owners.get(original.get("sample_uid") or "")
        is_owner = bool(owner_id is not None and str(owner_id) == me)
        sessions.append(
            {
                "session_id": key,
                "user_id": original.get("user_id") or "",
                "username": original.get("username") or "",
                "created_at": created,
                "sample_count": len(rows),
                "original_sample_uid": original.get("sample_uid") or "",
                "seq_len": int(original.get("seq_len") or 0),
                "fps": sample_fps(original),
                "source_type": original.get("source_type") or "",
                "has_preview": preview_exists,
                # Per-session permission flags computed on the server (by ID):
                #   is_owner    — this recording belongs to the caller
                #   can_manage  — caller may download/delete it (owner or admin)
                "is_owner": is_owner,
                "can_manage": bool(is_owner or current_user.get("is_admin")),
            }
        )

    sessions.sort(key=lambda s: s["created_at"], reverse=True)
    return {
        "class_uid": meta.class_uid,
        "label_original": meta.label_original,
        "slug": meta.slug,
        "language": meta.language,
        "dialect": meta.dialect,
        "count": len(sessions),
        "sessions": sessions,
    }


@router.delete("/{class_uid}/sessions/{session_id}")
def delete_label_session(
    class_uid: str,
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Soft-delete a whole recording (session) — the original sample plus any
    augmentations sharing its session_id — to Trash.

    Permission is by auth_user_id (UUID), NEVER by display name: a contributor
    may remove ONLY their own recording; an admin may remove any. The action is
    written to the application log with the acting user's id.
    """
    _get_class_or_404(class_uid)
    rows = _get_session_rows_or_404(class_uid, session_id)

    from app.storage.metadata_db import get_sample_owner
    from app.catalog_sync import sync_soft_delete_sample, CatalogSyncError

    original = pick_original_sample(rows) or {}
    owner_id = get_sample_owner(original.get("sample_uid") or "")
    is_admin = bool(current_user.get("is_admin"))
    me = str(current_user.get("id") or "")
    if not is_admin and (owner_id is None or str(owner_id) != me):
        logger.warning(
            "[SESSION_DELETE][DENY] user=%s(id=%s) tried to delete class=%s session=%s owned by %s",
            current_user.get("username"), me, class_uid, session_id, owner_id,
        )
        raise HTTPException(
            status_code=403, detail="Bạn chỉ có thể xóa lần quay của chính mình"
        )

    deleted: list = []
    failed: list = []
    for r in rows:
        uid = (r.get("sample_uid") or "").strip()
        if not uid:
            continue
        try:
            sync_soft_delete_sample(uid)
            deleted.append(uid)
        except Exception as exc:  # one bad row must not abort the rest
            failed.append({"sample_uid": uid, "error": str(exc)})

    logger.info(
        "[SESSION_DELETE] user=%s(id=%s) admin=%s class=%s session=%s deleted=%d failed=%d",
        current_user.get("username"), me, is_admin, class_uid, session_id, len(deleted), len(failed),
    )
    return {
        "success": True,
        "session_id": session_id,
        "deleted_count": len(deleted),
        "failed": failed,
    }


@router.post("/{class_uid}/sessions/{session_id}/reassign")
def reassign_label_session(
    class_uid: str,
    session_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Move a whole recording (session) to a different EXISTING label/class —
    for a recording captured under the wrong label. The original sample plus any
    augmentations sharing its session_id are relabeled and their .npz files moved
    into the target class folder (local + Drive).

    Permission is by auth_user_id (owner or admin); the action is logged.
    """
    _get_class_or_404(class_uid)
    rows = _get_session_rows_or_404(class_uid, session_id)

    from app.storage.metadata_db import get_sample_owner
    from app.catalog_sync import sync_reassign_sample

    original = pick_original_sample(rows) or {}
    owner_id = get_sample_owner(original.get("sample_uid") or "")
    is_admin = bool(current_user.get("is_admin"))
    me = str(current_user.get("id") or "")
    if not is_admin and (owner_id is None or str(owner_id) != me):
        logger.warning(
            "[SESSION_REASSIGN][DENY] user=%s(id=%s) tried to reassign class=%s session=%s owned by %s",
            current_user.get("username"), me, class_uid, session_id, owner_id,
        )
        raise HTTPException(
            status_code=403, detail="Bạn chỉ có thể đổi nhãn lần quay của chính mình"
        )

    target_ref = str(payload.get("target_class_ref") or "").strip()
    if not target_ref:
        raise HTTPException(status_code=400, detail="Thiếu nhãn đích")

    moved: list = []
    failed: list = []
    for r in rows:
        uid = (r.get("sample_uid") or "").strip()
        if not uid:
            continue
        try:
            sync_reassign_sample(uid, target_ref)
            moved.append(uid)
        except Exception as exc:  # one bad row must not abort the rest
            failed.append({"sample_uid": uid, "error": str(exc)})

    logger.info(
        "[SESSION_REASSIGN] user=%s(id=%s) admin=%s class=%s session=%s -> %s moved=%d failed=%d",
        current_user.get("username"), me, is_admin, class_uid, session_id, target_ref, len(moved), len(failed),
    )
    if not moved and failed:
        raise HTTPException(status_code=400, detail=failed[0].get("error") or "Đổi nhãn thất bại")
    return {
        "success": True,
        "session_id": session_id,
        "target_class_ref": target_ref,
        "moved_count": len(moved),
        "failed": failed,
    }


@router.get("/{class_uid}/sessions/{session_id}/frames")
def get_session_frames(
    class_uid: str,
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    _get_class_or_404(class_uid)
    rows = _get_session_rows_or_404(class_uid, session_id)

    row = pick_original_sample(rows)
    npz_path = resolve_sample_npz(row) if row else None
    if npz_path is None:
        raise HTTPException(status_code=404, detail="File dữ liệu .npz không còn trên hệ thống")

    try:
        with np.load(npz_path, allow_pickle=True) as data:
            sequence = np.asarray(data["sequence"], dtype=np.float32)
    except Exception as exc:
        logger.error("[FRAMES] npz read failed %s: %s", npz_path, exc)
        raise HTTPException(status_code=500, detail="File .npz bị hỏng, không đọc được")

    if sequence.ndim != 2:
        raise HTTPException(status_code=500, detail="Dữ liệu .npz sai định dạng (cần mảng 2 chiều)")

    payload = {
        "class_uid": class_uid,
        "session_id": session_id,
        "sample_uid": row.get("sample_uid") or "",
        "frames": int(sequence.shape[0]),
        "dim": int(sequence.shape[1]),
        "fps": sample_fps(row),
        # 5 decimals ≈ 0.001% of the coordinate range — halves the JSON size.
        "sequence": np.round(sequence, 5).tolist(),
    }
    return JSONResponse(payload, headers={"Cache-Control": _CACHE_HEADER})


def _preview_path(meta, session_id: str) -> Path:
    return Path(meta.hierarchy_path()) / preview_filename(session_id)


def _dispatch_or_render(class_uid: str, session_id: str) -> str:
    """Enqueue the async render; without a broker (bare dev) render inline.

    Returns "rendering" (queued) or "ready" (rendered inline).
    """
    try:
        from app.preview_tasks import render_session_preview_task

        render_session_preview_task.delay(class_uid, session_id)
        return "rendering"
    except Exception as exc:
        logger.warning("[PREVIEW] Celery dispatch failed (%s), rendering inline", exc)
        render_preview_for_session(class_uid, session_id)
        return "ready"


@router.get("/{class_uid}/sessions/{session_id}/preview")
def get_session_preview_status(
    class_uid: str,
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    meta = _get_class_or_404(class_uid)
    _get_session_rows_or_404(class_uid, session_id)

    if _preview_path(meta, session_id).exists():
        return {"status": "ready"}

    try:
        status = _dispatch_or_render(class_uid, session_id)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error("[PREVIEW] inline render failed %s/%s: %s", class_uid, session_id, exc)
        raise HTTPException(status_code=500, detail="Không render được video xem nhẹ")

    if status == "ready":
        return {"status": "ready"}
    return JSONResponse({"status": "rendering"}, status_code=202)


@router.get("/{class_uid}/sessions/{session_id}/preview.mp4")
def get_session_preview_video(
    class_uid: str,
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    meta = _get_class_or_404(class_uid)
    path = _preview_path(meta, session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video chưa được render — gọi /preview trước")
    return FileResponse(
        str(path),
        media_type="video/mp4",
        headers={"Cache-Control": _CACHE_HEADER},
    )

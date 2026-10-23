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
Visibility can be revoked: viewer payloads must not persist in browser caches.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

import numpy as np
from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.modules.identity._web_compat import get_current_user
from app.modules.saas.tenant_context import require_tenant
from app.modules.dataset.preview_render import (
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

# A contributor can make a session private after it has been viewed.
_CACHE_HEADER = "private, no-store"


def _get_class_or_404(class_uid: str):
    """Phạm vi lấy từ NGỮ CẢNH YÊU CẦU, không phải từ tài nguyên.

    `require_tenant()` đọc biến ngữ cảnh do `TenantScopeMiddleware` đặt ở đầu
    mỗi request, cùng giá trị được nạp vào GUC mà chính sách RLS của PostgreSQL
    so sánh. Dùng đúng nguồn ấy cho tầng CSV giữ hai mặt phẳng nói cùng một
    câu trả lời; lấy tenant từ `current_user` là một nguồn thứ hai có thể lệch.

    Không có ngữ cảnh tenant thì `require_tenant()` ném lỗi — đóng, không mở.
    """
    meta = find_class_meta(class_uid, tenant_id=require_tenant())
    if meta is None:
        # Cùng một câu trả lời cho "lớp của tenant khác" và "lớp không tồn tại".
        # Hai thông điệp khác nhau ở đây sẽ dựng lại đúng phép thử tồn tại mà
        # việc lọc theo phạm vi vừa gỡ bỏ.
        raise HTTPException(status_code=404, detail="Không tìm thấy nhãn")
    return meta


def _get_session_rows_or_404(class_uid: str, session_id: str) -> list:
    rows = list_session_rows(class_uid, tenant_id=require_tenant()).get(session_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Không tìm thấy lần quay (session)")
    return rows


def _owns_all_rows(rows: list, owners: dict, user_id: str) -> bool:
    return bool(user_id and rows) and all(
        owners.get(r.get("sample_uid") or "") is not None
        and str(owners[r.get("sample_uid") or ""]) == user_id for r in rows
    )


def _readable_groups(groups: dict, current_user: Dict[str, Any]) -> dict:
    from app.modules.dataset.sample_access import readable_sample_uids

    allowed = readable_sample_uids(
        current_user,
        [r.get("sample_uid") or "" for rows in groups.values() for r in rows],
        require_tenant(),
    )
    # A cached preview may contain any row in this group. Never partially
    # disclose a mixed-owner/mixed-visibility group via its shared preview.
    return {key: rows for key, rows in groups.items()
            if rows and all(r.get("sample_uid") in allowed for r in rows)}


def _require_session_read(rows: list, current_user: Dict[str, Any]) -> None:
    if not _readable_groups({"session": rows}, current_user):
        raise HTTPException(status_code=404, detail="Không tìm thấy lần quay (session)")


def _require_session_owner(rows: list, current_user: Dict[str, Any]) -> None:
    """Chủ của MỌI mẫu trong lần quay, hoặc admin/editor của tenant đang dùng."""
    from app.modules.dataset.sample_access import can_manage_tenant_samples
    from app.storage.metadata_db import get_sample_owners

    if can_manage_tenant_samples(current_user, require_tenant()):
        _require_session_read(rows, current_user)
        return
    owners = get_sample_owners([r.get("sample_uid") or "" for r in rows])
    if not _owns_all_rows(rows, owners, str(current_user.get("id") or "")):
        raise HTTPException(status_code=403, detail="Bạn chỉ có thể sửa lần quay gồm các mẫu của chính mình")


@router.get("/{class_uid}/sessions")
def list_label_sessions(
    class_uid: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    meta = _get_class_or_404(class_uid)
    groups = list_session_rows(class_uid, tenant_id=require_tenant())
    groups = _readable_groups(groups, current_user)

    # Ownership is decided by auth_user_id (a UUID), NOT by the display name in
    # user_id/username — two people can share a name. Read every row's owner
    # from Postgres: a client-supplied session_id can group different owners.
    from app.storage.metadata_db import get_sample_owners

    me = str(current_user.get("id") or "")
    from app.modules.dataset.sample_access import can_manage_tenant_samples

    manager = can_manage_tenant_samples(current_user, require_tenant())

    # One batched owner lookup for every sample (avoids an
    # N+1 query when the label has many recordings).
    originals = {key: (pick_original_sample(rows) or {}) for key, rows in groups.items()}
    owners = get_sample_owners([r.get("sample_uid") or "" for rows in groups.values() for r in rows])

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
                #   can_manage  — caller may download/delete it (owner, or
                #                 admin/editor of this tenant)
                "is_owner": is_owner,
                "can_manage": bool(manager or _owns_all_rows(rows, owners, me)),
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


@router.get("/{class_uid}/sessions/{session_id}/provenance")
def session_provenance(
    class_uid: str,
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Xuất xứ của MỘT lần thu (UC18).

    Trả lời ba câu hỏi tách bạch, và không trộn chúng vào nhau:

        nguồn gốc   — vật liệu này từ đâu ra (thu trực tiếp hay nhập vào)
        ngữ cảnh    — thu trong điều kiện nào, của ai, thuộc lớp nào
        dẫn xuất    — từ vật liệu gốc tới biểu diễn đang dùng, qua bước nào

    Luật của endpoint này: thứ KHÔNG được ghi lại thì báo là không có. Không suy
    ra, không điền giá trị hợp lý. Một xuất xứ bịa ra thì sau khi hiện lên màn
    hình không còn phân biệt được với một xuất xứ có thật, và đó là kiểu sai
    đắt nhất trong cả hệ thống.
    """
    meta = _get_class_or_404(class_uid)
    groups = list_session_rows(class_uid, tenant_id=require_tenant())
    rows = groups.get(session_id)
    if not rows:
        raise HTTPException(status_code=404, detail="Không có lần thu này")
    _require_session_read(rows, current_user)

    original = pick_original_sample(rows) or {}

    def val(row: Dict[str, Any], key: str):
        """Ô trống trả về None chứ không phải chuỗi rỗng — giao diện phân biệt
        được "không ghi nhận" với "ghi nhận một giá trị rỗng"."""
        v = row.get(key)
        if v is None:
            return None
        v = str(v).strip()
        return v or None

    def num(row: Dict[str, Any], key: str):
        v = val(row, key)
        if v is None:
            return None
        try:
            return float(v)
        except ValueError:
            return None

    # Người ký: sổ đăng ký có tên hiển thị, hàng mẫu chỉ có mã. Tra một lượt.
    signer_id = val(original, "signer_id")
    signer_name = None
    if signer_id:
        try:
            from app.signers import get_signer
            rec = get_signer(signer_id)
            signer_name = (rec or {}).get("display_name") or None
        except Exception:
            signer_name = None

    samples = [
        {
            "sample_uid": val(r, "sample_uid"),
            "augment_id": val(r, "augment_id"),
            "seq_len": num(r, "seq_len"),
            "completeness": num(r, "completeness"),
            "jitter": num(r, "jitter"),
            "file_path": val(r, "file_path"),
            "checksum": val(r, "checksum"),
            "storage_url": val(r, "storage_url"),
        }
        for r in rows
    ]

    return {
        "class_uid": meta.class_uid,
        "session_id": session_id,
        "sample_count": len(rows),
        # --- nguồn gốc -----------------------------------------------------
        "origin": {
            "source_type": val(original, "source_type"),
            "collection_campaign": val(original, "collection_campaign"),
            "created_at": min((r.get("created_at") or "" for r in rows), default="") or None,
            "gdrive_synced": val(original, "gdrive_synced"),
        },
        # --- ngữ cảnh thu --------------------------------------------------
        "context": {
            "label_original": meta.label_original,
            "slug": meta.slug,
            "language": meta.language,
            "dialect": meta.dialect,
            "signer_id": signer_id,
            "signer_name": signer_name,
            "contributor_label": val(original, "user_id"),
            "tenant_id": val(original, "tenant_id"),
        },
        # --- chuỗi dẫn xuất ------------------------------------------------
        "derivation": {
            # `raw_landmarks_available` là câu trả lời cho "vật liệu gốc còn giữ
            # được không". Nó KHÔNG suy ra từ sự tồn tại của tệp npz đã chuẩn hoá.
            "raw_landmarks_available": val(original, "raw_landmarks_available"),
            "normalization_version": val(original, "normalization_version"),
            "preprocess_contract_version": val(original, "preprocess_contract_version"),
            "fps_original": num(original, "fps_original"),
            "fps_processed": num(original, "fps_processed"),
            "sequence_length_original": num(original, "sequence_length_original"),
            "seq_len": num(original, "seq_len"),
            "file_path": val(original, "file_path"),
            "storage_url": val(original, "storage_url"),
            "checksum": val(original, "checksum"),
        },
        # --- chất lượng ----------------------------------------------------
        "quality": {
            "completeness": num(original, "completeness"),
            "jitter": num(original, "jitter"),
            "left_hand_ratio": num(original, "left_hand_ratio"),
            "right_hand_ratio": num(original, "right_hand_ratio"),
            "both_hands_ratio": num(original, "both_hands_ratio"),
            "quality_flags": val(original, "quality_flags"),
            "quality_status": val(original, "quality_status"),
        },
        "samples": samples,
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

    from app.catalog_sync import sync_soft_delete_sample

    _require_session_owner(rows, current_user)
    is_admin = bool(current_user.get("is_admin"))
    me = str(current_user.get("id") or "")

    deleted: list = []
    failed: list = []
    for r in rows:
        uid = (r.get("sample_uid") or "").strip()
        if not uid:
            continue
        try:
            sync_soft_delete_sample(uid, tenant_id=require_tenant())
            deleted.append(uid)
        except Exception as exc:  # one bad row must not abort the rest
            failed.append({"sample_uid": uid, "error": str(exc)})

    logger.info(
        "[SESSION_DELETE] user=%s(id=%s) admin=%s class=%s session=%s deleted=%d failed=%d",
        current_user.get("username"), me, is_admin, class_uid, session_id, len(deleted), len(failed),
    )
    return {
        "success": not failed,
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

    from app.catalog_sync import sync_reassign_sample

    _require_session_owner(rows, current_user)
    is_admin = bool(current_user.get("is_admin"))
    me = str(current_user.get("id") or "")

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
            # Phạm vi tenant của NGƯỜI GỌI, không phải của tài nguyên. Truyền
            # tenant của mẫu vào đây sẽ vô hiệu hoá chính phép kiểm: một mẫu của
            # tenant khác sẽ tự mang theo phạm vi làm nó hợp lệ.
            sync_reassign_sample(uid, target_ref, tenant_id=require_tenant())
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
        "success": not failed,
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
    _require_session_read(rows, current_user)

    row = pick_original_sample(rows)
    npz_path = resolve_sample_npz(row) if row else None
    if npz_path is None:
        raise HTTPException(status_code=404, detail="File dữ liệu .npz không còn trên hệ thống")

    try:
        # Raw landmarks when the sample has them: `sequence` is the model's
        # input, not a picture of the recording — it drops where the hands were
        # relative to each other and flattens depth. See load_display_sequence.
        from app.dataset_samples import load_display_sequence, load_world_sequence

        sequence, landmark_source = load_display_sequence(npz_path)
        world = load_world_sequence(npz_path)
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
        # "raw" = as recorded. "normalized" = wrist-centred model input, which
        # has no relative hand position and a flattened z; the viewer says so
        # instead of presenting it as a faithful picture.
        "landmark_source": landmark_source,
        # 5 decimals ≈ 0.001% of the coordinate range — halves the JSON size.
        "sequence": np.round(sequence, 5).tolist(),
    }
    # Metric 3D, when the sample was recorded with it. Sent alongside rather
    # than instead of `sequence`: world landmarks are centred on each hand, so
    # they carry true shape and depth but no relative hand position. The 2D
    # view needs the position, the 3D view needs the depth, and neither array
    # has both. Absent for every sample older than the capture-side change.
    if world is not None and world.ndim == 2 and world.shape[0] == sequence.shape[0]:
        # Metres, so the fifth decimal is 10 microns — well past hand detail.
        payload["sequence_world"] = np.round(world, 5).tolist()
    return JSONResponse(payload, headers={"Cache-Control": _CACHE_HEADER})


def _preview_path(meta, session_id: str) -> Path:
    return Path(meta.hierarchy_path()) / preview_filename(session_id)


def _dispatch_or_render(class_uid: str, session_id: str) -> str:
    """Enqueue the async render; without a broker (bare dev) render inline.

    Returns "rendering" (queued) or "ready" (rendered inline).
    """
    try:
        from app.modules.dataset.preview_tasks import render_session_preview_task

        # Phạm vi chốt lúc ĐƯA VÀO HÀNG ĐỢI, khi còn biết ai gọi. Worker
        # chạy trong system_scope và không suy lại được điều này.
        render_session_preview_task.delay(class_uid, session_id,
                                          tenant_id=require_tenant())
        return "rendering"
    except Exception as exc:
        logger.warning("[PREVIEW] Celery dispatch failed (%s), rendering inline", exc)
        render_preview_for_session(class_uid, session_id,
                                   tenant_id=require_tenant())
        return "ready"


@router.get("/{class_uid}/sessions/{session_id}/preview")
def get_session_preview_status(
    class_uid: str,
    session_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    meta = _get_class_or_404(class_uid)
    rows = _get_session_rows_or_404(class_uid, session_id)
    _require_session_read(rows, current_user)

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
    rows = _get_session_rows_or_404(class_uid, session_id)
    _require_session_read(rows, current_user)
    path = _preview_path(meta, session_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Video chưa được render — gọi /preview trước")
    return FileResponse(
        str(path),
        media_type="video/mp4",
        headers={"Cache-Control": _CACHE_HEADER},
    )

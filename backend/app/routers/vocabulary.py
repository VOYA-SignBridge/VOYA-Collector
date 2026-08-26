"""Dialect / recognition-profile registry API.

One write door. Every screen reads `GET /vocabulary/registry` instead of
carrying its own hardcoded list — six such lists existed and disagreed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app import audit
from app import vocabulary_registry as vr
from app.auth import get_current_user, get_current_user_optional, require_admin

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("/registry")
def get_registry(current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)):
    """Everything a screen needs to render dialect pickers.

    `registry_version` lets a client cache and know when to refetch.
    """
    viewer = str((current_user or {}).get("id") or "") or None
    return {
        "registry_version": vr.registry_version(),
        "dialects": vr.list_dialects(viewer_id=viewer),
        "profiles": vr.list_profiles(),
        # Vùng miền đi kèm ở đây thay vì một lời gọi riêng: màn hình nào dựng
        # ô chọn phương ngữ thì cũng cần ô chọn vùng, và hai thứ phải đến từ
        # cùng một ảnh chụp — lệch nhau thì người dùng thấy một tổ hợp không
        # tồn tại.
        "regions": vr.list_regions(),
    }


@router.post("/dialects", status_code=status.HTTP_201_CREATED)
def create_dialect(
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Anyone signed in may ask for a dialect; it starts `pending`.

    Pending means: usable right now by its creator (so collection never waits on
    an admin), invisible to everyone else until approved. Rejecting it later is
    a merge, not a deletion — see docs/02-data/DIALECT_LIFECYCLE.md §3.5.
    """
    try:
        row, created = vr.create_dialect(
            str(payload.get("display_name") or ""),
            language=str(payload.get("language") or "vn"),
            created_by=str(current_user.get("id") or "") or None,
            auto_approve=bool(current_user.get("is_admin")),
        )
    except vr.DialectConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "slug_taken",
                "dialect_id": exc.dialect_id,
                "existing_display_name": exc.existing_display_name,
                "message": str(exc),
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"dialect": row, "created": created}


@router.get("/dialects/pending")
def list_pending(_: Dict[str, Any] = Depends(require_admin)):
    from app.storage.metadata_db import _fetch_all

    return {
        "items": _fetch_all(
            "SELECT d.*, u.username AS created_by_username FROM dialects d "
            "LEFT JOIN users u ON u.id = d.created_by "
            "WHERE d.tenant_id = %s AND d.status = 'pending' ORDER BY d.created_at",
            (vr.DEFAULT_TENANT,),
        )
    }


@router.post("/dialects/{dialect_id}/approve")
def approve(dialect_id: str, request: Request,
            admin: Dict[str, Any] = Depends(require_admin)):
    vr.approve_dialect(dialect_id, str(admin.get("id") or ""))
    audit.record(
        "vocabulary.dialect.approved", actor=admin, request=request,
        target_type="dialect", target_id=dialect_id)
    return {"dialect_id": dialect_id, "status": "approved"}


@router.post("/dialects/{dialect_id}/reject")
def reject(
    dialect_id: str,
    request: Request,
    payload: Dict[str, Any] = Body(...),
    admin: Dict[str, Any] = Depends(require_admin),
):
    """Rejection REQUIRES a merge target.

    By the time an admin looks, the requester may already have recorded samples
    under this dialect — that is the deal we made by letting them start
    immediately. Rejecting without a destination would strand those rows in a
    dialect no query lists. `merge_into` says where they belong.
    """
    merge_into = str(payload.get("merge_into") or "").strip()
    if not merge_into:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phải chọn phương ngữ đích để gộp vào — từ chối suông sẽ bỏ rơi "
                   "số mẫu người dùng đã thu dưới phương ngữ này.",
        )
    if merge_into not in vr.known_dialect_ids():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Phương ngữ đích '{merge_into}' không tồn tại.")

    vr.record_merge(dialect_id, merge_into, str(admin.get("id") or ""))
    from app.catalog_migrations import merge_dialect_task

    merge_dialect_task.delay(old_id=dialect_id, new_id=merge_into)

    # Đây là hành động DI CHUYỂN DỮ LIỆU CỦA NGƯỜI KHÁC: mọi mẫu người đóng góp
    # đã thu dưới `dialect_id` sẽ mang nhãn `merge_into` sau lượt chạy nền, và
    # không có nút hoàn tác. `vr.record_merge` giữ được sự kiện trong registry,
    # nhưng registry trả lời "phương ngữ này đi đâu", không trả lời "ai quyết
    # định thế, lúc nào, từ máy nào" — mà đó mới là câu hỏi khi có người khiếu
    # nại rằng dữ liệu của họ bị đổi nhãn.
    audit.record(
        "vocabulary.dialect.merged", actor=admin, request=request,
        target_type="dialect", target_id=dialect_id,
        detail={"merged_into": merge_into})
    return {"dialect_id": dialect_id, "merged_into": merge_into, "status": "rejected"}


def _require_registry_editor(current_user: Dict[str, Any], tenant_id: str = vr.DEFAULT_TENANT):
    """Editing a tenant's catalogue needs admin/editor OF THAT TENANT.

    Not `require_admin`: that is the system-wide flag, and using it here would
    mean either that no tenant can manage its own vocabulary, or that any
    system admin silently becomes an editor of every tenant. The two authorities
    are checked separately — see vocabulary_registry.can_edit_registry.
    """
    try:
        vr.assert_can_edit_registry(
            tenant_id,
            str(current_user.get("id") or "") or None,
            is_system_admin=bool(current_user.get("is_admin")),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.patch("/dialects/{dialect_id}")
def update_dialect(
    dialect_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Rename (display only) or retire. `dialect_id` itself is never editable —
    it names directories, checkpoints and published split manifests."""
    _require_registry_editor(current_user)
    if "display_name" in payload:
        vr.rename_dialect(dialect_id, str(payload["display_name"]))
    if "is_active" in payload:
        vr.set_dialect_active(dialect_id, bool(payload["is_active"]))
    return {"dialect_id": dialect_id, "ok": True}


# --------------------------------------------------------------------------- system catalog
#
# The SYSTEM CATALOG: system-managed configuration templates (dialects,
# recognition profiles) that a new tenant is cloned from. Separate router
# prefix, separate guard, and nothing here is reachable by a tenant user — see
# docs/01-architecture/REGISTRY_ARCHITECTURE.md §2.
#
# NOT the Community Data Commons. These endpoints were briefly mounted at
# /vocabulary/community, which was wrong twice over: this holds no contributed
# data — no video, no landmarks, no consent record, no attribution — and it
# squatted on the namespace the real commons needs. "Community" in
# CTU-SignBridge means data people contributed and the governance around it
# (submission, review, licence, grants, withdrawal); see
# docs/01-architecture/COMMUNITY_DATA_COMMONS.md. The physical tables are still named
# community_* because renaming them is a migration, not a rename — the domain
# name is what had to stop being wrong first.
#
# `require_admin` is the system-wide flag, which is exactly the authority this
# plane wants, and it is re-asserted through vr.assert_system_admin so the rule
# lives in one place even if the dependency is ever swapped.

catalog_router = APIRouter(prefix="/vocabulary/catalog", tags=["vocabulary-catalog"])


def _system_admin(current_user: Dict[str, Any] = Depends(require_admin)) -> Dict[str, Any]:
    try:
        vr.assert_system_admin(bool(current_user.get("is_admin")))
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    return current_user


def _actor(current_user: Dict[str, Any]) -> Optional[str]:
    return str(current_user.get("id") or "") or None


@catalog_router.get("")
def get_catalog(_: Dict[str, Any] = Depends(_system_admin)):
    """The live (unpublished) system catalogue plus its last frozen version.

    `latest_version` is the last PUBLISHED one, so a UI can tell "edited since
    publish" from "in sync" by comparing content_hash — the same comparison
    publish_catalog_version makes before deciding to mint a version at all.
    """
    snapshot = vr.system_catalog_snapshot()
    versions = vr.list_catalog_versions(limit=1)
    latest = versions[0] if versions else None
    return {
        "dialects": snapshot["dialects"],
        "profiles": snapshot["profiles"],
        "content_hash": vr.content_hash(snapshot),
        "latest_version": latest["version"] if latest else None,
        "latest_content_hash": latest["content_hash"] if latest else None,
    }


@catalog_router.get("/versions")
def list_catalog_versions(limit: int = 50, _: Dict[str, Any] = Depends(_system_admin)):
    return {"items": vr.list_catalog_versions(limit=limit)}


@catalog_router.get("/versions/{version}")
def get_catalog_version(version: int, _: Dict[str, Any] = Depends(_system_admin)):
    row = vr.get_catalog_version(version)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Community version {version} không tồn tại.")
    return row


@catalog_router.post("/publish")
def publish_catalog(
    payload: Dict[str, Any] = Body(default={}),
    current_user: Dict[str, Any] = Depends(_system_admin),
):
    """Freeze the current template into an immutable version.

    Idempotent by content: publishing an unchanged catalogue returns the version
    that already holds it instead of minting a duplicate. `created` says which
    happened, so a UI can report "đã có v7" rather than a misleading success.
    """
    before = vr.list_catalog_versions(limit=1)
    previous = before[0]["version"] if before else None
    version = vr.publish_catalog_version(
        created_by=_actor(current_user),
        note=str(payload.get("note") or ""),
    )
    return {"version": version, "created": version != previous}


@catalog_router.post("/seed")
def seed_system_catalog(current_user: Dict[str, Any] = Depends(_system_admin)):
    """Re-run the first-install seed from config/*.seed.csv.

    Safe to call at any time: every insert is ON CONFLICT DO NOTHING, so rows an
    admin has since edited are left alone. Its real use is filling a gap after a
    seed file gains an entry, not resetting the catalogue — there is deliberately
    no endpoint that overwrites admin edits from a CSV.
    """
    return vr.seed_system_catalog(created_by=_actor(current_user))


@catalog_router.post("/dialects", status_code=status.HTTP_201_CREATED)
def create_catalog_dialect(
    request: Request,
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(_system_admin),
):
    """Thêm một phương ngữ vào KHUÔN Community — cửa ghi còn thiếu.

    Trước lượt này danh mục Community chỉ lớn lên được từ
    `config/dialects.seed.csv`: `PATCH` sửa được dòng đã có, `POST /seed` chạy
    lại tệp, và không đường nào tạo được dòng mới. Nên mọi phương ngữ duyệt sau
    lần cài đầu đều không bao giờ tới được tenant tạo sau đó.

    Đây KHÔNG phải `POST /vocabulary/dialects`: cửa kia thêm vào danh mục của
    MỘT tổ chức. Cửa này sửa khuôn của cả nền tảng, nên nó đòi quyền quản trị
    hệ thống.

    `201` khi tạo mới, `200` khi đã có sẵn đúng tên ấy (luỹ đẳng).
    """
    try:
        row, created = vr.create_catalog_dialect(
            str(payload.get("display_name") or ""),
            language=str(payload.get("language") or "vn"),
            is_alphabet=bool(payload.get("is_alphabet")),
            note=str(payload.get("note") or ""),
            created_by=_actor(current_user),
        )
    except vr.DialectConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    audit.record(
        "vocabulary.catalog.dialect_created", actor=current_user, request=request,
        target_type="community_dialect", target_id=row["dialect_id"],
        detail={"created": created})
    return JSONResponse(
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        content={"dialect": jsonable_encoder(row), "created": created},
    )


@catalog_router.patch("/dialects/{dialect_id}")
def patch_catalog_dialect(
    dialect_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(_system_admin),
):
    try:
        row = vr.update_catalog_dialect(dialect_id, payload, updated_by=_actor(current_user))
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Phương ngữ mẫu '{dialect_id}' không tồn tại.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"dialect": row}


@catalog_router.patch("/profiles/{profile_id}")
def patch_catalog_profile(
    profile_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(_system_admin),
):
    try:
        row = vr.update_catalog_profile(profile_id, payload, updated_by=_actor(current_user))
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Profile mẫu '{profile_id}' không tồn tại.")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"profile": row}


@catalog_router.post("/clone")
def clone_to_tenant(
    payload: Dict[str, Any] = Body(...),
    current_user: Dict[str, Any] = Depends(_system_admin),
):
    """Bootstrap a tenant's registry from the template. Once per tenant.

    Re-running is harmless (ON CONFLICT DO NOTHING) but never a repair tool: a
    tenant that has diverged keeps its own rows, so this fills gaps and does not
    restore the template.
    """
    tenant_id = str(payload.get("tenant_id") or "").strip()
    if not tenant_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Thiếu tenant_id.")

    # `dialects.tenant_id` carries no foreign key to `tenants`, so cloning to a
    # typo'd id would succeed halfway: the catalogue rows get written under a
    # tenant nobody can reach, while the `UPDATE tenants SET
    # cloned_from_community_version` silently matches zero rows and the
    # provenance is lost. Refuse before writing anything.
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import tenant_scope

    # Phạm vi của TENANT ĐÍCH — KHÔNG phải `system_scope`.
    #
    # Khi `tenants` bật RLS (15/08/2026), phép kiểm này chạy dưới phạm vi của
    # NGƯỜI GỌI sẽ thấy 0 dòng cho mọi tenant khác, và hàm kết luận "Tenant
    # không tồn tại" — một cái 404 nghe hợp lý cho một tenant vẫn đang ở đó.
    #
    # Bản vá đầu dùng `system_scope`, và `test_no_router_crosses_the_boundary_
    # except_the_documented_one` đã bắt đúng: *"một request handler hành động
    # nhân danh mọi tenant chính là cách biên giới bị mở lại"*. Danh sách cho
    # phép chỉ có `sot_admin.py`, và nó nên tiếp tục chỉ có một mục.
    #
    # Lời giải hẹp hơn nằm sẵn trong chính vị từ chính sách: dưới
    # `tenant_scope(đích)`, dòng của CHÍNH tenant đích nhìn thấy được. Không
    # cần quyền xuyên tenant nào cả — chỉ cần đứng đúng chỗ.
    #
    # Cùng phạm vi ấy được `clone_catalog_to_tenant` dùng lại cho toàn bộ phép
    # ghi, nên cả endpoint chạy dưới đúng một phạm vi: tenant đích.
    with tenant_scope(tenant_id):
        co_tenant = _fetch_all(
            "SELECT 1 FROM tenants WHERE tenant_id = %s AND deleted_at IS NULL",
            (tenant_id,))

    if not co_tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Tenant '{tenant_id}' không tồn tại.")

    counts = vr.clone_catalog_to_tenant(tenant_id, created_by=_actor(current_user))
    return {"tenant_id": tenant_id, "cloned": counts,
            "registry_version": vr.registry_version(tenant_id)}

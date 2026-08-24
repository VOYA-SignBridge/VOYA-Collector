"""API quản lý hồ sơ NGƯỜI KÝ (UC11 — Manage Signers).

Sổ đăng ký người ký đã có từ lược đồ v2 (`app/signers.py`, `dataset/signers.csv`
mirror sang bảng `signers`), nhưng cho tới nay chỉ có ĐƯỜNG GHI TỰ ĐỘNG: một
tài khoản đóng góp mẫu đầu tiên thì `resolve_signer_for_user` lập hồ sơ cho họ.
Không có đường nào để con người xem, sửa, hay nói "hai id này là một người" —
dù bảng `signer_aliases` được dựng sẵn cho đúng việc đó và `consent_gate` đã
đọc nó khi phân giải đồng thuận. Router này là đường đó.

Ba điều cố ý KHÔNG làm ở đây:

* `signer_id` không sửa được. Nó là khoá mà `samples.csv` và `samples.signer_id`
  đang trỏ tới; đổi nó từ giao diện là viết lại lịch sử của mẫu đã thu.
* Gộp KHÔNG viết lại mẫu. Nó ghi một dòng vào `signer_aliases`, và mẫu cũ vẫn
  mang id cũ — tra ngược được, và phân giải được qua `_resolve_aliases`.
* Vô hiệu hoá KHÔNG xoá. Hồ sơ và mọi quan hệ lịch sử ở nguyên chỗ.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app import activity, signers as signer_registry
from app.auth import require_tenant_editor
from app.consent_gate import SCOPE_LADDER, load_consents
from app.dataset_samples import list_samples
from app.storage.metadata_db import _execute, _fetch_all
from app.tenant_context import require_tenant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/signers", tags=["admin", "signers"])


# --------------------------------------------------------------------------- mô hình

class SignerRow(BaseModel):
    signer_id: str
    display_name: str = ""
    regional_group: str = ""
    external_user_id: str = ""
    is_active: bool = True
    created_at: str = ""
    # Đo được từ dữ liệu, không lưu trong sổ:
    sample_count: int = 0
    class_count: int = 0
    last_sample_at: Optional[str] = None
    # Đồng thuận: "granted" | "withdrawn" | "none"
    consent_state: str = "none"
    consent_scope: Optional[str] = None
    # Đã gộp vào ai (nếu có)
    merged_into: Optional[str] = None
    merged_reason: Optional[str] = None


class SignersResponse(BaseModel):
    signers: List[SignerRow]
    tenant_id: str
    total_samples: int
    #: Số mẫu KHÔNG mang signer_id nào. Không suy ra được chủ, và nói thẳng ra
    #: thì hơn là chia đều vào các hồ sơ đang có.
    unattributed_samples: int
    scope_ladder: List[str]


class UpdateSignerBody(BaseModel):
    display_name: Optional[str] = Field(None, max_length=200)
    regional_group: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class MergeSignerBody(BaseModel):
    target_signer_id: str = Field(..., min_length=1, max_length=50)
    reason: str = Field("", max_length=500)


# --------------------------------------------------------------------------- đọc

def _alias_map(tenant_id: str) -> Dict[str, Dict[str, Any]]:
    try:
        rows = _fetch_all(
            "SELECT old_signer_id, new_signer_id, reason FROM signer_aliases "
            "WHERE tenant_id = %s",
            (tenant_id,),
        )
    except Exception as exc:
        logger.warning("[SIGNER] khong doc duoc signer_aliases: %s", exc)
        return {}
    return {r["old_signer_id"]: r for r in rows}


@router.get("", response_model=SignersResponse)
def list_signers_api(current_user: Dict[str, Any] = Depends(require_tenant_editor)):
    """Sổ người ký + số đo lấy từ chính kho mẫu của tenant người gọi.

    Số mẫu KHÔNG đọc từ sổ mà đếm lại từ `samples` trong phạm vi tenant, nên
    một hồ sơ chưa từng đóng góp hiện đúng 0 chứ không phải một ô trống trông
    như lỗi tải.
    """
    scope = require_tenant()
    rows = signer_registry.list_signers()

    counts: Dict[str, int] = {}
    classes: Dict[str, set] = {}
    last_at: Dict[str, str] = {}
    unattributed = 0
    samples = list_samples(scope)
    for s in samples:
        sid = (s.get("signer_id") or "").strip()
        if not sid:
            unattributed += 1
            continue
        counts[sid] = counts.get(sid, 0) + 1
        classes.setdefault(sid, set()).add((s.get("class_uid") or s.get("slug") or "").strip())
        created = (s.get("created_at") or "").strip()
        if created and created > last_at.get(sid, ""):
            last_at[sid] = created

    consents = load_consents(scope)
    aliases = _alias_map(scope)

    out: List[SignerRow] = []
    for r in rows:
        sid = (r.get("signer_id") or "").strip()
        if not sid:
            continue
        c = consents.get(sid)
        if c is None or (c.highest_live_rank is None and not c.has_any_record):
            state, cscope = "none", None
        elif c.highest_live_rank is None:
            state, cscope = "withdrawn", None
        else:
            state, cscope = "granted", SCOPE_LADDER[c.highest_live_rank]
        alias = aliases.get(sid)
        out.append(SignerRow(
            signer_id=sid,
            display_name=(r.get("display_name") or "").strip(),
            regional_group=(r.get("regional_group") or "").strip(),
            external_user_id=(r.get("external_user_id") or "").strip(),
            is_active=str(r.get("is_active", "1")).strip() not in ("0", "false", "False", ""),
            created_at=(r.get("created_at") or "").strip(),
            sample_count=counts.get(sid, 0),
            class_count=len([x for x in classes.get(sid, set()) if x]),
            last_sample_at=last_at.get(sid),
            consent_state=state,
            consent_scope=cscope,
            merged_into=(alias or {}).get("new_signer_id"),
            merged_reason=(alias or {}).get("reason"),
        ))

    out.sort(key=lambda x: (-x.sample_count, x.signer_id))
    return SignersResponse(
        signers=out,
        tenant_id=scope,
        total_samples=len(samples),
        unattributed_samples=unattributed,
        scope_ladder=list(SCOPE_LADDER),
    )


# --------------------------------------------------------------------------- ghi

@router.patch("/{signer_id}", response_model=SignerRow)
def update_signer_api(signer_id: str, body: UpdateSignerBody, request: Request,
                      current_user: Dict[str, Any] = Depends(require_tenant_editor)):
    """Sửa tên hiển thị / nhóm vùng / trạng thái hoạt động của một hồ sơ."""
    require_tenant()
    if body.display_name is None and body.regional_group is None and body.is_active is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Không có gì để sửa")

    updated = signer_registry.update_signer(
        signer_id,
        display_name=body.display_name,
        regional_group=body.regional_group,
        is_active=body.is_active,
    )
    if updated is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Không có người ký {signer_id}")

    activity.log_security_event(
        "signer.updated", actor=str(current_user.get("username", "")),
        target=signer_id,
        # `.dict()`, KHÔNG phải `.model_dump()` — dự án này chạy pydantic 1.10.
        extra={k: v for k, v in body.dict().items() if v is not None},
        actor_user=current_user, request=request)

    return SignerRow(
        signer_id=signer_id,
        display_name=(updated.get("display_name") or "").strip(),
        regional_group=(updated.get("regional_group") or "").strip(),
        external_user_id=(updated.get("external_user_id") or "").strip(),
        is_active=str(updated.get("is_active", "1")).strip() not in ("0", "false", "False", ""),
        created_at=(updated.get("created_at") or "").strip(),
    )


@router.post("/{signer_id}/merge")
def merge_signer_api(signer_id: str, body: MergeSignerBody, request: Request,
                     current_user: Dict[str, Any] = Depends(require_tenant_editor)):
    """Tuyên bố `signer_id` và `target_signer_id` là CÙNG MỘT NGƯỜI.

    Ghi một dòng vào `signer_aliases` rồi vô hiệu hoá hồ sơ cũ. Mẫu đã thu KHÔNG
    bị viết lại: chúng vẫn mang id cũ, và `consent_gate._resolve_aliases` đi
    theo dòng ánh xạ này khi phân giải đồng thuận — nên gộp có hiệu lực ngay ở
    cổng dữ liệu mà không đụng tới một byte nào của lịch sử.
    """
    scope = require_tenant()
    target = body.target_signer_id.strip()

    if target == signer_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            detail="Không gộp một người ký vào chính nó")
    if signer_registry.get_signer(signer_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Không có người ký {signer_id}")
    if signer_registry.get_signer(target) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"Không có người ký {target}")

    aliases = _alias_map(scope)
    if signer_id in aliases:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"{signer_id} đã được gộp vào {aliases[signer_id]['new_signer_id']}")
    # Gộp vào một hồ sơ ĐÃ bị gộp đi nơi khác tạo ra dây chuyền. Bộ phân giải
    # đi hết được dây, nhưng người đọc bảng thì không — bắt chọn thẳng đích
    # cuối cùng để một dòng trong bảng chỉ có một cách hiểu.
    if target in aliases:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            detail=f"{target} đã được gộp vào {aliases[target]['new_signer_id']}; "
                                   f"hãy gộp thẳng vào hồ sơ đó")

    try:
        _execute(
            "INSERT INTO signer_aliases(tenant_id, old_signer_id, new_signer_id, reason, merged_by) "
            "VALUES(%s, %s, %s, %s, %s)",
            (scope, signer_id, target, body.reason.strip() or None, current_user.get("id")),
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail=f"Không gộp được: {exc}")

    signer_registry.update_signer(signer_id, is_active=False)

    activity.log_security_event(
        "signer.merged", actor=str(current_user.get("username", "")),
        target=signer_id, reason=body.reason.strip(),
        extra={"new_signer_id": target, "tenant_id": scope},
        actor_user=current_user, request=request)

    return {"old_signer_id": signer_id, "new_signer_id": target, "reason": body.reason.strip()}

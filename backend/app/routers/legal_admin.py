"""Quản trị văn bản pháp lý: công bố, xem lịch sử, đo độ phủ chấp thuận.

Vì sao công bố cần NÂNG QUYỀN
------------------------------
Công bố một bản mới với ``requires_reconsent`` bật lên sẽ đá mọi người dùng
đang hoạt động ra màn hình đồng ý ở lần gọi API tiếp theo của họ. Đó là thao
tác có tầm ảnh hưởng ngang một lần đổi thiết lập nền tảng, nên nó đi cùng luật
đã có ở ``admin.write_setting``: phải nhập lại mật khẩu trong 5 phút gần đây.

Và một lý do riêng của chỗ này: bản văn vừa công bố là thứ **không xoá lại
được** ngay khi có người đầu tiên bấm đồng ý — khoá ngoại ``ON DELETE RESTRICT``
từ ``user_consents`` chặn, đúng như thiết kế. Một thao tác không hoàn tác được
thì không nên chỉ cách một cú nhấp chuột.

Vì sao KHÔNG có endpoint sửa
-----------------------------
Không có ``PUT /admin/legal/documents/{id}``. Sửa một bản đã công bố là viết
lại bản văn nằm dưới những chữ ký đã thu; trigger ``trg_legal_documents_freeze``
chặn ở tầng cơ sở dữ liệu, và không dựng một đường API đi tới bức tường đó chỉ
để nhận về lỗi 500. Muốn đổi nội dung thì công bố phiên bản mới — đó không phải
hạn chế, đó là mô hình.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status,
)
from pydantic import BaseModel, Field

from app import legal, legal_store
from app.auth import require_admin

router = APIRouter(prefix="/admin/legal", tags=["admin", "legal"])


class PublishRequest(BaseModel):
    kind: str = Field(..., description=f"một trong {legal.KINDS}")
    version: str = Field(..., min_length=1, max_length=64)
    title: str = Field("", max_length=200)
    body: str = Field(..., min_length=1)
    body_format: str = Field("markdown")
    language: str = Field("vi", max_length=16)
    change_summary: str = Field("", max_length=2000)
    requires_reconsent: bool = False
    effective_from: Optional[datetime] = Field(
        None, description="Bỏ trống = hiệu lực ngay. Đặt tương lai = lên lịch.")


def _require_sudo(current_user: Dict[str, Any]) -> None:
    """Cùng hình dạng với `admin.write_setting`.

    Gọi trong thân hàm chứ không qua `Depends`: nó tự phụ thuộc `require_admin`,
    và khai báo cả hai sẽ chạy phép kiểm quản trị hai lần.
    """
    from app import sudo_mode

    if sudo_mode.seconds_remaining(str(current_user["id"])) <= 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "sudo_required",
                "message": "Công bố văn bản pháp lý cần xác thực lại bằng mật khẩu.",
                "ttl_seconds": sudo_mode.SUDO_TTL_SECONDS,
            },
        )


@router.get("/documents")
def list_documents(
    kind: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Mọi bản của mọi loại, kể cả bản chưa tới ngày hiệu lực.

    ĐỌC chỉ cần quyền quản trị. Bắt nâng quyền để xem sẽ khiến người ta nâng
    quyền theo thói quen — đúng thứ làm bước xác thực lại mất ý nghĩa.
    """
    try:
        docs = legal.list_documents(kind)
    except legal.ConsentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    return {
        "documents": docs,
        "kinds": list(legal.KINDS),
        "required_at_registration": list(legal.REQUIRED_AT_REGISTRATION),
        "missing_required": legal.missing_for_registration(),
        "coverage": legal.consent_coverage(),
    }


@router.get("/documents/{kind}/{version}")
def read_any_version(
    kind: str,
    version: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Nguyên văn một bản BẤT KỲ, kể cả bản hẹn giờ cho tương lai.

    Đường công khai `/legal/{kind}/content` cố ý không thấy bản tương lai; đây
    là nơi người soạn kiểm lại bản mình vừa lên lịch trước khi nó tự có hiệu
    lực. Không có nó thì cách duy nhất để đọc lại bản đã hẹn là chờ tới ngày.
    """
    try:
        doc = legal.admin_read_document(kind, version)
    except legal.ConsentError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc))
    if doc is None:
        raise HTTPException(status_code=404,
                            detail=f"Không có bản {version!r} của {kind!r}.")
    return doc


@router.post("/documents", status_code=status.HTTP_201_CREATED)
def publish_document(
    payload: PublishRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Công bố một bản. **Cần nâng quyền.**

    Idempotent: gửi lại đúng nội dung cũ dưới cùng số hiệu trả về 201 và không
    tạo thêm gì. Gửi nội dung KHÁC dưới số hiệu cũ là 409 — xem
    `legal.register_document`.
    """
    from app import audit

    _require_sudo(current_user)

    try:
        legal.register_document(
            payload.kind, payload.version,
            url=f"/legal/{payload.kind}",
            body=payload.body,
            title=payload.title,
            body_format=payload.body_format,
            language=payload.language,
            change_summary=payload.change_summary,
            requires_reconsent=payload.requires_reconsent,
            effective_from=payload.effective_from,
            published_by=str(current_user["id"]),
        )
    except legal.ConsentError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": str(exc)})

    # Dòng kiểm toán mang HASH, không mang thân văn bản. Sổ kiểm toán được đọc
    # và chuyển tiếp thường xuyên hơn bảng văn bản; nhét cả bản văn vào đó là
    # nhân bản một tài liệu có thể còn đang cấm phát hành.
    audit.record("legal.publish", actor=current_user, request=request,
                 target_type="legal_document",
                 target_id=f"{payload.kind}:{payload.version}",
                 detail={
                     "content_hash": legal.content_hash(payload.body),
                     "requires_reconsent": payload.requires_reconsent,
                     "effective_from": (payload.effective_from.isoformat()
                                        if payload.effective_from else "ngay"),
                 })

    doc = legal.admin_read_document(payload.kind, payload.version) or {}
    return {
        # Bản VỪA công bố...
        "published": {k: v for k, v in doc.items() if k != "body"},
        # ...và bản ĐANG hiệu lực, có thể là hai bản khác nhau khi vừa hẹn giờ.
        # Giao diện cần cả hai để nói đúng "đã lên lịch" thay vì "đã áp dụng".
        "current": legal.current_document(payload.kind),
    }


@router.post("/documents/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    kind: str = Form(...),
    version: str = Form(...),
    file: UploadFile = File(...),
    title: str = Form(""),
    language: str = Form("vi"),
    change_summary: str = Form(""),
    requires_reconsent: bool = Form(False),
    effective_from: Optional[str] = Form(None),
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Công bố một bản văn bằng cách TẢI TỆP LÊN. **Cần nâng quyền.**

    Vì sao có đường này bên cạnh `POST /documents`
    -----------------------------------------------
    Văn bản pháp lý thật không ra đời trong một ô soạn markdown. Phòng pháp chế
    gửi `.docx`; bản đã ký và đóng dấu về dưới dạng `.pdf`. Bắt người ta dán nội
    dung vào một ô markdown làm mất định dạng, mất chữ ký, mất con dấu — và mất
    luôn bản gốc để đối chiếu khi có tranh chấp.

    Đường markdown **không bị bỏ**: bốn văn bản đã công bố đang dùng nó và có
    chữ ký trỏ vào băm của thân bài. Hai đường cùng sống, và `body_format` là
    thứ phân biệt.

    Điều quan trọng nhất ở đây: `content_hash` băm **byte của tệp**. Đó là giá
    trị `user_consents` trỏ tới, nên nó phải mô tả đúng thứ đã hiển thị trên màn
    hình người ký — không phải một bản chuyển đổi nào của nó.
    """
    from app import audit

    _require_sudo(current_user)

    payload = await file.read()
    if len(payload) > legal_store.MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={"code": "file_too_large",
                    "message": f"Tệp vượt quá "
                               f"{legal_store.MAX_FILE_BYTES // (1024 * 1024)} MB."})

    when: Optional[datetime] = None
    if effective_from:
        try:
            # `fromisoformat` không nhận hậu tố `Z`; trình duyệt thì gửi nó.
            when = datetime.fromisoformat(effective_from.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail={"code": "bad_effective_from",
                        "message": "Ngày hiệu lực không đọc được."})

    try:
        legal.register_document(
            kind, version,
            url=f"/legal/{kind}",
            body="",
            body_format="file",
            file_bytes=payload,
            file_name=file.filename or "",
            title=title,
            language=language,
            change_summary=change_summary,
            requires_reconsent=requires_reconsent,
            effective_from=when,
            published_by=str(current_user["id"]),
        )
    except legal.ConsentError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": str(exc)})

    doc = legal.admin_read_document(kind, version) or {}
    # Dòng kiểm toán mang HASH và TÊN TỆP, không mang nội dung — sổ kiểm toán
    # được đọc và chuyển tiếp thường xuyên hơn bảng văn bản.
    audit.record("legal.upload", actor=current_user, request=request,
                 target_type="legal_document", target_id=f"{kind}:{version}",
                 detail={"content_hash": doc.get("content_hash"),
                         "file_name": file.filename,
                         "file_size": len(payload),
                         "requires_reconsent": requires_reconsent})

    return {
        "published": {k: v for k, v in doc.items() if k != "body"},
        "current": legal.current_document(kind),
    }


# ===========================================================================
# Bản nháp — công cụ soạn thảo
# ===========================================================================

class CreateDraftRequest(BaseModel):
    kind: str
    seed_from_current: bool = True


class UpdateDraftRequest(BaseModel):
    """`revision` là số hiệu bản mà người soạn ĐANG XEM, không phải bản muốn ghi.

    Máy chủ chỉ ghi khi hai số khớp. Đây là toàn bộ cơ chế chống hai người đè
    mất bài của nhau — xem `legal.update_draft`.
    """
    revision: int
    title: Optional[str] = None
    language: Optional[str] = None
    body: Optional[str] = None
    change_summary: Optional[str] = None
    target_version: Optional[str] = None
    requires_reconsent: Optional[bool] = None
    effective_from: Optional[datetime] = None


class DraftStatusRequest(BaseModel):
    revision: int
    status: str


class PublishDraftRequest(BaseModel):
    revision: int


def _draft_error(exc: Exception):
    """Đưa lỗi tầng dữ liệu thành HTTP mà giao diện xử được.

    `DraftConflict` mang theo `current_revision`; không trả nó về thì giao diện
    chỉ biết "hỏng" và cách duy nhất còn lại là bảo người dùng tải lại trang —
    mất luôn phần họ vừa gõ.
    """
    if isinstance(exc, legal.DraftConflict):
        return HTTPException(status_code=409, detail={
            "code": exc.code,
            "message": str(exc),
            "current_revision": exc.current_revision,
        })
    if isinstance(exc, legal.ConsentError):
        return HTTPException(status_code=exc.status_code,
                             detail={"code": exc.code, "message": str(exc)})
    raise exc


@router.get("/drafts")
def list_drafts(
    include_closed: bool = False,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    return {"drafts": legal.list_drafts(include_closed=include_closed)}


@router.post("/drafts", status_code=status.HTTP_201_CREATED)
def create_draft(
    payload: CreateDraftRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Mở bản nháp. KHÔNG cần nâng quyền — soạn thảo chưa thay đổi gì đối ngoại.

    Nâng quyền dành cho lúc công bố. Bắt nhập lại mật khẩu để mở một trang soạn
    thảo sẽ khiến người ta nâng quyền theo thói quen, và tới lúc thật sự cần thì
    cửa sổ nâng quyền đã mở sẵn.
    """
    try:
        return legal.create_draft(payload.kind,
                                  actor_id=str(current_user["id"]),
                                  seed_from_current=payload.seed_from_current)
    except Exception as exc:
        raise _draft_error(exc)


@router.get("/drafts/{draft_id}")
def read_draft(
    draft_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    draft = legal.get_draft(draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Không có bản nháp này.")
    return draft


@router.patch("/drafts/{draft_id}")
def update_draft(
    draft_id: str,
    payload: UpdateDraftRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    # `.dict()`, không phải `.model_dump()` — dự án này chạy pydantic 1.10.
    #
    # `exclude_unset` là phần quan trọng: nếu không có nó, một lượt sửa chỉ đổi
    # tiêu đề sẽ gửi kèm `body=None` và âm thầm xoá trắng thân bài. Trường không
    # có mặt trong JSON phải khác với trường gửi lên là `null`.
    changes = payload.dict(exclude_unset=True, exclude={"revision"})
    try:
        return legal.update_draft(draft_id, payload.revision, changes,
                                  actor_id=str(current_user["id"]))
    except Exception as exc:
        raise _draft_error(exc)


@router.post("/drafts/{draft_id}/status")
def set_draft_status(
    draft_id: str,
    payload: DraftStatusRequest,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    try:
        return legal.advance_draft(draft_id, payload.revision, payload.status,
                                   actor_id=str(current_user["id"]))
    except Exception as exc:
        raise _draft_error(exc)


@router.post("/drafts/{draft_id}/publish", status_code=status.HTTP_201_CREATED)
def publish_draft(
    draft_id: str,
    payload: PublishDraftRequest,
    request: Request,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Công bố bản nháp đã phê duyệt. **Cần nâng quyền.**"""
    from app import audit

    _require_sudo(current_user)
    try:
        result = legal.publish_draft(draft_id, payload.revision,
                                     actor_id=str(current_user["id"]))
    except Exception as exc:
        raise _draft_error(exc)

    published = (result.get("draft") or {}).get("published_version")
    audit.record("legal.publish", actor=current_user, request=request,
                 target_type="legal_document",
                 target_id=f"{(result.get('draft') or {}).get('kind')}:{published}",
                 detail={"from_draft": str(draft_id)})
    return result


@router.get("/events")
def read_events(
    kind: Optional[str] = None,
    limit: int = 200,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, Any]:
    """Sổ đăng bạ: ai làm gì, lên đối tượng nào, lúc nào.

    Không bao giờ chứa nội dung văn bản — xem `legal.record_event`.
    """
    return {"events": legal.list_events(kind=kind, limit=limit)}


@router.get("/consents/{user_id}")
def read_user_consents(
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_admin),
) -> Dict[str, List[Dict[str, Any]]]:
    """Toàn bộ lịch sử chấp thuận của một tài khoản, kể cả bản đã rút.

    Đây là câu trả lời cho "người này đã đồng ý những gì, bản nào, lúc nào" —
    câu hỏi mà cả bảng `user_consents` tồn tại để trả lời, và trước endpoint
    này chỉ trả lời được bằng cách mở psql.

    Câu truy vấn nằm ở `legal.consent_history`, không ở đây: nó cần
    `system_scope`, và không router nào được phép vượt ranh giới tenant. Xem
    chú thích tại hàm đó.
    """
    return {"consents": legal.consent_history(user_id)}

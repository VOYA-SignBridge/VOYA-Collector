"""Đọc văn bản pháp lý — công khai, vì phải đọc được TRƯỚC khi có tài khoản.

Ba đường, ba mục đích khác nhau
--------------------------------
``GET /legal/documents``
    Mục lục: mỗi loại một dòng, kèm số hiệu bản đang hiệu lực. Đủ để dựng
    trang "Điều khoản & Chính sách" bằng MỘT lượt gọi thay vì bốn.

``GET /legal/{kind}``
    Siêu dữ liệu của bản đang hiệu lực. Đây là thứ biểu mẫu đăng ký cần: nó
    phải biết số hiệu để gửi lại trong ``accepted_terms_version``, nhưng không
    cần tải cả bản văn về chỉ để hiển thị một dòng "Tôi đồng ý với…".

``GET /legal/{kind}/content``
    Nguyên văn. Nhận ``?version=`` để đọc lại đúng bản MÌNH đã ký — điểm này
    là lý do phần lớn thiết kế còn lại tồn tại: một bản ghi chấp thuận trỏ tới
    ``(kind, version)``, và nếu bản văn ấy không đọc lại được thì bản ghi kia
    chỉ là một con số.

Vì sao bây giờ nội dung ĐI qua API
-----------------------------------
Bản trước của tệp này viết: "Nội dung nằm ở file tĩnh do nginx phục vụ, không
nhét qua API". Lập luận ấy đi kèm một quyết định lưu trữ đã bị thay: file tĩnh
đó chưa từng tồn tại, thân văn bản không được lưu ở đâu cả, và ``url`` trỏ vào
404. Từ v5 thân văn bản nằm trong cơ sở dữ liệu — xem ``docs/04-legal/LEGAL_DOCUMENTS.md``
— nên API là đường đọc duy nhất, và ``content_hash`` đi kèm mỗi phản hồi để bên
đọc tự đối chiếu được.

Cổng truy cập khớp ĐƯỜNG NGUYÊN VĂN, không khớp template. Vì thế số hiệu phiên
bản là tham số TRUY VẤN chứ không phải một đoạn đường: ``/legal/terms/content``
là một đường cố định khai báo được trong ``PUBLIC_ROUTES``, còn
``/legal/terms/versions/1.0`` thì không.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app import legal, legal_store
from app.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legal", tags=["legal"])


def _shape(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "kind": doc["kind"],
        "version": doc["version"],
        "url": doc["url"],
        "title": doc["title"],
        "language": doc["language"],
        "effective_from": doc["effective_from"],
        "change_summary": doc["change_summary"],
        # Cho phép giao diện chứng minh nó hiển thị đúng bản đã ghi nhận.
        "content_hash": doc["content_hash"],
        "requires_reconsent": doc["requires_reconsent"],
        # Bản văn là TỆP hay là markdown. Giao diện dựa vào `has_file` để chọn
        # trình đọc; `file_key` KHÔNG lộ ra ngoài — nó là đường trong kho blob,
        # và một đường nội bộ trong phản hồi công khai là một lời mời dò kho.
        "has_file": bool(doc.get("file_key")),
        "file_name": doc.get("file_name"),
        "file_mime": doc.get("file_mime"),
        "file_size": doc.get("file_size"),
    }


def _reject_unknown_kind(kind: str) -> None:
    if kind not in legal.KINDS:
        raise HTTPException(
            status_code=404,
            detail=f"Không có loại văn bản {kind!r}. "
                   f"Hợp lệ: {', '.join(legal.KINDS)}.",
        )


@router.get("/documents")
def list_published() -> Dict[str, List[Dict[str, Any]]]:
    """Mục lục các văn bản ĐANG hiệu lực.

    Loại chưa công bố bản nào thì vắng mặt, không phải xuất hiện với giá trị
    rỗng: một dòng "Chính sách quyền riêng tư — (chưa có)" trên trang công khai
    nói với người đọc một điều mà tổ chức không muốn nói, và cũng không giúp gì
    cho họ.
    """
    docs = []
    for kind in legal.KINDS:
        doc = legal.current_document(kind)
        if doc is not None:
            docs.append(_shape(doc))
    return {"documents": docs}


# ĐẶT TRƯỚC `@router.get("/{kind}")` LÀ BẮT BUỘC, không phải sở thích sắp xếp.
# FastAPI khớp route theo THỨ TỰ KHAI BÁO, và `/{kind}` nuốt trọn một đoạn
# đường bất kỳ — khai báo sau nó thì `GET /legal/me/consents` sẽ vào
# `read_document(kind="me")` và trả 404 "văn bản không hợp lệ", một thông báo
# không gợi tới nguyên nhân nào cả.
@router.get("/me/consents")
def my_consents(current_user: dict = Depends(get_current_user)) -> Dict[str, Any]:
    """Tôi đã ký những gì, bản số mấy, và cái gì đang chờ tôi.

    Ba trường dưới đây có mặt vì thiếu chúng thì màn hình chấp thuận nói dối
    theo ba kiểu khác nhau:

    ``accepted_version``
        Bản ĐÃ ký, có thể khác bản đang hiệu lực. Đây là đường duy nhất từ giao
        diện tới `GET /legal/{kind}/content?version=…` — không có nó, "bạn đã
        đồng ý" là một câu không kiểm chứng được.

    ``needs_reconsent``
        Đã ký một bản cũ, và bản mới đòi ký lại. Khác hẳn "chưa ký bao giờ":
        gộp hai trạng thái này vào một chữ "Chưa" sẽ báo với người đã từng đồng
        ý rằng họ chưa từng làm vậy.

    ``grants_scope``
        Ký văn bản này thì dữ liệu được dùng tới mức nào. Bản văn
        `data_contribution` tách "Có" khỏi "chỉ khi đồng ý riêng bằng văn bản",
        và nút bấm phải nói ra ranh giới đó thay vì để người ta suy đoán —
        xem `consent_gate.CONSENT_DOCUMENT_SCOPE`.
    """
    from app.consent_gate import CONSENT_DOCUMENT_SCOPE

    user_id = str(current_user["id"])
    live = legal.live_consents(user_id)
    items = []
    for kind in legal.KINDS:
        doc = legal.current_document(kind)
        if doc is None:
            continue
        signed = live.get(kind)
        # `has_consent` là nguồn sự thật cho chữ "đã đồng ý", kể cả khi luật
        # tính toán của nó đổi. Suy lại tại chỗ từ `signed` + `requires_reconsent`
        # sẽ tạo ra bản sao thứ hai của cùng một quy tắc, và bản sao đó sẽ trôi.
        accepted = legal.has_consent(user_id, kind)
        items.append({
            "kind": kind,
            "title": doc["title"],
            "current_version": str(doc["version"]),
            "accepted": accepted,
            "accepted_version": signed["version"] if signed else None,
            "accepted_at": signed["accepted_at"] if signed else None,
            "needs_reconsent": bool(signed) and not accepted,
            "required_at_registration": kind in legal.REQUIRED_AT_REGISTRATION,
            # Ký được MỘT LẦN cho cả tài khoản hay không. `guardian` thì không:
            # chính bản văn nói nó được hỏi trong từng buổi ghi hình. Mời người
            # ta ký vĩnh viễn ở đây là mâu thuẫn với thứ họ sắp ký.
            "self_signable": kind not in legal.PER_SESSION_KINDS,
            # Rút được hay không là quyết định của máy chủ (xem `withdraw_document`).
            # Để giao diện tự suy sẽ có ngày nó hiện một cái nút chắc chắn 409.
            "withdrawable": kind not in legal.REQUIRED_AT_REGISTRATION,
            "grants_scope": CONSENT_DOCUMENT_SCOPE.get(kind),
        })
    return {"consents": items}



@router.get("/{kind}")
def read_document(kind: str) -> Dict[str, Any]:
    """Siêu dữ liệu bản đang hiệu lực của một loại văn bản.

    404 khi chưa công bố bản nào — khác với 404 "loại không tồn tại", và thông
    điệp nói rõ để người vận hành không đi tìm nhầm chỗ.
    """
    _reject_unknown_kind(kind)
    doc = legal.current_document(kind)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_published",
                "message": f"Hệ thống chưa công bố văn bản {kind!r}.",
            },
        )
    return _shape(doc)


@router.get("/{kind}/content")
def read_content(
    kind: str,
    version: Optional[str] = Query(
        None, description="Số hiệu bản cần đọc. Bỏ trống = bản đang hiệu lực."),
) -> Dict[str, Any]:
    """Nguyên văn một bản văn bản.

    Chỉ trả về bản ĐÃ tới ngày hiệu lực, kể cả khi gọi đích danh số hiệu — một
    bản soạn trước cho tháng sau chưa phải tài liệu công khai. Hệ quả cần biết:
    hỏi một số hiệu tương lai cho ra 404 giống hệt hỏi một số hiệu không tồn
    tại, và điều đó là cố ý.
    """
    _reject_unknown_kind(kind)
    doc = legal.read_document(kind, version)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "not_published",
                "message": (f"Không có bản {version!r} của văn bản {kind!r} đang "
                            f"hiệu lực." if version else
                            f"Hệ thống chưa công bố văn bản {kind!r}."),
            },
        )
    return {**_shape(doc), "body": doc["body"], "body_format": doc["body_format"]}


@router.get("/{kind}/file")
def download_file(
    kind: str,
    version: Optional[str] = Query(
        None, description="Số hiệu bản cần tải. Bỏ trống = bản đang hiệu lực."),
    download: bool = Query(
        False, description="true = buộc tải về; false = để trình duyệt tự mở."),
):
    """Tệp gốc của một bản văn (pdf/docx/odt).

    CÔNG KHAI, cùng lý do như `/{kind}/content`: người ta phải đọc được điều
    khoản **trước khi** tạo tài khoản. Gác nó sau cổng đăng nhập nghĩa là bắt
    người ta đồng ý với thứ họ chưa mở ra được.

    Hai chi tiết quyết định tính an toàn của đường này:

    * **`Content-Type` suy từ ĐUÔI CỦA KHOÁ trong kho**, không từ cột
      `file_mime` và càng không từ header người tải lên khai. Khoá do
      `legal_store.storage_key` sinh ra và đuôi của nó đã qua danh sách trắng,
      nên kể cả khi một hàng trong cơ sở dữ liệu bị sửa, đường này vẫn không
      phục vụ được một kiểu nội dung ngoài dự kiến.
    * **`Content-Disposition` luôn có `filename`**, và tên đó được làm sạch.
      Một tên tệp mang dấu ngoặc kép hoặc xuống dòng là một header bị tách.
    """
    from fastapi.responses import Response

    _reject_unknown_kind(kind)
    doc = legal.read_document(kind, version)
    if doc is None or not doc.get("file_key"):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "no_file",
                "message": (f"Bản {version!r} của {kind!r} không có tệp đính kèm."
                            if version else
                            f"Văn bản {kind!r} không có tệp đính kèm — "
                            f"bản này lưu dưới dạng văn bản, xem /{kind}/content."),
            },
        )

    key = str(doc["file_key"])
    try:
        payload = legal_store.read_bytes(key)
    except (OSError, ValueError):
        # Hàng trỏ tới một blob không đọc được. Đây là hỏng dữ liệu, không phải
        # đầu vào sai — nên nó phải KÊU, không im lặng trả 404.
        logger.error("[LEGAL] khong doc duoc blob %s cua %s ban %s",
                     key, kind, doc.get("version"))
        raise HTTPException(
            status_code=500,
            detail={"code": "file_unreadable",
                    "message": "Không đọc được tệp văn bản. Vui lòng báo quản trị viên."})

    safe_name = re.sub(r'[^\w.\- ]+', "_", str(doc.get("file_name") or "")) \
        or f"{kind}-{doc.get('version') or 'ban-hien-hanh'}"
    disposition = "attachment" if download else "inline"

    return Response(
        content=payload,
        media_type=legal_store.content_type_for(key),
        headers={
            "Content-Disposition": f'{disposition}; filename="{safe_name}"',
            # Nội dung định địa chỉ bằng băm ⇒ bất biến ⇒ cache được vĩnh viễn.
            # `immutable` là thứ ngăn trình duyệt hỏi lại mỗi lần mở trang.
            "Cache-Control": "public, max-age=31536000, immutable",
            "X-Content-Type-Options": "nosniff",
        },
    )


# ---------------------------------------------------------------------------
# Chấp thuận của chính mình: xem, ký, rút
#
# Ba đường dưới đây CẦN đăng nhập, khác hẳn ba đường đọc ở trên. Chúng ra đời
# vì một khoảng trống đo được ngày 2026-08-09: `data_contribution` đã được công
# bố và bắt buộc phải có để dữ liệu đi vào bất kỳ đâu, nhưng **không có màn hình
# hay endpoint nào để một người ký nó**. Nó không nằm trong
# `REQUIRED_AT_REGISTRATION` — và đúng là không được nằm ở đó, vì chính bản văn
# hứa "việc bạn từ chối không ảnh hưởng tới quyền dùng phần còn lại của hệ
# thống". Nên nó phải hỏi được ở chỗ khác, và đây là chỗ đó.
#
# Ký xong thì nó **ở lại**: `record_consent` chỉ giữ một dòng còn hiệu lực cho
# mỗi (người, loại), nên bấm hai lần không sinh hai dòng và không dời mốc thời
# gian đã ký. Rút rồi ký lại là hai dòng riêng, và dòng cũ giữ nguyên
# `withdrawn_at` — lịch sử chấp thuận là bằng chứng, không phải trạng thái.
# ---------------------------------------------------------------------------

class ConsentDecision(BaseModel):
    # `Literal`, không phải `Field(pattern=...)`: dự án chạy pydantic 1.10, ở đó
    # từ khoá là `regex` còn `pattern` bị nhận vào trong im lặng rồi bỏ qua.
    version: str = Field(..., min_length=1, max_length=64)


@router.post("/{kind}/accept")
def accept_document(
    kind: str,
    payload: ConsentDecision,
    request: Request,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ký một văn bản. Idempotent — ký lại bản đang hiệu lực không đổi gì."""
    _reject_unknown_kind(kind)
    from app.rate_limit import client_ip

    # Cùng công thức băm với luồng đăng ký (`routers/auth._record_consents`):
    # băm IP chứ không lưu IP, và trộn `user_id` vào để hai người cùng một mạng
    # không cho ra cùng một giá trị. Hai chỗ ghi cùng một loại bằng chứng thì
    # phải so sánh được với nhau.
    user_id = str(current_user["id"])
    ip_hash = hashlib.sha256(
        f"{client_ip(request)}|{user_id}".encode("utf-8")).hexdigest()
    try:
        legal.record_consent(
            user_id, kind, payload.version,
            ip_hash=ip_hash,
            user_agent=(request.headers.get("user-agent") or "")[:500],
            source="user",
        )
    except legal.ConsentError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": str(exc)}) from None
    return {"kind": kind, "accepted": True, "version": payload.version}


@router.post("/{kind}/withdraw")
def withdraw_document(
    kind: str,
    current_user: dict = Depends(get_current_user),
) -> Dict[str, Any]:
    """Rút chấp thuận.

    Từ chối rút những văn bản BẮT BUỘC để dùng hệ thống: rút `terms` mà vẫn
    đăng nhập được là một trạng thái không có thật. Muốn rời hẳn thì đó là xoá
    tài khoản, một hành động khác, ở một chỗ khác.

    Rút `data_contribution` thì đồng thuận của người ký bị rút theo, và cổng
    dữ liệu loại mẫu của họ khỏi lượt chọn TIẾP THEO ở mọi mức. Nó không xoá
    tệp đã có — xem `docs/04-legal/CONSENT_ENFORCEMENT.md` §5.
    """
    _reject_unknown_kind(kind)
    if kind in legal.REQUIRED_AT_REGISTRATION:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "required_document",
                "message": (f"Không rút được {kind!r} khi còn dùng hệ thống. "
                            f"Nếu bạn muốn dừng hẳn, hãy yêu cầu xoá tài khoản."),
            },
        )
    withdrawn = legal.withdraw_consent(str(current_user["id"]), kind)
    return {"kind": kind, "accepted": False, "withdrawn": withdrawn}

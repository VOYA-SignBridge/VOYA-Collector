"""Điều khoản, quyền riêng tư, đồng ý đóng góp — có phiên bản, có bằng chứng.

Bốn văn bản, không phải một
----------------------------
====================  =====================  ==========  ==============================
kind                  hỏi khi nào            bắt buộc    vì sao tách riêng
====================  =====================  ==========  ==============================
`terms`               đăng ký                có          quy tắc sử dụng dịch vụ
`privacy`             đăng ký                có          xử lý dữ liệu của NGƯỜI DÙNG
`data_contribution`   lần đóng góp đầu tiên  để đóng góp dữ liệu sinh trắc của NGƯỜI KÝ
`guardian`            người ký dưới 18 tuổi  trong ca đó  người giám hộ đồng ý
====================  =====================  ==========  ==============================

Ranh giới đáng nói nhất là `data_contribution`. Gộp nó vào lúc đăng ký thì bạn
thu được một chữ ký cho một việc người ta chưa hình dung: ở đây "đóng góp" nghĩa
là quay video bàn tay và khuôn mặt của một người vào một tập dữ liệu nghiên cứu
sẽ công bố. Đó là thứ phải hỏi khi họ đang đứng trước webcam, không phải khi
đang điền email.

Đồng ý phải là dữ liệu, không phải một tờ giấy
------------------------------------------------
Không có `users.accepted_terms BOOLEAN` ở đây, và đó là chủ ý — xem chú thích
trên bảng `legal_documents` trong `metadata_db.py`.

Bản văn sống trong cơ sở dữ liệu
---------------------------------
Tới v5, thân văn bản nằm ở cột `legal_documents.body`. Trước đó module này băm
nội dung rồi vứt và để `url` trỏ tới "một file tĩnh do nginx phục vụ" — file
chưa bao giờ tồn tại. Hệ quả: hash không đối chiếu được với gì, và không đường
nào đọc được bản văn mà người ta vừa đồng ý.

Lý do chọn cơ sở dữ liệu chứ không phải hệ tệp: chữ ký và bản văn được ký phải
sao lưu và khôi phục CÙNG NHAU. Xem `docs/04-legal/LEGAL_DOCUMENTS.md`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

KINDS = ("terms", "privacy", "data_contribution", "guardian")

#: Bắt buộc để tạo tài khoản. Hai cái còn lại hỏi sau, đúng lúc cần.
REQUIRED_AT_REGISTRATION = ("terms", "privacy")

#: Văn bản hỏi theo TỪNG BUỔI GHI HÌNH, không ký một lần cho cả tài khoản.
#:
#: Đọc thẳng từ bản `guardian` 2026-08-08: *"Nó được hỏi trong chính buổi ghi
#: hình đó, không phải một lần rồi thôi: mỗi buổi thu là một lần bạn biết cụ thể
#: hôm nay con em mình làm gì."*
#:
#: Danh sách này tồn tại để màn hình "Chấp thuận của tôi" không mời người ta ký
#: một chữ ký vĩnh viễn cho một văn bản vừa nói rằng nó KHÔNG hoạt động như vậy.
#: Trang tài khoản vẫn liệt kê chúng — người giám hộ có quyền đọc trước — nhưng
#: không đưa ra nút ký.
PER_SESSION_KINDS = ("guardian",)

#: Vòng đời một bản nháp. Lấy từ cách các hệ quản lý tài liệu có kiểm soát làm
#: việc (eQMS, ISO 9001): trạng thái là dữ liệu tường minh, không suy ra từ việc
#: một cột nào đó có rỗng hay không.
#:
#: `published` và `discarded` là hai trạng thái ĐÓNG — bản nháp ở đó không sửa
#: được nữa, và chỉ mục `uq_legal_draft_open` chỉ ràng buộc ba trạng thái mở.
DRAFT_STATUSES = ("draft", "in_review", "approved", "published", "discarded")
OPEN_DRAFT_STATUSES = ("draft", "in_review", "approved")

#: Chuyển trạng thái nào là hợp lệ. Bảng này tồn tại thay vì một chuỗi `if` vì
#: nó ĐỌC ĐƯỢC như một quy trình: người đọc thấy ngay rằng không có đường tắt
#: nào từ `draft` thẳng tới `published`.
DRAFT_TRANSITIONS = {
    "draft": ("in_review", "discarded"),
    "in_review": ("approved", "draft", "discarded"),
    "approved": ("published", "draft", "discarded"),
    "published": (),
    "discarded": (),
}


class DraftConflict(RuntimeError):
    """Ai đó đã ghi trước. Mang theo số hiệu bản hiện tại để giao diện nạp lại."""

    def __init__(self, message: str, *, current_revision: Optional[int] = None):
        super().__init__(message)
        self.code = "revision_conflict"
        self.status_code = 409
        self.current_revision = current_revision


#: Cách một dòng chấp thuận ra đời. Xem chú thích v5.3 trong `metadata_db.py`:
#: một chữ ký thật và một dòng người vận hành ghi hộ không phải cùng một loại
#: bằng chứng, và trước v5 chúng trông giống hệt nhau trong bảng.
CONSENT_SOURCES = ("user", "backfill", "import")

#: Cột trả về cho mọi truy vấn văn bản TRỪ khi cần thân bài.
#:
#: Thân văn bản có thể dài vài chục nghìn ký tự và `current_document` được gọi
#: ở mỗi lượt đăng ký cũng như mỗi lần dựng biểu mẫu; kéo nó về chỉ để vứt đi
#: là trả giá băng thông cho một thứ không ai đọc ở đường đó.
_META_COLUMNS = (
    "doc_id", "kind", "version", "effective_from", "content_hash", "url",
    "title", "requires_reconsent", "language", "change_summary", "body_format",
    "published_at", "published_by",
    # v3.15 - ban van la TEP. NULL voi cac ban markdown cong bo truoc do; giao
    # dien dua vao `file_key` de biet nen dung trinh doc nao.
    "file_key", "file_name", "file_mime", "file_size",
)


def _columns(prefix: str = "") -> str:
    """`_META_COLUMNS` thành mệnh đề SELECT, có thể kèm bí danh bảng.

    Tiền tố là bắt buộc ở `list_documents`, nơi truy vấn con chạm
    `user_consents` — bảng đó cũng có `kind` và `version`, và một tên trần ở
    đấy là lỗi mơ hồ cột chứ không phải kết quả sai lặng lẽ.
    """
    p = f"{prefix}." if prefix else ""
    return ", ".join(f"{p}{col}" for col in _META_COLUMNS)


class ConsentError(RuntimeError):
    """Chấp thuận thiếu, sai phiên bản, hoặc văn bản không tồn tại."""

    def __init__(self, message: str, *, code: str, status_code: int = 400):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def current_document(kind: str) -> Optional[Dict[str, Any]]:
    """Bản đang hiệu lực của một loại văn bản, hoặc None nếu chưa đăng ký bản nào.

    "Đang hiệu lực" = `effective_from` đã tới và mới nhất. Cho phép soạn trước
    một bản có hiệu lực trong tương lai mà không ảnh hưởng người đang đăng ký.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    if kind not in KINDS:
        raise ConsentError(f"loại văn bản không hợp lệ: {kind!r}",
                           code="unknown_kind", status_code=404)
    with system_scope("legal: văn bản áp dụng cho cả nền tảng"):
        rows = _fetch_all(
            f"""
            SELECT {_columns()}
            FROM legal_documents
            WHERE kind = %s AND effective_from <= now()
            ORDER BY effective_from DESC
            LIMIT 1
            """,
            (kind,),
        )
    return dict(rows[0]) if rows else None


def read_document(kind: str, version: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Bản văn ĐẦY ĐỦ, kèm thân bài. `version=None` nghĩa là bản đang hiệu lực.

    Chỉ trả về bản ĐÃ tới ngày hiệu lực, kể cả khi gọi đích danh số hiệu. Đó là
    ranh giới giữa hàm này và `admin_read_document`: một bản soạn trước cho
    tháng sau là tài liệu nội bộ chưa công bố, và để nó rò ra đường đọc công
    khai nghĩa là ai cũng xem được điều khoản sắp đổi trước khi tổ chức kịp
    thông báo.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    if kind not in KINDS:
        raise ConsentError(f"loại văn bản không hợp lệ: {kind!r}",
                           code="unknown_kind", status_code=404)
    sql = (f"SELECT {_columns()}, body FROM legal_documents "
           f"WHERE kind = %s AND effective_from <= now()")
    params: tuple = (kind,)
    if version is not None:
        sql += " AND version = %s"
        params += (str(version),)
    sql += " ORDER BY effective_from DESC LIMIT 1"

    with system_scope("legal: đọc nguyên văn một bản văn bản"):
        rows = _fetch_all(sql, params)
    return dict(rows[0]) if rows else None


def list_documents(kind: Optional[str] = None) -> List[Dict[str, Any]]:
    """Mọi bản của mọi loại, kể cả bản chưa tới ngày hiệu lực. Đường QUẢN TRỊ.

    Kèm `consent_count` — số chấp thuận CÒN HIỆU LỰC trỏ tới bản đó. Con số này
    là thứ biến "xoá bản nháp gõ nhầm" từ một canh bạc thành một quyết định:
    khác 0 nghĩa là có người đã ký, và khoá ngoại `ON DELETE RESTRICT` sẽ chặn.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    if kind is not None and kind not in KINDS:
        raise ConsentError(f"loại văn bản không hợp lệ: {kind!r}",
                           code="unknown_kind", status_code=404)

    sql = f"""
        SELECT {_columns("d")},
               length(d.body)            AS body_length,
               d.effective_from <= now() AS is_effective,
               (SELECT count(*) FROM user_consents c
                 WHERE c.kind = d.kind AND c.version = d.version
                   AND c.withdrawn_at IS NULL) AS consent_count
        FROM legal_documents d
    """
    params: tuple = ()
    if kind is not None:
        sql += " WHERE d.kind = %s"
        params = (kind,)
    sql += " ORDER BY d.kind, d.effective_from DESC"

    with system_scope("legal: liệt kê toàn bộ văn bản nền tảng"):
        return [dict(r) for r in _fetch_all(sql, params)]


def record_event(action: str, *, actor_id: Optional[str] = None,
                 actor_label: str = "", kind: Optional[str] = None,
                 version: Optional[str] = None, draft_id: Optional[str] = None,
                 revision: Optional[int] = None,
                 storage_key: Optional[str] = None,
                 content_hash_value: Optional[str] = None,
                 detail: Optional[Dict[str, Any]] = None) -> None:
    """Ghi một dòng vào sổ đăng bạ. HÀNH ĐỘNG và ĐỐI TƯỢNG, không phải nội dung.

    `detail` **không bao giờ** được mang thân văn bản. Sổ này được đọc, xuất và
    chuyển tiếp thường xuyên hơn bảng văn bản; nhét bản văn vào đây là nhân bản
    một tài liệu có thể còn đang cấm phát hành sang một chỗ có quyền đọc khác
    hẳn. Muốn biết nội dung thì đã có `storage_key` và `content_hash` trỏ tới nó.

    **Không bao giờ làm hỏng thao tác gọi nó.** Một lỗi ghi sổ không được biến
    một lượt công bố đã thành công thành 500 — bản văn đã nằm trong bảng và
    người dùng sẽ bấm lại rồi đụng chính số hiệu họ vừa chiếm. Cùng lập luận
    với `_send_welcome_verification` ở `routers/auth.py`.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    try:
        payload = json.dumps(detail or {}, ensure_ascii=False, default=str)
        actor_uuid = actor_id if _is_uuid(actor_id) else None
        with system_scope("legal: ghi sổ đăng bạ văn bản"):
            with _cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO legal_document_events
                        (actor_user_id, actor_label, action, kind, version,
                         draft_id, revision, storage_key, content_hash, detail)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (actor_uuid, actor_label or (actor_id or ""), action, kind,
                     version, draft_id, revision, storage_key,
                     content_hash_value, payload),
                )
    except Exception as exc:
        logger.error("[LEGAL] khong ghi duoc so dang ba cho %s: %s",
                     action, type(exc).__name__)


def _is_uuid(value: Optional[str]) -> bool:
    """`actor_user_id` là khoá ngoại UUID; người gọi bằng khoá API có id dạng
    `apikey:<uuid>`, không phải UUID. Cùng phép canh với `audit._is_uuid`."""
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def list_events(*, kind: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    """Sổ đăng bạ, mới nhất trước."""
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    sql = """
        SELECT e.event_id, e.occurred_at, e.action, e.kind, e.version,
               e.draft_id, e.revision, e.storage_key, e.content_hash, e.detail,
               COALESCE(u.username, e.actor_label, '') AS actor
        FROM legal_document_events e
        LEFT JOIN users u ON u.id = e.actor_user_id
    """
    params: tuple = ()
    if kind is not None:
        sql += " WHERE e.kind = %s"
        params = (kind,)
    sql += " ORDER BY e.occurred_at DESC, e.event_id DESC LIMIT %s"
    params += (max(1, min(int(limit), 1000)),)

    with system_scope("legal: đọc sổ đăng bạ"):
        return [dict(r) for r in _fetch_all(sql, params)]


def register_document(kind: str, version: str, *, url: str, body: str,
                      title: str = "", requires_reconsent: bool = False,
                      language: str = "vi", change_summary: str = "",
                      effective_from: Optional[datetime] = None,
                      published_by: Optional[str] = None,
                      body_format: str = "markdown",
                      file_bytes: Optional[bytes] = None,
                      file_name: str = "") -> Dict[str, Any]:
    """Công bố một bản văn bản. Idempotent theo `(kind, version)`.

    Nếu bản đó đã tồn tại với NỘI DUNG KHÁC, đây là lỗi chứ không phải cập
    nhật: sửa nội dung mà giữ nguyên số hiệu phiên bản khiến mọi chấp thuận đã
    thu trỏ tới một bản văn không còn là bản họ đọc. Từ v5 điều đó còn được
    trigger `trg_legal_documents_freeze` chặn ở tầng dưới, nên phép kiểm ở đây
    tồn tại để cho ra một thông điệp đọc được chứ không phải để làm hàng rào
    duy nhất.

    `effective_from` ở tương lai là cách lên lịch: bản mới nằm sẵn trong bảng,
    `current_document` chưa nhìn thấy nó, và tới đúng thời điểm nó tự thay bản
    cũ mà không cần ai chạy lệnh gì lúc nửa đêm.

    Trả về bản ĐANG hiệu lực sau lời gọi này — có thể KHÔNG phải bản vừa công
    bố, nếu bản vừa công bố hẹn giờ cho tương lai.
    """
    from app import legal_store
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    if kind not in KINDS:
        raise ConsentError(f"loại văn bản không hợp lệ: {kind!r}",
                           code="unknown_kind", status_code=400)
    # `file` là bản văn TẢI LÊN (pdf/docx/odt). Văn bản pháp lý thật đi qua tay
    # người không dùng trình soạn markdown: phòng pháp chế gửi `.docx`, bản đã
    # ký về dưới dạng `.pdf` có dấu. Bắt họ dán vào một ô markdown là làm mất
    # định dạng, mất chữ ký, và mất luôn bản gốc để đối chiếu.
    if body_format not in ("markdown", "text", "file"):
        raise ConsentError(f"định dạng không hợp lệ: {body_format!r}",
                           code="unknown_format", status_code=400)

    is_file = file_bytes is not None
    if is_file and body_format != "file":
        body_format = "file"

    if is_file:
        if not file_bytes:
            raise ConsentError(
                "Tệp rỗng. Công bố một bản rỗng nghĩa là thu chữ ký cho khoảng trắng.",
                code="empty_body", status_code=400)
        try:
            extension = legal_store.normalize_extension(file_name)
        except ValueError as exc:
            raise ConsentError(str(exc), code="bad_format", status_code=400) from exc
    else:
        # Cột `body` có DEFAULT '' để câu ALTER chạy được trên bảng đã có dòng;
        # chỗ duy nhất tạo dòng MỚI là đây, nên đây là chỗ đúng để nói "một văn
        # bản rỗng không phải văn bản". Công bố một bản rỗng nghĩa là thu chữ ký
        # cho khoảng trắng.
        if not (body or "").strip():
            raise ConsentError(
                "Thân văn bản rỗng. Công bố một bản rỗng nghĩa là thu chữ ký cho "
                "khoảng trắng.",
                code="empty_body", status_code=400,
            )

    version = str(version).strip()
    if not version:
        raise ConsentError("Thiếu số hiệu phiên bản.",
                           code="missing_version", status_code=400)

    # GHI TỆP TRƯỚC, GHI HÀNG SAU — thứ tự này là một phần của tính đúng.
    #
    # Một blob mồ côi (tệp ghi xong, hàng ghi hỏng) thì vô hại và `legal_store.
    # collect_garbage` dọn được. Chiều ngược lại — hàng trỏ tới tệp không tồn
    # tại — thì không cứu được. Và vì tên tệp LÀ băm nội dung, ghi lại sau một
    # lần hỏng giữa chừng là an toàn.
    #
    # `content_hash` băm ĐÚNG THỨ người ta ký: byte của tệp với bản tải lên,
    # byte UTF-8 của thân bài với bản markdown. Đây là giá trị mà `user_consents`
    # trỏ tới, nên nó phải mô tả được chính xác cái đã hiển thị trên màn hình.
    if is_file:
        storage_key, digest, byte_size = legal_store.write_bytes(
            kind, file_bytes, extension)
        file_mime = legal_store.content_type_for(storage_key)
    else:
        digest = content_hash(body)
        storage_key, _, byte_size = legal_store.write(kind, body)
        file_mime = None

    with system_scope("legal: công bố văn bản nền tảng"):
        with _cursor() as cur:
            # Khoá tư vấn theo LOẠI, giữ tới hết giao dịch.
            #
            # Không có nó, hai lượt công bố cùng lúc chạy xen kẽ giữa câu đọc
            # "đã có bản này chưa" và câu ghi — kinh điển TOCTOU. Chỉ mục duy
            # nhất vẫn chặn được hàng trùng, nhưng lỗi bật ra là một
            # `UniqueViolation` thô thay vì thông điệp giải thích được, và
            # nhánh idempotent "gửi lại đúng nội dung cũ" sẽ báo lỗi thay vì
            # trả về bình thường.
            #
            # Khoá theo `kind` chứ không khoá cả bảng: công bố `terms` và
            # `privacy` cùng lúc là việc hợp lệ và không đụng nhau.
            cur.execute("SELECT pg_advisory_xact_lock(hashtext(%s))",
                        (f"legal:{kind}",))

            cur.execute(
                "SELECT content_hash FROM legal_documents "
                "WHERE kind = %s AND version = %s",
                (kind, version),
            )
            existing = cur.fetchone()
            if existing:
                stored = existing["content_hash"] if isinstance(existing, dict) \
                    else existing[0]
                if stored != digest:
                    raise ConsentError(
                        f"{kind} bản {version} đã tồn tại với nội dung khác. "
                        f"Tăng số hiệu phiên bản thay vì sửa bản cũ.",
                        code="version_content_mismatch", status_code=409,
                    )
                return current_document(kind) or {}

            try:
                cur.execute(
                    """
                    INSERT INTO legal_documents
                        (doc_id, kind, version, content_hash, url, title,
                         requires_reconsent, body, body_format, language,
                         change_summary, published_by, effective_from,
                         storage_backend, storage_key, byte_size,
                         file_key, file_name, file_mime, file_size)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                            COALESCE(%s, now()), 'local', %s, %s,
                            %s, %s, %s, %s)
                    """,
                    (str(uuid.uuid4()), kind, version, digest, url, title,
                     bool(requires_reconsent), body, body_format, language,
                     change_summary, published_by, effective_from,
                     storage_key, byte_size,
                     # Bốn cột tệp NULL với bản markdown. `file_key` trùng
                     # `storage_key` ở bản tải lên — giữ cả hai vì `storage_key`
                     # là đường của kho blob (dùng cho GC và kiểm toàn vẹn), còn
                     # `file_key` là câu trả lời cho "hàng này có tệp không".
                     # Gộp làm một thì không phân biệt được markdown với tệp.
                     storage_key if is_file else None,
                     (file_name or "").strip()[:255] if is_file else None,
                     file_mime, byte_size if is_file else None),
                )
            except Exception as exc:
                # `uq_legal_effective` — hai bản cùng loại, cùng giờ hiệu lực.
                # Đổi thành thông điệp nói được phải làm gì; nếu không người
                # vận hành nhận một chuỗi tên chỉ mục và không biết vì sao.
                if "uq_legal_effective" in str(exc):
                    raise ConsentError(
                        f"Đã có một bản {kind} khác có hiệu lực đúng vào thời "
                        f"điểm này. Mỗi loại chỉ được một bản tại một thời điểm "
                        f"— chọn giờ hiệu lực khác.",
                        code="effective_from_taken", status_code=409,
                    ) from exc
                raise

    # Số hiệu và hash, KHÔNG phải nội dung: một dòng log là chỗ dễ bị chuyển
    # tiếp ra ngoài nhất, và bản văn có thể còn đang cấm phát hành.
    logger.info("[LEGAL] công bố %s bản %s (hash %s…, hiệu lực %s)",
                kind, version, digest[:12], effective_from or "ngay")
    record_event("document.publish", actor_id=published_by, kind=kind,
                 version=version, storage_key=storage_key,
                 content_hash_value=digest,
                 detail={"byte_size": byte_size,
                         "requires_reconsent": bool(requires_reconsent),
                         "effective_from": (effective_from.isoformat()
                                            if effective_from else "ngay")})
    return current_document(kind) or {}


def record_consent(user_id: str, kind: str, version: str, *,
                   ip_hash: Optional[str] = None,
                   user_agent: Optional[str] = None,
                   source: str = "user", note: str = "",
                   recorded_by: Optional[str] = None) -> None:
    """Ghi nhận một chấp thuận. Phải khớp bản ĐANG hiệu lực.

    Kiểm phiên bản ở đây chứ không tin phía client: một biểu mẫu cũ còn mở trong
    tab trình duyệt sẽ gửi lên số hiệu cũ, và chấp nhận nó nghĩa là thu được chữ
    ký cho một bản văn đã bị thay thế.

    `source` khác `'user'` nghĩa là dòng này KHÔNG phải chữ ký của người dùng.
    Xem `CONSENT_SOURCES`. Người vận hành ghi hộ cho tài khoản có sẵn là việc
    hợp lệ và đôi khi cần thiết, nhưng nó phải đọc ra được như đúng bản chất
    của nó — `note` và `recorded_by` là chỗ ghi ai ghi và vì sao.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    if source not in CONSENT_SOURCES:
        raise ConsentError(f"nguồn chấp thuận không hợp lệ: {source!r}",
                           code="unknown_source", status_code=400)
    if source != "user" and not note.strip():
        # Một dòng ghi hộ không giải thích được thì sáu tháng sau không ai đọc
        # ra vì sao nó ở đó, và nó sẽ bị đọc nhầm thành chữ ký thật.
        raise ConsentError(
            f"chấp thuận nguồn {source!r} phải kèm `note` giải thích vì sao nó "
            f"được ghi hộ.",
            code="note_required", status_code=400,
        )

    doc = current_document(kind)
    if doc is None:
        raise ConsentError(
            f"Chưa có văn bản {kind} nào được đăng ký trên hệ thống này.",
            code="no_document", status_code=503,
        )
    if str(version) != str(doc["version"]):
        raise ConsentError(
            f"Bản {kind} bạn đồng ý ({version}) không còn là bản hiện hành "
            f"({doc['version']}). Hãy tải lại trang và đọc bản mới.",
            code="stale_version", status_code=409,
        )

    with system_scope("legal: ghi chấp thuận, gắn với tài khoản chứ không với tenant"):
        with _cursor() as cur:
            # Rút lại bản cũ trước khi ghi bản mới: chỉ mục duy nhất bộ phận
            # cho phép đúng MỘT chấp thuận còn hiệu lực cho mỗi (người, loại).
            cur.execute(
                "UPDATE user_consents SET withdrawn_at = now() "
                "WHERE user_id = %s AND kind = %s AND withdrawn_at IS NULL "
                "AND version <> %s",
                (user_id, kind, str(doc["version"])),
            )
            cur.execute(
                """
                INSERT INTO user_consents
                    (consent_id, user_id, kind, version, ip_hash, user_agent,
                     source, note, recorded_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING
                """,
                (str(uuid.uuid4()), user_id, kind, str(doc["version"]),
                 ip_hash, user_agent, source, note, recorded_by),
            )

    # Phản chiếu sang `signer_consents` NGOÀI khối `_cursor` ở trên: chấp thuận
    # của tài khoản đã được ghi và cam kết xong: đó là bản gốc. Bảng người ký là
    # bản phản chiếu để cổng dữ liệu đọc, và một trục trặc ở bản phản chiếu
    # không được phép cuốn theo bản gốc. Hàm này tự nuốt lỗi và ghi log.
    from app.consent_gate import sync_signer_consent

    sync_signer_consent(user_id, kind)


def has_consent(user_id: str, kind: str) -> bool:
    """Người này có chấp thuận CÒN HIỆU LỰC cho bản HIỆN HÀNH không?

    Hai điều kiện, và điều kiện thứ hai là lý do hàm này tồn tại: đồng ý với
    bản cũ không tính khi bản mới đánh dấu `requires_reconsent`.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    doc = current_document(kind)
    if doc is None:
        return False

    with system_scope("legal: kiểm chấp thuận của một tài khoản"):
        rows = _fetch_all(
            "SELECT version FROM user_consents "
            "WHERE user_id = %s AND kind = %s AND withdrawn_at IS NULL",
            (user_id, kind),
        )
    if not rows:
        return False
    if not doc["requires_reconsent"]:
        # Bản mới không đòi đồng ý lại: một chấp thuận bất kỳ còn hiệu lực là đủ.
        return True
    return str(rows[0]["version"]) == str(doc["version"])


def live_consents(user_id: str) -> Dict[str, Dict[str, Any]]:
    """Mọi chấp thuận CÒN HIỆU LỰC của một người, khoá theo loại văn bản.

    `has_consent` trả về bool và vứt đi hai thứ mà màn hình "Chấp thuận của tôi"
    cần: **bản nào** đã ký và **lúc nào**. Không có số hiệu bản đã ký thì nút
    "đọc lại bản tôi đã ký" không dựng được, và cả chuỗi phiên bản — thứ mà
    `read_document(kind, version)` tồn tại để phục vụ — không có đường nào tới
    được từ giao diện.

    Một truy vấn cho cả bốn loại. Chỉ mục duy nhất bộ phận `uq_consent_live` bảo
    đảm mỗi loại có nhiều nhất một dòng còn hiệu lực, nên khoá theo `kind` không
    làm mất dòng nào.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("legal: đọc chấp thuận còn hiệu lực của một tài khoản"):
        rows = _fetch_all(
            "SELECT kind, version, accepted_at FROM user_consents "
            "WHERE user_id = %s AND withdrawn_at IS NULL",
            (str(user_id),),
        )
    return {r["kind"]: {"version": str(r["version"]),
                        "accepted_at": r["accepted_at"]} for r in rows}


def admin_read_document(kind: str, version: str) -> Optional[Dict[str, Any]]:
    """Như `read_document` nhưng THẤY cả bản chưa tới ngày hiệu lực.

    Tách thành hàm riêng thay vì thêm một cờ `include_future=True`: một tham số
    mặc-định-an-toàn vẫn là một tham số có thể truyền nhầm, và chỗ truyền nhầm
    ở đây làm rò bản điều khoản sắp đổi ra đường đọc công khai. Hai tên hàm
    khác nhau thì không nhầm được.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    if kind not in KINDS:
        raise ConsentError(f"loại văn bản không hợp lệ: {kind!r}",
                           code="unknown_kind", status_code=404)
    with system_scope("legal: quản trị đọc một bản bất kỳ"):
        rows = _fetch_all(
            f"SELECT {_columns()}, body FROM legal_documents "
            f"WHERE kind = %s AND version = %s",
            (kind, str(version)),
        )
    return dict(rows[0]) if rows else None


def consent_coverage() -> List[Dict[str, Any]]:
    """Với mỗi loại bắt buộc: bao nhiêu tài khoản đang hoạt động đã đồng ý.

    Đây là con số trả lời câu hỏi vận hành thật — "còn ai chưa ký?" — mà
    `list_documents` không trả lời được: nó đếm chấp thuận theo BẢN, còn ở đây
    mẫu số là số tài khoản.

    Chỉ đếm tài khoản `is_active`: một tài khoản đã vô hiệu hoá không dùng dịch
    vụ nên không nợ chữ ký nào, và để nó trong mẫu số làm con số không bao giờ
    về được 100% dù mọi việc đã xong.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    out: List[Dict[str, Any]] = []
    with system_scope("legal: thống kê độ phủ chấp thuận"):
        total = _fetch_all(
            "SELECT count(*) AS n FROM users WHERE is_active")[0]["n"]
        for kind in REQUIRED_AT_REGISTRATION:
            doc = current_document(kind)
            if doc is None:
                out.append({"kind": kind, "version": None, "accounts": total,
                            "accepted": 0, "accepted_by_user": 0, "missing": total})
                continue
            # Phải khớp ĐỊNH NGHĨA của `has_consent`, không được đếm lỏng hơn.
            #
            # Khi bản hiện hành bật `requires_reconsent`, một chấp thuận cho bản
            # CŨ không còn tính — `has_consent` trả False và người dùng bị đá ra
            # màn hình đồng ý. Nếu ở đây vẫn đếm nó, bảng độ phủ sẽ báo 100%
            # đúng vào lúc thực tế là 0%, tức là con số nói ngược lại điều đang
            # xảy ra ở đúng thời điểm người vận hành cần nó nhất.
            version_clause = ("AND c.version = %(version)s"
                              if doc["requires_reconsent"] else "")
            row = _fetch_all(
                f"""
                SELECT count(*)                                   AS accepted,
                       count(*) FILTER (WHERE c.source = 'user')  AS by_user
                FROM user_consents c JOIN users u ON u.id = c.user_id
                WHERE c.kind = %(kind)s AND c.withdrawn_at IS NULL
                  AND u.is_active {version_clause}
                """,
                {"kind": kind, "version": str(doc["version"])},
            )[0]
            out.append({
                "kind": kind,
                "version": doc["version"],
                "accounts": total,
                "accepted": int(row["accepted"]),
                # Tách riêng vì hai con số này KHÔNG cùng loại bằng chứng.
                "accepted_by_user": int(row["by_user"]),
                "missing": total - int(row["accepted"]),
            })
    return out


# ===========================================================================
# Bản nháp — mặt phẳng SỬA ĐƯỢC duy nhất trong toàn bộ phần pháp lý
# ===========================================================================

_DRAFT_COLUMNS = (
    "draft_id", "kind", "title", "language", "body_format", "change_summary",
    "target_version", "requires_reconsent", "effective_from", "status",
    "revision", "based_on_version", "published_version", "storage_key",
    "content_hash", "byte_size", "created_by", "updated_by", "created_at",
    "updated_at",
)

#: Trường người soạn sửa được. Cố ý KHÔNG có `status` và `revision`: đổi trạng
#: thái đi qua `advance_draft` (có bảng chuyển hợp lệ), còn `revision` do máy
#: tăng — để người gọi tự đặt là mở đường vô hiệu hoá chính khoá lạc quan.
EDITABLE_DRAFT_FIELDS = (
    "title", "language", "body", "change_summary", "target_version",
    "requires_reconsent", "effective_from",
)


def _draft_row(row: Dict[str, Any], *, with_body: bool = False) -> Dict[str, Any]:
    out = {c: row[c] for c in _DRAFT_COLUMNS if c in row}
    if with_body:
        out["body"] = row.get("body", "")
    else:
        out["body_length"] = len(row.get("body", "") or "")
    return out


def get_draft(draft_id: str, *, with_body: bool = True) -> Optional[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("legal: đọc một bản nháp"):
        rows = _fetch_all(
            f"SELECT {', '.join(_DRAFT_COLUMNS)}, body FROM legal_document_drafts "
            f"WHERE draft_id = %s", (str(draft_id),))
    return _draft_row(rows[0], with_body=with_body) if rows else None


def list_drafts(*, include_closed: bool = False) -> List[Dict[str, Any]]:
    """Bản nháp, mới sửa trước. Thân bài KHÔNG kèm — xem `get_draft`."""
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    sql = (f"SELECT {', '.join(_DRAFT_COLUMNS)}, body "
           f"FROM legal_document_drafts")
    params: tuple = ()
    if not include_closed:
        sql += " WHERE status = ANY(%s)"
        params = (list(OPEN_DRAFT_STATUSES),)
    sql += " ORDER BY updated_at DESC"

    with system_scope("legal: liệt kê bản nháp"):
        return [_draft_row(r) for r in _fetch_all(sql, params)]


def create_draft(kind: str, *, actor_id: Optional[str] = None,
                 seed_from_current: bool = True) -> Dict[str, Any]:
    """Mở một bản nháp mới cho một loại văn bản.

    `seed_from_current=True` chép nội dung bản đang hiệu lực làm điểm xuất phát.
    Đó là mặc định đúng: gần như mọi lần sửa điều khoản là sửa MỘT MỤC của bản
    cũ, và bắt người soạn dán lại 6.000 ký tự là mời họ đánh rơi một đoạn.

    409 khi đã có bản nháp mở cho loại này — xem chú thích `uq_legal_draft_open`
    trong `metadata_db.py` về vì sao chỉ cho một.
    """
    from app.storage.metadata_db import _cursor, _fetch_all
    from app.tenant_context import system_scope

    if kind not in KINDS:
        raise ConsentError(f"loại văn bản không hợp lệ: {kind!r}",
                           code="unknown_kind", status_code=400)

    current = read_document(kind) if seed_from_current else None
    draft_id = str(uuid.uuid4())

    with system_scope("legal: mở bản nháp"):
        existing = _fetch_all(
            "SELECT draft_id FROM legal_document_drafts "
            "WHERE kind = %s AND status = ANY(%s)",
            (kind, list(OPEN_DRAFT_STATUSES)))
        if existing:
            raise ConsentError(
                f"Đã có một bản nháp đang mở cho {kind}. Hoàn tất hoặc huỷ nó "
                f"trước khi mở bản mới.",
                code="draft_already_open", status_code=409,
            )
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO legal_document_drafts
                    (draft_id, kind, title, language, body, change_summary,
                     based_on_version, created_by, updated_by)
                VALUES (%s, %s, %s, %s, %s, '', %s, %s, %s)
                """,
                (draft_id, kind,
                 (current or {}).get("title", ""),
                 (current or {}).get("language", "vi"),
                 (current or {}).get("body", ""),
                 (current or {}).get("version"),
                 actor_id if _is_uuid(actor_id) else None,
                 actor_id if _is_uuid(actor_id) else None),
            )

    record_event("draft.create", actor_id=actor_id, kind=kind, draft_id=draft_id,
                 revision=1,
                 detail={"based_on_version": (current or {}).get("version"),
                         "seeded": bool(current)})
    return get_draft(draft_id) or {}


def update_draft(draft_id: str, revision: int, changes: Dict[str, Any], *,
                 actor_id: Optional[str] = None) -> Dict[str, Any]:
    """Sửa một bản nháp. Chỉ thành công khi `revision` khớp bản hiện tại.

    Đây là toàn bộ cơ chế chống hai người ghi đè nhau. `UPDATE ... WHERE
    revision = %s` trả về 0 hàng khi có người ghi trước; không có phép kiểm này
    thì người lưu sau âm thầm đè mất bài của người lưu trước, và đó là kiểu mất
    dữ liệu không để lại dấu vết nào — chỉ phát hiện được bằng cách đọc lại
    toàn văn và nhớ mình đã viết gì.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    unknown = set(changes) - set(EDITABLE_DRAFT_FIELDS)
    if unknown:
        raise ConsentError(f"trường không sửa được: {', '.join(sorted(unknown))}",
                           code="field_not_editable", status_code=400)
    if not changes:
        raise ConsentError("không có gì để sửa", code="empty_update",
                           status_code=400)

    assignments = ", ".join(f"{f} = %({f})s" for f in changes)
    params = dict(changes)
    params.update({"draft_id": str(draft_id), "revision": int(revision),
                   "actor": actor_id if _is_uuid(actor_id) else None})

    with system_scope("legal: sửa bản nháp"):
        with _cursor() as cur:
            cur.execute(
                f"""
                UPDATE legal_document_drafts
                   SET {assignments},
                       revision = revision + 1,
                       updated_at = now(),
                       updated_by = %(actor)s
                 WHERE draft_id = %(draft_id)s
                   AND revision = %(revision)s
                   AND status = ANY(%(open)s)
                """,
                {**params, "open": list(OPEN_DRAFT_STATUSES)},
            )
            changed = cur.rowcount

    if not changed:
        current = get_draft(draft_id, with_body=False)
        if current is None:
            raise ConsentError("bản nháp không tồn tại", code="draft_not_found",
                               status_code=404)
        if current["status"] not in OPEN_DRAFT_STATUSES:
            raise ConsentError(
                f"bản nháp đã {current['status']}, không sửa được nữa",
                code="draft_closed", status_code=409)
        raise DraftConflict(
            f"Có người vừa lưu bản nháp này (bản {current['revision']}, bạn đang "
            f"giữ bản {revision}). Tải lại để không ghi đè bài của họ.",
            current_revision=current["revision"],
        )

    updated = get_draft(draft_id) or {}
    # Chỉ ghi TÊN trường đã đổi, không ghi giá trị: giá trị của `body` chính là
    # bản văn, và sổ đăng bạ không mang nội dung.
    record_event("draft.update", actor_id=actor_id, kind=updated.get("kind"),
                 draft_id=str(draft_id), revision=updated.get("revision"),
                 detail={"fields": sorted(changes)})
    return updated


def advance_draft(draft_id: str, revision: int, status: str, *,
                  actor_id: Optional[str] = None) -> Dict[str, Any]:
    """Đổi trạng thái bản nháp theo bảng `DRAFT_TRANSITIONS`.

    `published` KHÔNG đi qua đây — nó là hệ quả của `publish_draft`, và cho phép
    đặt tay sẽ tạo ra một bản nháp tự nhận là đã công bố mà không có văn bản nào
    ứng với nó.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    if status == "published":
        raise ConsentError(
            "không đặt tay trạng thái 'published'; dùng `publish_draft`.",
            code="status_not_settable", status_code=400)
    if status not in DRAFT_STATUSES:
        raise ConsentError(f"trạng thái không hợp lệ: {status!r}",
                           code="unknown_status", status_code=400)

    current = get_draft(draft_id, with_body=False)
    if current is None:
        raise ConsentError("bản nháp không tồn tại", code="draft_not_found",
                           status_code=404)
    if status not in DRAFT_TRANSITIONS[current["status"]]:
        raise ConsentError(
            f"không chuyển được từ {current['status']!r} sang {status!r}",
            code="invalid_transition", status_code=409)

    # Ảnh chụp vào kho tệp ở bước PHÊ DUYỆT, không phải ở mỗi lần bấm Lưu.
    #
    # Bản nháp đang soạn sống trong cột `body`: giao dịch, có khoá lạc quan, sửa
    # rẻ. Ghi một tệp cho mỗi lần bấm Lưu sẽ rải hàng trăm blob cho một văn bản,
    # và không blob nào trong số đó là thứ ai muốn xem lại.
    #
    # Bản ĐÃ PHÊ DUYỆT thì khác: đó là hiện vật người duyệt đã đọc, và nó phải
    # có một địa chỉ cố định trước khi ai đó bấm Công bố. Vì tên tệp là băm nội
    # dung, nếu bản duyệt trùng bản đã công bố thì lượt ghi này không tốn byte
    # nào.
    storage_key = content_digest_value = None
    byte_size = 0
    if status == "approved":
        from app import legal_store

        full = get_draft(draft_id) or {}
        if (full.get("body") or "").strip():
            storage_key, content_digest_value, byte_size = legal_store.write(
                full["kind"], full["body"])

    with system_scope("legal: đổi trạng thái bản nháp"):
        with _cursor() as cur:
            cur.execute(
                "UPDATE legal_document_drafts "
                "   SET status = %s, revision = revision + 1, updated_at = now(), "
                "       updated_by = %s, "
                "       storage_key = COALESCE(%s, storage_key), "
                "       content_hash = COALESCE(%s, content_hash), "
                "       byte_size = CASE WHEN %s > 0 THEN %s ELSE byte_size END "
                " WHERE draft_id = %s AND revision = %s",
                (status, actor_id if _is_uuid(actor_id) else None,
                 storage_key, content_digest_value, byte_size, byte_size,
                 str(draft_id), int(revision)),
            )
            changed = cur.rowcount

    if not changed:
        fresh = get_draft(draft_id, with_body=False) or {}
        raise DraftConflict(
            f"Bản nháp đã đổi (bản {fresh.get('revision')}). Tải lại rồi thử lại.",
            current_revision=fresh.get("revision"),
        )

    updated = get_draft(draft_id, with_body=False) or {}
    record_event(f"draft.{status}", actor_id=actor_id, kind=updated.get("kind"),
                 draft_id=str(draft_id), revision=updated.get("revision"),
                 storage_key=storage_key, content_hash_value=content_digest_value,
                 detail={"from": current["status"], "to": status})
    return updated


def publish_draft(draft_id: str, revision: int, *,
                  actor_id: Optional[str] = None) -> Dict[str, Any]:
    """Công bố một bản nháp đã phê duyệt, rồi đóng nó lại.

    Mang theo `revision` và khớp nó khi đóng bản nháp: nếu ai đó sửa nội dung
    giữa lúc người này bấm Công bố và lúc câu ghi chạy, thì bản văn được công bố
    KHÔNG phải bản họ vừa đọc. Bắt buộc phải hỏng ở đó thay vì công bố nhầm.
    """
    draft = get_draft(draft_id)
    if draft is None:
        raise ConsentError("bản nháp không tồn tại", code="draft_not_found",
                           status_code=404)
    if int(draft["revision"]) != int(revision):
        raise DraftConflict(
            f"Bản nháp đã đổi kể từ lúc bạn mở (bản {draft['revision']}). Đọc "
            f"lại trước khi công bố — nội dung sắp công bố không phải nội dung "
            f"bạn vừa xem.",
            current_revision=draft["revision"],
        )
    if draft["status"] != "approved":
        raise ConsentError(
            f"chỉ công bố được bản nháp đã phê duyệt; bản này đang "
            f"{draft['status']!r}",
            code="draft_not_approved", status_code=409)
    if not str(draft.get("target_version") or "").strip():
        raise ConsentError("bản nháp chưa có số hiệu phiên bản",
                           code="missing_version", status_code=400)

    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    result = register_document(
        draft["kind"], draft["target_version"],
        url=f"/legal/{draft['kind']}",
        body=draft["body"],
        title=draft["title"],
        body_format=draft["body_format"],
        language=draft["language"],
        change_summary=draft["change_summary"],
        requires_reconsent=bool(draft["requires_reconsent"]),
        effective_from=draft["effective_from"],
        published_by=actor_id,
    )

    # Đóng bản nháp SAU khi công bố xong. Thứ tự này để lại một khả năng: công
    # bố thành công rồi câu dưới hỏng, và bản nháp còn "approved" trong khi văn
    # bản đã ra. Đó là hướng hỏng ĐÚNG — thử lại sẽ đi vào nhánh idempotent của
    # `register_document` và lần này đóng được nháp. Thứ tự ngược lại sẽ đóng
    # nháp rồi không công bố được, và nội dung mắc kẹt ở một bản nháp đã khoá.
    with system_scope("legal: đóng bản nháp đã công bố"):
        with _cursor() as cur:
            cur.execute(
                "UPDATE legal_document_drafts "
                "   SET status = 'published', published_version = %s, "
                "       revision = revision + 1, updated_at = now(), "
                "       updated_by = %s "
                " WHERE draft_id = %s AND revision = %s",
                (draft["target_version"], actor_id if _is_uuid(actor_id) else None,
                 str(draft_id), int(revision)),
            )

    record_event("draft.published", actor_id=actor_id, kind=draft["kind"],
                 version=draft["target_version"], draft_id=str(draft_id),
                 detail={"scheduled": bool(draft["effective_from"])})
    return {"draft": get_draft(draft_id, with_body=False), "current": result}


def referenced_storage_keys() -> List[str]:
    """Mọi khoá kho đang được một hàng nào đó trỏ tới — đầu vào của dọn rác.

    **Cả ba** bảng, và bảng thứ ba là bảng dễ quên nhất.
    `legal_document_events` là sổ chỉ-thêm ghi lại mọi lượt soạn và công bố; mỗi
    dòng giữ `storage_key` của bản văn tại thời điểm đó. Bỏ nó ra khỏi phép hợp
    này thì một bản nháp bị xoá sau khi công bố sẽ mất tham chiếu từ
    `legal_document_drafts`, dọn rác xoá blob sau 24 giờ, và sổ sự kiện còn lại
    một dòng trỏ vào tệp không tồn tại. Một sổ đăng bạ không đọc lại được thì
    không trả lời được câu hỏi duy nhất nó tồn tại để trả lời.

    `scripts/pg_backup.sh` đối chiếu đúng phép hợp ba bảng này trước khi đóng
    gói kho tệp. Hai bên PHẢI khớp: nếu dọn rác xoá thứ mà bản sao lưu coi là
    bắt buộc, mọi lượt sao lưu sau đó sẽ bị đánh dấu `.CORRUPT` và hệ thống mất
    sao lưu mà không ai hiểu vì sao.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("legal: liệt kê khoá kho đang dùng"):
        rows = _fetch_all(
            "SELECT storage_key FROM legal_documents WHERE storage_key IS NOT NULL "
            "UNION "
            "SELECT storage_key FROM legal_document_drafts WHERE storage_key IS NOT NULL "
            "UNION "
            "SELECT storage_key FROM legal_document_events WHERE storage_key IS NOT NULL")
    return [r["storage_key"] for r in rows]


def consent_history(user_id: str) -> List[Dict[str, Any]]:
    """Toàn bộ lịch sử chấp thuận của một tài khoản, kể cả bản đã rút.

    Sống ở đây chứ không ở router, và đó không phải chuyện sắp xếp tệp cho gọn:
    câu này cần `system_scope`, và `test_no_router_crosses_the_boundary_except_
    the_documented_one` khẳng định **không router nào** vượt ranh giới tenant.
    Phép khẳng định ấy đúng — một request handler tự cho mình quyền đọc xuyên
    tenant là cách ranh giới bị mở lại — nên chỗ đúng cho câu truy vấn là module
    dữ liệu, nơi lý do vượt ranh giới đã được ghi và được duyệt.

    `ip_hash` KHÔNG có trong danh sách cột. Nó là bằng chứng để đối chiếu, không
    phải thông tin để hiển thị: một chuỗi băm trên màn hình quản trị không nói
    với người xem điều gì, mà lại là một mẩu dữ liệu cá nhân nữa đi ra ngoài.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("legal: lịch sử chấp thuận của một tài khoản"):
        rows = _fetch_all(
            """
            SELECT kind, version, accepted_at, withdrawn_at, source, note,
                   recorded_by, user_agent
            FROM user_consents WHERE user_id = %s
            ORDER BY accepted_at DESC
            """,
            (user_id,),
        )
    return [dict(r) for r in rows]


def missing_for_registration() -> List[str]:
    """Loại văn bản bắt buộc mà hệ thống CHƯA đăng ký bản nào.

    Dùng ở boot và ở `/health`: nếu chưa có `terms` thì không ai đăng ký được,
    và triệu chứng ("đăng ký báo lỗi 503") không tự nói ra nguyên nhân.
    """
    return [kind for kind in REQUIRED_AT_REGISTRATION if current_document(kind) is None]


def withdraw_consent(user_id: str, kind: str) -> bool:
    """Rút chấp thuận CÒN HIỆU LỰC của một người cho một loại văn bản.

    Trả về True nếu có dòng bị rút, False nếu vốn chưa ký gì.

    Không xoá dòng cũ — đánh dấu `withdrawn_at`. Lịch sử chấp thuận là bằng
    chứng: xoá nó đi thì câu hỏi "ngày đó người này có đồng ý không" mất luôn
    câu trả lời, kể cả khi câu trả lời là "có, rồi sau đó rút".

    Kéo theo `signer_consents`: rút ở đây phải tới được đường dữ liệu, nếu không
    thì lại đúng cái lỗ hổng mà `app/consent_gate.py` sinh ra để bịt — đánh dấu
    đã rút rồi không có gì xảy ra tiếp.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    if kind not in KINDS:
        raise ConsentError(f"loại văn bản không hợp lệ: {kind!r}",
                           code="unknown_kind", status_code=400)

    with system_scope("legal: rút chấp thuận"):
        with _cursor() as cur:
            cur.execute(
                "UPDATE user_consents SET withdrawn_at = now() "
                "WHERE user_id = %s AND kind = %s AND withdrawn_at IS NULL",
                (user_id, kind),
            )
            changed = cur.rowcount or 0

    from app.consent_gate import sync_signer_consent

    sync_signer_consent(user_id, kind, withdrawn=True)
    return changed > 0

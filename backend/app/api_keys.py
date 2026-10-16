"""Khoá API: cách một hệ thống khác gọi được nền tảng mà không cần trình duyệt.

Cho tới v4, đường vào duy nhất là cookie phiên do biểu mẫu đăng nhập cấp. Nghĩa
là khách hàng không viết được script nào: không đồng bộ dữ liệu tự động, không
tích hợp vào hệ thống sẵn có của trường, không CI. Với một nền tảng bán cho tổ
chức thì đó là thiếu sót về năng lực, không phải về tiện nghi.

Hình dạng khoá
--------------
    voya_<8 hex>_<43 ký tự ngẫu nhiên>
    └────┬────┘
      prefix — lưu NGUYÊN VĂN, có chỉ mục duy nhất

Prefix phục vụ hai việc cùng lúc. Nó là thứ hiện trên giao diện (`voya_3f9a2b1c…`)
để người dùng nhận ra khoá nào đang nói tới mà không cần thấy lại bí mật. Và nó
là đường tra cứu O(1) lúc xác thực: không có nó, mỗi lượt gọi phải so băm với
mọi khoá của mọi tenant — một phép quét toàn bảng ở đường nóng nhất.

Vì sao SHA-256 trần, không thêm pepper
---------------------------------------
`audit.hash_ip` phải dùng HMAC kèm pepper vì miền đầu vào của nó nhỏ: bốn tỉ
địa chỉ IPv4 là thứ duyệt hết được, nên một bảng băm trần sẽ bị dò ngược.

Ở đây đầu vào là 43 ký tự sinh bằng `secrets` — hơn 256 bit entropy. Không có
bảng nào dựng được, không có phép duyệt nào chạy xong. Thêm pepper vào chỉ đổi
lấy một rủi ro mới: đổi hoặc mất pepper là **mọi khoá của mọi khách hàng chết
cùng lúc**, và không có cách khôi phục nào ngoài cấp lại tất cả.

Băm được so bằng `hmac.compare_digest`. Với một băm thì so sánh lệch thời gian
gần như không khai thác được, nhưng cái giá của việc làm đúng ở đây bằng không.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

#: Quyền một khoá mang theo. Cố ý thô: chỉ đọc, hoặc đọc và ghi.
#:
#: Phân quyền mịn (từng endpoint) nghe hay hơn nhưng sẽ là một hệ phân quyền
#: thứ hai chạy song song với vai trò thành viên, và hai hệ phân quyền cho cùng
#: một tài nguyên là cách chắc chắn để chúng nói khác nhau. Khoá không bao giờ
#: vượt được quyền của tenant nó thuộc về; đó mới là ranh giới thật.
SCOPES = ("read", "write")

_KEY_PREFIX = "voya"


class ApiKeyError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def _hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _mint() -> tuple[str, str]:
    """Sinh (khoá đầy đủ, prefix). Khoá đầy đủ không bao giờ được lưu."""
    prefix = f"{_KEY_PREFIX}_{secrets.token_hex(4)}"
    return f"{prefix}_{secrets.token_urlsafe(32)}", prefix


def create_key(
    tenant_id: str,
    *,
    name: str = "",
    scopes: str = "read",
    created_by: Optional[str] = None,
    expires_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Tạo khoá mới. Đây là lần DUY NHẤT khoá thật được trả về.

    Không endpoint nào đọc lại được nó về sau, vì không có gì để đọc — chỉ băm
    được lưu. Mất khoá thì thu hồi và cấp cái mới; đó là chi phí của việc không
    giữ một bản có thể bị lấy trộm.
    """
    from app.plans import QuotaExceeded, enforce
    from app.storage.metadata_db import _execute
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    scope = (scopes or "read").strip().lower()
    if scope not in SCOPES:
        raise ApiKeyError(f"scopes phải là một trong {', '.join(SCOPES)}", status_code=422)

    try:
        enforce(tenant, "api_keys", adding=1)
    except QuotaExceeded as exc:
        raise ApiKeyError(str(exc), status_code=exc.status_code) from exc

    last: Optional[Exception] = None
    for _ in range(5):
        raw, prefix = _mint()
        key_id = str(uuid.uuid4())
        try:
            with system_scope("api keys: create a key for a tenant"):
                _execute(
                    "INSERT INTO api_keys(key_id, tenant_id, name, prefix, key_hash, "
                    "scopes, created_by, expires_at) "
                    "VALUES(%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        key_id, tenant, (name or "").strip()[:120], prefix, _hash(raw),
                        scope, str(created_by) if created_by else None, expires_at,
                    ),
                )
            logger.info("[APIKEY] %s tạo khoá %s cho %s", created_by, prefix, tenant)
            # `key` chỉ có ở giá trị trả về này và không đi đâu khác. Nó KHÔNG
            # được đưa vào audit log — `audit._SENSITIVE_KEYS` đã chặn "api_key",
            # nhưng ở đây thì đơn giản là không ghi.
            return {
                "key_id": key_id, "tenant_id": tenant, "name": name,
                "prefix": prefix, "scopes": scope, "expires_at": expires_at,
                "key": raw,
            }
        except Exception as exc:
            # Đụng chỉ mục duy nhất trên prefix — 1 phần 4 tỉ, nhưng thử lại
            # rẻ hơn nhiều so với trả lỗi cho người dùng vì một lần xúc xắc xấu.
            last = exc
            continue
    raise ApiKeyError("không sinh được khoá duy nhất, vui lòng thử lại", status_code=503) from last


def list_keys(tenant_id: str, *, include_revoked: bool = False) -> List[Dict[str, Any]]:
    from app.storage.metadata_db import _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    where = "WHERE tenant_id = %s" + ("" if include_revoked else " AND revoked_at IS NULL")
    with system_scope("api keys: list the keys of a tenant"):
        rows = _fetch_all(
            f"SELECT key_id, tenant_id, name, prefix, scopes, created_by, created_at, "
            f"last_used_at, expires_at, revoked_at FROM api_keys {where} "
            f"ORDER BY created_at DESC",
            (tenant,),
        )
    return [dict(r) for r in rows]


def revoke_key(tenant_id: str, key_id: str, *, revoked_by: Optional[str] = None) -> None:
    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenancy import normalize_tenant_id
    from app.tenant_context import system_scope

    tenant = normalize_tenant_id(tenant_id)
    with system_scope("api keys: revoke a key"):
        # Phạm vi theo CẢ tenant lẫn id: một quản trị viên của tổ chức này
        # không được thu hồi khoá của tổ chức khác bằng cách đoán một UUID.
        rows = _fetch_all(
            "SELECT key_id FROM api_keys WHERE key_id = %s AND tenant_id = %s",
            (str(key_id), tenant),
        )
        if not rows:
            raise ApiKeyError("không tìm thấy khoá", status_code=404)
        _execute(
            "UPDATE api_keys SET revoked_at = NOW(), revoked_by = %s "
            "WHERE key_id = %s AND revoked_at IS NULL",
            (str(revoked_by) if revoked_by else None, str(key_id)),
        )
    logger.info("[APIKEY] thu hồi %s", key_id)


def authenticate(raw_key: str) -> Optional[Dict[str, Any]]:
    """Đổi một khoá thô lấy bản ghi của nó, hoặc None.

    Trả None cho MỌI lý do thất bại — sai định dạng, không tồn tại, đã thu hồi,
    đã hết hạn, tenant bị treo. Phân biệt chúng ra ngoài là nói cho người gọi
    biết prefix nào có thật, tức là biến endpoint này thành máy dò khoá.
    """
    text = (raw_key or "").strip()
    if not text.startswith(f"{_KEY_PREFIX}_"):
        return None
    # `split("_", 2)` — tách TỐI ĐA hai lần, không tách hết.
    #
    # `secrets.token_urlsafe` dùng bảng chữ base64url, trong đó CÓ dấu gạch
    # dưới. Một `split("_")` không giới hạn sẽ cắt phần bí mật thành nhiều
    # mảnh bất cứ khi nào nó chứa `_` — khoảng một phần ba số khoá — và những
    # khoá đó không bao giờ xác thực được. Lỗi này không lộ ra bằng ngoại lệ:
    # nó trả về None, tức là "khoá không hợp lệ", nên trông y hệt một khoá sai.
    parts = text.split("_", 2)
    if len(parts) != 3 or not parts[1] or not parts[2]:
        return None
    prefix = f"{parts[0]}_{parts[1]}"

    from app.storage.metadata_db import _execute, _fetch_all
    from app.tenant_context import system_scope

    with system_scope("api keys: authenticate a caller by key"):
        rows = _fetch_all(
            "SELECT k.*, t.billing_status, t.is_active, t.deleted_at "
            "FROM api_keys k JOIN tenants t ON t.tenant_id = k.tenant_id "
            "WHERE k.prefix = %s",
            (prefix,),
        )
    if not rows:
        return None
    row = dict(rows[0])

    if not hmac.compare_digest(row.get("key_hash") or "", _hash(text)):
        return None
    if row.get("revoked_at") is not None:
        return None
    expires = row.get("expires_at")
    if expires is not None and expires <= datetime.now(timezone.utc):
        return None
    if row.get("deleted_at") is not None or not row.get("is_active", True):
        return None

    from app.plans import WRITABLE_BILLING_STATUSES

    # Tenant bị treo vẫn ĐỌC được bằng khoá — cùng ranh giới với người dùng
    # trên giao diện. Chỉ đường ghi đóng lại, và việc đó do `plans.enforce` ở
    # từng endpoint lo, không phải ở đây.
    if row.get("billing_status") not in (*WRITABLE_BILLING_STATUSES, "suspended"):
        return None

    # Ghi thời điểm dùng cuối, nhưng đừng để nó chặn lượt gọi: cột này phục vụ
    # việc dọn khoá chết, và một lỗi ghi không đáng làm hỏng một yêu cầu hợp lệ.
    try:
        with system_scope("api keys: stamp last_used_at"):
            _execute(
                "UPDATE api_keys SET last_used_at = NOW() WHERE key_id = %s",
                (str(row["key_id"]),),
            )
    except Exception as exc:
        logger.debug("[APIKEY] không ghi được last_used_at: %s", type(exc).__name__)

    return {
        "key_id": str(row["key_id"]),
        "tenant_id": row["tenant_id"],
        "scopes": row.get("scopes") or "read",
        "name": row.get("name") or "",
        "prefix": row.get("prefix"),
    }

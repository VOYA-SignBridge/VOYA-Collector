"""Nhật ký kiểm toán bền, trong Postgres.

Vì sao cần, nói cho cụ thể
--------------------------
`app/activity.py` đã ghi hoạt động — vào REDIS. Redis ở triển khai này chạy
`maxmemory 400mb` với chính sách `volatile-lru`, nghĩa là khi bộ nhớ chật, các
khoá bị ĐUỔI. Với một hàng đợi hoạt động thì mất vài dòng cũ là chấp nhận
được. Với câu hỏi "ai đã nâng quyền sudo lúc 2 giờ sáng" thì không: dấu vết
kiểm toán mà hệ thống được phép tự xoá khi cần chỗ thì không phải dấu vết.

Cụ thể hơn nữa: sudo mode và việc admin đổi hạn mức trải nghiệm lúc chạy —
hai cơ chế vừa thêm — là hai hành động nhạy cảm nhất trong hệ thống, và trước
module này chúng KHÔNG để lại gì tồn tại qua một lần restart.

Cái gì KHÔNG bao giờ được vào đây
---------------------------------
`detail` là JSONB tự do, nên nó là chỗ hoàn hảo để vô tình làm rò bí mật. Quy
tắc, do người dùng đặt ra và không có ngoại lệ: **không log mã quan trọng**.
Không mật khẩu, không mã OTP, không token, không khoá riêng, không header
Authorization. Ràng buộc này không diễn đạt được bằng SQL, nên nó được ép ở
đây: `_SENSITIVE_KEYS` bị thay bằng "[da xoa]" trước khi ghi, và mọi lối vào
bảng `audit_log` phải đi qua `record()`.

Danh sách chặn là lưới an toàn, không phải giấy phép. Chỗ đúng để không rò bí
mật vẫn là không truyền nó vào.

Mặt phẳng dữ liệu ghi cái gì, và cố ý KHÔNG ghi cái gì
-------------------------------------------------------
Bản đầu của module này chỉ phục vụ mặt phẳng quản trị (sudo, hạn mức, thanh
toán, khoá API). Mặt phẳng dữ liệu không ghi gì cả — nên lần purge lớp
`lop-thu-70eb62` ngày 2026-08-08, một thao tác xoá không hồi được trên dữ liệu
sản xuất, không để lại dòng nào để tra lại ai đã làm.

Ranh giới hiện tại, và nó là một lựa chọn chứ không phải chỗ làm dở:

* **Có ghi** — mọi thao tác KHÔNG HỒI ĐƯỢC và mọi thao tác ở cấp LỚP:
  `data.class.purge`, `data.class.purge.bulk`, `data.class.soft_delete`,
  `data.sample.purge`, `data.sample.purge.bulk`.
* **Không ghi** — xoá mềm MỘT mẫu (`data.sample.soft_delete`). Nó hồi được từ
  Thùng rác, và nó xảy ra hàng trăm lần mỗi buổi thu. Ghi nó vào đây đổi một
  bảng bằng chứng thưa và đọc được lấy một bảng nhật ký dày mà không ai đọc —
  và bằng chứng bị chôn giữa tiếng ồn thì cũng như không có. Đường dấu vết cho
  thao tác đó là `operation_logs` và Thùng rác.

Nếu sau này cần ghi cả xoá mềm, hãy tách bảng chứ đừng đổ chung.

Ghi hỏng thì sao
----------------
`record()` NUỐT lỗi và ghi log ở mức ERROR kèm dấu hiệu riêng, chứ không ném
lên. Đây là một đánh đổi có thật, không phải sơ suất:

  - Ném lên: một trục trặc Postgres biến mọi hành động quản trị thành lỗi 500.
    Kiểm toán trở thành điểm chết của cả hệ thống.
  - Nuốt: kẻ tấn công nào phá được bảng này thì hành động của họ không được
    ghi.

Chọn nuốt, vì cái giá của lựa chọn kia rơi vào người dùng thật mỗi ngày còn
cái giá của lựa chọn này rơi vào một tình huống mà kẻ tấn công đã có quyền
ghi cơ sở dữ liệu — lúc đó họ cũng xoá được bảng kiểm toán. Bù lại, dòng
ERROR mang tiền tố `[AUDIT-FAIL]` để giám sát bắt được, và `count_since()`
cho phép cảnh báo khi số dòng ngừng tăng.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any, Mapping, Optional

logger = logging.getLogger(__name__)

#: Khoá bị che trước khi ghi. So khớp KHÔNG phân biệt hoa thường và theo
#: chuỗi con, nên "user_password" và "X-Auth-Token" đều dính.
_SENSITIVE_KEYS = (
    "password", "passwd", "secret", "token", "authorization", "cookie",
    "otp", "code_hash", "api_key", "apikey", "private_key", "passcode",
    "credential", "session_key", "csrf",
)

_REDACTED = "[da xoa]"

#: Giới hạn kích thước `detail`. Một dòng kiểm toán là bằng chứng, không phải
#: chỗ đổ payload; 8 KB đủ cho mọi hành động thật và chặn việc một request
#: khổng lồ làm phình bảng.
_MAX_DETAIL_BYTES = 8192


def _redact(value: Any, _depth: int = 0) -> Any:
    """Che giá trị của mọi khoá trông giống bí mật, đệ quy.

    Giới hạn độ sâu 6: cấu trúc lồng sâu hơn thế gần như chắc chắn là một
    payload lọt vào chứ không phải mô tả hành động, và đệ quy không giới hạn
    trên dữ liệu do người gọi cung cấp là một cách tự làm mình treo.
    """
    if _depth > 6:
        return _REDACTED
    if isinstance(value, Mapping):
        out = {}
        for key, val in value.items():
            name = str(key)
            if any(s in name.lower() for s in _SENSITIVE_KEYS):
                out[name] = _REDACTED
            else:
                out[name] = _redact(val, _depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact(v, _depth + 1) for v in value]
    return value


def _clip(value: Any, limit: int) -> Optional[str]:
    """Cắt về đúng độ dài cột, và coi chuỗi rỗng là None.

    Thay cho `(x or None) and str(x)[:n]` viết ở bản đầu. Biểu thức đó chạy
    đúng nhưng phải dừng lại đọc ba lần mới biết nó làm gì, và `and` trả về
    giá trị chứ không phải bool là loại mẹo khiến người đọc sau tưởng có lỗi.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


def hash_ip(request: Any) -> Optional[str]:
    """Băm địa chỉ IP thay vì lưu nó, băm SAO CHO CÒN ĐỐI CHIẾU ĐƯỢC.

    Hai quyết định ở đây, và bản đầu tiên sai cả hai.

    **Không muối theo người thực hiện.** Bản đầu nhận `salt=actor_id`, sao chép
    từ `routers/auth.py` mà không xét xem hai chỗ hỏi câu khác nhau. Ở đó, bằng
    chứng đồng ý là của TỪNG người và việc không đối chiếu được giữa các tài
    khoản là tính năng. Ở đây thì ngược hẳn: câu hỏi đắt giá nhất mà một nhật ký
    kiểm toán phải trả lời là *"có phải cùng một nơi vừa thử ba tài khoản quản
    trị không"* — và muối theo người thực hiện khiến cùng một IP cho ra ba bản
    băm khác nhau, tức là đúng câu hỏi đó thành không trả lời được. Bản băm phải
    ổn định theo IP.

    **HMAC với pepper ngoài cơ sở dữ liệu, không phải SHA-256 trần.** Không gian
    IPv4 chỉ có 4 tỉ giá trị; một bản băm trần là duyệt cạn trong vài giây, nên
    nó KHÔNG che gì cả — chỉ tạo cảm giác đã che. Cùng lập luận đã viết cho mã
    OTP sáu chữ số trong `app/tokens.py`, và dùng lại đúng pepper đó, có tách
    miền bằng tiền tố nên một bản băm IP không bao giờ trùng nghĩa với một
    bản băm mã.

    Không có pepper thì trả None. Ghi một bản băm đảo ngược được còn tệ hơn
    không ghi gì: nó tạo ra ảo giác đã ẩn danh trong khi thực tế là đang lưu
    địa chỉ IP.
    """
    if request is None:
        return None
    try:
        from app.config import settings
        from app.rate_limit import client_ip

        pepper = (getattr(settings, "otp_pepper", "") or "").strip()
        if not pepper:
            return None
        message = f"audit-ip\x00{client_ip(request)}".encode("utf-8")
        return hmac.new(pepper.encode("utf-8"), message, hashlib.sha256).hexdigest()
    except Exception:
        return None


def _is_uuid(value: Any) -> bool:
    import uuid as _uuid

    try:
        _uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False


def record(
    action: str,
    *,
    actor: Optional[Mapping[str, Any]] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[Mapping[str, Any]] = None,
    request: Any = None,
    tenant_id: Optional[str] = None,
) -> bool:
    """Ghi một dòng kiểm toán. Trả về True nếu đã ghi được.

    `actor` là dict người dùng hiện tại như các router vẫn truyền quanh
    (`{"id": ..., "username": ..., "email": ...}`). Cả `actor_user_id` lẫn
    `actor_label` đều được lưu, và đó là chủ ý: khoá ngoại là `ON DELETE SET
    NULL`, nên khi tài khoản bị xoá cứng thì `actor_label` là thứ duy nhất còn
    lại nói ai đã làm. Một dòng kiểm toán mất danh tính người thực hiện thì
    gần như vô dụng.

    `tenant_id` để None nghĩa là "lấy theo phạm vi hiện tại".

    Cần MỘT phạm vi, và đây là chỗ dễ hiểu nhầm. Trong **system scope**, dòng
    được ghi ở tầng nền tảng (`tenant_id` NULL) và chỉ đọc lại được trong
    system scope. Trong **tenant scope**, dòng mang tenant đó. Nhưng NGOÀI mọi
    phạm vi thì vị từ RLS cho ra NULL chứ không phải TRUE, WITH CHECK từ chối,
    và vì hàm này nuốt lỗi nên dấu vết biến mất lặng lẽ — chỉ còn một dòng
    `[AUDIT-FAIL]`. Bản trước của docstring này hứa ngược lại, và lời hứa đó
    sai; xem `test_audit_fails_closed_when_there_is_no_scope_at_all`.

    Sản xuất không rơi vào đó: middleware HTTP, `task_prerun` của Celery, và
    `platform_command` của CLI đều đặt phạm vi. Một lối vào thứ tư thì phải tự
    đặt lấy.
    """
    if not action:
        return False

    try:
        from app.storage import metadata_db as db
        from app.tenant_context import current_tenant

        scope = tenant_id if tenant_id is not None else current_tenant()

        payload = None
        if detail:
            cleaned = _redact(dict(detail))
            text = json.dumps(cleaned, ensure_ascii=False, default=str)
            if len(text.encode("utf-8")) > _MAX_DETAIL_BYTES:
                cleaned = {"_truncated": True, "_bytes": len(text.encode("utf-8"))}
            payload = cleaned

        actor_id = None
        actor_label = None
        if actor:
            actor_id = actor.get("id") or actor.get("user_id")
            actor_label = _clip(
                actor.get("username") or actor.get("email") or actor.get("name"), 200)
            # `actor_user_id` là UUID có khoá ngoại tới `users`. Một người gọi
            # bằng KHOÁ API mang id dạng "apikey:<uuid>", vốn không phải UUID
            # và không có dòng nào trong `users` — chèn thẳng vào sẽ ném lỗi
            # kiểu, và vì hàm này nuốt mọi lỗi, hệ quả là MỌI hành động thực
            # hiện qua khoá API biến mất khỏi nhật ký kiểm toán mà không ai
            # thấy gì.
            #
            # Bỏ trống cột khoá ngoại và giữ `actor_label` là câu trả lời đúng:
            # dòng vẫn được ghi, và nhãn ("apikey:voya_3f9a2b1c") vẫn nói được
            # ai đã làm — đúng vai trò mà docstring đã dành cho `actor_label`
            # trong trường hợp tài khoản bị xoá.
            if actor_id is not None and not _is_uuid(actor_id):
                actor_id = None

        db.insert_audit_log(
            tenant_id=scope,
            actor_user_id=str(actor_id) if actor_id else None,
            actor_label=actor_label,
            action=_clip(action, 200),
            target_type=_clip(target_type, 100),
            target_id=_clip(target_id, 200),
            detail=payload,
            ip_hash=hash_ip(request),
        )
        return True
    except Exception as exc:
        # Xem docstring module: cố ý không ném lên. Tiền tố để giám sát bắt.
        logger.error("[AUDIT-FAIL] khong ghi duoc dong kiem toan '%s': %s",
                     action, exc.__class__.__name__)
        _count_failure()
        return False


def _count_failure() -> None:
    """Đếm một lượt ghi kiểm toán hỏng vào Prometheus.

    Cho tới giờ `[AUDIT-FAIL]` chỉ tồn tại trong nhật ký ứng dụng, tức là chỉ
    tìm ra khi có người đi tìm. Một bộ đếm thì báo động được: giá trị chỉ tăng,
    nên `increase(...[1h]) > 0` là một quy tắc cảnh báo không thể bỏ sót lần
    hỏng nào, kể cả lần hỏng duy nhất lúc ba giờ sáng.

    Nhập bên trong hàm và nuốt lỗi: nếu hệ đo lường chưa nạp được thì đường ghi
    kiểm toán vẫn phải chạy tiếp. Hàm này nằm trên đường xử-lý-lỗi rồi, và một
    ngoại lệ ở đây sẽ nuốt mất chính lời phàn nàn nó đang đếm.
    """
    try:
        from app.metrics import audit_write_failures_total

        audit_write_failures_total.inc()
    except Exception:  # pragma: no cover - hệ đo lường không phải đường tới hạn
        pass


# --------------------------------------------------------------------------- giám sát
#
# Hai câu hỏi khác nhau, và chỉ hỏi một câu là không đủ:
#
#   * "Có lần ghi nào HỎNG không?" → bộ đếm `_count_failure` ở trên.
#   * "Sổ có còn LỚN LÊN không?"   → hai hàm dưới đây.
#
# Câu thứ hai mới là câu bắt được kiểu hỏng nguy hiểm nhất: một đường ghi biến
# mất mà không ném lỗi nào cả — ai đó xoá lời gọi `record`, hoặc một nhánh mã
# mới không gọi nó ngay từ đầu. Không có gì hỏng, không có gì được ghi, và một
# nhật ký kiểm toán im lặng trông hệt như một hệ thống yên tĩnh.


def count_since(seconds: int) -> int:
    """Số dòng kiểm toán ghi được trong `seconds` giây vừa qua. -1 nếu không đọc được.

    -1 chứ không phải 0: "không hỏi được cơ sở dữ liệu" và "không có hoạt động
    nào" là hai chuyện khác nhau, và trả 0 cho cả hai sẽ biến một sự cố kết nối
    thành một cảnh báo "sổ ngừng tăng" — báo động đúng hồi chuông vì sai lý do,
    rồi lần sau không ai tin nó nữa.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    try:
        with system_scope("audit: đếm số dòng kiểm toán gần đây"):
            rows = _fetch_all(
                "SELECT count(*) AS n FROM audit_log "
                "WHERE created_at >= NOW() - make_interval(secs => %s)",
                (int(max(0, seconds)),),
            )
        return int(rows[0]["n"]) if rows else 0
    except Exception as exc:
        logger.warning("[AUDIT] không đếm được dòng kiểm toán: %s", type(exc).__name__)
        return -1


def seconds_since_last_entry() -> float:
    """Tuổi của dòng kiểm toán mới nhất, tính bằng giây. -1 nếu không đọc được.

    Sổ rỗng cũng trả -1. Một bản triển khai vừa dựng chưa có dòng nào là bình
    thường; báo động "đã 10^9 giây không ai ghi gì" ở đó là báo động giả ngay
    từ phút đầu, và một cảnh báo kêu sai từ đầu thì không bao giờ được bật.
    """
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    try:
        with system_scope("audit: tuổi của dòng kiểm toán mới nhất"):
            rows = _fetch_all(
                "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(created_at))) AS age FROM audit_log"
            )
        age = rows[0]["age"] if rows else None
        return float(age) if age is not None else -1.0
    except Exception as exc:
        logger.warning("[AUDIT] không đọc được tuổi dòng kiểm toán: %s", type(exc).__name__)
        return -1.0

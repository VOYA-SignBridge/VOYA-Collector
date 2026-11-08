"""Sổ ghi "tác vụ nào của tổ chức nào" — để màn hình hàng đợi lọc được theo tenant.

Vì sao cần sổ riêng
-------------------
`worker.stamp_tenant_on_task` đã đóng dấu tenant lên header của từng message,
và worker đọc header đó để chạy việc đúng phạm vi. Nhưng màn hình UC16 hỏi
worker qua `celery inspect`, và `Request.info()` của Celery chỉ trả một bộ khoá
cố định (id, name, args, kwargs, …) — header tự đặt KHÔNG nằm trong đó. Không
có sổ này thì màn hình không biết việc nào của ai, và trước 23/10/2026 nó trả
nguyên danh sách của cả nền tảng cho biên tập viên của bất kỳ tổ chức nào.

Ghi ở lúc PUBLISH, cùng chỗ đóng dấu header: đó là thời điểm duy nhất biết
chắc ai yêu cầu việc, và nó phủ mọi lời gọi `.delay()`/`.apply_async()` mà
không phải sửa từng chỗ.

Luật đọc: fail-closed
---------------------
Việc không có dòng trong sổ — việc nền tảng (beat, CLI), việc gửi trước khi sổ
tồn tại, hoặc dòng đã hết hạn / bị Redis đẩy ra khi thiếu bộ nhớ — được coi là
"không thuộc tổ chức nào". Người dùng tổ chức không thấy và không huỷ được nó;
chỉ quản trị nền tảng thấy. Sổ hỏng thì màn hình hiện ÍT đi, không hiện NHIỀU
lên.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, Optional

logger = logging.getLogger(__name__)

KEY_PREFIX = "voya:task_tenant:"

#: Bảy ngày. Đủ dài cho một việc huấn luyện xếp hàng qua cuối tuần; quá hạn thì
#: việc đó chỉ còn hiện với quản trị nền tảng, đúng theo luật fail-closed.
TTL_SECONDS = 7 * 24 * 3600

_client_singleton = None


def _client():
    """Client Redis dùng chung, timeout ngắn: hàm ghi chạy trên đường publish."""
    global _client_singleton
    if _client_singleton is None:
        import redis  # pyright: ignore[reportMissingImports]

        from app.config import settings

        _client_singleton = redis.Redis.from_url(
            settings.broker_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _client_singleton


def record_owner(task_id: Optional[str], tenant_id: Optional[str]) -> bool:
    """Ghi tenant chủ của một tác vụ. Không bao giờ ném.

    Ghi hỏng không được chặn việc publish: tác vụ vẫn chạy đúng phạm vi nhờ
    header, chỉ là nó sẽ không hiện với người dùng tổ chức trên màn hình hàng
    đợi.
    """
    if not task_id or not tenant_id:
        return False
    try:
        _client().set(f"{KEY_PREFIX}{task_id}", tenant_id, ex=TTL_SECONDS)
        return True
    except Exception as exc:  # pragma: no cover - phụ thuộc Redis
        logger.warning("[TASK-REGISTRY] khong ghi duoc chu cua %s: %s", task_id, exc)
        return False


def owners_of(task_ids: Iterable[str]) -> Dict[str, Optional[str]]:
    """`{task_id: tenant hoặc None}` cho mọi id được hỏi.

    Ném lỗi nếu không đọc được Redis — người gọi phải phân biệt "không đọc được
    sổ" với "việc không có chủ", vì hai thứ đó hiện khác nhau trên màn hình.
    """
    ids = [str(t) for t in task_ids if t]
    if not ids:
        return {}
    values = _client().mget([f"{KEY_PREFIX}{t}" for t in ids])
    return {t: (v or None) for t, v in zip(ids, values)}

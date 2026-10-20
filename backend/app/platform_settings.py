"""Thiết lập đổi được lúc chạy, không cần triển khai lại.

Vì sao cần lớp này khi đã có biến môi trường
---------------------------------------------
Backend được nướng vào image và `.env` chỉ nạp lại khi force-recreate container
(xem `deploy-env-reload-and-image`). Nghĩa là đổi hạn ngạch dùng thử từ 60 xuống
20 phút vì máy chủ đang quá tải sẽ mất một lần dựng lại cả stack — đúng lúc
không nên dựng lại cái gì.

Nên: biến môi trường là **giá trị khởi tạo**, bảng này là **giá trị đang có hiệu
lực**. Không có dòng nào trong bảng thì rơi về biến môi trường. Trật tự đó khiến
một bản triển khai mới chạy đúng ngay mà không cần seed gì.

Vì sao có bộ nhớ đệm
--------------------
`trial_minutes_per_day` được đọc ở MỖI lượt suy luận — tới 5 lần mỗi giây cho
mỗi khách. Một truy vấn cho mỗi lần đọc sẽ biến một thiết lập thành một điểm
nghẽn. Đệm 30 giây: đủ ngắn để người vận hành thấy thay đổi có hiệu lực gần như
ngay, đủ dài để bỏ gần hết tải đọc.

Đệm trong tiến trình chứ không phải Redis, có chủ ý: mỗi worker giữ bản riêng và
tự hết hạn, nên không có gì phải vô hiệu hoá xuyên tiến trình. Cái giá là hai
worker có thể lệch nhau tối đa 30 giây — không quan trọng với một hạn ngạch.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_CACHE_TTL = 30.0
_cache: Dict[str, Tuple[float, Optional[str]]] = {}

#: Chỉ những khoá ở đây mới đổi được lúc chạy.
#:
#: Danh sách trắng, không phải bảng tự do. Một bảng khoá-giá trị ai ghi gì cũng
#: được sẽ trở thành nơi cất mọi thứ, và không ai biết khoá nào còn được đọc.
#: Mỗi mục: (khoá, tên thuộc tính trong Settings, min, max, mô tả).
EDITABLE: Dict[str, Dict[str, Any]] = {
    "trial_minutes_per_day": {
        "attr": "trial_minutes_per_day",
        "type": int,
        "min": 0,
        "max": 1440,
        "label": "Số phút dùng thử mô hình mỗi ngày cho khách chưa đăng nhập",
        # 0 nghĩa là TẮT hẳn dùng thử — hợp lệ, và là cách đóng nhanh khi máy
        # chủ quá tải mà không phải triển khai lại.
        "note": "0 = tắt dùng thử. 1440 = không giới hạn trong ngày.",
    },
    "rate_limit_predict_per_minute": {
        "attr": "rate_limit_predict_per_minute",
        "type": int,
        "min": 10,
        "max": 5000,
        "label": "Trần lượt suy luận mỗi phút cho mỗi người gọi",
        "note": "Client gửi 5 lượt/giây khi ký liên tục, tức 300/phút. Đặt dưới "
                "mức đó sẽ làm gián đoạn phiên dùng bình thường.",
    },
}


def _fetch(key: str) -> Optional[str]:
    from app.storage.metadata_db import _fetch_all
    from app.tenant_context import system_scope

    with system_scope("platform settings: giá trị toàn hệ thống, không thuộc tenant nào"):
        rows = _fetch_all(
            "SELECT value FROM platform_settings WHERE key = %s", (key,))
    return str(rows[0]["value"]) if rows else None


def get_int(key: str) -> int:
    """Giá trị đang có hiệu lực của một khoá kiểu số nguyên.

    Thứ tự: bảng → biến môi trường. Mọi lỗi đọc đều rơi về biến môi trường và chỉ
    ghi cảnh báo: một sự cố cơ sở dữ liệu không được phép làm hỏng đường suy
    luận, và giá trị khởi tạo luôn là một giá trị an toàn.
    """
    from app.config import settings

    spec = EDITABLE.get(key)
    if spec is None:
        raise KeyError(f"thiết lập không đổi được lúc chạy: {key!r}")
    fallback = int(getattr(settings, spec["attr"]))

    now = time.monotonic()
    cached = _cache.get(key)
    if cached is not None and now - cached[0] < _CACHE_TTL:
        raw = cached[1]
    else:
        try:
            raw = _fetch(key)
        except Exception as exc:
            logger.warning("[settings] không đọc được %s, dùng mặc định: %s", key, exc)
            raw = None
        _cache[key] = (now, raw)

    if raw is None:
        return fallback
    try:
        return int(raw)
    except (TypeError, ValueError):
        logger.warning("[settings] %s có giá trị hỏng %r, dùng mặc định", key, raw)
        return fallback


def set_int(key: str, value: int, *, updated_by: str) -> int:
    """Đặt giá trị mới. Kiểm biên TRƯỚC khi ghi.

    Kiểm ở đây chứ không chỉ ở tầng HTTP: đây là nơi duy nhất mọi đường ghi đi
    qua, kể cả một lệnh CLI thêm sau này.
    """
    from app.storage.metadata_db import _cursor
    from app.tenant_context import system_scope

    spec = EDITABLE.get(key)
    if spec is None:
        raise KeyError(f"thiết lập không đổi được lúc chạy: {key!r}")
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError("giá trị phải là số nguyên")
    if not (spec["min"] <= value <= spec["max"]):
        raise ValueError(
            f"{key} phải nằm trong [{spec['min']}, {spec['max']}], nhận {value}")

    with system_scope("platform settings: ghi giá trị toàn hệ thống"):
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO platform_settings (key, value, updated_by, updated_at)
                VALUES (%s, %s, %s, now())
                ON CONFLICT (key) DO UPDATE
                   SET value = EXCLUDED.value,
                       updated_by = EXCLUDED.updated_by,
                       updated_at = now()
                """,
                (key, str(value), updated_by),
            )
    # Xoá đệm của CHÍNH tiến trình này để người vừa đổi thấy ngay kết quả. Các
    # worker khác bắt kịp trong 30 giây.
    _cache.pop(key, None)
    logger.info("[settings] %s = %s (bởi %s)", key, value, updated_by)
    return value


def current() -> Dict[str, Dict[str, Any]]:
    """Toàn bộ thiết lập đổi được, kèm giá trị hiện tại và biên — cho giao diện."""
    from app.config import settings

    out: Dict[str, Dict[str, Any]] = {}
    for key, spec in EDITABLE.items():
        out[key] = {
            "value": get_int(key),
            "default": int(getattr(settings, spec["attr"])),
            "min": spec["min"],
            "max": spec["max"],
            "label": spec["label"],
            "note": spec["note"],
        }
    return out

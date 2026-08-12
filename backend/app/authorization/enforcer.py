"""Vòng đời của Casbin Enforcer: nạp, nạp lại, và hỏng-thì-đóng.

Một enforcer cho mỗi tiến trình
--------------------------------
§21 Phase 1. Toàn bộ policy đang hiệu lực nằm trong bộ nhớ của mỗi tiến trình
API. Với quy mô hiện tại đó là vài nghìn dòng; nạp theo tenant (Phase 2) là tối
ưu hoá cho một vấn đề chưa tồn tại, và nó đổi lấy một tầng cache
enforcer-theo-tenant có bài toán vô hiệu hoá riêng.

"Hỏng thì đóng" nghĩa là gì ở đây
----------------------------------
§40: nạp policy thất bại thì **phân quyền = CHƯA SẴN SÀNG**, không được lặng lẽ
cho qua. Nhưng "không cho qua" có hai mức, và trộn chúng là sai:

    chế độ `casbin`  Casbin ĐANG quyết định. Không nạp được = không trả lời
                     được = mọi `authorize()` trả DENY. Đó là hỏng-thì-đóng
                     thật, và nó sẽ làm hệ thống ngừng phục vụ — đúng như phải
                     thế, vì phương án còn lại là phục vụ mà không biết cho ai.

    chế độ `shadow`  Casbin chỉ đang QUAN SÁT; hệ cũ vẫn quyết định. Không nạp
                     được thì tắt quan sát và ghi log, KHÔNG chặn request nào.
                     Bắt shadow mode làm sập hệ thống sẽ khiến không ai dám bật
                     nó — và shadow mode không bao giờ được chạy là cách chắc
                     chắn nhất để lên thẳng enforcement với mismatch chưa biết.

`_state` giữ luôn cả LỖI chứ không chỉ enforcer, vì "chưa nạp lần nào" và "đã
thử và hỏng" là hai tình trạng khác nhau và chỉ có cái thứ hai đáng báo động.

Nạp lại thay vì vá tại chỗ
---------------------------
Khi policy đổi, cả enforcer được dựng lại từ đầu chứ không `add_policy` từng
dòng. Chậm hơn (một lượt đọc năm bảng), nhưng nó có tính chất mà cách vá không
có: **trạng thái sau khi nạp lại chỉ phụ thuộc vào cơ sở dữ liệu**, không phụ
thuộc vào việc mọi sự kiện trước đó đã được áp đúng thứ tự hay chưa. Một sự
kiện bị mất chỉ làm policy cũ đi tới lần nạp sau; với cách vá, nó làm policy
SAI vĩnh viễn.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).with_name("model.conf")


class PolicyNotLoaded(RuntimeError):
    """Không có policy nào để quyết định. Người gọi phải coi là DENY."""


@dataclass
class _State:
    enforcer: Any = None
    loaded_at: float = 0.0
    error: Optional[str] = None
    generation: int = 0
    stats: dict = field(default_factory=dict)


_state = _State()
_lock = threading.Lock()


def _build() -> tuple[Any, dict]:
    """Dựng một enforcer mới và trả về kèm thống kê policy đã nạp.

    Trả cả hai thay vì để adapter ghi vào `_state`: hai luồng cùng gọi
    `reload_policy` sẽ giẫm lên nhau, và thống kê hiển thị có thể thuộc về một
    thế hệ policy khác với enforcer đang phục vụ. Không nguy hiểm, nhưng nó làm
    `status()` nói dối đúng lúc người ta đọc nó để chẩn đoán.
    """
    import casbin

    from app.authorization.adapter import ReadOnlyPolicyAdapter

    adapter = ReadOnlyPolicyAdapter()
    # `casbin.Enforcer(model, adapter)` tự gọi `load_policy` trong hàm dựng.
    enforcer = casbin.Enforcer(str(MODEL_PATH), adapter)
    # `auto_save` mặc định BẬT, và với adapter chỉ-đọc thì mọi lời gọi làm
    # thay đổi policy sẽ ném NotImplementedError. Tắt nó ở đây sẽ biến lỗi ồn
    # ào đó thành một thay đổi chỉ-trong-bộ-nhớ biến mất ở lần nạp sau — im
    # lặng và sai. Cứ để bật.
    return enforcer, dict(adapter.stats)


def reload_policy(*, reason: str = "unspecified") -> bool:
    """Dựng lại enforcer từ cơ sở dữ liệu. True nếu thành công.

    Không ném lỗi: người gọi là đường khởi động, một tác vụ nền, hoặc bộ nhận
    sự kiện vô hiệu hoá — không cái nào nên chết vì Postgres chớp một nhịp.
    Thất bại được ghi vào `_state.error`, và `get_enforcer()` là nơi biến nó
    thành DENY.
    """
    global _state
    started = time.monotonic()
    try:
        enforcer, stats = _build()
    except Exception as exc:
        message = f"{exc.__class__.__name__}: {exc}"
        with _lock:
            _state.error = message
        logger.error("[CASBIN] nap policy THAT BAI (%s): %s", reason, message)
        return False

    with _lock:
        _state = _State(
            enforcer=enforcer,
            loaded_at=time.time(),
            error=None,
            generation=_state.generation + 1,
            stats=stats,
        )
        generation = _state.generation

    logger.info(
        "[CASBIN] policy the he %d nap xong sau %.0fms (%s)",
        generation, (time.monotonic() - started) * 1000, reason,
    )

    # Không đụng tới chỉ số ở đây. `metrics._refresh_authz_gauges()` đọc
    # `status()` lúc QUÉT, nên nó tính được tuổi thật; đặt một giá trị ở thời
    # điểm nạp sẽ cho ra một đồng hồ đứng yên và một cảnh báo "policy quá cũ"
    # không bao giờ kêu.
    return True


def get_enforcer():
    """Enforcer đang hiệu lực, hoặc `PolicyNotLoaded`.

    KHÔNG tự nạp khi chưa có. Nạp lười sẽ biến một lần khởi động hỏng thành
    một lần thử nạp ở request đầu tiên — tức là một độ trễ bất ngờ trên đường
    nóng, và tệ hơn, một lỗi phân quyền hiện ra ở một chỗ hoàn toàn không liên
    quan. `startup()` là nơi nạp, và nó chạy trước khi cổng mở.
    """
    state = _state
    if state.enforcer is None:
        raise PolicyNotLoaded(state.error or "policy chua duoc nap (startup chua chay?)")
    return state.enforcer


def is_ready() -> bool:
    return _state.enforcer is not None


def status() -> dict:
    """Trạng thái đọc được, cho endpoint sức khoẻ và `verify_deployment`."""
    state = _state
    return {
        "ready": state.enforcer is not None,
        "generation": state.generation,
        "loaded_at": state.loaded_at or None,
        "age_seconds": round(time.time() - state.loaded_at, 1) if state.loaded_at else None,
        "error": state.error,
        "policy": dict(state.stats),
    }


def startup(*, strict: bool) -> bool:
    """Nạp policy lúc khởi động. `strict` = hỏng thì phải nổ.

    `strict` đến từ chế độ phân quyền, không phải từ một biến môi trường riêng:
    nó BẬT khi và chỉ khi Casbin đang thực sự quyết định. Xem docstring module
    về vì sao shadow mode không được phép làm sập tiến trình.
    """
    ok = reload_policy(reason="startup")
    if not ok and strict:
        raise PolicyNotLoaded(
            f"AUTHZ_MODE=casbin nhung khong nap duoc policy: {_state.error}. "
            f"He thong tu choi khoi dong thay vi cho qua moi request."
        )
    return ok


def reset_for_tests() -> None:
    """Quên enforcer hiện tại. Chỉ dùng trong test."""
    global _state
    with _lock:
        _state = _State()

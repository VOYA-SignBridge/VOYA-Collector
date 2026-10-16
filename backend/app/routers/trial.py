"""Xin và xem hạn ngạch dùng thử ẩn danh.

Hai endpoint, và cả hai đều công khai — phải thế, vì đây là cách một người chưa
có gì trong tay bắt đầu.

Vì sao `start` là POST chứ không phải GET
------------------------------------------
Nó ĐẶT một cookie, tức là thay đổi trạng thái. Một GET đặt cookie sẽ bị trình
duyệt nạp trước (prefetch) và bởi mọi bộ quét link, nên hạn ngạch bắt đầu tiêu
trước khi người dùng bấm gì.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, Request, Response

from app import trial
from app.rate_limit import enforce_ip_limit

router = APIRouter(prefix="/trial", tags=["trial"])


def _payload(state: trial.TrialState, has_grant: bool) -> Dict[str, Any]:
    return {
        "has_grant": has_grant,
        "minutes_limit": state.minutes_limit,
        "minutes_used": state.minutes_used,
        "minutes_remaining": state.minutes_remaining,
        "resets_at": state.resets_at,
        "exhausted": not state.allowed and has_grant,
    }


@router.post("/start")
def start_trial(request: Request, response: Response) -> Dict[str, Any]:
    """Cấp phiếu dùng thử, hoặc trả lại tình trạng của phiếu đang có.

    Idempotent theo cookie: bấm hai lần không cấp phiếu thứ hai và không làm mới
    hạn ngạch. Nếu cấp mới mỗi lần gọi thì hạn ngạch hằng ngày trở thành vô hạn —
    chỉ cần gọi lại endpoint này.
    """
    # Giới hạn theo IP ở ĐÂY thì hợp lý, khác với việc dùng IP làm danh tính:
    # cái này chỉ chặn một máy đúc hàng loạt phiếu, không quyết định ai là ai.
    enforce_ip_limit(request, bucket="trial_start", max_calls=20, window=3600)

    existing = trial.peek(request)
    if existing.grant_id is not None:
        return _payload(existing, has_grant=True)

    trial.issue(response)
    # Phiếu vừa cấp: chưa tiêu phút nào, và đồng hồ chưa chạy — nó chỉ chạy ở
    # lượt suy luận đầu tiên.
    fresh = trial.TrialState(
        allowed=True, minutes_used=0,
        minutes_limit=existing.minutes_limit,
        resets_at=existing.resets_at, grant_id="new",
    )
    return _payload(fresh, has_grant=True)


@router.get("/status")
def trial_status(request: Request) -> Dict[str, Any]:
    """Số phút còn lại. Không tiêu tốn gì — giao diện gọi cái này để vẽ đồng hồ."""
    state = trial.peek(request)
    return _payload(state, has_grant=state.grant_id is not None)

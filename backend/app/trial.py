"""Gói dùng thử ẩn danh: 60 phút mô hình nhận diện mỗi ngày, cho mỗi khách.

Đếm PHÚT CÓ HOẠT ĐỘNG, không đếm lượt gọi
------------------------------------------
Yêu cầu là "60 phút, liên tục hay ngắt quãng đều được". Đếm lượt gọi không diễn
đạt được điều đó: người ký liên tục gửi 5 lượt/giây (client debounce 200 ms) còn
người ký từng đợt gửi ít hơn nhiều, nên cùng một "phút trải nghiệm" tiêu tốn số
lượt rất khác nhau.

Nên đơn vị là phút: một phút bị tính là ĐÃ DÙNG nếu trong phút đó có ít nhất một
lượt suy luận. Người dừng lại đọc kết quả không mất gì, đúng như đã hứa.

Cài bằng bitmap Redis, một bit cho mỗi phút trong ngày:

    SETBIT   trial:<grant>:<YYYYMMDD>  <phút thứ 0..1439>  1
    BITCOUNT trial:<grant>:<YYYYMMDD>              -> số phút đã dùng

1440 bit = 180 byte mỗi khách mỗi ngày. Chính xác tuyệt đối, không cần dọn dẹp
(khoá tự hết hạn), và một lệnh cho mỗi request.

Vì sao 60 phút chứ không phải 30
---------------------------------
Đo trên chính bản triển khai này, 2026-08-07: một lượt `/realtime/predict` tốn
**40 ms CPU (p50)** và **không dùng GPU** (`torch.cuda.is_available()` là False,
container không có `DeviceRequests`). 60 phút ký LIÊN TỤC ở 5 lượt/giây là 18.000
lượt ≈ 12 phút CPU — trên máy 6 lõi, một khách liên tục chiếm khoảng 20% một lõi.
Rẻ. Số này nằm ở `settings.trial_minutes_per_day`; nếu mô hình sau này chuyển
sang GPU thì đo lại rồi chỉnh, đừng đoán.

Danh tính khách: phiếu ký, KHÔNG phải địa chỉ IP
-------------------------------------------------
Cả CTU đi ra Internet qua một NAT. Đếm theo IP nghĩa là một sinh viên dùng hết
là cả trường mất lượt — còn đổi sang 4G thì reset. Vân tay trình duyệt thì vừa
xâm phạm vừa là dữ liệu cá nhân, không hợp với một nền tảng phục vụ giáo dục
đặc biệt.

Nên: một phiếu ngẫu nhiên đặt trong cookie HttpOnly, chỉ lưu BĂM của nó ở phía
máy chủ. Xoá cookie là được phiếu mới, và điều đó **chấp nhận được**: mục tiêu
không phải chặn người quyết tâm mà là tạo một thời điểm mời đăng ký tự nhiên cho
người bình thường. Chống lạm dụng có hệ thống là việc của trần toàn cục trong
`rate_limit.py`, không phải việc của module này.

Fail-closed hay fail-open khi Redis chết?
------------------------------------------
**Fail-open**, và đây là lựa chọn có cân nhắc, khác với mọi chỗ khác trong hệ
thống này. Redis chết mà chặn nghĩa là tính năng dùng thử biến mất với mọi
người vì một sự cố hạ tầng; thứ bị rủi ro chỉ là một hạn ngạch trải nghiệm, chứ
không phải dữ liệu của ai. `rate_limit.py` đã fail-open vì cùng lý do. Ranh giới
THẬT — ai đọc được dữ liệu nào — nằm ở RLS và ở `access_gate`, không nằm ở đây.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Request, Response

from app.config import settings

logger = logging.getLogger(__name__)

#: Tên cookie mang phiếu. Cùng tiền tố với các cookie khác của hệ thống.
TRIAL_COOKIE = "voya_trial"

_KEY_PREFIX = "trial:"

#: Bitmap sống 48 giờ: đủ dài để bao trọn một ngày theo múi giờ bất kỳ, đủ ngắn
#: để Redis tự dọn mà không cần một tác vụ quét.
_TTL_SECONDS = 48 * 3600


@dataclass(frozen=True)
class TrialState:
    """Kết quả một lần xin dùng mô hình."""

    allowed: bool
    minutes_used: int
    minutes_limit: int
    #: Thời điểm hạn ngạch làm mới, dạng ISO — giao diện hiện "thử lại sau...".
    resets_at: str
    #: None khi khách chưa từng có phiếu (chưa bấm "Thử nhận diện").
    grant_id: Optional[str] = None

    @property
    def minutes_remaining(self) -> int:
        return max(0, self.minutes_limit - self.minutes_used)

    def requiring_grant(self) -> "TrialState":
        """Cùng trạng thái, nhưng "chưa có phiếu" được coi là KHÔNG được vào.

        `peek()` báo cáo hạn ngạch chứ không phán quyền, nên với người chưa có
        phiếu nó trả `allowed=True` — đúng với câu hỏi nó trả lời ("đã dùng bao
        nhiêu?"), sai với câu hỏi cổng gác hỏi ("cho vào không?").

        Bản đầu vá chỗ lệch này ngay trong `access_gate` bằng
        `grant.__class__(False, grant.minutes_used, ...)` — dựng lại dataclass
        theo THỨ TỰ THAM SỐ. Đổi thứ tự trường trong `TrialState` sẽ khiến câu
        đó lặng lẽ gán nhầm giá trị sang trường khác mà không có lỗi nào, và
        đó là cổng gác. Đưa phép biến đổi về đúng chỗ định nghĩa kiểu, dùng
        `replace` theo TÊN trường.
        """
        if self.grant_id is not None:
            return self
        return replace(self, allowed=False)


def _limit() -> int:
    """Hạn ngạch ĐANG có hiệu lực, không phải giá trị lúc khởi động.

    Đọc qua `platform_settings` để quản trị viên đổi được lúc chạy (có sudo)
    mà không phải dựng lại stack. Lớp đó tự đệm 30 giây, nên gọi ở mỗi lượt suy
    luận không thành điểm nghẽn. Mọi sự cố đọc đều rơi về
    `settings.trial_minutes_per_day`.
    """
    from app.platform_settings import get_int

    return get_int("trial_minutes_per_day")


def _client():
    """Dùng chung singleton Redis của `rate_limit` thay vì mở kết nối thứ hai.

    Hai pool tới cùng một Redis là hai lần chi phí kết nối và hai chỗ phải sửa
    khi URL đổi — và pool kia đã có sẵn xử lý fail-open cần thiết.
    """
    from app.rate_limit import _client as shared_client

    return shared_client()


def _hash_token(token: str) -> str:
    """Chỉ BĂM của phiếu được lưu.

    Phiếu là 32 byte ngẫu nhiên, tức entropy cao, nên SHA-256 trần là đủ —
    khác với mã OTP sáu chữ số vốn cần HMAC kèm pepper. Cùng lập luận đã viết
    trong `app/tokens.py`.
    """
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _local(now: datetime) -> datetime:
    """Chuyển sang múi giờ quyết định ranh giới ngày của hạn ngạch.

    Bản đầu tính mọi thứ theo UTC, và điều đó khiến "mỗi ngày 60 phút" thực ra
    reset lúc **7 giờ sáng giờ Việt Nam**. Người dùng lúc 6h sáng bị chặn rồi
    được mở lại một tiếng sau, còn câu "quay lại vào ngày mai" trong thông báo
    thì sai. Với người dùng ở Việt Nam, một ngày kết thúc lúc nửa đêm của họ.
    """
    offset = timezone(timedelta(hours=settings.trial_reset_utc_offset_hours))
    return now.astimezone(offset)


def _today_key(grant_hash: str, now: datetime) -> str:
    return f"{_KEY_PREFIX}{grant_hash}:{_local(now).strftime('%Y%m%d')}"


def _minute_of_day(now: datetime) -> int:
    """Vị trí bit, tính theo giờ ĐỊA PHƯƠNG.

    Phải cùng hệ quy chiếu với `_today_key`. Nếu khoá theo ngày địa phương mà
    bit theo giờ UTC thì hai phút cách nhau đúng một ngày sẽ đập vào cùng một
    bit, và người dùng mất phút mà không hiểu vì sao.
    """
    local = _local(now)
    return local.hour * 60 + local.minute


def _next_reset(now: datetime) -> str:
    """Thời điểm hạn ngạch làm mới, dạng ISO CÓ kèm độ lệch múi giờ.

    Giữ độ lệch trong chuỗi để giao diện không phải đoán: một ISO không múi giờ
    sẽ được trình duyệt hiểu là giờ địa phương của máy khách, và đồng hồ đếm
    ngược sẽ lệch đúng bằng độ lệch múi giờ.
    """
    local = _local(now)
    tomorrow = (local + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    return tomorrow.isoformat()


def issue(response: Response) -> str:
    """Cấp một phiếu mới và đặt cookie. Trả về phiếu thô (chỉ lần này).

    Đồng hồ KHÔNG bắt đầu ở đây — nó bắt đầu ở lượt suy luận đầu tiên. Cấp phiếu
    lúc mở trang rồi tính giờ ngay sẽ khiến người đọc thư viện mười phút mất mười
    phút mà chưa dùng gì.
    """
    token = secrets.token_urlsafe(32)
    response.set_cookie(
        key=TRIAL_COOKIE,
        value=token,
        max_age=_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=bool(getattr(settings, "cookie_secure", False)),
        path=(getattr(settings, "cookie_path_prefix", "") or "") + "/",
    )
    return token


def _read_token(request: Request) -> Optional[str]:
    token = request.cookies.get(TRIAL_COOKIE)
    return token.strip() if token else None


def peek(request: Request) -> TrialState:
    """Hạn ngạch còn lại, KHÔNG tiêu tốn gì. Dùng cho `/trial/status`."""
    now = datetime.now(timezone.utc)
    limit = _limit()
    token = _read_token(request)
    if not token:
        return TrialState(True, 0, limit, _next_reset(now), None)

    grant_hash = _hash_token(token)
    client = _client()
    if client is None:
        return TrialState(True, 0, limit, _next_reset(now), grant_hash[:12])

    try:
        used = int(client.bitcount(_today_key(grant_hash, now)) or 0)
    except Exception as exc:
        logger.warning("[trial] Redis đọc lỗi, coi như chưa dùng: %s", exc)
        used = 0
    return TrialState(used < limit, used, limit, _next_reset(now), grant_hash[:12])


def consume_minute(request: Request) -> TrialState:
    """Đánh dấu phút hiện tại là đã dùng và cho biết còn được đi tiếp không.

    Kiểm hạn mức TRƯỚC khi đánh dấu, và chỉ đánh dấu khi còn hạn. Làm ngược lại
    thì lượt gọi bị từ chối vẫn tiêu một phút, và người dùng thấy đồng hồ tụt đi
    trong lúc không nhận được gì.
    """
    now = datetime.now(timezone.utc)
    limit = _limit()
    token = _read_token(request)

    if not token:
        # Chưa bấm "Thử nhận diện". Không cấp phiếu ngầm ở đây: cấp phiếu là một
        # hành động có chủ ý của người dùng, và nó đặt cookie — việc đặt cookie
        # không nên xảy ra như tác dụng phụ của một lượt suy luận.
        return TrialState(False, 0, limit, _next_reset(now), None)

    grant_hash = _hash_token(token)
    client = _client()
    if client is None:
        # Fail-open — xem docstring của module.
        return TrialState(True, 0, limit, _next_reset(now), grant_hash[:12])

    key = _today_key(grant_hash, now)
    try:
        used = int(client.bitcount(key) or 0)
        minute = _minute_of_day(now)
        already = bool(client.getbit(key, minute))
        if not already:
            if used >= limit:
                return TrialState(False, used, limit, _next_reset(now), grant_hash[:12])
            pipe = client.pipeline()
            pipe.setbit(key, minute, 1)
            pipe.expire(key, _TTL_SECONDS)
            pipe.execute()
            used += 1
    except Exception as exc:
        logger.warning("[trial] Redis ghi lỗi, cho đi tiếp: %s", exc)
        return TrialState(True, 0, limit, _next_reset(now), grant_hash[:12])

    return TrialState(used <= limit, used, limit, _next_reset(now), grant_hash[:12])


def describe(state: TrialState) -> str:
    """Câu thông báo cho người dùng khi bị từ chối.

    Hai lý do từ chối khác nhau cần hai câu khác nhau: chưa xin phiếu là một lời
    mời, hết hạn ngạch là một thông tin kèm lối đi tiếp. Trả về cùng một câu cho
    cả hai sẽ khiến người mới vào tưởng mình đã dùng hết.
    """
    if state.grant_id is None:
        return ("Hãy bấm “Thử nhận diện” để bắt đầu phiên dùng thử, "
                "hoặc đăng nhập để dùng không giới hạn.")
    return (f"Bạn đã dùng hết {state.minutes_limit} phút trải nghiệm hôm nay. "
            f"Tạo tài khoản để tiếp tục không giới hạn, hoặc quay lại vào ngày mai.")

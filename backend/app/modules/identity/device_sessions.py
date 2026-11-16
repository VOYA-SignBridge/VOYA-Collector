"""Thiết bị đang đăng nhập của một người: xem, và đăng xuất từng thiết bị.

Một "thiết bị" ở đây là một HỌ refresh token (`family_id`): một lần đăng nhập sinh
một họ, và mỗi lần làm mới chỉ nối thêm một token cùng họ (xem `rotate_session`).
Nên mỗi họ còn sống tương ứng đúng một phiên trên một trình duyệt.

Không lưu địa chỉ IP thô ở đây. Để người dùng NHẬN RA thiết bị của mình, tên trình
duyệt + hệ điều hành và thời điểm là đủ, và là phần dữ liệu tối thiểu.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.modules.identity import _web_compat as identity
from app.modules.security import session_controls

#: Trần độ dài User-Agent được lưu.
UA_MAX = 255

# Thứ tự QUAN TRỌNG: Edge và Opera cũng có chữ "Chrome", Chrome cũng có chữ "Safari".
_BROWSERS = (
    ("Edge", re.compile(r"Edg(?:e|A|iOS)?/")),
    ("Opera", re.compile(r"OPR/|Opera")),
    ("Firefox", re.compile(r"Firefox/|FxiOS/")),
    ("Chrome", re.compile(r"Chrome/|CriOS/")),
    ("Safari", re.compile(r"Safari/")),
)
# "Android" đứng trước "Linux" và iOS trước macOS vì UA của chúng chứa cả hai chữ.
_SYSTEMS = (
    ("Android", re.compile(r"Android")),
    ("iPhone", re.compile(r"iPhone")),
    ("iPad", re.compile(r"iPad")),
    ("Windows", re.compile(r"Windows")),
    ("macOS", re.compile(r"Mac OS X|Macintosh")),
    ("Linux", re.compile(r"Linux|X11")),
)


def clip_user_agent(raw: Optional[str]) -> Optional[str]:
    """User-Agent để lưu: cắt độ dài, rỗng thì None."""
    text = (raw or "").strip()
    return text[:UA_MAX] or None


def describe_device(user_agent: Optional[str]) -> str:
    """Nhãn ngắn cho người đọc, ví dụ "Chrome · Windows". Không nhận ra thì nói thật."""
    ua = user_agent or ""
    browser = next((name for name, pat in _BROWSERS if pat.search(ua)), None)
    system = next((name for name, pat in _SYSTEMS if pat.search(ua)), None)
    parts = [p for p in (browser, system) if p]
    return " · ".join(parts) if parts else "Thiết bị không xác định"


def current_family(access_token: Optional[str]) -> Optional[str]:
    """Họ của phiên đang gọi, đọc từ access token (`fam`); None nếu không có."""
    if not access_token:
        return None
    try:
        return str(identity._decode_token(access_token).get("fam") or "") or None
    except Exception:  # noqa: BLE001 — token hỏng nghĩa là "không biết", không phải lỗi
        return None


def list_sessions(user_id: str, current: Optional[str]) -> List[Dict[str, Any]]:
    """Các phiên còn sống của `user_id`, mới dùng gần nhất trước."""
    default = identity.default_session_lifetime()
    with identity._identity_cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (r.family_id)
                   r.family_id, r.user_agent, r.created_at AS last_active, r.expires_at,
                   (SELECT min(f.created_at) FROM refresh_tokens f
                     WHERE f.family_id = r.family_id) AS started_at
            FROM refresh_tokens r
            WHERE r.user_id = %s
              AND r.family_id IS NOT NULL
              AND r.revoked_at IS NULL
              AND r.reuse_detected_at IS NULL
              AND r.expires_at > NOW()
            ORDER BY r.family_id, r.created_at DESC
            """,
            (str(user_id),),
        )
        rows = cur.fetchall()
    out = [
        {
            "id": str(r["family_id"]),
            "device": describe_device(r["user_agent"]),
            "started_at": r["started_at"],
            "last_active": r["last_active"],
            "remembered": (r["expires_at"] - r["last_active"]) > default + timedelta(seconds=5),
            "current": current is not None and str(r["family_id"]) == current,
        }
        for r in rows
    ]
    out.sort(key=lambda s: s["last_active"], reverse=True)
    return out


def _kill(cur, user_id: str, *, family: Optional[str], keep: Optional[str]) -> List[str]:
    """Kết thúc các họ khớp; trả về danh sách họ đã kết thúc.

    Đặt cả `expires_at = NOW()`, không chỉ `revoked_at`: token vừa thu hồi vẫn được
    làm mới trong cửa sổ ân hạn (hai tab đua nhau), và một thiết bị vừa bị đăng xuất
    sẽ lợi dụng đúng cửa sổ đó để sống tiếp. Kiểm hạn đứng TRƯỚC kiểm ân hạn trong
    `rotate_session`, nên hạn đã hết thì không còn đường nào quay lại.
    """
    where = "user_id = %s AND family_id IS NOT NULL AND revoked_at IS NULL"
    params: list = [str(user_id)]
    if family is not None:
        where += " AND family_id = %s"
        params.append(family)
    if keep is not None:
        where += " AND family_id <> %s"
        params.append(keep)
    cur.execute(
        f"""
        UPDATE refresh_tokens
        SET revoked_at = NOW(), expires_at = LEAST(expires_at, NOW())
        WHERE {where}
        RETURNING family_id
        """,
        params,
    )
    return sorted({str(r[0]) for r in cur.fetchall()})


def _deny_access_tokens(families: List[str]) -> None:
    """Access token của các họ vừa kết thúc cũng phải chết ngay (chúng stateless)."""
    for fam in families:
        session_controls.deny_token_family(fam)


def revoke_session(user_id: str, family_id: str) -> bool:
    """Đăng xuất MỘT thiết bị của chính `user_id`. False nếu không có phiên đó."""
    with identity._identity_cursor(dict_rows=False) as cur:
        killed = _kill(cur, user_id, family=family_id, keep=None)
    _deny_access_tokens(killed)
    return bool(killed)


def revoke_other_sessions(user_id: str, keep_family: Optional[str]) -> int:
    """Đăng xuất mọi thiết bị trừ `keep_family`. Trả về số thiết bị đã đăng xuất."""
    with identity._identity_cursor(dict_rows=False) as cur:
        killed = _kill(cur, user_id, family=None, keep=keep_family)
    _deny_access_tokens(killed)
    return len(killed)

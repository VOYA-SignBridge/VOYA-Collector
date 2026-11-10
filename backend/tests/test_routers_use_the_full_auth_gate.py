"""Every router authenticates through the same, full dependency (10/11/2026).

`app.modules.identity.get_current_user`/`require_admin` are a trimmed copy that
does not check a logged-out token (jti), a revoked token family, the
"sessions invalid before" marker set by a password change, or API keys.
`admin_data` imported it, so a revoked admin session still reached
/admin/sync-local until the token expired. Routers must import the gate from
`app.modules.identity._web_compat`, like every other router does.
"""

from __future__ import annotations

import re
from pathlib import Path

ROUTERS = Path(__file__).resolve().parents[1] / "app" / "routers"
TRIMMED = re.compile(
    r"from\s+app\.modules\.identity(\.dependencies|\.api)?\s+import\s+[^\n]*"
    r"\b(get_current_user|get_current_user_optional|require_admin)\b")


def test_no_router_uses_the_trimmed_auth_dependency():
    offenders = [p.name for p in ROUTERS.glob("*.py") if TRIMMED.search(p.read_text(encoding="utf-8"))]
    assert offenders == []


def test_admin_data_uses_the_full_gate():
    from app.modules.identity import _web_compat
    from app.routers import admin_data

    assert admin_data.require_admin is _web_compat.require_admin

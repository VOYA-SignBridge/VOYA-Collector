"""Keep persistence and outbound account email out of HTTP routers."""

from __future__ import annotations

import inspect

from app.routers import admin, auth, vocabulary


def test_refactored_routers_do_not_own_persistence_or_account_email() -> None:
    forbidden = (
        "_fetch_all",
        "_execute",
        "_identity_cursor",
        "send_password_reset_email",
        "send_verification_code_email",
    )

    for module in (auth, admin, vocabulary):
        source = inspect.getsource(module)
        for token in forbidden:
            assert token not in source, f"{module.__name__} still owns {token}"

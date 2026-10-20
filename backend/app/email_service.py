"""Compatibility facade: legacy ``app.email_service`` import path.

Implementation now lives in :mod:`app.services.email` (son_arrange module layout). The
``sys.modules`` alias keeps every legacy import pointed at that one module.
"""

import sys as _sys

from app.services import email as _impl

_sys.modules[__name__] = _impl

"""Compatibility alias for :mod:`app.services.email`."""

import sys

from app.services import email as _implementation

sys.modules[__name__] = _implementation

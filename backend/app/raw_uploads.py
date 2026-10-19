"""Compatibility alias for :mod:`app.modules.dataset.raw_uploads`."""

import sys

from app.modules.dataset import raw_uploads as _implementation

sys.modules[__name__] = _implementation

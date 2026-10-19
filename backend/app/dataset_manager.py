"""Compatibility alias for :mod:`app.modules.dataset.catalog`."""

import sys

from app.modules.dataset import catalog as _implementation

sys.modules[__name__] = _implementation

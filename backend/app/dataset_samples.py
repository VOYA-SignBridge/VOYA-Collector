"""Compatibility alias for :mod:`app.modules.dataset.samples`."""

import sys

from app.modules.dataset import samples as _implementation

sys.modules[__name__] = _implementation

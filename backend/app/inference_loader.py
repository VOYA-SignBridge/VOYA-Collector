"""Compatibility alias for :mod:`app.modules.dataset.inference`."""

import sys

from app.modules.dataset import inference as _implementation

sys.modules[__name__] = _implementation

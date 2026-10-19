"""Compatibility alias for :mod:`app.modules.dataset.signers`."""

import sys

from app.modules.dataset import signers as _implementation

sys.modules[__name__] = _implementation

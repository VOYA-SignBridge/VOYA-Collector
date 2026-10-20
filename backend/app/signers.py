"""Compatibility facade: legacy ``app.signers`` import path.

Implementation now lives in :mod:`app.modules.dataset.signers` (son_arrange module layout). The
``sys.modules`` alias keeps every legacy import pointed at that one module.
"""

import sys as _sys

from app.modules.dataset import signers as _impl

_sys.modules[__name__] = _impl

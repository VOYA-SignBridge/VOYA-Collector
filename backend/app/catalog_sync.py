"""Compatibility facade: legacy ``app.catalog_sync`` import path.

Implementation now lives in :mod:`app.modules.dataset.catalog_sync` (son_arrange module layout). The
``sys.modules`` alias keeps every legacy import pointed at that one module.
"""

import sys as _sys

from app.modules.dataset import catalog_sync as _impl

_sys.modules[__name__] = _impl

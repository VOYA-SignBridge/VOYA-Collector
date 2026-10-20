"""Compatibility facade: legacy ``app.dataset_prep_tasks`` import path.

The implementation now lives in :mod:`app.modules.dataset.preparation_tasks` (son_arrange module layout).
Aliasing the module object in ``sys.modules`` keeps every legacy import —
including private names and monkeypatch targets — pointed at the exact same
module object, the same pattern used by ``app.tasks`` / ``app.postgres_connection``.
"""

import sys as _sys

from app.modules.dataset import preparation_tasks as _impl

_sys.modules[__name__] = _impl

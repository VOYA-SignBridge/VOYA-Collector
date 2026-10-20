"""Compatibility facade for web-system rate limiting.

Canonical implementation decision (merge son_arrange ← deploy_ctu_ver-2.2.1):
the rate-limit model that runs is deploy's (pair-based login backoff, actor and
registration throttles, Redis key scheme), so ``app.rate_limit`` resolves to the
complete deploy-era implementation hosted at
:mod:`app.modules.security._web_compat`. Aliasing the module in ``sys.modules``
keeps every legacy import — public and private names alike — on one module.
"""

import sys as _sys

from app.modules.security import _web_compat as _impl

_sys.modules[__name__] = _impl

"""Compatibility facade for the identity bounded context.

Canonical implementation decision (merge son_arrange ← deploy_ctu_ver-2.2.1):
the merged database schema is deploy's (``refresh_tokens.family_id``, 2FA and
password-reset-ticket tables, API-key auth), so the auth implementation that
runs MUST match it. ``app.auth`` therefore resolves to the complete deploy-era
web-auth implementation hosted at :mod:`app.modules.identity._web_compat`
rather than son_arrange's older pre-family identity split, keeping token
families / reuse-detection / 2FA consistent across every caller.

Aliasing the module object in ``sys.modules`` keeps every legacy import —
public and private names alike — pointed at the one implementation.
"""

import sys as _sys

from app.modules.identity import _web_compat as _impl

_sys.modules[__name__] = _impl

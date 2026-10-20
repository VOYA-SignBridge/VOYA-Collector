"""FastAPI wiring for rate limits, kept apart from the limiter itself.

`rate_limit.py` is the mechanism and knows nothing about authentication;
`auth.py` imports it. Putting the dependency factory there too would close that
loop into an import cycle, so the wiring lives here — the one module allowed to
know about both.

Why the limits are what they are
--------------------------------
The goal is to stop a runaway loop or crude abuse, not to inconvenience someone
recording sign samples for an afternoon. Every ceiling below is set well above
observed real usage and is overridable by environment variable, because the
right number is a property of a deployment rather than of the code.

Before this, `grep -rl rate_limit backend/app/routers/` matched exactly one file:
`auth.py`. Everything else — including `upload.py`, the most expensive path in
the system, where one request writes to disk, runs MediaPipe and enqueues a
Celery task — had no ceiling at all.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import Depends, Request

from app.auth import get_current_user_optional
from app.config import settings
from app.rate_limit import enforce_actor_limit


def rate_limited(
    bucket: str, max_calls: int, window: int = 3600, *, allow_anonymous: bool = False
):
    """A dependency enforcing `max_calls` per `window` for this caller.

    Uses `get_current_user_optional`, not `get_current_user`: a limiter must
    never be the thing that decides a request is unauthenticated. Endpoints keep
    their own auth dependency and their own 401; this only picks a bucket key.

    `allow_anonymous` says whether the endpoint is reachable without a session.

      False (default) — the endpoint requires authentication, so an anonymous
        request is going to be refused by its own auth dependency anyway.
        Counting it would be pure downside, in two ways that both showed up in
        the test suite before this flag existed:

          * The caller is told **429 instead of 401**. A limiter that changes
            the answer to "are you allowed in?" has stepped outside its job.
          * Anonymous callers share ONE bucket, keyed by IP. A rejected caller
            could therefore exhaust the allowance of the legitimate users behind
            the same NAT — a denial of service *introduced by* the limiter, and
            at a special-education facility the whole room is one NAT.

        So the counter is left alone and the request continues to its 401.

      True — the endpoint genuinely serves anonymous callers (`/realtime/predict`
        is the only one), so IP is the only key available and skipping would mean
        no ceiling at all.
    """

    def dependency(
        request: Request,
        user: Optional[Dict[str, Any]] = Depends(get_current_user_optional),
    ) -> None:
        user_id = (user or {}).get("id")
        if not user_id and not allow_anonymous:
            return
        enforce_actor_limit(
            request,
            bucket=bucket,
            max_calls=max_calls,
            window=window,
            user_id=user_id,
        )

    return dependency


#: Sample capture and video upload. One request writes a file, runs MediaPipe
#: and enqueues a task, so this is the path worth protecting most. A collector
#: in a recording session produces on the order of 100/hour.
limit_upload = rate_limited("upload", settings.rate_limit_upload_per_hour, 3600)

#: Starting or promoting a training run. Each one occupies the trainer container
#: for minutes, so a low ceiling costs nothing legitimate.
limit_training = rate_limited("training", settings.rate_limit_training_per_hour, 3600)

#: Catalogue writes (create/rename/delete a class).
limit_catalog = rate_limited("catalog", settings.rate_limit_catalog_per_hour, 3600)

#: Realtime inference — the ONLY limited endpoint reachable without a session,
#: so the only one that must count anonymous callers. Windowed at a few frames
#: per second during a live demo, hence a per-MINUTE ceiling and a generous one:
#: the point is to make systematic bulk querying of the model (extraction —
#: MITRE ATLAS AML.T0024) expensive, not to interrupt a demo.
limit_predict = rate_limited(
    "predict", settings.rate_limit_predict_per_minute, 60, allow_anonymous=True
)

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ValidationError, root_validator, validator

from app.config import settings

logger = logging.getLogger("realtime_proxy")

router = APIRouter(prefix="/realtime", tags=["realtime"])

# ---------------------------------------------------------------------------
# Module-level state — initialized at application startup via init_client()
# ---------------------------------------------------------------------------
_client: Optional[httpx.AsyncClient] = None
_semaphore: Optional[asyncio.Semaphore] = None


def init_client() -> None:
    """Initialize dedicated httpx client and concurrency semaphore.

    Must be called once at application startup before any requests are served.
    Uses its own timeout config — deliberately NOT shared with upload/training clients.
    """
    global _client, _semaphore

    timeout = httpx.Timeout(
        connect=settings.realtime_connect_timeout,   # 5.0s default
        read=settings.realtime_read_timeout,          # 10.0s default
        write=3.0,                                    # small JSON payload; 3s sufficient
        pool=settings.realtime_connect_timeout,       # 5.0s default
    )
    _client = httpx.AsyncClient(
        timeout=timeout,
        limits=httpx.Limits(
            max_connections=32,
            max_keepalive_connections=8,
            keepalive_expiry=30,  # expire idle sockets; prevents latency spikes
        ),
    )
    _semaphore = asyncio.Semaphore(settings.realtime_max_concurrent)
    logger.info(
        "[REALTIME_PROXY] client initialized url=%s connect_timeout=%.1fs "
        "read_timeout=%.1fs max_concurrent=%d",
        settings.realtime_service_url,
        settings.realtime_connect_timeout,
        settings.realtime_read_timeout,
        settings.realtime_max_concurrent,
    )


async def close_client() -> None:
    """Gracefully close httpx client. Call at application shutdown."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
    logger.info("[REALTIME_PROXY] client closed")


def _get_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("realtime HTTP client not initialized — call init_client() at startup")
    return _client


def _get_semaphore() -> asyncio.Semaphore:
    if _semaphore is None:
        raise RuntimeError("realtime semaphore not initialized — call init_client() at startup")
    return _semaphore


# ---------------------------------------------------------------------------
# Transport-level schemas
# Backend responsibility: shape, finite-value, model_id format.
# Backend does NOT normalize, reorder, interpret semantics, or decode labels.
# ---------------------------------------------------------------------------

class RealtimeProxyRequest(BaseModel):
    request_id: Optional[str] = None  # transport metadata; generated if absent
    model_id: str
    frames: List[List[float]]         # forwarded verbatim — no mutation

    @validator("model_id")
    def model_id_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("model_id must not be empty")
        return v

    @root_validator
    def validate_frames_shape(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        frames = values.get("frames") or []
        if len(frames) != 60:
            raise ValueError(f"frames: expected 60 rows, got {len(frames)}")
        for i, row in enumerate(frames):
            if len(row) != 126:
                raise ValueError(f"frames[{i}]: expected 126 elements, got {len(row)}")
            for j, val in enumerate(row):
                try:
                    f = float(val)
                except (TypeError, ValueError):
                    raise ValueError(f"frames[{i}][{j}]: not a number")
                if f != f:  # NaN
                    raise ValueError(f"frames[{i}][{j}]: NaN not allowed")
                if f == float("inf") or f == float("-inf"):
                    raise ValueError(f"frames[{i}][{j}]: Inf not allowed")
        return values


class RealtimeProxyResponse(BaseModel):
    # request_id is NOT in the response body.
    # It is propagated via X-Request-ID response header only.
    # Reason: request_id is transport metadata — including it in the body
    # would couple FE reducers and caches to an observability field.
    label: str
    confidence: float
    label_key: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/models")
async def proxy_models(response: Response) -> Any:
    """Pure passthrough to inference service /models.

    No caching, mutation, or reordering in backend.
    Cache-Control: no-store prevents stale browser model list.
    """
    client = _get_client()
    try:
        upstream = await client.get(f"{settings.realtime_service_url}/models")
    except httpx.ConnectError:
        logger.error("[REALTIME_PROXY] event=CONNECT_ERROR endpoint=models")
        raise HTTPException(status_code=503, detail="Inference service unavailable")
    except httpx.TimeoutException:
        logger.warning("[REALTIME_PROXY] event=TIMEOUT endpoint=models")
        raise HTTPException(status_code=504, detail="Gateway timeout")

    if upstream.status_code == 200:
        response.headers["Cache-Control"] = "no-store"
        return upstream.json()

    logger.error(
        "[REALTIME_PROXY] event=UPSTREAM_ERROR endpoint=models status=%d",
        upstream.status_code,
    )
    raise HTTPException(status_code=502, detail="Upstream error")


@router.get("/health")
async def proxy_health(response: Response) -> Any:
    """Proxy realtime service health through the backend gateway.

    Keeps frontend traffic behind one consistent public entrypoint.
    """
    client = _get_client()
    try:
        upstream = await client.get(f"{settings.realtime_service_url}/health")
    except httpx.ConnectError:
        logger.error("[REALTIME_PROXY] event=CONNECT_ERROR endpoint=health")
        raise HTTPException(status_code=503, detail="Inference service unavailable")
    except httpx.TimeoutException:
        logger.warning("[REALTIME_PROXY] event=TIMEOUT endpoint=health")
        raise HTTPException(status_code=504, detail="Gateway timeout")

    if upstream.status_code == 200:
        response.headers["Cache-Control"] = "no-store"
        return upstream.json()

    logger.error(
        "[REALTIME_PROXY] event=UPSTREAM_ERROR endpoint=health status=%d",
        upstream.status_code,
    )
    raise HTTPException(status_code=502, detail="Upstream error")


@router.post("/predict", response_model=RealtimeProxyResponse)
async def proxy_predict(request: Request, response: Response) -> RealtimeProxyResponse:
    """Proxy POST /predict to inference service.

    Backend responsibilities (this function):
      - Body size enforcement
      - Transport-level input validation (shape, finite values)
      - request_id generation and propagation
      - Bounded concurrency (semaphore)
      - Timeout enforcement
      - Error mapping
      - Structured logging (never logs raw frames)

    Inference service responsibilities:
      - Normalization
      - Inference
      - Label decoding
      - Confidence computation
      - Semantic contracts
    """
    max_body = settings.realtime_max_body_bytes

    # 1. Fast reject via Content-Length header (before reading body)
    content_length = int(request.headers.get("content-length", 0))
    if content_length > max_body:
        raise HTTPException(status_code=413, detail="Request body too large")

    # 2. Read body ONCE — size-check then parse from same bytes
    raw = await request.body()
    if len(raw) > max_body:
        raise HTTPException(status_code=413, detail="Request body too large")

    # 3. JSON decode (manual — avoids double body read)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON")

    # 4. Transport-level Pydantic validation
    try:
        body = RealtimeProxyRequest(**parsed)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    # 5. Generate request_id if absent
    request_id = (body.request_id or "").strip() or uuid.uuid4().hex
    model_id = body.model_id

    logger.info(
        "[REALTIME_PROXY] req=%s model=%s event=REQUEST",
        request_id, model_id,
    )

    # 6. Bounded concurrency — safety boundary against 30fps FE floods
    elapsed_ms = 0.0
    async with _get_semaphore():
        start_time = time.monotonic()

        # 7. Forward to inference service — frames forwarded verbatim, no mutation
        upstream_payload = {
            "model_id": body.model_id,
            "frames": body.frames,
        }
        upstream_headers = {"X-Request-ID": request_id}

        try:
            upstream = await _get_client().post(
                f"{settings.realtime_service_url}/predict",
                json=upstream_payload,
                headers=upstream_headers,
            )
        except httpx.ConnectError:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "[REALTIME_PROXY] req=%s model=%s event=CONNECT_ERROR latency_ms=%.1f",
                request_id, model_id, elapsed_ms,
            )
            raise HTTPException(status_code=503, detail="Inference service unavailable")
        except httpx.TimeoutException:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.warning(
                "[REALTIME_PROXY] req=%s model=%s event=TIMEOUT latency_ms=%.1f",
                request_id, model_id, elapsed_ms,
            )
            raise HTTPException(status_code=504, detail="Gateway timeout")
        except httpx.HTTPError:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "[REALTIME_PROXY] req=%s model=%s event=HTTP_ERROR latency_ms=%.1f",
                request_id, model_id, elapsed_ms,
            )
            raise HTTPException(status_code=502, detail="Bad gateway")

        elapsed_ms = (time.monotonic() - start_time) * 1000

    # 8. Map upstream status code
    status_code = upstream.status_code

    logger.info(
        "[REALTIME_PROXY] req=%s model=%s event=RESPONSE status=%d latency_ms=%.1f",
        request_id, model_id, status_code, elapsed_ms,
    )

    if status_code == 200:
        try:
            data = upstream.json()
            result = RealtimeProxyResponse(
                label=data["label"],
                confidence=data["confidence"],
                label_key=data["label_key"],
            )
        except (KeyError, ValueError, ValidationError):
            # Upstream returned 200 but body is malformed — upstream bug
            logger.error(
                "[REALTIME_PROXY] req=%s event=MALFORMED_UPSTREAM_RESPONSE",
                request_id,
            )
            raise HTTPException(status_code=502, detail="Bad gateway")

        # Echo request_id in response header ONLY — not in body
        response.headers["X-Request-ID"] = request_id
        return result

    elif status_code == 404:
        # Preserve: meaningful semantic error — FE needs to know model not found
        try:
            detail = upstream.json().get("detail", "Model not found")
        except Exception:
            detail = "Model not found"
        raise HTTPException(status_code=404, detail=detail)

    elif status_code == 422:
        # Preserve: meaningful semantic error — FE needs to know what was invalid
        try:
            detail = upstream.json().get("detail", "Invalid request payload")
        except Exception:
            detail = "Invalid request payload"
        raise HTTPException(status_code=422, detail=detail)

    elif status_code == 503:
        raise HTTPException(status_code=503, detail="Inference service unavailable")

    else:
        # Unexpected upstream status (any other 5xx or unknown) → 502
        # Use sanitized message — never leak upstream internals
        logger.error(
            "[REALTIME_PROXY] req=%s model=%s event=UPSTREAM_ERROR status=%d",
            request_id, model_id, status_code,
        )
        raise HTTPException(status_code=502, detail="Upstream error")

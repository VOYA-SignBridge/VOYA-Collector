#!/usr/bin/env python
"""
STEP 2 TEST SUITE — Backend Proxy Integration
=============================================

Tests the proxy layer at /realtime/models and /realtime/predict.

Design:
  - Isolated test app (realtime_proxy router only — no DB, no auth)
  - httpx.AsyncClient is replaced by a MagicMock in each test
  - No real inference service required
  - No real database required

Run:
  cd e:\\VOYA\\VOYA-Collector\\backend
  python test_step2.py

Expected: 14/14 passed
"""
import asyncio
import json
import os
import sys
from unittest.mock import AsyncMock, MagicMock

# Set env BEFORE importing app modules
os.environ["REALTIME_SERVICE_URL"] = "http://mock-inference:8010"
os.environ["REALTIME_MAX_CONCURRENT"] = "4"
os.environ["REALTIME_MAX_BODY_BYTES"] = str(1 * 1024 * 1024)  # 1MB
os.environ["REALTIME_CONNECT_TIMEOUT"] = "5.0"
os.environ["REALTIME_READ_TIMEOUT"] = "10.0"

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.routers.realtime_proxy as proxy_module
from app.routers.realtime_proxy import router as realtime_router

# ---------------------------------------------------------------------------
# Isolated test app — no DB, no auth, no startup side effects
# ---------------------------------------------------------------------------
test_app = FastAPI()
test_app.include_router(realtime_router)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------
RESULTS = {"passed": 0, "failed": 0}


def log(ok: bool, name: str, detail: str = "") -> None:
    symbol = "✓" if ok else "✗"
    line = f"  {symbol} {name}"
    if detail:
        line += f": {detail}"
    print(line)
    RESULTS["passed" if ok else "failed"] += 1


def valid_frames():
    """60 rows x 126 zeros — valid transport payload."""
    return [[0.0] * 126 for _ in range(60)]


class _MockResponse:
    """Minimal httpx.Response stand-in for mocking."""
    def __init__(self, status_code: int, data=None):
        self.status_code = status_code
        self._data = data if data is not None else {}

    def json(self):
        return self._data


def setup_mock(
    *,
    post_response: _MockResponse = None,
    post_exc: Exception = None,
    get_response: _MockResponse = None,
    get_exc: Exception = None,
) -> MagicMock:
    """Replace proxy module's httpx client with a mock and reset semaphore."""
    mock = MagicMock(spec=httpx.AsyncClient)

    if post_exc is not None:
        mock.post = AsyncMock(side_effect=post_exc)
    elif post_response is not None:
        mock.post = AsyncMock(return_value=post_response)
    else:
        mock.post = AsyncMock(return_value=_MockResponse(200))

    if get_exc is not None:
        mock.get = AsyncMock(side_effect=get_exc)
    elif get_response is not None:
        mock.get = AsyncMock(return_value=get_response)
    else:
        mock.get = AsyncMock(return_value=_MockResponse(200, []))

    proxy_module._client = mock
    proxy_module._semaphore = asyncio.Semaphore(4)
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_proxy_models():
    """GET /realtime/models returns 200 with Cache-Control: no-store."""
    setup_mock(get_response=_MockResponse(200, [{"id": "hoa-de", "name": "Hòa đê"}]))
    with TestClient(test_app) as c:
        r = c.get("/realtime/models")
    ok = r.status_code == 200
    ok = ok and isinstance(r.json(), list)
    ok = ok and r.headers.get("cache-control") == "no-store"
    log(ok, "test_proxy_models", f"status={r.status_code} cache-control={r.headers.get('cache-control')}")


def test_proxy_models_pure_passthrough():
    """GET /realtime/models: backend must not mutate or reorder the upstream response."""
    upstream_data = [{"id": "hoa-de", "name": "Hòa đê", "language": "vn", "dialect": "hoa-de"}]
    setup_mock(get_response=_MockResponse(200, upstream_data))
    with TestClient(test_app) as c:
        r = c.get("/realtime/models")
    returned = r.json()
    ok = r.status_code == 200 and returned == upstream_data
    log(ok, "test_proxy_models_pure_passthrough", f"data_identical={ok}")


def test_proxy_predict_success():
    """POST /realtime/predict with valid payload returns 200."""
    setup_mock(post_response=_MockResponse(200, {
        "label": "hello", "confidence": 0.95, "label_key": "vn_hello"
    }))
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "hoa-de", "frames": valid_frames()})
    ok = r.status_code == 200
    data = r.json()
    ok = ok and {"label", "confidence", "label_key"}.issubset(data.keys())
    ok = ok and "x-request-id" in r.headers       # request_id in header
    ok = ok and "request_id" not in data            # NOT in response body
    log(ok, "test_proxy_predict_success",
        f"status={r.status_code} has_header={'x-request-id' in r.headers} "
        f"request_id_in_body={'request_id' in data}")


def test_proxy_predict_wrong_shape():
    """59 frames (not 60) must be rejected by backend before proxy call."""
    setup_mock()
    frames_59 = [[0.0] * 126 for _ in range(59)]
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "hoa-de", "frames": frames_59})
    ok = r.status_code == 422
    log(ok, "test_proxy_predict_wrong_shape", f"status={r.status_code} (expected 422)")


def test_proxy_predict_wrong_feature_dim():
    """125 elements per frame (not 126) must be rejected by backend."""
    setup_mock()
    frames_125 = [[0.0] * 125 for _ in range(60)]
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "hoa-de", "frames": frames_125})
    ok = r.status_code == 422
    log(ok, "test_proxy_predict_wrong_feature_dim", f"status={r.status_code} (expected 422)")


def test_proxy_predict_nan():
    """Frame containing NaN string (coerced to float NaN) must be rejected → 422."""
    setup_mock()
    frames = [[0.0] * 126 for _ in range(60)]
    frames[0][0] = "nan"  # coerced by Pydantic to float NaN, then caught by root_validator
    raw = json.dumps({"model_id": "hoa-de", "frames": frames}).encode()
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", content=raw, headers={"Content-Type": "application/json"})
    ok = r.status_code == 422
    log(ok, "test_proxy_predict_nan", f"status={r.status_code} (expected 422)")


def test_proxy_predict_inf():
    """Frame containing Inf string (coerced to float Inf) must be rejected → 422."""
    setup_mock()
    frames = [[0.0] * 126 for _ in range(60)]
    frames[5][10] = "inf"  # coerced to float Inf, then caught by root_validator
    raw = json.dumps({"model_id": "hoa-de", "frames": frames}).encode()
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", content=raw, headers={"Content-Type": "application/json"})
    ok = r.status_code == 422
    log(ok, "test_proxy_predict_inf", f"status={r.status_code} (expected 422)")


def test_proxy_predict_empty_model_id():
    """model_id consisting only of whitespace must be rejected → 422."""
    setup_mock()
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "   ", "frames": valid_frames()})
    ok = r.status_code == 422
    log(ok, "test_proxy_predict_empty_model_id", f"status={r.status_code} (expected 422)")


def test_proxy_predict_unknown_model():
    """Unknown model_id: upstream 404 must be preserved in proxy response."""
    setup_mock(post_response=_MockResponse(404, {"detail": "model_id not found: unknown-model"}))
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "unknown-model", "frames": valid_frames()})
    ok = r.status_code == 404
    log(ok, "test_proxy_predict_unknown_model", f"status={r.status_code} (expected 404)")


def test_proxy_predict_timeout():
    """TimeoutException from inference service must map to 504 Gateway Timeout."""
    setup_mock(post_exc=httpx.TimeoutException("read timeout"))
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "hoa-de", "frames": valid_frames()})
    ok = r.status_code == 504
    detail = r.json().get("detail", "")
    log(ok, "test_proxy_predict_timeout", f"status={r.status_code} detail='{detail}'")


def test_proxy_predict_inference_unavailable():
    """ConnectError from inference service must map to 503 (immediate, no retry)."""
    setup_mock(post_exc=httpx.ConnectError("connection refused"))
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "hoa-de", "frames": valid_frames()})
    ok = r.status_code == 503
    # Verify no internal paths leaked in error detail
    detail = r.json().get("detail", "")
    ok = ok and "mock-inference" not in detail  # sanitized
    ok = ok and "traceback" not in detail.lower()
    log(ok, "test_proxy_predict_inference_unavailable",
        f"status={r.status_code} detail_sanitized={'mock-inference' not in detail}")


def test_proxy_predict_large_body():
    """Body exceeding 1MB must be rejected with 413 before proxy call."""
    setup_mock()
    # Build payload > 1MB: model_id is 1.1MB of 'x' characters
    large_payload = json.dumps({
        "model_id": "x" * (1024 * 1024 + 100),
        "frames": [],
    }).encode()
    with TestClient(test_app) as c:
        r = c.post(
            "/realtime/predict",
            content=large_payload,
            headers={"Content-Type": "application/json"},
        )
    ok = r.status_code == 413
    log(ok, "test_proxy_predict_large_body",
        f"status={r.status_code} body_size_bytes={len(large_payload)}")


def test_proxy_request_id_generated():
    """When no request_id is provided, backend generates one and echoes it in X-Request-ID header."""
    setup_mock(post_response=_MockResponse(200, {
        "label": "test", "confidence": 0.9, "label_key": "k"
    }))
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "hoa-de", "frames": valid_frames()})
    ok = r.status_code == 200
    rid = r.headers.get("x-request-id", "")
    ok = ok and len(rid) > 0
    log(ok, "test_proxy_request_id_generated", f"x-request-id='{rid}'")


def test_proxy_request_id_forwarded():
    """When request_id is provided, it must be echoed back in X-Request-ID header."""
    setup_mock(post_response=_MockResponse(200, {
        "label": "test", "confidence": 0.9, "label_key": "k"
    }))
    my_id = "my-request-id-abc123"
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={
            "model_id": "hoa-de",
            "request_id": my_id,
            "frames": valid_frames(),
        })
    ok = r.status_code == 200
    echoed = r.headers.get("x-request-id", "")
    ok = ok and echoed == my_id
    log(ok, "test_proxy_request_id_forwarded", f"expected='{my_id}' echoed='{echoed}'")


def test_request_id_not_in_response_body():
    """request_id must NOT appear in the JSON response body."""
    setup_mock(post_response=_MockResponse(200, {
        "label": "hello", "confidence": 0.8, "label_key": "k"
    }))
    with TestClient(test_app) as c:
        r = c.post("/realtime/predict", json={"model_id": "hoa-de", "frames": valid_frames()})
    ok = r.status_code == 200
    data = r.json()
    ok = ok and "request_id" not in data
    ok = ok and set(data.keys()) == {"label", "confidence", "label_key"}
    log(ok, "test_request_id_not_in_response_body",
        f"body_keys={sorted(data.keys())} request_id_absent={'request_id' not in data}")


def test_backend_starts_without_inference():
    """init_client() must succeed even when inference service is offline.
    Backend startup is never blocked by inference service availability.
    """
    old_client = proxy_module._client
    old_semaphore = proxy_module._semaphore
    new_client = None
    try:
        proxy_module._client = None
        proxy_module._semaphore = None
        proxy_module.init_client()  # must not raise or contact inference
        new_client = proxy_module._client
        ok = new_client is not None and proxy_module._semaphore is not None
        log(ok, "test_backend_starts_without_inference",
            f"client_created={ok}")
    except Exception as exc:
        log(False, "test_backend_starts_without_inference",
            f"{type(exc).__name__}: {exc}")
    finally:
        if new_client is not None and new_client is not old_client:
            asyncio.run(new_client.aclose())
        proxy_module._client = old_client
        proxy_module._semaphore = old_semaphore


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------
TESTS = [
    test_proxy_models,
    test_proxy_models_pure_passthrough,
    test_proxy_predict_success,
    test_proxy_predict_wrong_shape,
    test_proxy_predict_wrong_feature_dim,
    test_proxy_predict_nan,
    test_proxy_predict_inf,
    test_proxy_predict_empty_model_id,
    test_proxy_predict_unknown_model,
    test_proxy_predict_timeout,
    test_proxy_predict_inference_unavailable,
    test_proxy_predict_large_body,
    test_proxy_request_id_generated,
    test_proxy_request_id_forwarded,
    test_request_id_not_in_response_body,
    test_backend_starts_without_inference,
]

if __name__ == "__main__":
    print(f"\n{'=' * 60}")
    print("STEP 2 TEST SUITE: Backend Proxy Integration")
    print(f"{'=' * 60}\n")

    for test_fn in TESTS:
        try:
            test_fn()
        except Exception as exc:
            log(False, test_fn.__name__, f"EXCEPTION: {type(exc).__name__}: {exc}")

    total = RESULTS["passed"] + RESULTS["failed"]
    print(f"\n{'=' * 60}")
    print(f"Results: {RESULTS['passed']}/{total} passed")
    if RESULTS["failed"]:
        print(f"FAILED: {RESULTS['failed']} tests")
        print(f"{'=' * 60}\n")
        sys.exit(1)
    else:
        print("All tests passed.")
        print(f"{'=' * 60}\n")

"""Server-side latency instrumentation for the realtime inference path.

Records three spans per /predict call so preprocessing and inference can be
reported separately rather than as one opaque number:

    normalize_ms      preprocessing (60 frames through normalize_hands_vector_126)
    infer_ms          tensor prep + forward pass + softmax/argmax
    server_total_ms   the whole handler, excluding network and MediaPipe

`normalize_ms` and `infer_ms` are disjoint sub-spans of `server_total_ms`, not a
partition of it: the remainder covers request validation, label decoding and
response construction. Report the total as the total; do not present the two
sub-stages as adding up to it.

End-to-end interaction latency (camera → landmarks → HTTP → render) is NOT
measured here: it belongs to the client. `bench_latency.py` reports both sides so
the two are never conflated.

Kept dependency-free on purpose — the realtime image ships a minimal requirement
set and must not grow a metrics library for this.
"""

from __future__ import annotations

import os
import threading
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List

from fastapi import APIRouter, Request

router = APIRouter()

STAGES = ("normalize_ms", "infer_ms", "server_total_ms")

# Rolling window per (model, stage). Bounded so a long-running service cannot
# grow without limit; percentiles describe recent behaviour, which is what a
# latency claim about a live service should mean.
DEFAULT_WINDOW = 1000


def _window_size() -> int:
    try:
        value = int(os.getenv("LATENCY_WINDOW", "") or DEFAULT_WINDOW)
    except ValueError:
        return DEFAULT_WINDOW
    return value if value > 0 else DEFAULT_WINDOW


class LatencyRecorder:
    """Thread-safe rolling latency statistics.

    /predict is a sync endpoint, so FastAPI runs it in a worker threadpool and
    several threads may record concurrently.
    """

    def __init__(self, window: int | None = None) -> None:
        self._window = window or _window_size()
        self._lock = threading.Lock()
        self._samples: Dict[str, Dict[str, Deque[float]]] = defaultdict(
            lambda: {stage: deque(maxlen=self._window) for stage in STAGES}
        )
        self._counts: Dict[str, int] = defaultdict(int)
        self._devices: Dict[str, str] = {}

    def record(self, model_id: str, timings: Dict[str, float], device: str = "") -> None:
        with self._lock:
            per_stage = self._samples[model_id]
            for stage, value in timings.items():
                if stage in per_stage:
                    per_stage[stage].append(float(value))
            self._counts[model_id] += 1
            if device:
                self._devices[model_id] = device

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            models = {
                model_id: {
                    "requests": self._counts[model_id],
                    "device": self._devices.get(model_id, "unknown"),
                    "stages": {
                        stage: _summarize(list(samples))
                        for stage, samples in per_stage.items()
                    },
                }
                for model_id, per_stage in self._samples.items()
            }
        return {
            "window": self._window,
            "unit": "milliseconds",
            "note": (
                "Server-side only: excludes network, MediaPipe landmark extraction, "
                "and browser render. normalize_ms and infer_ms are disjoint sub-spans "
                "of server_total_ms; the remainder is validation, label decode and "
                "response construction."
            ),
            "models": dict(sorted(models.items())),
        }

    def reset(self) -> None:
        with self._lock:
            self._samples.clear()
            self._counts.clear()
            self._devices.clear()


def _summarize(samples: List[float]) -> Dict[str, Any]:
    n = len(samples)
    if n == 0:
        return {"n": 0}
    ordered = sorted(samples)
    return {
        "n": n,
        "p50": _percentile(ordered, 50),
        "p95": _percentile(ordered, 95),
        "p99": _percentile(ordered, 99),
        "mean": round(sum(ordered) / n, 3),
        "max": round(ordered[-1], 3),
    }


def _percentile(ordered: List[float], pct: float) -> float:
    """Nearest-rank percentile.

    No interpolation: with a modest window the reported value is always an
    observed measurement, which is easier to defend than a synthesized one.
    """
    if not ordered:
        return 0.0
    rank = max(1, min(len(ordered), int(-(-pct / 100.0 * len(ordered) // 1))))
    return round(ordered[rank - 1], 3)


def get_recorder(app_state: Any) -> LatencyRecorder:
    """Return the app's recorder, creating one if startup did not attach it."""
    recorder = getattr(app_state, "latency", None)
    if recorder is None:
        recorder = LatencyRecorder()
        app_state.latency = recorder
    return recorder


@router.get("/metrics")
def metrics(request: Request) -> Dict[str, Any]:
    """Latency percentiles over the recent request window, per model."""
    return get_recorder(request.app.state).snapshot()


@router.post("/metrics/reset")
def reset_metrics(request: Request) -> Dict[str, Any]:
    """Clear the window — call before a benchmark run to isolate its samples.

    Docker-network only, like /reload: not exposed through nginx.
    """
    get_recorder(request.app.state).reset()
    return {"status": "reset"}

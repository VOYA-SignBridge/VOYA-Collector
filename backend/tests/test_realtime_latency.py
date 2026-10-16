"""Unit tests for the realtime latency recorder (backend/realtime_service/app/latency.py).

The recorder feeds the inference-latency numbers reported for the platform, so
the parts that could silently distort those numbers are pinned here: the rolling
window must stay bounded, percentiles must be observed values, and concurrent
recording must not lose samples (/predict is a sync endpoint, so FastAPI serves
it from a threadpool).
"""

from __future__ import annotations

import threading

from realtime_service.app.latency import LatencyRecorder, _percentile, _summarize


def test_percentile_is_nearest_rank_observed_value():
    ordered = [float(x) for x in range(1, 101)]
    assert _percentile(ordered, 50) == 50.0
    assert _percentile(ordered, 95) == 95.0
    assert _percentile(ordered, 99) == 99.0
    # Never interpolates: every reported percentile is a real measurement.
    assert _percentile(ordered, 95) in ordered


def test_percentile_handles_degenerate_inputs():
    assert _percentile([], 95) == 0.0
    assert _percentile([7.0], 50) == 7.0
    assert _percentile([7.0], 99) == 7.0


def test_summarize_empty_stage_reports_no_samples():
    assert _summarize([]) == {"n": 0}


def test_window_is_bounded_but_request_count_is_not():
    recorder = LatencyRecorder(window=5)
    for i in range(1, 11):
        recorder.record("m", {"normalize_ms": i, "infer_ms": i * 2, "server_total_ms": i * 3})

    stats = recorder.snapshot()["models"]["m"]
    # All ten requests are counted...
    assert stats["requests"] == 10
    # ...but only the last five are retained, so memory cannot grow unbounded.
    assert stats["stages"]["infer_ms"]["n"] == 5
    assert stats["stages"]["infer_ms"]["max"] == 20.0


def test_stages_are_tracked_separately_per_model():
    recorder = LatencyRecorder(window=100)
    recorder.record("a", {"infer_ms": 1.0}, device="cpu")
    recorder.record("b", {"infer_ms": 50.0}, device="cuda:0")

    models = recorder.snapshot()["models"]
    assert models["a"]["stages"]["infer_ms"]["p50"] == 1.0
    assert models["b"]["stages"]["infer_ms"]["p50"] == 50.0
    assert models["a"]["device"] == "cpu"
    assert models["b"]["device"] == "cuda:0"


def test_unknown_stage_keys_are_ignored():
    recorder = LatencyRecorder(window=10)
    recorder.record("m", {"infer_ms": 1.0, "not_a_stage": 999.0})

    stages = recorder.snapshot()["models"]["m"]["stages"]
    assert set(stages) == {"normalize_ms", "infer_ms", "server_total_ms"}


def test_concurrent_recording_loses_no_samples():
    recorder = LatencyRecorder(window=100_000)

    def worker():
        for _ in range(2_000):
            recorder.record("m", {"infer_ms": 2.0})

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    stats = recorder.snapshot()["models"]["m"]
    assert stats["requests"] == 16_000
    assert stats["stages"]["infer_ms"]["n"] == 16_000


def test_reset_clears_all_models():
    recorder = LatencyRecorder(window=10)
    recorder.record("m", {"infer_ms": 1.0})
    recorder.reset()
    assert recorder.snapshot()["models"] == {}

#!/usr/bin/env python3
"""Measure realtime inference latency against a running realtime_service.

Reports two things that must not be conflated:

  * **Client-observed latency**  --  request send -> response parsed. Includes HTTP
    and JSON serialization of a 60x126 payload. Still NOT end-to-end interaction
    latency: camera capture, MediaPipe landmark extraction and browser render
    happen upstream of this script.
  * **Server-side stages**  --  normalize / infer / server_total, read from
    /metrics, which the service records per served prediction.

The service is not published to the host by docker-compose (`expose`, not
`ports`), so run this from inside the container:

    docker compose exec realtime_service python bench_latency.py --model-id hoa-de

Synthetic landmark frames are used by default: latency depends on tensor shape,
not on the values, and this keeps the benchmark runnable without participant
data. Pass --frames-from to replay a real .npz sample instead.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List

SEQ_LEN = 60
FEATURE_DIM = 126


def _post(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _get(url: str, timeout: float) -> Dict[str, Any]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _synthetic_frames() -> List[List[float]]:
    """Deterministic non-degenerate frames.

    Values are irrelevant to timing but must be finite and in a plausible range,
    since /predict rejects NaN/Inf.
    """
    return [
        [((t * FEATURE_DIM + d) % 97) / 97.0 for d in range(FEATURE_DIM)]
        for t in range(SEQ_LEN)
    ]


def _frames_from_npz(path: str) -> List[List[float]]:
    import numpy as np  # local import: only needed for this optional path

    with np.load(path, allow_pickle=False) as data:
        for key in ("sequence", "features", "x", "data", "arr_0"):
            if key in data:
                arr = np.asarray(data[key], dtype=float)
                break
        else:
            raise KeyError(f"no recognizable array in {path}")
    if arr.shape != (SEQ_LEN, FEATURE_DIM):
        raise ValueError(f"expected ({SEQ_LEN}, {FEATURE_DIM}), got {arr.shape}")
    return arr.tolist()


def _percentile(ordered: List[float], pct: float) -> float:
    """Nearest-rank percentile  --  matches app/latency.py so both sides agree."""
    if not ordered:
        return 0.0
    rank = max(1, min(len(ordered), int(-(-pct / 100.0 * len(ordered) // 1))))
    return ordered[rank - 1]


def _summary(samples: List[float]) -> str:
    ordered = sorted(samples)
    return (
        f"n={len(ordered)}  "
        f"p50={_percentile(ordered, 50):7.2f}  "
        f"p95={_percentile(ordered, 95):7.2f}  "
        f"p99={_percentile(ordered, 99):7.2f}  "
        f"mean={statistics.fmean(ordered):7.2f}  "
        f"max={ordered[-1]:7.2f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--url", default="http://localhost:8010", help="realtime_service base URL")
    parser.add_argument("--model-id", required=True, help="model_id as listed by /models")
    parser.add_argument("-n", "--requests", type=int, default=1000)
    parser.add_argument("--warmup", type=int, default=50,
                        help="discarded requests before measuring (lazy init, cache warmup)")
    parser.add_argument("--frames-from", default="", help="optional .npz sample to replay")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--out", default="", help="optional JSON destination for the results")
    args = parser.parse_args()

    base = args.url.rstrip("/")
    frames = _frames_from_npz(args.frames_from) if args.frames_from else _synthetic_frames()
    payload = {"model_id": args.model_id, "frames": frames}

    try:
        health = _get(f"{base}/health", args.timeout)
    except urllib.error.URLError as exc:
        print(f"cannot reach {base}/health: {exc}", file=sys.stderr)
        return 2
    available = [m["id"] for m in health.get("models", [])]
    if args.model_id not in available:
        print(f"model_id {args.model_id!r} not loaded; available: {available}", file=sys.stderr)
        return 2

    print(f"target      {base}")
    print(f"model_id    {args.model_id}")
    print(f"payload     {'synthetic' if not args.frames_from else args.frames_from}")
    print(f"warmup      {args.warmup} requests (discarded)")
    print()

    for _ in range(args.warmup):
        _post(f"{base}/predict", payload, args.timeout)

    # Reset AFTER warmup so the server window holds only measured requests.
    try:
        urllib.request.urlopen(
            urllib.request.Request(f"{base}/metrics/reset", data=b"", method="POST"),
            timeout=args.timeout,
        ).read()
    except urllib.error.URLError as exc:
        print(f"warning: could not reset server metrics ({exc}); "
              f"server stages may include warmup", file=sys.stderr)

    client_ms: List[float] = []
    for i in range(args.requests):
        t0 = time.perf_counter()
        _post(f"{base}/predict", payload, args.timeout)
        client_ms.append((time.perf_counter() - t0) * 1000.0)
        if (i + 1) % 200 == 0:
            print(f"  ... {i + 1}/{args.requests}", file=sys.stderr)

    server = _get(f"{base}/metrics", args.timeout)
    model_stats = server.get("models", {}).get(args.model_id, {})

    print("\n=== client-observed (includes HTTP + JSON, excludes camera/MediaPipe) ===")
    print(f"  request_ms        {_summary(client_ms)}")

    print("\n=== server-side stages (from /metrics) ===")
    print(f"  device            {model_stats.get('device', 'unknown')}")
    for stage, stats in (model_stats.get("stages") or {}).items():
        if stats.get("n"):
            print(
                f"  {stage:<18}n={stats['n']}  p50={stats['p50']:7.2f}  "
                f"p95={stats['p95']:7.2f}  p99={stats['p99']:7.2f}  "
                f"mean={stats['mean']:7.2f}  max={stats['max']:7.2f}"
            )

    ordered = sorted(client_ms)
    overhead = _percentile(ordered, 50) - (
        (model_stats.get("stages", {}).get("server_total_ms") or {}).get("p50") or 0.0
    )
    print(f"\n  transport overhead at p50: {overhead:.2f} ms "
          f"(client p50 - server_total p50)")

    if args.out:
        result = {
            "model_id": args.model_id,
            "requests": args.requests,
            "warmup": args.warmup,
            "payload": args.frames_from or "synthetic",
            "client_ms": {
                "n": len(ordered),
                "p50": _percentile(ordered, 50),
                "p95": _percentile(ordered, 95),
                "p99": _percentile(ordered, 99),
                "mean": statistics.fmean(ordered),
                "max": ordered[-1],
            },
            "server": model_stats,
            "note": (
                "client_ms excludes camera capture, MediaPipe landmark extraction and "
                "browser render; it is not end-to-end interaction latency."
            ),
        }
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
        print(f"\nwrote {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

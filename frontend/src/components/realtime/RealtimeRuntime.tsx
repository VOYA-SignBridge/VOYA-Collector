import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Hands } from "@mediapipe/hands";
import { Camera } from "@mediapipe/camera_utils";

import { flattenRealtimeHands, type MediaPipeHandsLikeResults } from "../../utils/realtimeFlatten";
import { RealtimeRingBuffer } from "../../utils/realtimeRingBuffer";
import {
  RealtimeInferenceScheduler,
  type RealtimeSchedulerStatus,
} from "../../utils/realtimeInferenceScheduler";
import { PredictionSmoother } from "../../utils/predictionSmoother";
import {
  realtimePredict,
  type RealtimePredictResponse,
} from "../../api/realtime";

type Props = {
  /** Visual-only mirror for preview. Never affects payload semantics. */
  mirrorPreview?: boolean;
  /** Auto start webcam + MediaPipe on mount. Default: true. */
  autoStart?: boolean;
  /** Debounce interval for inference. Default: 200ms. */
  debounceMs?: number;
};

const parseBoolEnv = (value: unknown, fallback: boolean) => {
  if (typeof value !== "string") return fallback;
  const v = value.trim().toLowerCase();
  if (v === "1" || v === "true" || v === "yes" || v === "on") return true;
  if (v === "0" || v === "false" || v === "no" || v === "off") return false;
  return fallback;
};

// Keep CDN asset version aligned with pinned dependency (matches capture modal).
const MP_HANDS_VERSION = "0.4.1675469240";

export default function RealtimeRuntime({
  mirrorPreview = parseBoolEnv(import.meta.env.VITE_MIRROR_PREVIEW, true),
  autoStart = true,
  debounceMs = 200,
}: Props) {
  // DOM refs
  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Runtime refs (mutable, no rerender)
  const handsRef = useRef<Hands | null>(null);
  const cameraRef = useRef<Camera | null>(null);

  const ringRef = useRef<RealtimeRingBuffer | null>(null);
  const smootherRef = useRef<PredictionSmoother | null>(null);
  const schedulerRef = useRef<RealtimeInferenceScheduler<RealtimePredictResponse> | null>(null);

  // Reusable frame vector scratch (copied into ring buffer each frame).
  const frameScratchRef = useRef<Float32Array | null>(null);

  // Safety: prevent post-unmount work.
  const disposedRef = useRef(false);

  // Prevent double-start / overlapping init.
  const startingRef = useRef(false);
  const startEpochRef = useRef(0);

  // Minimal UI state (only updates on prediction/status/error, not per frame)
  const [running, setRunning] = useState<boolean>(autoStart);
  const [status, setStatus] = useState<RealtimeSchedulerStatus>("idle");
  const [prediction, setPrediction] = useState<{ label: string; confidence: number; samples: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState<boolean>(false);

  const previewStyle = useMemo(() => {
    return mirrorPreview ? ({ transform: "scaleX(-1)" } as const) : undefined;
  }, [mirrorPreview]);

  const stopAll = useCallback(async () => {
    // Ensure start guard is released even if stop happens mid-init.
    startingRef.current = false;
    setIsStarting(false);

    // Dispose scheduler first (prevents callbacks firing after stop).
    try {
      schedulerRef.current?.dispose();
    } catch {
      // ignore
    }
    schedulerRef.current = null;

    // Stop MediaPipe camera loop.
    try {
      cameraRef.current?.stop();
    } catch {
      // ignore
    }
    cameraRef.current = null;

    // Stop underlying webcam tracks.
    const video = videoRef.current;
    if (video?.srcObject) {
      try {
        (video.srcObject as MediaStream).getTracks().forEach((t) => t.stop());
      } catch {
        // ignore
      }
      video.srcObject = null;
    }

    // Close MediaPipe Hands.
    try {
      handsRef.current?.close();
    } catch {
      // ignore
    }
    handsRef.current = null;

    // Clear semantic buffers.
    ringRef.current?.clear();
    smootherRef.current?.reset();

    // Status back to idle.
    setStatus("idle");
  }, []);

  // Ensure cleanup on unmount.
  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
      void stopAll();
    };
  }, [stopAll]);

  // Start/stop runtime based on `running`.
  useEffect(() => {
    if (!running) {
      void stopAll();
      return;
    }

    // Guard: prevent double init (double-click, StrictMode effect re-run, etc.).
    if (startingRef.current) return;
    startingRef.current = true;
    setIsStarting(true);
    const startEpoch = ++startEpochRef.current;

    const video = videoRef.current;
    if (!video) {
      setError("Video element not ready");
      setRunning(false);
      return;
    }

    setError(null);

    // Initialize utilities once per run.
    ringRef.current = new RealtimeRingBuffer({ capacity: 60, featureDim: 126 });
    smootherRef.current = new PredictionSmoother({ historySize: 5, emaAlpha: 0.5 });
    frameScratchRef.current = new Float32Array(126);

    // MediaPipe Hands
    const hands = new Hands({
      locateFile: (file: string) =>
        `https://cdn.jsdelivr.net/npm/@mediapipe/hands@${MP_HANDS_VERSION}/${file}`,
    });

    hands.setOptions({
      maxNumHands: 2,
      modelComplexity: 1,
      refineLandmarks: true,
      minDetectionConfidence: 0.7,
      minTrackingConfidence: 0.75,
    });

    hands.onResults((results: unknown) => {
      if (disposedRef.current) return;

      try {
        const scratch = frameScratchRef.current;
        const ring = ringRef.current;
        const scheduler = schedulerRef.current;

        if (!scratch || !ring) return;

        // RAW encoding only (no mirroring, no swapping, no normalization).
        const vec = flattenRealtimeHands(results as MediaPipeHandsLikeResults, scratch);
        ring.append(vec);

        // Scheduler itself gates on isReady() and inFlight.
        scheduler?.trigger();
      } catch (e) {
        // Encoding/buffer errors should not crash the app.
        // Keep last stable prediction; surface error text.
        const msg = e instanceof Error ? e.message : String(e);
        setError((prev) => (prev === msg ? prev : msg));
      }
    });

    handsRef.current = hands;

    // Inference scheduler
    const provider = {
      isReady: () => ringRef.current?.isReady() ?? false,
      snapshot: () => ringRef.current?.snapshot() ?? new Array(60).fill(0).map(() => new Array(126).fill(0)),
    };

    const scheduler = new RealtimeInferenceScheduler<RealtimePredictResponse>({
      provider,
      debounceMs,
      expectedSeqLen: 60,
      expectedFeatureDim: 126,
      snapshotValidation: "sampled",
      request: async (frames) => {
        const res = await realtimePredict({ frames });
        if (res.ok) return res.data;
        throw new Error(res.error);
      },
      onStatusChange: (s) => {
        if (disposedRef.current) return;
        setStatus(s);
      },
      onPrediction: (pred) => {
        if (disposedRef.current) return;
        const smoother = smootherRef.current;
        if (!smoother) return;

        smoother.pushPrediction(pred.label, pred.confidence);
        const smoothed = smoother.getSmoothed();
        if (smoothed) {
          const next = {
            label: smoothed.label,
            confidence: smoothed.confidence,
            samples: smoothed.samples,
          };

          // Avoid spam/rerenders if nothing materially changed.
          setPrediction((prev) => {
            if (!prev) return next;
            if (prev.label !== next.label) return next;
            if (prev.samples !== next.samples) return next;
            if (Math.abs(prev.confidence - next.confidence) >= 0.01) return next;
            return prev;
          });
        }
      },
      onError: (err) => {
        if (disposedRef.current) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError((prev) => (prev === msg ? prev : msg));
      },
    });

    schedulerRef.current = scheduler;

    // MediaPipe Camera loop: hands.send({image: video})
    const camera = new Camera(video, {
      onFrame: async () => {
        if (disposedRef.current) return;
        try {
          await hands.send({ image: video });
        } catch (e) {
          // hands.send can throw if closed mid-loop
        }
      },
      width: 1280,
      height: 720,
      facingMode: "user",
    });

    cameraRef.current = camera;

    camera
      .start()
      .then(() => {
        if (disposedRef.current) return;
        if (startEpochRef.current !== startEpoch) return;
        startingRef.current = false;
        setIsStarting(false);
        setError(null);
      })
      .catch((e: unknown) => {
        if (disposedRef.current) return;
        if (startEpochRef.current !== startEpoch) return;
        startingRef.current = false;
        setIsStarting(false);
        const msg = e instanceof Error ? e.message : String(e);
        setError(`Camera start failed: ${msg}`);
        setRunning(false);
      });

    return () => {
      void stopAll();
    };
  }, [running, debounceMs, stopAll]);

  const handleStartStop = useCallback(() => {
    if (running) {
      setRunning(false);
      return;
    }

    // Ignore double-start clicks while init is in-flight.
    if (startingRef.current) return;

    setError(null);
    setPrediction(null);
    setRunning(true);
  }, [running]);

  return (
    <div className="card space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-lg font-semibold text-slate-900">Realtime Recognition (Runtime)</div>
          <div className="text-sm text-slate-600">Minimal runtime preview + smoothed prediction</div>
        </div>
        <div className="flex items-center gap-2">
          <button
            className={
              "px-3 py-2 rounded-lg text-sm font-medium border transition-colors " +
              (running
                ? "bg-red-600 text-white border-red-500 hover:bg-red-500"
                : "bg-emerald-600 text-white border-emerald-500 hover:bg-emerald-500")
            }
            onClick={handleStartStop}
            type="button"
            disabled={isStarting}
          >
            {running ? "Stop" : isStarting ? "Starting…" : "Start"}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-xl overflow-hidden border bg-black">
          <video
            ref={videoRef}
            style={previewStyle}
            className="w-full h-auto"
            autoPlay
            playsInline
            muted
          />
        </div>

        <div className="space-y-3">
          <div className="p-3 rounded-xl border bg-white">
            <div className="text-xs text-slate-500">Status</div>
            <div className="text-sm font-medium text-slate-800">{status}</div>
          </div>

          <div className="p-3 rounded-xl border bg-white">
            <div className="text-xs text-slate-500">Prediction (smoothed)</div>
            {prediction ? (
              <div className="text-sm font-semibold text-slate-900">
                {prediction.label}{" "}
                <span className="font-normal text-slate-600">
                  ({Math.round(prediction.confidence * 1000) / 10}% · {prediction.samples} samples)
                </span>
              </div>
            ) : (
              <div className="text-sm text-slate-500">No prediction yet</div>
            )}
          </div>

          <div className="p-3 rounded-xl border bg-white">
            <div className="text-xs text-slate-500">Errors</div>
            <div className="text-sm text-slate-700">{error ?? "None"}</div>
          </div>

          <div className="text-xs text-slate-500">
            Notes: payload uses raw MediaPipe landmarks only; preview mirroring is visual-only.
          </div>
        </div>
      </div>
    </div>
  );
}

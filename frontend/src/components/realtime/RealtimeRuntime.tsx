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
  fetchRealtimeModels,
  type RealtimePredictResponse,
  type RealtimeModel,
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

  // Model management refs (lifetime of component)
  // selectedModelIdRef: always current, read by scheduler closure at request time
  // activeGenerationRef: incremented on model switch, prevents stale responses
  const selectedModelIdRef = useRef<string | null>(null);
  const activeGenerationRef = useRef(0);

  // Minimal UI state (only updates on prediction/status/error/model, not per frame)
  const [running, setRunning] = useState<boolean>(autoStart);
  const [status, setStatus] = useState<RealtimeSchedulerStatus>("idle");
  const [prediction, setPrediction] = useState<{ label: string; confidence: number; samples: number; labelKey: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState<boolean>(false);

  // Model management state
  const [models, setModels] = useState<RealtimeModel[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState<boolean>(true);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [selectedModelId, setSelectedModelId] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);
  const [selectionWarning, setSelectionWarning] = useState<string | null>(null);

  const groupedModels = useMemo(() => {
    const groups = new Map<string, RealtimeModel[]>();
    models.forEach((model) => {
      if (!groups.has(model.language)) {
        groups.set(model.language, []);
      }
      groups.get(model.language)!.push(model);
    });
    return groups;
  }, [models]);

  const languages = useMemo(() => {
    const langs = Array.from(groupedModels.keys());
    return langs.sort((a, b) => a.localeCompare(b));
  }, [groupedModels]);

  const filteredModels = useMemo(() => {
    if (!selectedLanguage) return [];
    return groupedModels.get(selectedLanguage) || [];
  }, [selectedLanguage, groupedModels]);

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

  // Fetch available models on mount (independent of webcam lifecycle)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    let cancelled = false;

    setIsLoadingModels(true);
    setModelsError(null);
    setSelectionWarning(null);

    fetchRealtimeModels().then((res) => {
      if (cancelled) return;

      if (res.ok) {
        setModels(res.data);

        // Check if previously selected model still exists
        const currentModelId = selectedModelIdRef.current;
        const currentModelExists = currentModelId && res.data.some((m) => m.id === currentModelId);

        if (!currentModelExists && currentModelId) {
          // Model disappeared after refresh
          setSelectionWarning(`Model "${currentModelId}" is no longer available. Please select another.`);
          selectedModelIdRef.current = null;
          setSelectedModelId(null);
          setSelectedLanguage(null);
        } else if (currentModelExists) {
          // Selection still valid, keep it
          const currentModel = res.data.find((m) => m.id === currentModelId);
          if (currentModel && !selectedLanguage) {
            setSelectedLanguage(currentModel.language);
          }
        } else if (selectedModelIdRef.current === null && res.data.length > 0) {
          // First load: auto-select first language and first model
          const firstLang = res.data[0].language;
          const firstModel = res.data[0].id;
          selectedModelIdRef.current = firstModel;
          setSelectedModelId(firstModel);
          setSelectedLanguage(firstLang);
        }

        setIsLoadingModels(false);
      } else {
        setModelsError(res.error);
        setIsLoadingModels(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, []);

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

        // RAW webcam coordinates only; flatten handles the required handedness swap.
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
        // Capture generation and model_id at request start time
        const capturedGeneration = activeGenerationRef.current;
        const modelId = selectedModelIdRef.current;

        if (!modelId) {
          throw new Error("No model selected");
        }

        // Fire request
        const res = await realtimePredict({ model_id: modelId, frames });

        // Check if model switched while we were waiting for response
        if (activeGenerationRef.current !== capturedGeneration) {
          // Model changed during this request — drop stale response silently
          throw new Error("[stale_response]");
        }

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
            labelKey: pred.label_key,
          };

          // Avoid spam/rerenders if nothing materially changed.
          setPrediction((prev) => {
            if (!prev) return next;
            if (prev.label !== next.label) return next;
            if (prev.labelKey !== next.labelKey) return next;
            if (prev.samples !== next.samples) return next;
            if (Math.abs(prev.confidence - next.confidence) >= 0.01) return next;
            return prev;
          });
        }
      },
      onError: (err) => {
        if (disposedRef.current) return;
        const msg = err instanceof Error ? err.message : String(err);
        // Silently drop stale responses from previous model
        if (msg === "[stale_response]") return;
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

  const handleModelSelect = useCallback((modelId: string) => {
    // Clear any selection warning when user actively selects a model
    setSelectionWarning(null);
    // Increment generation to drop any in-flight stale responses
    activeGenerationRef.current++;
    // Update ref for scheduler to use on next request
    selectedModelIdRef.current = modelId;
    // Update state for UI
    setSelectedModelId(modelId);
    // Clear stale predictions from previous model
    smootherRef.current?.reset();
    setPrediction(null);
    if (import.meta.env.DEV) {
      console.debug("[realtime] model switched:", modelId);
    }
  }, []);

  const handleLanguageSelect = useCallback(
    (lang: string) => {
      setSelectionWarning(null);
      setSelectedLanguage(lang);

      // ISSUE 2: If current model is already in this language, keep it (don't reselect)
      const currentModelId = selectedModelIdRef.current;
      const currentModel = models.find((m) => m.id === currentModelId);

      if (currentModel && currentModel.language === lang) {
        // Current model is already in this language, no need to reselect
        return;
      }

      // Otherwise, switch to first model in new language
      const firstInLang = groupedModels.get(lang)?.[0];
      if (firstInLang) {
        handleModelSelect(firstInLang.id);
      }
    },
    [models, groupedModels, handleModelSelect]
  );

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

      {/* Model Selector (Language-Aware Two-Stage) */}
      <div className="p-3 rounded-xl border bg-white space-y-3">
        <div className="text-xs font-medium text-slate-700">Select Language & Model</div>

        {/* Selection Warning */}
        {selectionWarning && (
          <div className="p-2 rounded-lg bg-amber-50 border border-amber-200">
            <div className="text-xs text-amber-800">{selectionWarning}</div>
          </div>
        )}

        {/* Error State */}
        {modelsError && (
          <div className="space-y-2">
            <div className="text-sm text-red-600">{modelsError}</div>
            <button
              className="px-3 py-1.5 rounded-lg text-xs font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
              onClick={() => {
                setModelsError(null);
                setIsLoadingModels(true);
                fetchRealtimeModels().then((res) => {
                  if (res.ok) {
                    setModels(res.data);
                    if (res.data.length > 0 && selectedModelIdRef.current === null) {
                      const firstLang = res.data[0].language;
                      const firstModel = res.data[0].id;
                      selectedModelIdRef.current = firstModel;
                      setSelectedModelId(firstModel);
                      setSelectedLanguage(firstLang);
                    }
                    setIsLoadingModels(false);
                  } else {
                    setModelsError(res.error);
                    setIsLoadingModels(false);
                  }
                });
              }}
              type="button"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading State */}
        {isLoadingModels && (
          <div className="text-sm text-slate-600">Loading models…</div>
        )}

        {/* Empty State */}
        {!isLoadingModels && !modelsError && models.length === 0 && (
          <div className="text-sm text-slate-600">No models available</div>
        )}

        {/* Language + Model Selectors */}
        {!isLoadingModels && !modelsError && models.length > 0 && (
          <div className="space-y-2">
            {/* Language Selector */}
            <div>
              <label className="text-xs text-slate-600">Language</label>
              <select
                className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={selectedLanguage || ""}
                onChange={(e) => handleLanguageSelect(e.target.value)}
                disabled={running && isStarting}
              >
                <option value="">-- Select Language --</option>
                {languages.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Selector (Filtered by Language) */}
            {selectedLanguage && (
              <div>
                <label className="text-xs text-slate-600">Model</label>
                {filteredModels.length === 0 ? (
                  <div className="mt-1 px-3 py-2 rounded-lg text-sm text-slate-600 bg-slate-50">
                    No models in selected language
                  </div>
                ) : (
                  <select
                    className="w-full mt-1 px-3 py-2 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    value={selectedModelId || ""}
                    onChange={(e) => handleModelSelect(e.target.value)}
                    disabled={running && isStarting}
                  >
                    <option value="">-- Select Model --</option>
                    {filteredModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name}
                        {model.dialect && model.dialect !== model.name && ` (${model.dialect})`}
                      </option>
                    ))}
                  </select>
                )}
              </div>
            )}
          </div>
        )}
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
              <div className="space-y-1">
                <div className="text-sm font-semibold text-slate-900">
                  {prediction.label}{" "}
                  <span className="font-normal text-slate-600">
                    ({Math.round(prediction.confidence * 1000) / 10}% · {prediction.samples} samples)
                  </span>
                </div>
                <div className="text-xs text-slate-500">
                  Label Key: <span className="font-mono text-slate-700">{prediction.labelKey}</span>
                </div>
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

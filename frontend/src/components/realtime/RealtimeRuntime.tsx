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

  const [showDebug, setShowDebug] = useState(false);

  // Map scheduler status to user-friendly Vietnamese message
  const getFriendlyStatusMessage = (): string => {
    if (!running) return "Chưa bắt đầu";
    if (isStarting) return "Đang khởi động...";
    switch (status) {
      case "idle":
        return "Đang chờ...";
      case "debouncing":
        return "Đang xử lý...";
      case "in_flight":
        return "Đang gửi yêu cầu...";
      default:
        return "Đang xử lý...";
    }
  };

  // Map errors to user-friendly Vietnamese messages (memoized to prevent recomputation)
  const friendlyError = useMemo(() => {
    if (!error) return null;
    if (error.includes("Camera")) return "Vui lòng cấp quyền sử dụng camera";
    if (error.includes("timeout") || error.includes("504")) return "Phản hồi chậm, vui lòng thử lại";
    if (error.includes("503") || error.includes("unavailable")) return "Không thể kết nối hệ thống nhận diện";
    if (error.includes("404") || error.includes("not found")) return "Bộ nhận diện không tồn tại";
    return null;
  }, [error]);

  return (
    <div className="w-full max-w-6xl mx-auto space-y-6 p-4">
      {/* Header */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-slate-900">Nhận diện ngôn ngữ kí hiệu</h1>
        <p className="text-slate-600">Ứng dụng nhận diện ngôn ngữ kí hiệu theo thời gian thực</p>
      </div>

      {/* Model Selection */}
      <div className="bg-white rounded-xl border border-slate-200 p-4 space-y-3 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-900">Cấu hình nhận diện</h2>

        {/* Selection Warning */}
        {selectionWarning && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
            <div className="text-sm text-amber-800">{selectionWarning}</div>
          </div>
        )}

        {/* Error State */}
        {modelsError && (
          <div className="space-y-2">
            <div className="text-sm text-red-700">Không thể tải danh sách bộ nhận diện</div>
            <button
              className="px-4 py-2 rounded-lg text-sm font-medium bg-red-100 text-red-700 hover:bg-red-200 transition-colors"
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
              Thử lại
            </button>
          </div>
        )}

        {/* Loading State */}
        {isLoadingModels && (
          <div className="text-sm text-slate-600">Đang tải bộ nhận diện...</div>
        )}

        {/* Empty State */}
        {!isLoadingModels && !modelsError && models.length === 0 && (
          <div className="text-sm text-slate-600">Không có bộ nhận diện khả dụng</div>
        )}

        {/* Language + Model Selectors */}
        {!isLoadingModels && !modelsError && models.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Language Selector */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-2">Ngôn ngữ</label>
              <select
                className="w-full px-3 py-2.5 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                value={selectedLanguage || ""}
                onChange={(e) => handleLanguageSelect(e.target.value)}
                disabled={!running && isStarting}
              >
                <option value="">-- Chọn ngôn ngữ --</option>
                {languages.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Selector (Filtered by Language) */}
            <div>
              <label className="block text-xs font-medium text-slate-700 mb-2">Bộ nhận diện</label>
              {!selectedLanguage ? (
                <div className="px-3 py-2.5 rounded-lg text-sm text-slate-500 bg-slate-50">
                  Chọn ngôn ngữ trước
                </div>
              ) : filteredModels.length === 0 ? (
                <div className="px-3 py-2.5 rounded-lg text-sm text-slate-500 bg-slate-50">
                  Không có bộ nhận diện cho ngôn ngữ này
                </div>
              ) : (
                <select
                  className="w-full px-3 py-2.5 rounded-lg border border-slate-300 bg-white text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  value={selectedModelId || ""}
                  onChange={(e) => handleModelSelect(e.target.value)}
                  disabled={!running && isStarting}
                >
                  <option value="">-- Chọn bộ nhận diện --</option>
                  {filteredModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name}
                      {model.dialect && model.dialect !== model.name && ` (${model.dialect})`}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Camera Preview (Left/Top) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="rounded-2xl overflow-hidden border border-slate-200 bg-black shadow-sm aspect-[4/5] lg:aspect-video">
            <video
              ref={videoRef}
              style={previewStyle}
              className="w-full h-full object-contain"
              autoPlay
              playsInline
              muted
            />
          </div>

          {/* Error Message (if any) — only show when error stable */}
          {friendlyError && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 animate-in fade-in duration-300">
              <p className="text-sm text-red-800">{friendlyError}</p>
            </div>
          )}
        </div>

        {/* Right Panel: Prediction + Controls */}
        <div className="space-y-4">
          {/* Prediction Display (PROMINENT) */}
          <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-blue-50 to-white p-6 shadow-sm">
            <div className="text-xs font-medium text-slate-600 uppercase tracking-wide mb-3">
              Kết quả nhận diện
            </div>
            <div className="min-h-[140px] flex flex-col justify-center">
              {prediction ? (
                <div className="space-y-3">
                  <div className="text-4xl sm:text-5xl font-bold text-blue-600 text-center break-words line-clamp-2">
                    {prediction.label}
                  </div>
                  <div className="space-y-2 text-center">
                    <div className="text-sm text-slate-600">
                      Độ tin cậy: <span className="font-semibold text-slate-900">{Math.round(prediction.confidence * 100)}%</span>
                    </div>
                    {import.meta.env.DEV && (
                      <div className="text-xs text-slate-500">
                        {prediction.samples} mẫu
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <div className="text-4xl text-slate-300 mb-2">–</div>
                  <div className="text-sm text-slate-500">
                    {running ? "Chờ dữ liệu..." : "Chưa bắt đầu"}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Status Indicator */}
          <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${
                running && status === "in_flight" ? "bg-green-500" :
                running && status === "debouncing" ? "bg-yellow-500" :
                running ? "bg-blue-500" : "bg-slate-300"
              }`} />
              <div className="text-xs text-slate-600">{getFriendlyStatusMessage()}</div>
            </div>
          </div>

          {/* Start/Stop Button (LARGE & PROMINENT) */}
          <button
            className={
              "w-full py-3 rounded-xl text-base font-semibold border transition-all " +
              (running
                ? "bg-red-600 text-white border-red-600 hover:bg-red-700 active:scale-95"
                : "bg-emerald-600 text-white border-emerald-600 hover:bg-emerald-700 active:scale-95")
            }
            onClick={handleStartStop}
            type="button"
            disabled={isStarting}
          >
            {running ? "Dừng nhận diện" : isStarting ? "Đang khởi động..." : "Bắt đầu nhận diện"}
          </button>

          {/* Optional: Debug Toggle (DEV only) */}
          {import.meta.env.DEV && (
            <button
              className="w-full py-2 rounded-lg text-xs font-medium border border-slate-300 text-slate-600 hover:bg-slate-50 transition-colors"
              onClick={() => setShowDebug(!showDebug)}
              type="button"
            >
              {showDebug ? "Ẩn thông tin kỹ thuật" : "Hiện thông tin kỹ thuật"}
            </button>
          )}
        </div>
      </div>

      {/* Debug Panel (DEV mode, collapsible) */}
      {import.meta.env.DEV && showDebug && (
        <div className="rounded-xl border border-slate-300 bg-slate-50 p-4 space-y-2 text-xs font-mono text-slate-700">
          <div className="text-xs font-semibold text-slate-900 mb-2">Thông tin kỹ thuật</div>
          <div>Status: <span className="text-slate-600">{status}</span></div>
          <div>Model ID: <span className="text-slate-600">{selectedModelId ?? "none"}</span></div>
          <div>Generation: <span className="text-slate-600">{activeGenerationRef.current}</span></div>
          {prediction && (
            <div>Label Key: <span className="text-slate-600 font-normal">{prediction.labelKey}</span></div>
          )}
          {error && (
            <div className="mt-2 text-red-600">Raw Error: {error}</div>
          )}
        </div>
      )}
    </div>
  );
}

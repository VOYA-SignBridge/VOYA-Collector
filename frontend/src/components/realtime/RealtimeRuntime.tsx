/**
 * AI Studio: DO NOT copy patterns from this file into new components.
 *
 * Anti-patterns present here (all replaced by shared primitives in src/components/ui/):
 *
 *  ❌ Raw <button> with full inline Tailwind string (lines ~503, ~532)
 *     → Use: import Button from "../ui/Button"
 *
 *  ❌ Raw <w-2 h-2 rounded-full bg-sky-600> status dots (lines ~550–555)
 *     → Use: import Badge from "../ui/Badge" with variant="success"|"warning"|etc.
 *
 *  ❌ Inline bg-amber-50 / bg-red-50 error divs (lines ~465–480)
 *     → Use: import ErrorBanner from "../ErrorBanner"
 *
 *  ❌ Plain text "Đang tải bộ nhận diện..." loading state (line ~490)
 *     → Use: import LoadingSpinner from "../ui/LoadingSpinner"
 *
 *  ❌ Inline <select> with repeated conditional Tailwind classes (lines ~510–530)
 *     → Use: import Select from "../ui/Select"
 *
 * These anti-patterns are retained here for backward compatibility only.
 * All new AI Studio components must use the shared ui/ primitives.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Hands } from "@mediapipe/hands";
import { Camera } from "@mediapipe/camera_utils";

import { flattenRealtimeHands, type MediaPipeHandsLikeResults } from "../../utils/realtimeFlatten";
import { HAND_TRACKING_OPTIONS, MP_HANDS_VERSION } from "../../config/handTracking";
import type { HandAnchors } from "../../utils/handIdentity";
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
import { fetchTTSAudio, prewarmTTS } from "../../api/tts";
import PageHeader from "../ui/PageHeader";
import Button from "../ui/Button";
import { useI18n } from "../../i18n";

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

// Extraction settings and CDN asset version come from the shared contract in
// config/handTracking.ts so serving can never drift from how the corpus was
// recorded. Do not re-declare them here.

// Server-side TTS voice options
const TTS_VOICES = [
  // @i18n-key-table — `label` là KHOÁ, dịch ở chỗ dựng `t(voice.label)`.
  { id: "vi-VN-HoaiMyNeural", label: "HoaiMy (Nữ)", gender: "female" as const },
  { id: "vi-VN-NamMinhNeural", label: "NamMinh (Nam)", gender: "male" as const },
] as const;
const TTS_DEFAULT_VOICE = "vi-VN-HoaiMyNeural";

// Speak once the smoothed confidence reaches this bar (user-chosen: 85%).
const SPEAK_CONFIDENCE_THRESHOLD = 0.85;
// Warm the TTS audio cache as soon as a label is this likely — well before it
// crosses the speak threshold — so playback is instant instead of waiting
// ~780ms for edge-tts synthesis on the first utterance of a word.
const TTS_PREFETCH_THRESHOLD = 0.5;
// Debounce between a stable prediction and speaking. Was 600ms (felt laggy);
// prefetch now hides synthesis latency, so a short debounce is enough to avoid
// speaking on transient flicker.
const TTS_DEBOUNCE_MS = 200;

export default function RealtimeRuntime({
  mirrorPreview = parseBoolEnv(import.meta.env.VITE_MIRROR_PREVIEW, true),
  autoStart = true,
  // Measured (bench_latency.py, hoa-de, CPU): server_total p50 5.6 ms, client
  // -observed p50 21 ms / p95 25 ms. At 60 ms the next trigger still fires well
  // after the previous reply, so the scheduler's single-in-flight guard almost
  // never has to skip — and the smoother (historySize 2) settles a label in
  // ~2 cycles, i.e. ~170 ms instead of ~250 ms at the old 100 ms.
  debounceMs = 60,
}: Props) {
  const { t } = useI18n();
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
  // Left/right identity carried across frames, mirroring what the capture modal
  // does. Reset whenever a run starts so a new session never inherits stale
  // wrist positions from the previous one.
  const handAnchorsRef = useRef<HandAnchors>({});

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
  const [speechEnabled, setSpeechEnabled] = useState<boolean>(() => {
    try {
      const stored = localStorage.getItem("realtimeSpeechEnabled");
      if (stored === null) return true;
      return stored === "1" || stored === "true";
    } catch {
      return true;
    }
  });
  const [ttsVoiceId, setTtsVoiceId] = useState<string>(() => {
    try {
      return localStorage.getItem("realtimeTtsVoiceId") || TTS_DEFAULT_VOICE;
    } catch {
      return TTS_DEFAULT_VOICE;
    }
  });

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

  // Server-side TTS refs
  const ttsTimerRef = useRef<number | null>(null);
  const lastSpokenLabelRef = useRef<string | null>(null);
  const ttsAudioRef = useRef<HTMLAudioElement | null>(null);
  // Client-side blob cache: labelKey:voiceId → objectURL
  const ttsBlobCacheRef = useRef<Map<string, string>>(new Map());
  // In-flight fetches keyed by cacheKey → promise, so a prefetch and the actual
  // speak share ONE network request (and speak can await an in-flight prefetch).
  const ttsFetchingRef = useRef<Map<string, Promise<void>>>(new Map());

  useEffect(() => {
    try {
      localStorage.setItem("realtimeSpeechEnabled", speechEnabled ? "1" : "0");
    } catch {
      // ignore persistence errors
    }
  }, [speechEnabled]);

  useEffect(() => {
    try {
      localStorage.setItem("realtimeTtsVoiceId", ttsVoiceId);
    } catch {
      // ignore persistence errors
    }
  }, [ttsVoiceId]);

  // Cleanup TTS resources on unmount
  useEffect(() => {
    return () => {
      // Revoke all cached blob URLs to prevent memory leaks
      ttsBlobCacheRef.current.forEach((url) => URL.revokeObjectURL(url));
      ttsBlobCacheRef.current.clear();
      if (ttsTimerRef.current !== null) {
        window.clearTimeout(ttsTimerRef.current);
        ttsTimerRef.current = null;
      }
      if (ttsAudioRef.current) {
        ttsAudioRef.current.pause();
        ttsAudioRef.current = null;
      }
    };
  }, []);

  // Fetch + cache the TTS audio for a label (no playback). Deduplicates
  // concurrent requests so a prefetch and the actual speak share one fetch;
  // callers can await the returned promise to be sure the blob is cached.
  const warmTts = useCallback((labelKey: string, label: string): Promise<void> => {
    const cacheKey = `${labelKey}:${ttsVoiceId}`;
    if (ttsBlobCacheRef.current.has(cacheKey)) return Promise.resolve();
    const inflight = ttsFetchingRef.current.get(cacheKey);
    if (inflight) return inflight;

    const p = (async () => {
      const blob = await fetchTTSAudio(label, ttsVoiceId);
      if (blob) {
        const url = URL.createObjectURL(blob);
        ttsBlobCacheRef.current.set(cacheKey, url);
        // Evict oldest entry if the cache grows past 100.
        if (ttsBlobCacheRef.current.size > 100) {
          const firstKey = ttsBlobCacheRef.current.keys().next().value;
          if (firstKey) {
            const oldUrl = ttsBlobCacheRef.current.get(firstKey);
            if (oldUrl) URL.revokeObjectURL(oldUrl);
            ttsBlobCacheRef.current.delete(firstKey);
          }
        }
      }
    })().finally(() => {
      ttsFetchingRef.current.delete(cacheKey);
    });

    ttsFetchingRef.current.set(cacheKey, p);
    return p;
  }, [ttsVoiceId]);

  // Server-side TTS: fetch audio from backend and play
  useEffect(() => {
    if (!running || !speechEnabled || !prediction) {
      if (ttsTimerRef.current !== null) {
        window.clearTimeout(ttsTimerRef.current);
        ttsTimerRef.current = null;
      }
      if (ttsAudioRef.current) {
        ttsAudioRef.current.pause();
      }
      return;
    }

    const normalizedLabel = prediction.label.trim();

    // Prefetch: warm the audio cache as soon as a label is reasonably likely,
    // BEFORE it crosses the speak threshold, so playback is instant when it does.
    if (normalizedLabel.length > 0 && prediction.confidence >= TTS_PREFETCH_THRESHOLD) {
      void warmTts(prediction.labelKey, normalizedLabel);
    }

    const shouldSpeak = normalizedLabel.length > 0 && prediction.confidence >= SPEAK_CONFIDENCE_THRESHOLD;

    if (!shouldSpeak) {
      if (ttsTimerRef.current !== null) {
        window.clearTimeout(ttsTimerRef.current);
        ttsTimerRef.current = null;
      }
      return;
    }

    if (lastSpokenLabelRef.current === prediction.labelKey) {
      return;
    }

    if (ttsTimerRef.current !== null) {
      window.clearTimeout(ttsTimerRef.current);
    }

    ttsTimerRef.current = window.setTimeout(async () => {
      if (!speechEnabled || !running) return;
      const currentPrediction = prediction;
      const label = currentPrediction.label.trim();
      if (!label || currentPrediction.confidence < SPEAK_CONFIDENCE_THRESHOLD) return;
      if (lastSpokenLabelRef.current === currentPrediction.labelKey) return;

      const cacheKey = `${currentPrediction.labelKey}:${ttsVoiceId}`;

      try {
        // Stop any currently playing audio
        if (ttsAudioRef.current) {
          ttsAudioRef.current.pause();
          ttsAudioRef.current.currentTime = 0;
        }

        // Usually already warmed by the prefetch above; await guarantees the
        // blob is cached (joining any in-flight prefetch, not double-fetching).
        if (!ttsBlobCacheRef.current.has(cacheKey)) {
          await warmTts(currentPrediction.labelKey, label);
        }
        const audioUrl = ttsBlobCacheRef.current.get(cacheKey);
        if (!audioUrl) return;

        const audio = new Audio(audioUrl);
        audio.volume = 1;
        ttsAudioRef.current = audio;

        audio.onended = () => {
          lastSpokenLabelRef.current = currentPrediction.labelKey;
        };
        audio.onerror = () => {
          lastSpokenLabelRef.current = null;
        };

        await audio.play();
      } catch {
        lastSpokenLabelRef.current = null;
      } finally {
        ttsTimerRef.current = null;
      }
    }, TTS_DEBOUNCE_MS);

    return () => {
      if (ttsTimerRef.current !== null) {
        window.clearTimeout(ttsTimerRef.current);
        ttsTimerRef.current = null;
      }
    };
  }, [prediction, running, speechEnabled, ttsVoiceId, selectedLanguage, warmTts]);

  // Prewarm the backend TTS cache for the WHOLE selected model's vocabulary so
  // the first utterance of each sign is a cache hit (~105ms) instead of a cold
  // ~780ms synthesis — for every user. Fires on model/voice change (covers the
  // auto-selected model too); the backend skips already-cached labels, so
  // repeat calls are cheap.
  useEffect(() => {
    if (!selectedModelId) return;
    const model = models.find((m) => m.id === selectedModelId);
    if (!model) return;
    void prewarmTTS(model.language, model.dialect, [ttsVoiceId]);
  }, [selectedModelId, ttsVoiceId, models]);

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

    if (ttsTimerRef.current !== null) {
      window.clearTimeout(ttsTimerRef.current);
      ttsTimerRef.current = null;
    }
    if (ttsAudioRef.current) {
      ttsAudioRef.current.pause();
      ttsAudioRef.current = null;
    }

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
  useEffect(() => {
    let cancelled = false;

    setIsLoadingModels(true);
    setModelsError(null);
    setSelectionWarning(null);

    console.log("[realtime] Starting to fetch models from /api/v1/realtime/models");

    fetchRealtimeModels().then((res) => {
      if (cancelled) return;

      if (res.ok) {
        console.log("[realtime] Models loaded successfully:", res.data.length, "models", res.data);
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
          console.log("[realtime] Auto-selected model:", firstModel, "language:", firstLang);
        }

        setIsLoadingModels(false);
      } else {
        console.error("[realtime] Models fetch FAILED:", res.error);
        setModelsError(res.error);
        setIsLoadingModels(false);
      }
    });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Start/stop runtime based on `running`.
  useEffect(() => {
    if (!running) {
      void stopAll();
      lastSpokenLabelRef.current = null;
      return;
    }

    // Guard: prevent double init (double-click, StrictMode effect re-run, etc.).
    if (startingRef.current) return;
    startingRef.current = true;
    setIsStarting(true);
    const startEpoch = ++startEpochRef.current;

    const video = videoRef.current;
    if (!video) {
      setError(t("Chưa mở được khung hình camera. Hãy thử lại."));
      setRunning(false);
      return;
    }

    setError(null);
    lastSpokenLabelRef.current = null;

    // Initialize utilities once per run.
    // minReadyFrames: 40 allows inference to start after ~0.67s instead of 1s (60 frames)
    // Ring buffer still stores full 60 frames with zero-padding for initial frames
    ringRef.current = new RealtimeRingBuffer({ capacity: 60, featureDim: 126, minReadyFrames: 40 });
    smootherRef.current = new PredictionSmoother({ historySize: 2, emaAlpha: 0.7 });
    frameScratchRef.current = new Float32Array(126);
    handAnchorsRef.current = {};

    // MediaPipe Hands
    const hands = new Hands({
      locateFile: (file: string) =>
        `https://cdn.jsdelivr.net/npm/@mediapipe/hands@${MP_HANDS_VERSION}/${file}`,
    });

    // Shared contract — must stay identical to the capture modal. Realtime used
    // to run modelComplexity 0 with 0.6/0.65, i.e. a different landmark network
    // and stricter tracking than the one that produced the training corpus.
    hands.setOptions({ ...HAND_TRACKING_OPTIONS });

    hands.onResults((results: unknown) => {
      if (disposedRef.current) return;

      try {
        const scratch = frameScratchRef.current;
        const ring = ringRef.current;
        const scheduler = schedulerRef.current;

        if (!scratch || !ring) return;

        const mpResults = results as MediaPipeHandsLikeResults;
        const hasHands = mpResults?.multiHandLandmarks && mpResults.multiHandLandmarks.length > 0;

        if (!hasHands) {
          // No hands detected: clear ring buffer to reset on next hand detection.
          // Anchors are left alone — they expire on their own, so a hand lost for
          // a frame or two still resolves back into the slot it came from.
          ring.clear();
          return;
        }

        // flatten applies the handedness swap, the cross-frame identity lock and
        // the x mirror, so the vector matches how the corpus was recorded.
        const vec = flattenRealtimeHands(mpResults, scratch, {
          anchors: handAnchorsRef.current,
        });
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
          throw new Error(t("Chưa chọn mô hình nhận dạng."));
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
      width: 960,
      height: 540,
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
        setError(t("Không khởi động được camera: {msg}", { msg }));
        setRunning(false);
      });

    return () => {
      void stopAll();
    };
  }, [running, debounceMs, stopAll]);

  const canSwitchModel = useCallback((): boolean => {
    // If scheduler doesn't exist (not running), can always switch
    if (!schedulerRef.current) {
      return true;
    }

    // ✅ SAFETY CHECK 1: Cannot switch if inference is in-flight
    if (schedulerRef.current.isInFlight()) {
      if (import.meta.env.DEV) {
        console.debug("[realtime] cannot switch model: inference in-flight");
      }
      return false;
    }

    // ✅ SAFETY CHECK 2: Cannot switch if scheduler is debouncing or processing
    const schedulerStatus = schedulerRef.current.getStatus();
    if (schedulerStatus !== "idle") {
      if (import.meta.env.DEV) {
        console.debug("[realtime] cannot switch model: scheduler status is", schedulerStatus);
      }
      return false;
    }

    return true;
  }, []);

  const handleModelSelect = useCallback((modelId: string) => {
    // ✅ SAFETY CHECK: Verify we can switch before proceeding
    if (!canSwitchModel()) {
      setSelectionWarning(t("Không thể thay đổi bộ nhận diện khi đang xử lý. Vui lòng chờ đến khi xong."));
      return;
    }

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
  }, [canSwitchModel]);

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
    if (!running) return t("Chưa bắt đầu");
    if (isStarting) return t("Đang khởi động...");
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
    <div className="w-full max-w-6xl mx-auto space-y-2.5 sm:space-y-4 p-2.5 sm:p-4 lg:p-5">
      {/* Header */}
      <PageHeader
        title={t("Nhận diện ngôn ngữ kí hiệu")}
        subtitle={t("Ứng dụng nhận diện ngôn ngữ kí hiệu theo thời gian thực")}
        breadcrumb={[{ label: "Dashboard", href: "/" }, t("Nhận dạng realtime")]}
      />

      {/* Model Selection */}
      <div className="bg-white rounded-xl border border-slate-200 p-2.5 sm:p-4 space-y-2 sm:space-y-3 shadow-sm">
        <h2 className="text-xs sm:text-sm font-semibold text-slate-900">{t("Cấu hình nhận diện")}</h2>

        {/* Selection Warning */}
        {selectionWarning && (
          <div className="p-3 rounded-lg bg-amber-50 border border-amber-200">
            <div className="text-sm text-amber-800">{selectionWarning}</div>
          </div>
        )}

        {/* Error State */}
        {modelsError && (
          <div className="space-y-2">
            <div className="text-sm text-red-700">{t("Không thể tải danh sách bộ nhận diện")}</div>
            <Button
              size="sm"
              variant="secondary"
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
              {t("Thử lại")}
            </Button>
          </div>
        )}

        {/* Loading State */}
        {isLoadingModels && (
          <div className="text-sm text-slate-600">{t("Đang tải bộ nhận diện...")}</div>
        )}

        {/* Empty State */}
        {!isLoadingModels && !modelsError && models.length === 0 && (
          <div className="text-sm text-slate-600">{t("Không có bộ nhận diện khả dụng")}</div>
        )}

        {/* Language + Model Selectors */}
        {!isLoadingModels && !modelsError && models.length > 0 && (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-2 sm:gap-4">
            {/* Language Selector */}
            <div>
              <label className="block text-[11px] font-medium text-slate-700 mb-1.5">{t("Ngôn ngữ")}</label>
              <select
                className={`w-full px-2.5 py-2 rounded-lg border text-xs sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:border-transparent transition-all ${running && (isStarting || !canSwitchModel())
                  ? "bg-slate-100 border-slate-300 text-slate-500 cursor-not-allowed opacity-60"
                  : "border-slate-300 bg-white focus:ring-ctu-blue"
                  }`}
                value={selectedLanguage || ""}
                onChange={(e) => handleLanguageSelect(e.target.value)}
                disabled={running && (isStarting || !canSwitchModel())}
                title={running && !canSwitchModel() ? t("Không thể thay đổi khi đang xử lý") : ""}
              >
                <option value="">{t("-- Chọn ngôn ngữ --")}</option>
                {languages.map((lang) => (
                  <option key={lang} value={lang}>
                    {lang}
                  </option>
                ))}
              </select>
            </div>

            {/* Model Selector (Filtered by Language) */}
            <div>
              <label className="block text-[11px] font-medium text-slate-700 mb-1.5">{t("Bộ nhận diện")}</label>
              {!selectedLanguage ? (
                <div className="px-2.5 py-2 rounded-lg text-xs sm:text-sm text-slate-500 bg-slate-50">
                  {t("Chọn ngôn ngữ trước")}
                </div>
              ) : filteredModels.length === 0 ? (
                <div className="px-2.5 py-2 rounded-lg text-xs sm:text-sm text-slate-500 bg-slate-50">
                  {t("Không có bộ nhận diện cho ngôn ngữ này")}
                </div>
              ) : (
                <select
                  className={`w-full px-2.5 py-2 rounded-lg border text-xs sm:text-sm text-slate-900 focus:outline-none focus:ring-2 focus:border-transparent transition-all ${running && (isStarting || !canSwitchModel())
                    ? "bg-slate-100 border-slate-300 text-slate-500 cursor-not-allowed opacity-60"
                    : "border-slate-300 bg-white focus:ring-ctu-blue"
                    }`}
                  value={selectedModelId || ""}
                  onChange={(e) => handleModelSelect(e.target.value)}
                  disabled={running && (isStarting || !canSwitchModel())}
                  title={running && !canSwitchModel() ? t("Không thể thay đổi khi đang xử lý") : ""}
                >
                  <option value="">{t("-- Chọn bộ nhận diện --")}</option>
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 sm:gap-4 lg:gap-6">
        {/* Camera Preview (Left/Top) */}
        <div className="lg:col-span-2 space-y-3 sm:space-y-4">
          <div className="relative rounded-2xl overflow-hidden border border-slate-200 bg-black shadow-sm aspect-video">
            <video
              ref={videoRef}
              style={previewStyle}
              className="w-full h-full object-cover"
              autoPlay
              playsInline
              muted
            />

            {/* Live caption: mirrors the result panel directly on the feed, so the
                answer is visible without looking away from the camera. */}
            {running && prediction && (
              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent px-3 pb-3 pt-8 sm:px-5 sm:pb-4">
                <div className="text-center text-lg font-bold text-white drop-shadow line-clamp-1 sm:text-3xl">
                  {prediction.label}
                </div>
                <div className="mt-0.5 text-center text-[11px] text-white/80 sm:text-sm">
                  {Math.round(prediction.confidence * 100)}%
                </div>
              </div>
            )}
          </div>

          {/* Status + Start/Stop: the primary controls live right under the video so
              they're reachable without scrolling past the result panel on mobile. */}
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-2.5 sm:p-3 shadow-sm">
            <div className={`w-2 h-2 rounded-full shrink-0 ${running && status === "in_flight" ? "bg-sky-600" :
              running && status === "debouncing" ? "bg-yellow-500" :
                running ? "bg-ctu-blue" : "bg-slate-300"
              }`} />
            <div className="text-xs text-slate-600">{getFriendlyStatusMessage()}</div>
          </div>

          <button
            className={
              "w-full py-2.5 rounded-xl text-sm sm:text-base font-semibold border transition-all " +
              (running
                ? "bg-red-600 text-white border-red-600 hover:bg-red-700 active:scale-95"
                : "bg-sky-600 text-white border-sky-600 hover:bg-sky-700 active:scale-95")
            }
            onClick={handleStartStop}
            type="button"
            disabled={isStarting}
          >
            {running ? t("Dừng nhận diện") : isStarting ? t("Đang khởi động...") : t("Bắt đầu nhận diện")}
          </button>

          {/* Error Message (if any) — only show when error stable */}
          {friendlyError && (
            <div className="p-3 rounded-lg bg-red-50 border border-red-200 animate-in fade-in duration-300">
              <p className="text-sm text-red-800">{friendlyError}</p>
            </div>
          )}
        </div>

        {/* Right Panel: Prediction detail + speech settings */}
        <div className="space-y-2.5 sm:space-y-4">
          {/* Prediction Display (detail) */}
          <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-ctu-blue/5 to-white p-3 sm:p-6 shadow-sm">
            <div className="text-[11px] sm:text-xs font-medium text-slate-600 uppercase tracking-wide mb-2 sm:mb-3">
              {t("Kết quả nhận diện")}
            </div>
            <div className="min-h-[88px] sm:min-h-[112px] flex flex-col justify-center">
              {prediction ? (
                <div className="space-y-2 sm:space-y-3">
                  <div className="text-2xl sm:text-4xl lg:text-5xl font-bold text-ctu-blue text-center break-words line-clamp-2">
                    {prediction.label}
                  </div>
                  <div className="space-y-2 text-center">
                    <div className="text-[11px] sm:text-sm text-slate-600">
                      {t("Độ tin cậy:")} <span className="font-semibold text-slate-900">{Math.round(prediction.confidence * 100)}%</span>
                    </div>
                    {import.meta.env.DEV && (
                      <div className="text-xs text-slate-500">
                        {t("{n} mẫu", { n: prediction.samples })}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div className="text-center">
                  <div className="text-4xl text-slate-300 mb-2">–</div>
                  <div className="text-sm text-slate-500">
                    {running ? t("Chờ dữ liệu...") : t("Chưa bắt đầu")}
                  </div>
                </div>
              )}
            </div>
            <div className="mt-3 flex items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white/80 px-3 py-2">
              <div className="min-w-0">
                <div className="text-xs font-medium text-slate-700">{t("Đọc kết quả thành tiếng")}</div>
              </div>
              <button
                type="button"
                onClick={() => setSpeechEnabled((prev) => !prev)}
                className={`relative inline-flex h-8 w-14 items-center rounded-full transition-colors ${speechEnabled ? "bg-sky-600" : "bg-slate-300"
                  }`}
                aria-pressed={speechEnabled}
                aria-label={speechEnabled ? t("Tắt đọc kết quả thành tiếng") : t("Bật đọc kết quả thành tiếng")}
              >
                <span
                  className={`inline-block h-6 w-6 transform rounded-full bg-white shadow transition-transform ${speechEnabled ? "translate-x-7" : "translate-x-1"
                    }`}
                />
              </button>
            </div>

            {speechEnabled && (
              <div className="mt-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <label className="mb-1.5 block text-[11px] font-medium text-slate-700">{t("Giọng đọc")}</label>
                <div className="flex gap-2">
                  {TTS_VOICES.map((voice) => (
                    <button
                      key={voice.id}
                      type="button"
                      onClick={() => {
                        setTtsVoiceId(voice.id);
                        lastSpokenLabelRef.current = null;
                      }}
                      className={`flex-1 rounded-lg border px-3 py-2 text-xs sm:text-sm font-medium transition-all ${ttsVoiceId === voice.id
                        ? "border-ctu-blue bg-ctu-blue/10 text-ctu-blue ring-1 ring-ctu-blue"
                        : "border-slate-300 bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                    >
                      <div className="flex items-center justify-center gap-1.5">
                        <span>{t(voice.label)}</span>
                      </div>
                    </button>
                  ))}
                </div>

              </div>
            )}
          </div>

          {/* Optional: Debug Toggle (DEV only) */}
          {import.meta.env.DEV && (
            <Button
              variant="secondary"
              className="w-full justify-center"
              onClick={() => setShowDebug(!showDebug)}
              type="button"
            >
              {showDebug ? t("Ẩn thông tin kỹ thuật") : t("Hiện thông tin kỹ thuật")}
            </Button>
          )}
        </div>
      </div>

      {/* Debug Panel (DEV mode, collapsible) */}
      {import.meta.env.DEV && showDebug && (
        <div className="rounded-xl border border-slate-300 bg-slate-50 p-3 sm:p-4 space-y-2 text-[11px] sm:text-xs font-mono text-slate-700">
          <div className="text-xs font-semibold text-slate-900 mb-2">{t("Thông tin kỹ thuật")}</div>
          <div>{t("Trạng thái:")} <span className="text-slate-600">{status}</span></div>
          <div>{t("Mã mô hình:")} <span className="text-slate-600">{selectedModelId ?? t("chưa chọn")}</span></div>
          <div>{t("Thế hệ:")} <span className="text-slate-600">{activeGenerationRef.current}</span></div>
          {prediction && (
            <div>{t("Khoá nhãn:")} <span className="text-slate-600 font-normal">{prediction.labelKey}</span></div>
          )}
          {error && (
            <div className="mt-2 text-red-600">
              {t("Lỗi kỹ thuật: {chi_tiet}", { chi_tiet: error })}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

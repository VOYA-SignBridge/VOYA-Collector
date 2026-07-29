import { useEffect, useRef, useState } from 'react';
import { Hands } from '@mediapipe/hands';
import { Camera } from '@mediapipe/camera_utils';
import axiosClient from '../../../api/axiosClient';

import { flattenRealtimeHands, type MediaPipeHandsLikeResults } from '../../../utils/realtimeFlatten';
import { RealtimeRingBuffer } from '../../../utils/realtimeRingBuffer';
import {
  RealtimeInferenceScheduler,
  type RealtimeSchedulerStatus,
} from '../../../utils/realtimeInferenceScheduler';
import { PredictionSmoother } from '../../../utils/predictionSmoother';
import { HAND_TRACKING_OPTIONS, MP_HANDS_VERSION } from '../../../config/handTracking';
import type { HandAnchors } from '../../../utils/handIdentity';

interface TestTrainedModelModalProps {
  isOpen: boolean;
  onClose: () => void;
  modelId: string; // training_<job_id>
}

export default function TestTrainedModelModal({
  isOpen,
  onClose,
  modelId,
}: TestTrainedModelModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const handsRef = useRef<Hands | null>(null);
  const cameraRef = useRef<Camera | null>(null);
  const ringRef = useRef<RealtimeRingBuffer | null>(null);
  const smootherRef = useRef<PredictionSmoother | null>(null);
  const schedulerRef = useRef<RealtimeInferenceScheduler<{ label: string; confidence: number; label_key: string }> | null>(null);
  const frameScratchRef = useRef<Float32Array | null>(null);
  const handAnchorsRef = useRef<HandAnchors>({});
  const disposedRef = useRef(false);
  const startingRef = useRef(false);
  const startEpochRef = useRef(0);
  const activeGenerationRef = useRef(0);

  const [running, setRunning] = useState(true);
  const [status, setStatus] = useState<RealtimeSchedulerStatus>('idle');
  const [prediction, setPrediction] = useState<{ label: string; confidence: number } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isStarting, setIsStarting] = useState(false);

  const stopAll = async () => {
    startingRef.current = false;
    setIsStarting(false);

    try {
      schedulerRef.current?.dispose();
    } catch {
      //
    }
    schedulerRef.current = null;

    try {
      cameraRef.current?.stop();
    } catch {
      //
    }
    cameraRef.current = null;

    const video = videoRef.current;
    if (video?.srcObject) {
      try {
        (video.srcObject as MediaStream).getTracks().forEach((t) => t.stop());
      } catch {
        //
      }
      video.srcObject = null;
    }

    try {
      handsRef.current?.close();
    } catch {
      //
    }
    handsRef.current = null;

    ringRef.current?.clear();
    smootherRef.current?.reset();

    setStatus('idle');
  };

  // Cleanup on unmount
  useEffect(() => {
    disposedRef.current = false;
    return () => {
      disposedRef.current = true;
      void stopAll();
    };
  }, []);

  // Start/stop based on running state and modal open
  useEffect(() => {
    if (!isOpen || !running) {
      void stopAll();
      return;
    }

    if (startingRef.current) return;
    startingRef.current = true;
    setIsStarting(true);
    const startEpoch = ++startEpochRef.current;

    const video = videoRef.current;
    if (!video) {
      setError('Video element not ready');
      setRunning(false);
      return;
    }

    setError(null);

    // Initialize
    ringRef.current = new RealtimeRingBuffer({ capacity: 60, featureDim: 126, minReadyFrames: 40 });
    smootherRef.current = new PredictionSmoother({ historySize: 2, emaAlpha: 0.7 });
    frameScratchRef.current = new Float32Array(126);
    handAnchorsRef.current = {};

    const hands = new Hands({
      locateFile: (file: string) =>
        `https://cdn.jsdelivr.net/npm/@mediapipe/hands@${MP_HANDS_VERSION}/${file}`,
    });

    // Shared contract — this modal exists to preview how a trained model will
    // behave, so it must extract exactly as capture and realtime do.
    hands.setOptions({ ...HAND_TRACKING_OPTIONS });

    hands.onResults((results: unknown) => {
      if (disposedRef.current) return;

      try {
        const scratch = frameScratchRef.current;
        const ring = ringRef.current;
        const scheduler = schedulerRef.current;
        const canvas = canvasRef.current;

        if (!scratch || !ring) return;

        const mpResults = results as MediaPipeHandsLikeResults;
        const hasHands = mpResults?.multiHandLandmarks && mpResults.multiHandLandmarks.length > 0;

        // Draw hand skeleton + prediction text on canvas
        if (canvas && mpResults) {
          const ctx = canvas.getContext('2d');
          if (ctx) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (hasHands && mpResults.multiHandLandmarks) {
              const w = canvas.width;
              const h = canvas.height;

              mpResults.multiHandLandmarks.forEach((landmarks: any[]) => {
                // Draw connections (skeleton)
                const connections = [
                  [0, 1], [1, 2], [2, 3], [3, 4],
                  [0, 5], [5, 6], [6, 7], [7, 8],
                  [0, 9], [9, 10], [10, 11], [11, 12],
                  [0, 13], [13, 14], [14, 15], [15, 16],
                  [0, 17], [17, 18], [18, 19], [19, 20],
                ];

                ctx.strokeStyle = '#00ff00';
                ctx.lineWidth = 2;
                connections.forEach(([start, end]) => {
                  if (landmarks[start] && landmarks[end]) {
                    const x1 = landmarks[start].x * w;
                    const y1 = landmarks[start].y * h;
                    const x2 = landmarks[end].x * w;
                    const y2 = landmarks[end].y * h;
                    ctx.beginPath();
                    ctx.moveTo(x1, y1);
                    ctx.lineTo(x2, y2);
                    ctx.stroke();
                  }
                });

                // Draw joints
                ctx.fillStyle = '#00ff00';
                landmarks.forEach((lm: any) => {
                  const x = lm.x * w;
                  const y = lm.y * h;
                  ctx.beginPath();
                  ctx.arc(x, y, 3, 0, 2 * Math.PI);
                  ctx.fill();
                });
              });
            }

            // Draw prediction text if available
            if (prediction) {
              const fontSize = 28;
              ctx.font = `bold ${fontSize}px Arial, sans-serif`;
              const text = `${prediction.label} (${Math.round(prediction.confidence * 100)}%)`;
              const padding = 8;
              const x = 10;
              const y = fontSize + 10;

              // Text background (black with opacity)
              ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
              const metrics = ctx.measureText(text);
              ctx.fillRect(x - padding, y - fontSize + padding, metrics.width + padding * 2, fontSize + padding);

              // Text
              ctx.fillStyle = '#00ff00';
              ctx.fillText(text, x, y);
            }
          }
        }

        if (!hasHands) {
          ring.clear();
          return;
        }

        const vec = flattenRealtimeHands(mpResults, scratch, {
          anchors: handAnchorsRef.current,
        });
        ring.append(vec);
        scheduler?.trigger();
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setError((prev) => (prev === msg ? prev : msg));
      }
    });

    handsRef.current = hands;

    const provider = {
      isReady: () => ringRef.current?.isReady() ?? false,
      snapshot: () =>
        ringRef.current?.snapshot() ?? new Array(60).fill(0).map(() => new Array(126).fill(0)),
    };

    const scheduler = new RealtimeInferenceScheduler<{ label: string; confidence: number; label_key: string }>({
      provider,
      debounceMs: 100,
      expectedSeqLen: 60,
      expectedFeatureDim: 126,
      snapshotValidation: 'sampled',
      request: async (frames) => {
        const capturedGeneration = activeGenerationRef.current;

        // Extract job ID from modelId (format: training_<job_id>)
        const jobId = modelId.replace('training_', '');

        const response = await axiosClient.post(
          `/api/v1/training/jobs/${jobId}/predict`,
          { frames },
        );

        if (activeGenerationRef.current !== capturedGeneration) {
          throw new Error('[stale_response]');
        }

        return response.data;
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
          setPrediction((prev) => {
            if (!prev) return { label: smoothed.label, confidence: smoothed.confidence };
            if (prev.label !== smoothed.label) return { label: smoothed.label, confidence: smoothed.confidence };
            if (Math.abs(prev.confidence - smoothed.confidence) >= 0.01) return { label: smoothed.label, confidence: smoothed.confidence };
            return prev;
          });
        }
      },
      onError: (err) => {
        if (disposedRef.current) return;
        const msg = err instanceof Error ? err.message : String(err);
        if (msg === '[stale_response]') return;
        setError((prev) => (prev === msg ? prev : msg));
      },
    });

    schedulerRef.current = scheduler;

    const camera = new Camera(video, {
      onFrame: async () => {
        if (disposedRef.current) return;
        try {
          await hands.send({ image: video });
        } catch (e) {
          //
        }
      },
      width: 960,
      height: 540,
      facingMode: 'user',
    });

    cameraRef.current = camera;

    // Setup canvas size
    const canvas = canvasRef.current;
    if (canvas && video) {
      const updateCanvasSize = () => {
        canvas.width = video.offsetWidth;
        canvas.height = video.offsetHeight;
      };
      updateCanvasSize();
      window.addEventListener('resize', updateCanvasSize);
    }

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
  }, [isOpen, running, modelId]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">🧪 Test Model Realtime</h2>
          <button
            onClick={() => {
              setRunning(false);
              onClose();
            }}
            className="text-slate-400 hover:text-slate-600 text-2xl leading-none"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6 space-y-4">
          {/* Camera Preview with Hand Skeleton */}
          <div className="rounded-xl overflow-hidden border border-slate-200 bg-black aspect-video relative">
            <video
              ref={videoRef}
              className="w-full h-full object-cover"
              autoPlay
              playsInline
              muted
            />
            <canvas
              ref={canvasRef}
              className="absolute inset-0 w-full h-full"
            />
          </div>

          {/* Prediction Display */}
          <div className="rounded-xl border border-slate-200 bg-gradient-to-br from-ctu-blue/10 to-white p-4">
            <div className="text-xs font-medium text-slate-600 uppercase tracking-wide mb-3">
              Kết quả nhận diện
            </div>
            {prediction ? (
              <div className="space-y-2">
                <div className="text-3xl font-bold text-ctu-blue break-words">
                  {prediction.label}
                </div>
                <div className="text-sm text-slate-600">
                  Độ tin cậy: <span className="font-semibold">{Math.round(prediction.confidence * 100)}%</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-4">
                <div className="text-2xl text-slate-300 mb-2">–</div>
                <div className="text-sm text-slate-500">
                  {running ? 'Chờ dữ liệu...' : 'Chưa bắt đầu'}
                </div>
              </div>
            )}
          </div>

          {/* Status */}
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-3">
            <div
              className={`w-2 h-2 rounded-full ${
                running && status === 'in_flight'
                  ? 'bg-green-500'
                  : running && status === 'debouncing'
                    ? 'bg-yellow-500'
                    : running
                      ? 'bg-ctu-blue'
                      : 'bg-slate-300'
              }`}
            />
            <div className="text-xs text-slate-600">
              {!running ? 'Chưa bắt đầu' : isStarting ? 'Đang khởi động...' : 'Đang xử lý...'}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 p-3">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 flex gap-3">
          <button
            onClick={() => setRunning(!running)}
            className={`flex-1 py-2 rounded-lg font-medium transition-colors ${
              running
                ? 'bg-red-600 text-white hover:bg-red-700'
                : 'bg-emerald-600 text-white hover:bg-emerald-700'
            }`}
          >
            {running ? 'Dừng' : 'Bắt đầu'}
          </button>
          <button
            onClick={() => {
              setRunning(false);
              onClose();
            }}
            className="flex-1 py-2 rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50 transition-colors font-medium"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}

import { useEffect, useRef, useState, useCallback } from "react";
import { Hands, HAND_CONNECTIONS } from "@mediapipe/hands";
import { Camera } from "@mediapipe/camera_utils";
import * as drawing from "@mediapipe/drawing_utils";
import Button from "./ui/Button";
import Badge from "./ui/Badge";
import type { MediaPipeLandmark, CameraInfo, QualityInfo } from "../types";

import { TARGET_FRAMES, CAPTURE_COUNT, FRAME_INTERVAL_MS } from "../config/capture";
import SpeechInputButton from "./SpeechInputButton";
import AddDialectModal from "./AddDialectModal";

// ---------------------------------------------------------------------------
// Module-level constants — stable across renders, safe in hook dep arrays.
// ---------------------------------------------------------------------------
const FIXED_TARGET_FRAMES = TARGET_FRAMES;
const FIXED_CAPTURE_COUNT = CAPTURE_COUNT;

// FIX (type): Moved CaptureFrame type out of the component body so it is not
// re-evaluated on every render.
type CaptureFrame = {
  left_hand: MediaPipeLandmark[];
  right_hand: MediaPipeLandmark[];
  timestamp_ms?: number;
  fallback_used?: boolean;
  confidence?: number;
};

const parseBoolEnv = (value: unknown, fallback: boolean) => {
  if (typeof value !== "string") return fallback;
  const v = value.trim().toLowerCase();
  if (v === "1" || v === "true" || v === "yes" || v === "on") return true;
  if (v === "0" || v === "false" || v === "no" || v === "off") return false;
  return fallback;
};

// Default to selfie-style mirroring (front camera). Override with VITE_MIRROR_PREVIEW=0.
const MIRROR_PREVIEW = parseBoolEnv(import.meta.env.VITE_MIRROR_PREVIEW, false);

// FIX (handedness): When @mediapipe/camera_utils sends raw (unflipped) video
// frames to MediaPipe Hands, the model — which was trained on mirrored selfie
// images — returns handedness labels from the CAMERA's perspective, which is
// the OPPOSITE of the person's:
//
//   MediaPipe "Left"  → user's actual RIGHT hand  (for front/mirrored camera)
//   MediaPipe "Right" → user's actual LEFT hand
//
// We must swap the labels so `left_hand` / `right_hand` in saved data matches
// the person's anatomy.  Set VITE_SWAP_HANDEDNESS=0 to disable if your setup
// sends pre-mirrored frames to MediaPipe (e.g., a rear-facing camera).
const SWAP_HANDEDNESS = parseBoolEnv(
  import.meta.env.VITE_SWAP_HANDEDNESS,
  true  
);

// Enable verbose hand diagnostics: set VITE_DEBUG_HANDS=1
const DEBUG_HANDS = parseBoolEnv(import.meta.env.VITE_DEBUG_HANDS, false);

// Keep CDN asset version aligned with pinned npm dependency.
const MP_HANDS_VERSION = "0.4.1675469240";

// ---------------------------------------------------------------------------
// Camera error → Vietnamese message
// ---------------------------------------------------------------------------
function getCameraErrorMessage(error: unknown): string {
  const err = error as Record<string, unknown> | null;
  const errorName = err?.name || "Unknown";
  const errorMessage = String(err?.message || error);

  console.warn(`Camera error [${errorName}]: ${errorMessage}`);

  if (errorName === "NotAllowedError" || errorName === "PermissionDenied")
    return "Camera bị từ chối. Vui lòng cấp quyền truy cập camera trong cài đặt trình duyệt.";
  if (errorName === "NotFoundError" || errorName === "DevicesNotFoundError")
    return "Không tìm thấy camera. Vui lòng kiểm tra xem camera có được kết nối và không bị sử dụng bởi ứng dụng khác.";
  if (errorName === "NotReadableError" || errorName === "TrackStartError")
    return "Không thể khởi động camera. Camera có thể bị sử dụng bởi ứng dụng khác hoặc bị hỏng.";
  if (errorName === "OverconstrainedError" || errorName === "ConstraintError")
    return "Không thể đạt được cấu hình camera yêu cầu. Vui lòng thử lại hoặc sử dụng trình duyệt khác.";
  if (errorName === "TypeError" && errorMessage.includes("Invalid constraint"))
    return "Cấu hình camera không hợp lệ. Vui lòng làm mới trang.";
  if (errorName === "SecurityError")
    return "Lỗi bảo mật khi truy cập camera. Trang phải được cấp quyền HTTPS.";
  if (errorMessage.toLowerCase().includes("no video input device"))
    return "Không có thiết bị camera nào được tìm thấy. Vui lòng kiểm tra kết nối phần cứng.";

  return `Lỗi camera: ${errorMessage}`;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------
interface FullscreenCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSampleCapture: (
    frames: Array<{ left_hand: MediaPipeLandmark[]; right_hand: MediaPipeLandmark[] }>,
    label: string,
    user: string,
    meta?: { camera_info?: CameraInfo; quality_info?: QualityInfo; dialect?: string }
  ) => void;
  initialLabel?: string;
  initialUser?: string;
  targetFrames?: number;
  captureCount?: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function FullscreenCaptureModal({
  isOpen,
  onClose,
  onSampleCapture,
  initialLabel = "",
  initialUser = "",
  targetFrames = 60,
  captureCount = 1,
}: FullscreenCaptureModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef<Camera | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const [recording, setRecording] = useState(false);
  const [frames, setFrames] = useState<CaptureFrame[]>([]);
  const [label, setLabel] = useState(initialLabel);
  const [user, setUser] = useState(initialUser);
  const [dialect, setDialect] = useState<string>("Bắc");
  const [dialectList, setDialectList] = useState<string[]>(["Bắc", "Trung", "Nam", "Cần Thơ"]);
  const [countdown, setCountdown] = useState(0);
  const [isReady, setIsReady] = useState(false);
  const [paused, setPaused] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);

  const [currentCaptureIndex, setCurrentCaptureIndex] = useState(0);
  const [completedCaptures, setCompletedCaptures] = useState(0);
  const [showTips, setShowTips] = useState(false);
  const [showGuide, setShowGuide] = useState(false);
  const [expectedHandsOption, setExpectedHandsOption] = useState<number | null>(null);
  const expectedHandsOptionRef = useRef<number | null>(expectedHandsOption);
  useEffect(() => { expectedHandsOptionRef.current = expectedHandsOption; }, [expectedHandsOption]);

  const [mode, setMode] = useState<"IDLE" | "COUNTDOWN" | "RECORD">("IDLE");
  const [handsVisible, setHandsVisible] = useState(false);
  const [showAddDialectModal, setShowAddDialectModal] = useState(false);
  const [recentUsers, setRecentUsers] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem("recentSigners");
      const parsed = raw ? JSON.parse(raw) : [];
      if (Array.isArray(parsed)) return parsed.filter((x) => typeof x === "string").slice(0, 5);
    } catch { /* ignore */ }
    return [];
  });

  // -------------------------------------------------------------------------
  // Refs (prevent stale closures in MediaPipe callbacks)
  // -------------------------------------------------------------------------
  const recordingRef = useRef(false);
  const pausedRef = useRef(false);
  const framesRef = useRef<CaptureFrame[]>([]);
  const expectedHandsRef = useRef<number | null>(null);
  const modeRef = useRef<typeof mode>(mode);
  const labelRef = useRef(label);
  const userRef = useRef(user);
  const dialectRef = useRef(dialect);
  const targetFramesRef = useRef(targetFrames);
  const onSampleCaptureRef = useRef(onSampleCapture);
  const handleCloseRef = useRef<() => void>(() => {});
  const completedCapturesRef = useRef(0);
  const lastFrameTimeRef = useRef(0);
  const frameIntervalMs = useRef(FRAME_INTERVAL_MS);

  // FIX (backup timer): Use a ref so the 30-second backup timer fires only
  // once, not on every re-render while countdown===0 && recording.
  const backupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // -------------------------------------------------------------------------
  // Sync state → refs
  // -------------------------------------------------------------------------
  useEffect(() => { recordingRef.current = recording; }, [recording]);
  useEffect(() => { pausedRef.current = paused; }, [paused]);
  useEffect(() => { framesRef.current = frames; }, [frames]);
  useEffect(() => { labelRef.current = label; }, [label]);
  useEffect(() => { dialectRef.current = dialect; }, [dialect]);
  useEffect(() => { userRef.current = user; }, [user]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { onSampleCaptureRef.current = onSampleCapture; }, [onSampleCapture]);
  useEffect(() => { completedCapturesRef.current = completedCaptures; }, [completedCaptures]);
  useEffect(() => { targetFramesRef.current = FIXED_TARGET_FRAMES; }, [targetFrames]);


  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------
  const rememberUser = useCallback((name: string) => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setRecentUsers((prev) => {
      const next = [trimmed, ...prev.filter((x) => x !== trimmed)].slice(0, 5);
      try { localStorage.setItem("recentSigners", JSON.stringify(next)); } catch { /* ignore */ }
      return next;
    });
  }, []);

  const handleSetExpectedHands = useCallback((v: number | null) => {
    setExpectedHandsOption(v);
    expectedHandsOptionRef.current = v;
  }, []);

  const computeQuality = useCallback((capturedFrames: Array<{ left_hand: MediaPipeLandmark[]; right_hand: MediaPipeLandmark[] }>) => {
    let totalHandLandmarks = 0;
    let framesWithHands = 0;
    let framesAccepted = 0;
    let confidenceSum = 0;
    let confidenceCount = 0;

    for (const f of capturedFrames) {
      const leftCount = (f.left_hand || []).length;
      const rightCount = (f.right_hand || []).length;
      const handCount = leftCount + rightCount;
      totalHandLandmarks += handCount;
      if (handCount > 0) { framesWithHands++; framesAccepted++; }

      for (const lm of [...(f.left_hand || []), ...(f.right_hand || [])]) {
        if (typeof lm.visibility === "number") { confidenceSum += lm.visibility; confidenceCount++; }
      }
    }

    const quality: QualityInfo = {
      framesCollected: capturedFrames.length,
      framesAccepted,
      avgPoseLandmarksPerFrame: capturedFrames.length ? totalHandLandmarks / capturedFrames.length : 0,
      percentFramesWithHands: capturedFrames.length ? (framesWithHands / capturedFrames.length) * 100 : 0,
      confidenceSummary: confidenceCount ? { avg: confidenceSum / confidenceCount } : undefined,
    };
    return quality;
  }, []);

  // -------------------------------------------------------------------------
  // Canvas / render helpers
  // -------------------------------------------------------------------------
  const pendingRenderRef = useRef(false);
  const renderDataRef = useRef<{
    leftHandLandmarks?: MediaPipeLandmark[];
    rightHandLandmarks?: MediaPipeLandmark[];
    image?: HTMLImageElement | HTMLVideoElement;
  } | null>(null);

  const renderAlpha = 0.6;

  const renderPrevRef = useRef<Record<string, MediaPipeLandmark>>({});

  const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

  const getRenderLandmarks = useCallback((raw: MediaPipeLandmark[] | undefined, group = "pose") => {
    if (!raw) return [] as MediaPipeLandmark[];
    const prev = renderPrevRef.current;
    const alpha = Math.max(0, Math.min(1, renderAlpha));
    const maxChange = 1.0;
    return raw.map((lm, idx) => {
      const key = `${group}.${idx}`;
      const prevLm = prev[key];
      const tx = lm.x ?? 0, ty = lm.y ?? 0, tz = lm.z ?? 0;
      const tv = typeof lm.visibility === "number" ? lm.visibility : undefined;
      if (!prevLm) { const nl = { ...lm } as MediaPipeLandmark; prev[key] = nl; return nl; }
      let nx = lerp(prevLm.x ?? tx, tx, alpha);
      let ny = lerp(prevLm.y ?? ty, ty, alpha);
      const dx = Math.abs((prevLm.x ?? tx) - tx), dy = Math.abs((prevLm.y ?? ty) - ty);
      if (dx > maxChange) nx = (prevLm.x ?? tx) + Math.sign(tx - (prevLm.x ?? tx)) * maxChange;
      if (dy > maxChange) ny = (prevLm.y ?? ty) + Math.sign(ty - (prevLm.y ?? ty)) * maxChange;
      const nz = lerp(prevLm.z ?? tz, tz, alpha);
      const nv = typeof tv === "number" ? lerp((prevLm.visibility as number) ?? tv, tv, alpha) : (prevLm.visibility as number | undefined);
      const out: MediaPipeLandmark = { ...lm, x: nx, y: ny, z: nz, visibility: typeof nv === "number" ? nv : undefined };
      prev[key] = out;
      return out;
    });
  }, [renderAlpha]);

  const PRESENCE_HISTORY_SIZE = 7;
  const leftPresenceHistoryRef = useRef<boolean[]>([]);
  const rightPresenceHistoryRef = useRef<boolean[]>([]);
  const visibilityStateRef = useRef<{ left: boolean; right: boolean }>({ left: false, right: false });
  const lastRenderedLeftRef = useRef<MediaPipeLandmark[] | undefined>(undefined);
  const lastRenderedRightRef = useRef<MediaPipeLandmark[] | undefined>(undefined);

  const renderLandmarks = useCallback(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    const data = renderDataRef.current;
    if (!canvas || !data) return;

    const ctx = canvas.getContext("2d", { alpha: false });
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    if (MIRROR_PREVIEW) { ctx.translate(canvas.width, 0); ctx.scale(-1, 1); }

    if (video && video.readyState >= 2 && video.videoWidth > 0)
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    else if (data.image)
      ctx.drawImage(data.image, 0, 0, canvas.width, canvas.height);

    if (data.leftHandLandmarks) {
      // @ts-expect-error - HAND_CONNECTIONS types not exported in this version
      drawing.drawConnectors(ctx, data.leftHandLandmarks, HAND_CONNECTIONS, { color: "#FF6B35", lineWidth: 2 });
      drawing.drawLandmarks(ctx, data.leftHandLandmarks, { color: "#FF6B35", radius: 5 });
    }
    if (data.rightHandLandmarks) {
      // @ts-expect-error - HAND_CONNECTIONS types not exported in this version
      drawing.drawConnectors(ctx, data.rightHandLandmarks, HAND_CONNECTIONS, { color: "#4ECDC4", lineWidth: 2 });
      drawing.drawLandmarks(ctx, data.rightHandLandmarks, { color: "#4ECDC4", radius: 5 });
    }
    ctx.restore();

    // HUD (debug overlay)
    if (DEBUG_HANDS) {
      try {
        const hudPadding = 8;
        const vis = visibilityStateRef.current;
        const lines = [
          `MODE: ${modeRef.current}`,
          `HANDS: ${((data.leftHandLandmarks?.length ?? 0) > 0 ? 1 : 0) + ((data.rightHandLandmarks?.length ?? 0) > 0 ? 1 : 0)}`,
          `FRAMES: ${framesRef.current.length}/${targetFramesRef.current}`,
          `VIS: L=${vis.left ? "ON" : "OFF"} R=${vis.right ? "ON" : "OFF"}`,
          `FLAGS: MIRROR=${MIRROR_PREVIEW ? "ON" : "OFF"} SWAP=${SWAP_HANDEDNESS ? "ON" : "OFF"}`,
        ];
        ctx.save();
        ctx.font = '14px ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial';
        ctx.textBaseline = "top";
        let maxW = 0;
        for (const l of lines) { const m = ctx.measureText(l).width; if (m > maxW) maxW = m; }
        const boxW = Math.ceil(maxW + hudPadding * 2);
        const boxH = Math.ceil(lines.length * 18 + hudPadding * 2);
        const rx = 12, x = 12, y = 12;
        ctx.fillStyle = "rgba(0,0,0,0.45)";
        ctx.beginPath();
        ctx.moveTo(x + rx, y);
        ctx.arcTo(x + boxW, y, x + boxW, y + boxH, rx);
        ctx.arcTo(x + boxW, y + boxH, x, y + boxH, rx);
        ctx.arcTo(x, y + boxH, x, y, rx);
        ctx.arcTo(x, y, x + boxW, y, rx);
        ctx.closePath();
        ctx.fill();
        ctx.fillStyle = "#fff";
        for (let i = 0; i < lines.length; i++) ctx.fillText(lines[i], x + hudPadding, y + hudPadding + i * 18);
        ctx.restore();
      } catch (e) { console.warn("HUD draw failed", e); }
    }

    pendingRenderRef.current = false;
  }, []);

  // -------------------------------------------------------------------------
  // handleClose
  // -------------------------------------------------------------------------
  const stopCameraResources = useCallback(() => {
    if (cameraRef.current) {
      try { cameraRef.current.stop(); } catch { /* ignore */ }
      cameraRef.current = null;
    }

    const video = videoRef.current;
    if (video?.srcObject) {
      try {
        (video.srcObject as MediaStream).getTracks().forEach((track) => track.stop());
      } catch { /* ignore */ }
      video.srcObject = null;
    }
  }, []);

  const handleClose = useCallback(() => {
    const partialFrames = framesRef.current?.length || 0;
    if (recordingRef.current || (partialFrames > 0 && partialFrames < targetFramesRef.current)) {
      const ok = window.confirm(`Capture chưa hoàn tất (${partialFrames}/${targetFramesRef.current}) — bạn có muốn thoát và bỏ dữ liệu này không?`);
      if (!ok) return;
    }
    setRecording(false); setMode("IDLE"); setFrames([]);
    expectedHandsRef.current = null; setCountdown(0); setIsReady(false);
    setCurrentCaptureIndex(0); setCompletedCaptures(0); setCameraError(null);
    try { if (document.fullscreenElement) document.exitFullscreen?.(); } catch { /* ignore */ }
    stopCameraResources();
    onClose();
  }, [onClose, stopCameraResources]);

  useEffect(() => { handleCloseRef.current = handleClose; }, [handleClose]);

  // -------------------------------------------------------------------------
  // Fullscreen
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return;
    const root = rootRef.current;
    if (!root) return;
    try {
      type Fn = (...args: unknown[]) => unknown;
      const el = root as HTMLElement & Partial<Record<"webkitRequestFullscreen" | "mozRequestFullScreen" | "msRequestFullscreen" | "requestFullscreen", Fn>>;
      const request = el.requestFullscreen ?? el.webkitRequestFullscreen ?? el.mozRequestFullScreen ?? el.msRequestFullscreen;
      if (request) {
        const maybe = request.call(el);
        if (maybe && typeof (maybe as Promise<unknown>).catch === "function")
          (maybe as Promise<unknown>).catch((err) => console.warn("Fullscreen request failed:", err));
      }
    } catch { /* ignore */ }
    return () => { try { if (document.fullscreenElement) document.exitFullscreen?.(); } catch { /* ignore */ } };
  }, [isOpen]);

  // -------------------------------------------------------------------------
  // Dialect persistence
  // -------------------------------------------------------------------------
  useEffect(() => {
    try {
      const stored = JSON.parse(localStorage.getItem("dialectList") || "null");
      if (Array.isArray(stored) && stored.length > 0) {
        const merged = Array.from(new Set([...stored, "Cần Thơ"]));
        setDialectList(merged); localStorage.setItem("dialectList", JSON.stringify(merged));
      } else {
        const defaultList = ["Bắc", "Trung", "Nam", "Cần Thơ"];
        setDialectList(defaultList); localStorage.setItem("dialectList", JSON.stringify(defaultList));
      }
      const storedSel = localStorage.getItem("dialectSelected");
      if (storedSel) setDialect(storedSel);
    } catch { /* ignore */ }
  }, []);

  // -------------------------------------------------------------------------
  // Capture handlers
  // -------------------------------------------------------------------------
  const handleQuickCapture = useCallback(() => {
    if (!labelRef.current || !userRef.current) return;
    setFrames([]); framesRef.current = [];
    expectedHandsRef.current = expectedHandsOptionRef.current;
    setCurrentCaptureIndex(0); setCompletedCaptures(0); completedCapturesRef.current = 0;
    lastFrameTimeRef.current = 0; setCountdown(3); setMode("COUNTDOWN");
    setTimeout(() => {
      setRecording(true); recordingRef.current = true; setMode("RECORD");
      lastFrameTimeRef.current = Date.now();
    }, 3000);
  }, []);

  const handlePause  = useCallback(() => { setPaused(true);  pausedRef.current = true;  }, []);
  const handleResume = useCallback(() => {
    setPaused(false); pausedRef.current = false;
    lastFrameTimeRef.current = Date.now();
  }, []);

  const handleRestart = useCallback(() => {
    setFrames([]); framesRef.current = [];
    expectedHandsRef.current = expectedHandsOptionRef.current;
    setPaused(false); pausedRef.current = false;
    lastFrameTimeRef.current = Date.now();
  }, []);

  const handleStop = useCallback(() => {
    const collected = framesRef.current.length || 0;
    const required = targetFramesRef.current || 0;
    if (collected < required) {
      window.alert(`Bạn chưa thu đủ khung hình: ${collected}/${required}. Vui lòng tiếp tục quay cho đến khi đủ.`);
      return;
    }
    setRecording(false); recordingRef.current = false;
    setPaused(false); pausedRef.current = false;
    if (framesRef.current.length > 0) {
      const quality = computeQuality(framesRef.current);
      onSampleCaptureRef.current(framesRef.current, labelRef.current, userRef.current, { quality_info: quality, dialect: dialectRef.current });
      setFrames([]); framesRef.current = [];
      expectedHandsRef.current = expectedHandsOptionRef.current;
    }
  }, [computeQuality]);

  // -------------------------------------------------------------------------
  // FIX (training data): Mirror helper for x-coordinates.
  //
  // When MIRROR_PREVIEW=true the canvas is drawn flipped horizontally.
  // The model will receive mirrored frames at inference time.  To keep
  // training data consistent with inference-time input we also mirror the
  // x-coordinate: x_mirrored = 1 - x_raw.
  //
  // This does NOT touch y/z/visibility — those are already correct.
  // IMPORTANT: Only apply this transform to data saved for training.
  //            The render path continues to use raw coordinates.
  // -------------------------------------------------------------------------
  const mirrorLandmarkX = useCallback(
    (lm: MediaPipeLandmark): MediaPipeLandmark =>
      MIRROR_PREVIEW ? { ...lm, x: 1 - (lm.x ?? 0) } : { ...lm },
    []
  );

  // -------------------------------------------------------------------------
  // Main MediaPipe + Camera effect
  //
  // FIX (deps): Removed `expectedHandsOption` — it caused the entire
  // MediaPipe model and Camera to be torn down and re-initialized every time
  // the user toggled the 1/2/Auto hands selector.  The callback already reads
  // `expectedHandsOptionRef.current` which stays in sync via the sync effect
  // above, so no restart is needed.
  //
  // FIX (deps): Removed `filterLandmarks` — it was listed as a dep but is
  // never called inside this effect (training uploads use raw landmarks).
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return;

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
      const r = results as {
        multiHandLandmarks?: MediaPipeLandmark[][];
        multiHandedness?: Array<{ label?: string; score?: number }>;
        image?: HTMLImageElement | HTMLVideoElement;
      };

      const detected     = r.multiHandLandmarks || [];
      const handednessData = r.multiHandedness || [];

      // FIX (handedness): MediaPipe Hands was trained on MIRRORED selfie
      // images but receives the RAW (unflipped) frame from the camera
      // utility.  As a result its labels are from the camera's point of
      // view, not the person's:
      //
      //   MP "Left"  → user's actual RIGHT hand  (raw frame, front camera)
      //   MP "Right" → user's actual LEFT hand
      //
      // SWAP_HANDEDNESS defaults to true when MIRROR_PREVIEW is active,
      // correcting the labels so that `leftHandLandmarks` contains the
      // person's left hand landmarks (and vice-versa).
      //
      // Previously this was documented incorrectly and defaulted to false,
      // so every saved sample had left/right swapped — this is the primary
      // fix for wrong hand recognition in the trained model.
      let leftHandLandmarks:  MediaPipeLandmark[] | undefined;
      let rightHandLandmarks: MediaPipeLandmark[] | undefined;

      detected.forEach((landmarks, i) => {
        const rawLabel = handednessData[i]?.label; // "Left" or "Right" from MP
        const effectiveLabel = SWAP_HANDEDNESS
          ? rawLabel === "Left" ? "Right" : "Left"
          : rawLabel;

        if (effectiveLabel === "Left")  leftHandLandmarks  = landmarks;
        else if (effectiveLabel === "Right") rightHandLandmarks = landmarks;
      });

      // ---- Temporal smoothing for presence / preview ----
      const leftDetectedNow  = !!(leftHandLandmarks  && leftHandLandmarks.length  > 0);
      const rightDetectedNow = !!(rightHandLandmarks && rightHandLandmarks.length > 0);

      leftPresenceHistoryRef.current.push(leftDetectedNow);
      if (leftPresenceHistoryRef.current.length > PRESENCE_HISTORY_SIZE) leftPresenceHistoryRef.current.shift();
      rightPresenceHistoryRef.current.push(rightDetectedNow);
      if (rightPresenceHistoryRef.current.length > PRESENCE_HISTORY_SIZE) rightPresenceHistoryRef.current.shift();

      const leftVotes  = leftPresenceHistoryRef.current.filter(Boolean).length;
      const rightVotes = rightPresenceHistoryRef.current.filter(Boolean).length;
      const leftSmoothedVisible  = leftVotes  > leftPresenceHistoryRef.current.length  / 2;
      const rightSmoothedVisible = rightVotes > rightPresenceHistoryRef.current.length / 2;

      visibilityStateRef.current = { left: leftSmoothedVisible, right: rightSmoothedVisible };

      if (DEBUG_HANDS) {
        console.debug("Hands debug", {
          numHands: detected.length,
          handedness: handednessData,
          leftDetectedNow, rightDetectedNow, leftSmoothedVisible, rightSmoothedVisible,
        });
      }

      // ---- Render (preview uses smoothed/lerped positions) ----
      let renderLeft:  MediaPipeLandmark[] = [];
      let renderRight: MediaPipeLandmark[] = [];

      if (leftDetectedNow) {
        renderLeft = getRenderLandmarks(leftHandLandmarks, "leftHand");
        lastRenderedLeftRef.current = renderLeft;
      } else if (leftSmoothedVisible && lastRenderedLeftRef.current) {
        renderLeft = lastRenderedLeftRef.current;
      } else {
        lastRenderedLeftRef.current = undefined;
      }

      if (rightDetectedNow) {
        renderRight = getRenderLandmarks(rightHandLandmarks, "rightHand");
        lastRenderedRightRef.current = renderRight;
      } else if (rightSmoothedVisible && lastRenderedRightRef.current) {
        renderRight = lastRenderedRightRef.current;
      } else {
        lastRenderedRightRef.current = undefined;
      }

      // Clear ghost when only one hand detected
      if (leftDetectedNow && !rightDetectedNow) {
        lastRenderedRightRef.current = undefined;
        rightPresenceHistoryRef.current = [];
      }
      if (rightDetectedNow && !leftDetectedNow) {
        lastRenderedLeftRef.current = undefined;
        leftPresenceHistoryRef.current = [];
      }

      renderDataRef.current = {
        leftHandLandmarks: renderLeft,
        rightHandLandmarks: renderRight,
        image: r.image as HTMLImageElement | HTMLVideoElement,
      };

      if (!pendingRenderRef.current) {
        pendingRenderRef.current = true;
        requestAnimationFrame(renderLandmarks);
      }

      // ---- Capture logic ----
      if (!recordingRef.current || pausedRef.current) return;

      const currentTime = Date.now();
      if (currentTime - lastFrameTimeRef.current < frameIntervalMs.current) return;
      lastFrameTimeRef.current = currentTime;

      // IMPORTANT: use RAW MediaPipe output for training uploads — no smoothing.
      const rawLeft  = leftHandLandmarks;
      const rawRight = rightHandLandmarks;

      const rawLeftHas  = (rawLeft?.length  ?? 0) > 0;
      const rawRightHas = (rawRight?.length ?? 0) > 0;

      const computeHandConfidence = (lms?: MediaPipeLandmark[]) => {
        if (!lms || lms.length === 0) return undefined;
        let sum = 0, cnt = 0;
        for (const lm of lms) if (typeof lm.visibility === "number") { sum += lm.visibility; cnt++; }
        return cnt > 0 ? sum / cnt : undefined;
      };

      const leftConf  = computeHandConfidence(rawLeft);
      const rightConf = computeHandConfidence(rawRight);

      const confCandidates: number[] = [];
      if (typeof leftConf  === "number") confCandidates.push(leftConf);
      if (typeof rightConf === "number") confCandidates.push(rightConf);
      if (confCandidates.length === 0 && r.multiHandedness) {
        for (const h of r.multiHandedness) {
          if (typeof (h as { score?: number }).score === "number") confCandidates.push((h as { score: number }).score);
        }
      }
      const confidence = confCandidates.length
        ? confCandidates.reduce((a, b) => a + b, 0) / confCandidates.length
        : undefined;

      setHandsVisible(leftSmoothedVisible || rightSmoothedVisible || rawLeftHas || rawRightHas);

      const presentLeftRaw  = rawLeftHas;
      const presentRightRaw = rawRightHas;
      const detectedHandsCountRaw = (presentLeftRaw ? 1 : 0) + (presentRightRaw ? 1 : 0);

      let accept = false;
      const userChoice = expectedHandsOptionRef.current;
      if (detectedHandsCountRaw === 0) {
        accept = false;
      } else if (userChoice != null) {
        if (userChoice === 2) accept = presentLeftRaw && presentRightRaw;
        else if (userChoice === 1) accept = presentLeftRaw !== presentRightRaw;
        else accept = true;
      } else if (expectedHandsRef.current == null) {
        expectedHandsRef.current = detectedHandsCountRaw === 2 ? 2 : 1;
        accept = true;
        if (DEBUG_HANDS) console.log("Inferred expectedHands =", expectedHandsRef.current);
      } else if (expectedHandsRef.current === 2) {
        accept = presentLeftRaw && presentRightRaw;
      } else if (expectedHandsRef.current === 1) {
        accept = presentLeftRaw !== presentRightRaw;
      } else {
        accept = true;
      }

      if (!accept) {
        if (DEBUG_HANDS) console.debug("Skipping frame:", { expectedHands: expectedHandsRef.current, detectedRaw: detectedHandsCountRaw });
        return;
      }

      // FIX (training data x): Mirror x-coordinates to match the mirrored
      // display so that training samples are anatomically consistent with
      // what the model will receive at inference time (mirrored video).
      const timestamp_ms =
        typeof performance !== "undefined" && (performance as Performance).timeOrigin
          ? (performance as Performance).timeOrigin + (performance as Performance).now()
          : Date.now();

      const frameEntry: CaptureFrame = {
        left_hand:  rawLeft  ? rawLeft.map(mirrorLandmarkX)  : [],
        right_hand: rawRight ? rawRight.map(mirrorLandmarkX) : [],
        timestamp_ms,
        fallback_used: false,
        confidence: typeof confidence === "number" ? confidence : undefined,
      };

      framesRef.current.push(frameEntry);
      setFrames([...framesRef.current]);

      if (framesRef.current.length >= FIXED_TARGET_FRAMES) {
        recordingRef.current = false;
        setRecording(false);
        setMode("IDLE");

        const capturedFrames = [...framesRef.current];
        const quality = computeQuality(capturedFrames);
        const newCompleted = completedCapturesRef.current + 1;

        onSampleCaptureRef.current(capturedFrames, labelRef.current, userRef.current, {
          quality_info: quality, dialect: dialectRef.current,
        });

        completedCapturesRef.current = newCompleted;
        setCompletedCaptures(newCompleted);
        setCurrentCaptureIndex(newCompleted);

        if (newCompleted < FIXED_CAPTURE_COUNT) {
          setFrames([]); framesRef.current = [];
          expectedHandsRef.current = expectedHandsOptionRef.current;
          lastFrameTimeRef.current = 0;
          setTimeout(() => {
            setCountdown(3); setMode("COUNTDOWN");
            setTimeout(() => {
              setRecording(true); recordingRef.current = true;
              setMode("RECORD"); lastFrameTimeRef.current = Date.now();
            }, 3000);
          }, 2000);
        } else {
          setTimeout(() => {
            setFrames([]); framesRef.current = [];
            expectedHandsRef.current = expectedHandsOptionRef.current;
            lastFrameTimeRef.current = 0;
            completedCapturesRef.current = 0;
            setCompletedCaptures(0); setCurrentCaptureIndex(0);
            recordingRef.current = false; setRecording(false); setMode("IDLE"); setLabel("");
          }, 1000);
        }
      }
    });

    if (!videoRef.current) {
      return () => {
        hands.close();
        if (cameraRef.current) { cameraRef.current.stop(); cameraRef.current = null; }
      };
    }

    const canvas = canvasRef.current;
    if (canvas) { canvas.width = 1280; canvas.height = 720; }

    const video = videoRef.current;
    const onLoadedMetadata = () => console.log("Video metadata loaded:", { w: video.videoWidth, h: video.videoHeight });
    const onCanPlay = () => console.log("Video can play");
    video.addEventListener("loadedmetadata", onLoadedMetadata);
    video.addEventListener("canplay", onCanPlay);

    // FIX (redundant getUserMedia): The previous code called getUserMedia,
    // immediately stopped the resulting stream, then started Camera() which
    // also calls getUserMedia.  This caused double permission prompts on some
    // browsers and race conditions.  Camera handles permissions internally —
    // just start it directly.
    const camera = new Camera(videoRef.current, {
      onFrame: async () => {
        if (videoRef.current) await hands.send({ image: videoRef.current });
      },
      width: 1280,
      height: 720,
      facingMode: "user",
    });

    cameraRef.current = camera;
    camera.start()
      .then(() => { setIsReady(true); setCameraError(null); })
      .catch((error: unknown) => {
        const errorMsg = getCameraErrorMessage(error);
        setCameraError(errorMsg); setIsReady(false);
      });

    return () => {
      video.removeEventListener("loadedmetadata", onLoadedMetadata);
      video.removeEventListener("canplay", onCanPlay);
      hands.close();
      stopCameraResources();
    };
    // FIX: `expectedHandsOption` removed — would restart MediaPipe on every
    //       hands-mode toggle.  Use `expectedHandsOptionRef` inside callback.
    // FIX: `filterLandmarks` removed — it is not used inside this effect.
  }, [isOpen, renderLandmarks, computeQuality, getRenderLandmarks, mirrorLandmarkX, stopCameraResources]);

  // -------------------------------------------------------------------------
  // Countdown effect
  // FIX (backup timer): Previous code created a new 30-second backup timer
  // on every re-render while countdown===0 && recording, leading to dozens of
  // timers all calling handleStop.  Use backupTimerRef so only ONE fires.
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (countdown > 0) {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000);
      return () => clearTimeout(timer);
    }

    if (countdown === 0 && recording && !backupTimerRef.current) {
      backupTimerRef.current = setTimeout(() => {
        console.warn("BACKUP TIMEOUT: Frame completion failed after 30 seconds");
        handleStop();
        backupTimerRef.current = null;
      }, 30000);
    }

    if (!recording && backupTimerRef.current) {
      clearTimeout(backupTimerRef.current);
      backupTimerRef.current = null;
    }

    return () => {
      if (backupTimerRef.current) { clearTimeout(backupTimerRef.current); backupTimerRef.current = null; }
    };
  }, [countdown, recording, handleStop]);

  // -------------------------------------------------------------------------
  // Cleanup on unmount
  // -------------------------------------------------------------------------
  useEffect(() => {
    return () => {
      stopCameraResources();
    };
  }, [stopCameraResources]);

  useEffect(() => {
    if (!isOpen) {
      setRecording(false);
      recordingRef.current = false;
      setPaused(false);
      pausedRef.current = false;
      stopCameraResources();
    }
  }, [isOpen, stopCameraResources]);

  // -------------------------------------------------------------------------
  // Keyboard shortcuts
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyPress = (e: KeyboardEvent) => {
      const active = document.activeElement as HTMLElement | null;
      if (active && (active.tagName === "INPUT" || active.tagName === "TEXTAREA" || active.isContentEditable)) return;

      if (e.code === "Enter") {
        e.preventDefault();
        if (!recordingRef.current && labelRef.current && userRef.current) {
          setFrames([]); framesRef.current = [];
          expectedHandsRef.current = expectedHandsOptionRef.current;
          setCurrentCaptureIndex(0); setCompletedCaptures(0); completedCapturesRef.current = 0;
          setCountdown(3); setMode("COUNTDOWN");
          setTimeout(() => { setRecording(true); recordingRef.current = true; setMode("RECORD"); }, 3000);
        } else if (recordingRef.current) {
          const collected = framesRef.current.length || 0;
          const required  = targetFramesRef.current  || 0;
          if (collected < required) {
            window.alert(`Bạn chưa thu đủ khung hình: ${collected}/${required}. Vui lòng tiếp tục quay cho đến khi đủ.`);
          } else {
            setRecording(false); recordingRef.current = false;
            if (framesRef.current.length > 0) {
              const quality = computeQuality(framesRef.current);
              onSampleCaptureRef.current(framesRef.current, labelRef.current, userRef.current, { quality_info: quality, dialect: dialectRef.current });
              setFrames([]); framesRef.current = [];
              expectedHandsRef.current = expectedHandsOptionRef.current;
            }
          }
        }
      } else if (e.code === "Escape") {
        handleCloseRef.current?.();
      } else if (e.code === "Space") {
        e.preventDefault();
        if (recordingRef.current) { if (pausedRef.current) handleResume(); else handlePause(); }
      } else if (e.code === "KeyS") {
        setShowGuide((s) => !s);
      } else if (e.code === "KeyD") {
        setShowTips((s) => !s);
      } else if (e.code === "KeyA") {
        if (recordingRef.current) {
          recordingRef.current = false; setRecording(false);
          setPaused(false); pausedRef.current = false;
          setFrames([]); framesRef.current = [];
          expectedHandsRef.current = expectedHandsOptionRef.current; setMode("IDLE");
        }
      }
    };
    document.addEventListener("keydown", handleKeyPress);
    return () => document.removeEventListener("keydown", handleKeyPress);
  }, [isOpen, computeQuality, handlePause, handleResume]);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (!isOpen) return null;

  return (
    <div ref={rootRef} className="fixed inset-0 z-[9999] bg-black">
      {/* Camera Error */}
      {cameraError && (
        <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-red-900/80 backdrop-blur-md border-2 border-red-500 rounded-xl p-8 max-w-md mx-4 text-center">
            <svg className="w-16 h-16 mx-auto mb-4 text-red-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8v4m0 4v.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h3 className="text-xl font-bold text-white mb-3">Lỗi Camera</h3>
            <p className="text-red-100 mb-6 leading-relaxed">{cameraError}</p>
            <div className="flex gap-3 flex-col sm:flex-row">
              <button onClick={() => { setCameraError(null); window.location.reload(); }} className="flex-1 bg-blue-600 hover:bg-blue-500 text-white font-semibold py-3 px-4 rounded-lg transition-colors">Làm mới Trang</button>
              <button onClick={handleClose} className="flex-1 bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 px-4 rounded-lg transition-colors">Thoát</button>
            </div>
            <p className="text-xs text-red-200/70 mt-4">Nếu vấn đề tiếp tục, vui lòng kiểm tra quyền truy cập camera trong cài đặt trình duyệt.</p>
          </div>
        </div>
      )}

      {/* Header Bar */}
      <div className="absolute top-0 left-0 right-0 z-10 bg-black/80 backdrop-blur-sm border-b border-gray-700 hidden sm:block">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between px-4 sm:px-6 py-3 sm:py-4">
          <div className="flex flex-wrap items-center gap-3">
            <h2 className="text-xl font-semibold text-white">🎬 Ghi toàn màn hình</h2>
            {isReady && (
              <Badge variant="success">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse mr-2"></span>Camera sẵn sàng
              </Badge>
            )}
            <div className="ml-3 hidden sm:flex items-center space-x-2">
              <div className="text-sm text-gray-300">Hands:</div>
              <div className="inline-flex bg-gray-800 rounded-md overflow-hidden">
                {([null, 1, 2] as const).map((v) => (
                  <button
                    key={String(v)}
                    onClick={() => handleSetExpectedHands(v)}
                    disabled={recording}
                    className={`px-3 py-1 text-sm ${expectedHandsOption === v ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-700"}`}
                  >
                    {v === null ? "Auto" : v}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2 sm:gap-4">
            <div className="text-white text-sm hidden sm:block">
              Nhấn <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">Enter</kbd> để chụp •{" "}
              <kbd className="px-2 py-1 bg-gray-700 rounded text-xs">Esc</kbd> để thoát
            </div>
            <button onClick={() => setShowGuide(!showGuide)} className="bg-gray-700 hover:bg-gray-600 text-white px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 flex items-center space-x-2">
              <span>{showGuide ? "🙈" : "👁️"}</span>
              <span>{showGuide ? "Ẩn hướng dẫn" : "Hiển thị hướng dẫn"}</span>
            </button>
            <button onClick={handleClose} className="text-white hover:text-gray-300 p-2">
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="h-full flex flex-col lg:flex-row pt-16 sm:pt-20">
        {/* Camera Feed */}
        <div className="flex-1 relative flex items-center justify-center bg-gray-900 w-full h-[40vh] sm:h-[50vh] lg:h-full">
          <video ref={videoRef} autoPlay muted playsInline className="hidden" />
          <canvas
            ref={canvasRef}
            width={1280}
            height={720}
            className="w-full h-full max-w-full max-h-full object-contain border border-gray-600 rounded-lg"
            style={{ minHeight: "200px", backgroundColor: "#1a1a1a" }}
          />

          {recording && !handsVisible && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="bg-black/70 text-yellow-300 px-4 py-2 rounded-lg text-center">
                <div className="font-semibold">Không thấy tay — vui lòng hiển thị cả hai tay</div>
                <div className="text-xs mt-1">Hệ thống sẽ chỉ lưu khung khi tay được phát hiện</div>
              </div>
            </div>
          )}

          <button onClick={handleClose} className="sm:hidden absolute top-3 right-3 z-20 bg-black/60 hover:bg-black/70 text-white rounded-full p-2" aria-label="Thoát toàn màn hình">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>

          {showGuide && !recording && countdown === 0 && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className="relative">
                <div className="w-80 h-80 relative">
                  <div className="absolute top-0 left-0 w-8 h-8 border-l-4 border-t-4 border-green-400/80 rounded-tl-xl"></div>
                  <div className="absolute top-0 right-0 w-8 h-8 border-r-4 border-t-4 border-green-400/80 rounded-tr-xl"></div>
                  <div className="absolute bottom-0 left-0 w-8 h-8 border-l-4 border-b-4 border-green-400/80 rounded-bl-xl"></div>
                  <div className="absolute bottom-0 right-0 w-8 h-8 border-r-4 border-b-4 border-green-400/80 rounded-br-xl"></div>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <div className="w-1 h-8 bg-green-400/60 rounded-full"></div>
                    <div className="absolute w-8 h-1 bg-green-400/60 rounded-full"></div>
                  </div>
                  {/* Labels now match corrected handedness: orange=Left, teal=Right */}
                  <div className="absolute top-16 -left-6 w-8 h-8 border border-orange-400/60 rounded-full bg-orange-400/10 flex items-center justify-center">
                    <span className="text-orange-400 text-xs">L</span>
                  </div>
                  <div className="absolute top-16 -right-6 w-8 h-8 border border-teal-400/60 rounded-full bg-teal-400/10 flex items-center justify-center">
                    <span className="text-teal-400 text-xs">R</span>
                  </div>
                </div>
                <div className="absolute -top-12 left-1/2 transform -translate-x-1/2 bg-gray-800/80 backdrop-blur-sm text-white px-4 py-2 rounded-lg text-sm font-medium">🎯 Đặt vị trí vào khung</div>
                <div className="absolute -bottom-8 left-1/2 transform -translate-x-1/2 bg-gray-800/70 backdrop-blur-sm text-white px-3 py-1 rounded-lg text-xs">Thấy phần trên cơ thể và hai tay</div>
              </div>
            </div>
          )}

          {countdown > 0 && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm">
              <div className="text-center text-white">
                <div className="text-8xl font-bold mb-4 animate-pulse">{countdown}</div>
                <div className="text-2xl mb-2">Chuẩn bị thực hiện:</div>
                <div className="text-3xl font-semibold text-green-400">{label}</div>
                {captureCount > 1 && (
                  <div className="text-lg mt-4 text-gray-300">Lần chụp {currentCaptureIndex + 1} / {FIXED_CAPTURE_COUNT}</div>
                )}
              </div>
            </div>
          )}

          {recording && paused && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm z-20">
              <div className="bg-gray-900 border border-gray-700 rounded-xl p-8 w-[500px]">
                <div className="text-center">
                  <div className="text-6xl mb-4">⏸️</div>
                  <h3 className="text-3xl font-bold text-white mb-2">Đã tạm dừng</h3>
                  <p className="text-gray-300 mb-6">Bạn muốn làm gì với dữ liệu hiện tại?</p>
                  <div className="bg-gray-800 rounded-lg p-4 mb-6">
                    <div className="flex justify-between text-sm mb-2">
                      <span className="text-gray-400">Tiến độ:</span>
                      <span className="text-white font-medium">{frames.length} / {FIXED_TARGET_FRAMES} khung</span>
                    </div>
                    <div className="w-full bg-gray-700 rounded-full h-2">
                      <div className="bg-yellow-500 h-2 rounded-full transition-all duration-300" style={{ width: `${Math.min((frames.length / FIXED_TARGET_FRAMES) * 100, 100)}%` }} />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <button onClick={handleResume} className="w-full px-4 py-3 bg-green-600 hover:bg-green-500 text-white rounded-lg font-medium transition-colors flex items-center justify-center space-x-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <span>Tiếp tục thu (giữ {frames.length} khung)</span>
                    </button>
                    <button onClick={handleRestart} className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-lg font-medium transition-colors flex items-center justify-center space-x-2">
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
                      <span>Bắt đầu lại từ đầu (xóa dữ liệu)</span>
                    </button>
                    {frames.length >= FIXED_TARGET_FRAMES && (
                      <button onClick={() => { setPaused(false); pausedRef.current = false; handleStop(); }} className="w-full px-4 py-3 bg-purple-600 hover:bg-purple-500 text-white rounded-lg font-medium transition-colors flex items-center justify-center space-x-2">
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                        <span>Hoàn tất và lưu</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </div>
          )}

          {!recording && !countdown && completedCaptures > 0 && completedCaptures < captureCount && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/70 backdrop-blur-sm">
              <div className="text-center text-white">
                <div className="text-4xl mb-4">🎉</div>
                <div className="text-2xl font-bold mb-2 text-green-400">Đã chụp {completedCaptures} mẫu!</div>
                <div className="text-xl mb-4">Chuẩn bị chụp tiếp...</div>
                <div className="text-lg text-gray-300">Tiến độ: {completedCaptures} / {FIXED_CAPTURE_COUNT}</div>
                <div className="w-64 bg-gray-700 rounded-full h-3 mt-4 mx-auto">
                  <div className="bg-green-500 h-3 rounded-full transition-all duration-500" style={{ width: `${(completedCaptures / captureCount) * 100}%` }} />
                </div>
              </div>
            </div>
          )}

          {!recording && !countdown && completedCaptures > 0 && completedCaptures >= captureCount && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/80 backdrop-blur-sm">
              <div className="text-center text-white">
                <div className="text-6xl mb-4">✅</div>
                <div className="text-3xl font-bold mb-2 text-green-400">Hoàn tất tất cả lần chụp!</div>
                <div className="text-xl mb-4">Đã chụp {completedCaptures} mẫu cho "{label}"</div>
                <div className="text-lg text-gray-300">Sẵn sàng chụp tiếp — nhập nhãn mới và nhấn nút Bắt đầu chụp</div>
              </div>
            </div>
          )}

          {recording && (
            <div className="absolute top-24 left-6 flex items-center space-x-3 bg-red-500 text-white px-4 py-2 rounded-full shadow-lg">
              <div className="w-3 h-3 bg-white rounded-full animate-pulse"></div>
              <span className="font-medium">ĐANG GHI</span>
              {FIXED_CAPTURE_COUNT > 1 && <span className="text-sm">({completedCaptures + 1}/{FIXED_CAPTURE_COUNT})</span>}
            </div>
          )}

          {recording && (
            <div className="absolute bottom-6 left-1/2 transform -translate-x-1/2 bg-black/50 backdrop-blur-sm rounded-full px-6 py-2">
              <div className="text-white text-sm">📊 {frames.length} khung đã chụp</div>
            </div>
          )}
        </div>

        {/* Control Panel */}
        <div className="w-full lg:w-96 bg-gray-900 border-l border-gray-700 flex flex-col max-h-[calc(100vh-8rem)] lg:max-h-none">
          <div className="flex-1 p-6 space-y-6 overflow-y-auto">
            <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 rounded-xl p-5 border border-blue-500/20">
              <h3 className="text-lg font-semibold text-white mb-4 flex items-center">
                <span className="w-3 h-3 bg-blue-400 rounded-full mr-3"></span>Cài đặt chụp
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-blue-300 mb-2">📝 Nhãn hành động *</label>
                  <div className="relative">
                    <input type="text" value={label} onChange={(e) => setLabel(e.target.value)} placeholder="ví dụ: đi bộ, nhảy, vẫy tay" className="w-full pr-12 px-4 py-3 bg-gray-800/80 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200" disabled={recording || countdown > 0} />
                    <div className="absolute inset-y-0 right-2 flex items-center">
                      <SpeechInputButton onText={(text) => setLabel(text)} title="Dùng giọng nói để điền nhãn hành động" className="h-8 w-8" />
                    </div>
                  </div>
                  {!label && <p className="text-xs text-yellow-400 mt-1">⚠️ Nhãn hành động là bắt buộc</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-blue-300 mb-2">👤 Người thực hiện *</label>
                  <div className="relative">
                    <input type="text" value={user} onChange={(e) => setUser(e.target.value)} placeholder="ví dụ: user001, john_doe" className="w-full pr-12 px-4 py-3 bg-gray-800/80 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200" disabled={recording || countdown > 0} onBlur={() => rememberUser(user)} />
                    <div className="absolute inset-y-0 right-2 flex items-center">
                      <SpeechInputButton onText={(text) => setUser(text)} title="Dùng giọng nói để điền tên người thực hiện" className="h-8 w-8" />
                    </div>
                  </div>
                  {!user && <p className="text-xs text-yellow-400 mt-1">⚠️ ID người dùng là bắt buộc</p>}
                  {recentUsers.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-blue-200">
                      <span className="text-[11px] text-blue-300">Gợi ý:</span>
                      {recentUsers.map((name) => (
                        <button type="button" key={name} onClick={() => setUser(name)} className="px-2 py-1 rounded-full bg-blue-900/60 hover:bg-blue-800 text-blue-100 border border-blue-500/40 text-[11px]">{name}</button>
                      ))}
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-blue-300 mb-2">🗂️ Bộ ngôn ngữ</label>
                  <select value={dialect} onChange={(e) => { const v = e.target.value; if (v === "Khác") { setShowAddDialectModal(true); } else { setDialect(v); localStorage.setItem("dialectSelected", v); } }} className="w-full px-4 py-3 bg-gray-800/80 border border-gray-600 rounded-lg text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-200" disabled={recording || countdown > 0}>
                    {dialectList.map((d) => <option key={d} value={d}>{d}</option>)}
                    <option value="Khác">Khác (thêm mới)</option>
                  </select>
                </div>
              </div>
            </div>

            <AddDialectModal isOpen={showAddDialectModal} onClose={() => setShowAddDialectModal(false)} onAdd={(name) => {
              const updated = Array.from(new Set([...dialectList, name]));
              setDialectList(updated); setDialect(name);
              localStorage.setItem("dialectList", JSON.stringify(updated));
              localStorage.setItem("dialectSelected", name);
            }} />

            <div className="bg-gray-800 rounded-lg p-4 hidden sm:block">
              <h4 className="text-sm font-medium text-gray-300 mb-3">📊 Cài đặt & Tiến độ chụp</h4>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between text-gray-400"><span>Tổng số lần chụp:</span><span className="text-white">{FIXED_CAPTURE_COUNT}</span></div>
                <div className="flex justify-between text-gray-400"><span>Lần chụp hiện tại:</span><span className="text-white">{currentCaptureIndex + 1}/{FIXED_CAPTURE_COUNT}</span></div>
                <div className="flex justify-between text-gray-400"><span>Đã hoàn thành:</span><span className="text-white">{completedCaptures}/{FIXED_CAPTURE_COUNT}</span></div>
                <div className="flex justify-between text-gray-400"><span>Khung hiện tại:</span><span className="text-white">{frames.length}/{FIXED_TARGET_FRAMES}</span></div>
                {frames.length > 0 && (
                  <div className="w-full bg-gray-700 rounded-full h-2 mt-2">
                    <div className="bg-blue-600 h-2 rounded-full transition-all duration-300" style={{ width: `${Math.min((frames.length / FIXED_TARGET_FRAMES) * 100, 100)}%` }} />
                  </div>
                )}
                <div className="flex justify-between text-gray-400">
                  <span>Trạng thái:</span>
                  <Badge variant={recording ? "danger" : isReady ? "success" : "warning"} size="sm">
                    {recording ? "Đang ghi" : isReady ? "Sẵn sàng" : "Đang tải"}
                  </Badge>
                </div>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="p-6 border-t border-gray-700 space-y-3">
            {countdown > 0 ? (
              <div className="w-full py-4 bg-yellow-600 text-white rounded-lg text-center font-medium">Bắt đầu sau {countdown}...</div>
            ) : !recording ? (
              <Button onClick={handleQuickCapture} disabled={!label || !user || !isReady} className="w-full py-4 text-lg font-medium" variant="primary">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                {FIXED_CAPTURE_COUNT > 1 ? `Bắt đầu chụp (${FIXED_CAPTURE_COUNT}x)` : "Bắt đầu chụp"} (Enter)
              </Button>
            ) : paused ? (
              <div className="text-center py-4 text-gray-400">
                <span className="text-yellow-500 font-medium">⏸ Đã tạm dừng</span>
                <p className="text-sm mt-1">Xem các tùy chọn trên màn hình</p>
              </div>
            ) : (
              <>
                <Button onClick={handlePause} className="w-full py-4 text-lg font-medium bg-yellow-600 hover:bg-yellow-500" variant="secondary">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  Tạm dừng (Space)
                </Button>
                <Button onClick={handleStop} className="w-full py-3" variant="danger" disabled={frames.length < FIXED_TARGET_FRAMES} title={frames.length < FIXED_TARGET_FRAMES ? `Cần ${FIXED_TARGET_FRAMES} khung trước khi dừng` : undefined}>
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9h6v6H9z" /></svg>
                  Dừng và lưu
                </Button>
              </>
            )}
            <Button onClick={handleClose} className="w-full" variant="secondary">Thoát toàn màn hình</Button>
          </div>

          {/* Tips */}
          <div className="bg-gray-800 border-t border-gray-700 p-4">
            <button onClick={() => setShowTips(!showTips)} className="w-full flex items-center justify-between text-sm font-medium text-gray-300 hover:text-white transition-colors">
              <span>💡 Mẹo nhanh để có kết quả tốt</span>
              <span className="text-xs">{showTips ? "🔽" : "▶️"}</span>
            </button>
            {showTips && (
              <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-400">
                <div>✨ Đảm bảo ánh sáng tốt và nền rõ ràng</div>
                <div>🤲 Giữ tay hiển thị và ngón tay duỗi</div>
                <div>👁️ Dùng nút "Hiển thị hướng dẫn" để hỗ trợ định vị</div>
                <div>🔗 Quan sát kết nối giữa các bộ phận tay để theo dõi tốt hơn</div>
                <div>🎯 Giữ ở giữa khung hình</div>
                <div>⚡ Di chuyển tự nhiên để có kết quả tốt nhất</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

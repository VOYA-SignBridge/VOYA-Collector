import { useEffect, useRef, useState, useCallback } from "react";
import { Hands, HAND_CONNECTIONS } from "@mediapipe/hands";
import { Camera } from "@mediapipe/camera_utils";
import * as drawing from "@mediapipe/drawing_utils";
import Button from "./ui/Button";
import Badge from "./ui/Badge";
import type { ClassRow, MediaPipeLandmark, CameraInfo, QualityInfo } from "../types";

import { TARGET_FRAMES, CAPTURE_COUNT, FRAME_INTERVAL_MS } from "../config/capture";
import SpeechInputButton from "./SpeechInputButton";
import AddDialectModal from "./AddDialectModal";
import { getClassesList, getClassesStats } from "../api/dataset";
import { fetchLabelSuggestions, fetchCollectorSuggestions, getPreference, setPreference } from "../api/preferences";

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
const MIRROR_PREVIEW = parseBoolEnv(import.meta.env.VITE_MIRROR_PREVIEW, true);

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
const CAPTURE_FRAME_WIDTH = 1280;
const CAPTURE_FRAME_HEIGHT = 720;
// Thứ tự khớp recognition profiles v2: Bảng chữ cái là nhóm độc lập, các miền
// hiển thị đầy đủ "Miền ..." cho rõ nghĩa. Danh sách này chỉ là fallback khi
// chưa tải được catalog từ server.
const DEFAULT_DIALECTS = ["Bảng chữ cái", "Miền Bắc", "Miền Trung", "Miền Nam", "Hòa Đê"];
const DEFAULT_LANGUAGES = ["vn", "en"];

const DIALECT_LABELS: Record<string, string> = {
  common: "Chung",
  "bang-chu-cai": "Bảng chữ cái",
  bac: "Miền Bắc",
  trung: "Miền Trung",
  nam: "Miền Nam",
  "hoa-de": "Hòa Đê",
  "can-tho": "Cần Thơ",
  spa: "Spa",
};

const LANGUAGE_LABELS: Record<string, string> = {
  vn: "Tiếng Việt",
  vi: "Tiếng Việt",
  en: "English",
};

// Chuẩn hóa tên người thu: bỏ ký tự lạ, gộp khoảng trắng, và tự viết hoa
// chữ cái đầu mỗi từ (theo locale vi) — để "trân"/"Trân"/"TRÂN" đều nhập ra
// cùng một dạng hiển thị, tránh tạo thêm biến thể signer trùng người.
const titleCaseVi = (value: string) =>
  value
    .split(" ")
    .map((w) => (w ? w.charAt(0).toLocaleUpperCase("vi") + w.slice(1) : w))
    .join(" ");

const sanitizeCollectorName = (value: string) =>
  titleCaseVi(
    value
      .replace(/[^\p{L}\s]/gu, " ")
      .replace(/\s+/g, " ")
  )
    .trim();

const normalizeText = (value: string) =>
  value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const normalizeLanguageKey = (value?: string) => (value || "").trim().toLowerCase();

const normalizeDialectKey = (value?: string) => {
  const normalized = normalizeText(value || "");
  if (!normalized) return "";

  const compact = normalized.replace(/\s+/g, " ");
  const slug = compact.replace(/\s+/g, "-");

  const mappings: Record<string, string> = {
    bac: "bac",
    "mien bac": "bac",
    trung: "trung",
    "mien trung": "trung",
    nam: "nam",
    "mien nam": "nam",
    "hoa de": "hoa-de",
    hoade: "hoa-de",
    "hoa-de": "hoa-de",
    "can tho": "can-tho",
    cantho: "can-tho",
    "can-tho": "can-tho",
    "bang chu cai": "bang-chu-cai",
    "bang-chu-cai": "bang-chu-cai",
    chung: "common",
    common: "common",
  };

  return mappings[compact] || mappings[slug] || slug;
};

const displayDialectLabel = (value?: string) => {
  const key = normalizeDialectKey(value);
  if (key && DIALECT_LABELS[key]) return DIALECT_LABELS[key];
  return value?.trim() || "";
};

const displayLanguageLabel = (value?: string) => {
  const key = normalizeLanguageKey(value);
  if (key && LANGUAGE_LABELS[key]) return LANGUAGE_LABELS[key];
  return value?.trim() || "";
};

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

function getFrameDimensions(source: HTMLImageElement | HTMLVideoElement): { width: number; height: number } {
  if (source instanceof HTMLVideoElement && source.videoWidth > 0 && source.videoHeight > 0) {
    return { width: source.videoWidth, height: source.videoHeight };
  }

  if (source instanceof HTMLImageElement && source.naturalWidth > 0 && source.naturalHeight > 0) {
    return { width: source.naturalWidth, height: source.naturalHeight };
  }

  return { width: CAPTURE_FRAME_WIDTH, height: CAPTURE_FRAME_HEIGHT };
}

// ---------------------------------------------------------------------------
// SearchableSelect — compact dropdown with inline search (mobile-friendly)
// ---------------------------------------------------------------------------
function SearchableSelect({
  label,
  value,
  options,
  displayFn,
  onChange,
  disabled = false,
}: {
  label: string;
  value: string;
  options: string[];
  displayFn: (v: string) => string;
  onChange: (v: string) => void;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Focus search input when opened
  useEffect(() => {
    if (open) { setSearch(""); setTimeout(() => searchInputRef.current?.focus(), 50); }
  }, [open]);

  const normalizeForSearch = (t: string) => t.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d");
  const filtered = search
    ? options.filter((o) => normalizeForSearch(displayFn(o)).includes(normalizeForSearch(search)))
    : options;

  return (
    <div ref={containerRef} className="relative">
      <label className="block text-[10px] sm:text-[11px] text-blue-200/70 mb-0.5">{label}</label>
      <button
        type="button"
        onClick={() => { if (!disabled) setOpen(!open); }}
        className={`w-full px-2 py-1.5 sm:px-3 sm:py-2 bg-gray-800/80 border border-gray-600 rounded-lg text-white text-xs sm:text-sm text-left flex items-center justify-between ${disabled ? "opacity-50 cursor-not-allowed" : "hover:border-blue-500 cursor-pointer"}`}
      >
        <span className="truncate">{displayFn(value)}</span>
        <svg className={`w-3 h-3 ml-1 flex-shrink-0 transition-transform ${open ? "rotate-180" : ""}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
      </button>
      {open && (
        <div className="absolute z-50 mt-1 w-full bg-gray-800 border border-gray-600 rounded-lg shadow-xl overflow-hidden">
          <div className="p-1.5">
            <input
              ref={searchInputRef}
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm..."
              className="w-full px-2 py-1 bg-gray-700 border border-gray-600 rounded text-white text-xs placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-blue-500"
              onMouseDown={(e) => e.stopPropagation()}
            />
          </div>
          <div className="max-h-32 overflow-y-auto">
            {filtered.length === 0 ? (
              <div className="px-2 py-1.5 text-[10px] text-gray-400 text-center">Không tìm thấy</div>
            ) : (
              filtered.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => { onChange(opt); setOpen(false); }}
                  className={`w-full text-left px-2.5 py-1.5 text-xs hover:bg-blue-600/40 transition-colors ${opt === value ? "bg-blue-600/20 text-blue-200 font-medium" : "text-gray-200"}`}
                >
                  {displayFn(opt)}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// CapturedWordsSummary — collapsed-by-default list of words saved this
// session; expands on click so it never eats screen space by default.
// ---------------------------------------------------------------------------
function CapturedWordsSummary({ summary }: { summary: Record<string, number> }) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(summary).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-gray-200 hover:bg-gray-700/50 transition-colors"
      >
        <span className="flex items-center gap-2 text-xs sm:text-sm font-medium truncate">
          <span>📋</span>
          <span className="truncate">Đã lưu phiên này: {total} mẫu · {entries.length} từ</span>
        </span>
        <span className="text-xs text-gray-400 flex-shrink-0">{open ? "🔽" : "▶️"}</span>
      </button>
      {open && (
        <div className="max-h-32 sm:max-h-40 overflow-y-auto border-t border-gray-700">
          {entries.length === 0 ? (
            <div className="px-3 py-3 text-xs text-gray-500 text-center">Chưa có mẫu nào được lưu</div>
          ) : (
            <ul className="divide-y divide-gray-800">
              {entries.map(([word, count]) => (
                <li key={word} className="flex items-center justify-between px-3 py-1.5 text-xs sm:text-sm">
                  <span className="text-gray-100 truncate">{word}</span>
                  <span className="text-gray-400 flex-shrink-0 ml-2">{count}×</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
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
    meta?: {
      camera_info?: CameraInfo;
      quality_info?: QualityInfo;
      dialect?: string;
      language?: string;
      /** Số tay dùng khi thu: lựa chọn thủ công 1/2, hoặc số suy ra từ warmup ở chế độ Auto. */
      hands_used?: number | null;
    }
  ) => void;
  initialLabel?: string;
  initialUser?: string;
  targetFrames?: number;
  captureCount?: number;
  /** Số mẫu đã lưu thành công lên server trong phiên hiện tại, theo từng từ. */
  capturedSummary?: Record<string, number>;
  /** Thông báo lỗi kết nối/lưu server hiện tại; khi có giá trị, tạm chặn bắt đầu thu mới. */
  connectionIssue?: string | null;
  /**
   * Thông báo QC sau khi upload (warning = mẫu được lưu nhưng bị đánh dấu,
   * error = mẫu bị từ chối). Phải render BÊN TRONG modal vì element-fullscreen
   * che toàn bộ ToastContainer global. `key` tăng dần để re-trigger auto-dismiss.
   */
  qualityNotice?: { kind: "warning" | "error"; message: string; key: number } | null;
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
  capturedSummary = {},
  connectionIssue = null,
  qualityNotice = null,
}: FullscreenCaptureModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cameraRef = useRef<Camera | null>(null);
  const rootRef = useRef<HTMLDivElement | null>(null);

  const [recording, setRecording] = useState(false);
  const [frames, setFrames] = useState<CaptureFrame[]>([]);
  const [label, setLabel] = useState(initialLabel);
  const [user, setUser] = useState(initialUser);
  const [language, setLanguage] = useState<string>("vn");
  const [dialect, setDialect] = useState<string>("Miền Bắc");
  const [languageList, setLanguageList] = useState<string[]>(DEFAULT_LANGUAGES);
  const [dialectList, setDialectList] = useState<string[]>(DEFAULT_DIALECTS);
  const [catalogRows, setCatalogRows] = useState<ClassRow[]>([]);
  const [catalogStatsByUid, setCatalogStatsByUid] = useState<Record<string, number>>({});
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogError, setCatalogError] = useState<string>("");
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

  // --- Debounced label suggestions from server ---
  const [serverLabelSuggestions, setServerLabelSuggestions] = useState<string[]>([]);
  const labelSuggestTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [labelConfirmed, setLabelConfirmed] = useState(false);
  const [labelFocused, setLabelFocused] = useState(false);

  // --- Debounced collector suggestions from server ---
  const [collectorSuggestions, setCollectorSuggestions] = useState<string[]>([]);
  const collectorSuggestTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [collectorConfirmed, setCollectorConfirmed] = useState(false);
  const [collectorFocused, setCollectorFocused] = useState(false);

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
  const languageRef = useRef(language);
  const targetFramesRef = useRef(targetFrames);
  const onSampleCaptureRef = useRef(onSampleCapture);
  const connectionIssueRef = useRef(connectionIssue);
  const handleCloseRef = useRef<() => void>(() => { });
  const completedCapturesRef = useRef(0);
  const lastFrameTimeRef = useRef(0);
  const frameIntervalMs = useRef(FRAME_INTERVAL_MS);

  // FIX (backup timer): Use a ref so the 30-second backup timer fires only
  // once, not on every re-render while countdown===0 && recording.
  const backupTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // =========================================================================
  // PHASE 1A: TEMPORAL STABILIZATION REFS (Majority voting + grace + recovery)
  // =========================================================================
  const initializationCompleteRef = useRef(false);
  const initFrameCountRef = useRef(0);
  const detectionHistoryRef = useRef<number[]>([0, 0, 0, 0, 0, 0, 0]); // Ring buffer for hand counts
  const historyIndexRef = useRef(0);
  const graceCounterRef = useRef(0);           // Counts CONSECUTIVE hand-count mismatches
  const isRecoveringRef = useRef(false);       // True when in recovery state
  const recoveryTimeoutRef = useRef(0);        // Counts total frames in recovery (for timeout)
  const recoveryConfirmRef = useRef(0);        // Counts CONSECUTIVE matching frames (for resume)

  // -------------------------------------------------------------------------
  // Sync state → refs
  // -------------------------------------------------------------------------
  useEffect(() => { recordingRef.current = recording; }, [recording]);
  useEffect(() => { pausedRef.current = paused; }, [paused]);
  useEffect(() => { framesRef.current = frames; }, [frames]);
  useEffect(() => { labelRef.current = label; }, [label]);
  useEffect(() => { dialectRef.current = dialect; }, [dialect]);
  useEffect(() => { languageRef.current = language; }, [language]);
  useEffect(() => { userRef.current = user; }, [user]);
  useEffect(() => { modeRef.current = mode; }, [mode]);
  useEffect(() => { onSampleCaptureRef.current = onSampleCapture; }, [onSampleCapture]);
  useEffect(() => { connectionIssueRef.current = connectionIssue; }, [connectionIssue]);
  useEffect(() => { completedCapturesRef.current = completedCaptures; }, [completedCaptures]);
  useEffect(() => { targetFramesRef.current = FIXED_TARGET_FRAMES; }, [targetFrames]);

  useEffect(() => {
    if (!isOpen) return;
    setLabel(initialLabel);
    setUser(sanitizeCollectorName(initialUser));
  }, [isOpen, initialLabel, initialUser]);

  // PHASE 1A: Reset temporal stabilization refs when recording starts
  useEffect(() => {
    if (recording) {
      // Recording just started: reset all temporal stabilization refs
      initializationCompleteRef.current = false;
      initFrameCountRef.current = 0;
      detectionHistoryRef.current = [0, 0, 0, 0, 0, 0, 0];
      historyIndexRef.current = 0;
      graceCounterRef.current = 0;
      isRecoveringRef.current = false;
      recoveryTimeoutRef.current = 0;
      recoveryConfirmRef.current = 0;
    }
  }, [recording]);

  // -------------------------------------------------------------------------
  // Debounced label suggestions from server
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (labelSuggestTimerRef.current) clearTimeout(labelSuggestTimerRef.current);
    // Don't fetch when confirmed or empty
    if (labelConfirmed || !label.trim()) {
      setServerLabelSuggestions([]);
      return;
    }
    const langKey = normalizeLanguageKey(language);
    const diaKey = normalizeDialectKey(dialect);
    labelSuggestTimerRef.current = setTimeout(async () => {
      const results = await fetchLabelSuggestions(label, langKey, diaKey, 3);
      setServerLabelSuggestions(results);
    }, 200);
    return () => { if (labelSuggestTimerRef.current) clearTimeout(labelSuggestTimerRef.current); };
  }, [label, language, dialect, labelConfirmed]);

  // -------------------------------------------------------------------------
  // Debounced collector suggestions from server
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (collectorSuggestTimerRef.current) clearTimeout(collectorSuggestTimerRef.current);
    // Don't fetch when confirmed or empty
    if (collectorConfirmed || !user.trim()) {
      setCollectorSuggestions([]);
      return;
    }
    const langKey = normalizeLanguageKey(language);
    const diaKey = normalizeDialectKey(dialect);
    collectorSuggestTimerRef.current = setTimeout(async () => {
      const results = await fetchCollectorSuggestions(user, langKey, diaKey, 3);
      setCollectorSuggestions(results);
    }, 200);
    return () => { if (collectorSuggestTimerRef.current) clearTimeout(collectorSuggestTimerRef.current); };
  }, [user, language, dialect, collectorConfirmed]);

  // -------------------------------------------------------------------------
  // Helpers
  // -------------------------------------------------------------------------

  const handleSetExpectedHands = useCallback((v: number | null) => {
    setExpectedHandsOption(v);
    expectedHandsOptionRef.current = v;
  }, []);

  const computeQuality = useCallback((capturedFrames: Array<{ left_hand: MediaPipeLandmark[]; right_hand: MediaPipeLandmark[] }>) => {
    let totalHandLandmarks = 0;
    let framesWithHands = 0;
    let framesWithBothHands = 0;
    let framesAccepted = 0;
    let confidenceSum = 0;
    let confidenceCount = 0;

    for (const f of capturedFrames) {
      const leftCount = (f.left_hand || []).length;
      const rightCount = (f.right_hand || []).length;
      const handCount = leftCount + rightCount;
      totalHandLandmarks += handCount;
      if (handCount > 0) { framesWithHands++; framesAccepted++; }
      if (leftCount > 0 && rightCount > 0) framesWithBothHands++;

      for (const lm of [...(f.left_hand || []), ...(f.right_hand || [])]) {
        if (typeof lm.visibility === "number") { confidenceSum += lm.visibility; confidenceCount++; }
      }
    }

    const quality: QualityInfo = {
      framesCollected: capturedFrames.length,
      framesAccepted,
      avgPoseLandmarksPerFrame: capturedFrames.length ? totalHandLandmarks / capturedFrames.length : 0,
      percentFramesWithHands: capturedFrames.length ? (framesWithHands / capturedFrames.length) * 100 : 0,
      percentFramesWithBothHands: capturedFrames.length ? (framesWithBothHands / capturedFrames.length) * 100 : 0,
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

    const frameSource = (video && video.readyState >= 2 && video.videoWidth > 0 ? video : data.image) as HTMLImageElement | HTMLVideoElement | null | undefined;
    if (!frameSource) return;

    const { width: frameWidth, height: frameHeight } = getFrameDimensions(frameSource);
    if (canvas.width !== frameWidth) canvas.width = frameWidth;
    if (canvas.height !== frameHeight) canvas.height = frameHeight;

    ctx.clearRect(0, 0, frameWidth, frameHeight);
    ctx.save();
    if (MIRROR_PREVIEW) { ctx.translate(frameWidth, 0); ctx.scale(-1, 1); }

    ctx.drawImage(frameSource, 0, 0, frameWidth, frameHeight);

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
  // Catalog sync
  // -------------------------------------------------------------------------
  useEffect(() => {
    if (!isOpen) return;

    let active = true;

    const loadDialectCatalog = async () => {
      setCatalogLoading(true);
      setCatalogError("");

      try {
        // Load saved preferences from server (replaces localStorage)
        const [classesRes, statsRes, savedLanguage, savedDialect] = await Promise.all([
          getClassesList(),
          getClassesStats(),
          getPreference("languageSelected"),
          getPreference("dialectSelected"),
        ]);

        if (!active) return;

        const serverRows = classesRes.ok ? classesRes.data.items : [];
        const serverDialects = Array.from(
          new Set(
            serverRows
              .map((row) => displayDialectLabel(row.dialect))
              .filter((item): item is string => Boolean(item))
          )
        );
        const serverLanguages = Array.from(
          new Set(
            serverRows
              .map((row) => normalizeLanguageKey(row.language))
              .filter((item): item is string => Boolean(item))
          )
        );

        const mergedDialects = Array.from(new Set([
          ...serverDialects,
          ...DEFAULT_DIALECTS,
        ]));
        const mergedLanguages = Array.from(new Set([
          ...serverLanguages,
          ...DEFAULT_LANGUAGES,
        ]));

        setLanguageList(mergedLanguages);
        setDialectList(mergedDialects);
        setCatalogRows(serverRows);

        const nextStats: Record<string, number> = {};
        if (statsRes.ok) {
          for (const row of statsRes.data.distribution) {
            if (row.class_uid) nextStats[row.class_uid] = row.count ?? row.samples_count ?? 0;
          }
        }
        setCatalogStatsByUid(nextStats);

        // Restore language/dialect from server preferences
        const storedLanguage = normalizeLanguageKey(savedLanguage || "");
        const nextLanguage = storedLanguage && mergedLanguages.includes(storedLanguage)
          ? storedLanguage
          : (mergedLanguages[0] || DEFAULT_LANGUAGES[0]);

        const storedSel = displayDialectLabel(savedDialect || "");
        const availableDialectsForLanguage = Array.from(
          new Set(
            serverRows
              .filter((row) => normalizeLanguageKey(row.language) === nextLanguage)
              .map((row) => displayDialectLabel(row.dialect))
              .filter((item): item is string => Boolean(item))
          )
        );

        const nextDialect = storedSel && mergedDialects.includes(storedSel) && (
          availableDialectsForLanguage.length === 0 || availableDialectsForLanguage.includes(storedSel)
        )
          ? storedSel
          : (availableDialectsForLanguage[0] || mergedDialects[0] || DEFAULT_DIALECTS[0]);

        setLanguage(nextLanguage);
        setDialect(nextDialect);

        // Persist to server
        setPreference("languageSelected", nextLanguage);
        setPreference("dialectSelected", nextDialect);

        if (!classesRes.ok && !statsRes.ok) {
          setCatalogError("Không tải được danh sách bộ ngôn ngữ từ máy chủ.");
        }
      } catch {
        if (!active) return;
        setCatalogError("Không tải được dữ liệu bộ ngôn ngữ.");
        setDialectList((prev) => prev.length > 0 ? prev : DEFAULT_DIALECTS);
      } finally {
        if (active) setCatalogLoading(false);
      }
    };

    loadDialectCatalog();

    return () => {
      active = false;
    };
  }, [isOpen]);

  const selectedLanguageKey = normalizeLanguageKey(language);
  const selectedDialectKey = normalizeDialectKey(dialect);
  const selectedLanguageRows = catalogRows.filter((row) => normalizeLanguageKey(row.language) === selectedLanguageKey);
  const selectedDialectRows = selectedLanguageRows.filter((row) => normalizeDialectKey(row.dialect) === selectedDialectKey);
  const normalizedLabel = normalizeText(label);
  // Use server-side suggestions instead of client-side filter
  const labelSuggestions = serverLabelSuggestions;
  const matchingCatalogRow = normalizedLabel
    ? selectedDialectRows.find((row) => normalizeText(row.label_original) === normalizedLabel)
    : undefined;
  const labelExists = Boolean(matchingCatalogRow);
  const labelSamplesCount = matchingCatalogRow ? (catalogStatsByUid[matchingCatalogRow.class_uid] ?? 0) : 0;
  const currentCatalogLabelCount = selectedDialectRows.length;

  // Nhãn đã có hands_required trên class (đã chuẩn hoá thành 1|2|null ở
  // getClassesList) → khoá selector theo giá trị của class.
  const lockedHands = typeof matchingCatalogRow?.hands_required === "number"
    ? matchingCatalogRow.hands_required
    : null;

  useEffect(() => {
    if (lockedHands !== null) handleSetExpectedHands(lockedHands);
  }, [lockedHands, handleSetExpectedHands]);

  // In-modal QC toast: auto-dismiss sau 5s, re-trigger theo notice.key
  const [visibleNotice, setVisibleNotice] = useState<typeof qualityNotice>(null);
  useEffect(() => {
    if (!qualityNotice) return;
    setVisibleNotice(qualityNotice);
    const timer = setTimeout(() => setVisibleNotice(null), 5000);
    return () => clearTimeout(timer);
  }, [qualityNotice]);

  // -------------------------------------------------------------------------
  // Capture handlers
  // -------------------------------------------------------------------------
  const handleQuickCapture = useCallback(() => {
    if (!labelRef.current || !userRef.current || connectionIssueRef.current) return;
    setFrames([]); framesRef.current = [];
    expectedHandsRef.current = expectedHandsOptionRef.current;
    setCurrentCaptureIndex(0); setCompletedCaptures(0); completedCapturesRef.current = 0;
    lastFrameTimeRef.current = 0; setCountdown(3); setMode("COUNTDOWN");
    setTimeout(() => {
      setRecording(true); recordingRef.current = true; setMode("RECORD");
      lastFrameTimeRef.current = Date.now();
    }, 3000);
  }, []);

  const handlePause = useCallback(() => { setPaused(true); pausedRef.current = true; }, []);
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
      onSampleCaptureRef.current(framesRef.current, labelRef.current, userRef.current, {
        quality_info: quality,
        dialect: dialectRef.current,
        language: languageRef.current,
        hands_used: expectedHandsOptionRef.current ?? expectedHandsRef.current,
      });
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

      const detected = r.multiHandLandmarks || [];
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
      let leftHandLandmarks: MediaPipeLandmark[] | undefined;
      let rightHandLandmarks: MediaPipeLandmark[] | undefined;

      detected.forEach((landmarks, i) => {
        const rawLabel = handednessData[i]?.label; // "Left" or "Right" from MP
        const effectiveLabel = SWAP_HANDEDNESS
          ? rawLabel === "Left" ? "Right" : "Left"
          : rawLabel;

        if (effectiveLabel === "Left") leftHandLandmarks = landmarks;
        else if (effectiveLabel === "Right") rightHandLandmarks = landmarks;
      });

      // ---- Temporal smoothing for presence / preview ----
      const leftDetectedNow = !!(leftHandLandmarks && leftHandLandmarks.length > 0);
      const rightDetectedNow = !!(rightHandLandmarks && rightHandLandmarks.length > 0);

      leftPresenceHistoryRef.current.push(leftDetectedNow);
      if (leftPresenceHistoryRef.current.length > PRESENCE_HISTORY_SIZE) leftPresenceHistoryRef.current.shift();
      rightPresenceHistoryRef.current.push(rightDetectedNow);
      if (rightPresenceHistoryRef.current.length > PRESENCE_HISTORY_SIZE) rightPresenceHistoryRef.current.shift();

      const leftVotes = leftPresenceHistoryRef.current.filter(Boolean).length;
      const rightVotes = rightPresenceHistoryRef.current.filter(Boolean).length;
      const leftSmoothedVisible = leftVotes > leftPresenceHistoryRef.current.length / 2;
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
      let renderLeft: MediaPipeLandmark[] = [];
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
      const rawLeft = leftHandLandmarks;
      const rawRight = rightHandLandmarks;

      const rawLeftHas = (rawLeft?.length ?? 0) > 0;
      const rawRightHas = (rawRight?.length ?? 0) > 0;

      const computeHandConfidence = (lms?: MediaPipeLandmark[]) => {
        if (!lms || lms.length === 0) return undefined;
        let sum = 0, cnt = 0;
        for (const lm of lms) if (typeof lm.visibility === "number") { sum += lm.visibility; cnt++; }
        return cnt > 0 ? sum / cnt : undefined;
      };

      const leftConf = computeHandConfidence(rawLeft);
      const rightConf = computeHandConfidence(rawRight);

      const confCandidates: number[] = [];
      if (typeof leftConf === "number") confCandidates.push(leftConf);
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

      const presentLeftRaw = rawLeftHas;
      const presentRightRaw = rawRightHas;
      const detectedHandsCountRaw = (presentLeftRaw ? 1 : 0) + (presentRightRaw ? 1 : 0);

      let accept = false;
      const userChoice = expectedHandsOptionRef.current;

      // =====================================================================
      // PHASE 1A: TEMPORAL STABILIZATION
      // Majority voting (init) + grace period + recovery with no auto-switching
      // =====================================================================
      const INIT_WINDOW = 5;
      const INIT_MAJORITY_THRESHOLD = 0.60;
      const GRACE_FRAMES = 2;
      const RECOVERY_TIMEOUT = 3;
      const RECOVERY_CONFIRM = 3;
      const HISTORY_SIZE = 7;

      if (detectedHandsCountRaw === 0) {
        // No hands detected at all
        accept = false;
      } else if (userChoice != null) {
        // Manual mode: user selected 1 or 2 hands explicitly
        if (userChoice === 2) accept = presentLeftRaw && presentRightRaw;
        else if (userChoice === 1) accept = presentLeftRaw !== presentRightRaw;
        else accept = true;
      } else if (expectedHandsRef.current == null) {
        // AUTO MODE: INITIALIZATION PHASE (warmup-only, no append to dataset)
        initFrameCountRef.current++;

        // Update history ring buffer
        detectionHistoryRef.current[historyIndexRef.current] = detectedHandsCountRaw;
        historyIndexRef.current = (historyIndexRef.current + 1) % HISTORY_SIZE;

        if (initFrameCountRef.current < INIT_WINDOW) {
          // Still collecting frames for initialization
          accept = false;
        } else if (initFrameCountRef.current === INIT_WINDOW) {
          // End of warmup window: infer the most likely hand-count mode.
          const recentCounts = detectionHistoryRef.current.slice(0, INIT_WINDOW);
          const oneHandCount = recentCounts.filter(c => c === 1).length;
          const twoHandCount = recentCounts.filter(c => c === 2).length;

          if (twoHandCount >= INIT_WINDOW * INIT_MAJORITY_THRESHOLD && twoHandCount >= oneHandCount) {
            expectedHandsRef.current = 2;
          } else if (oneHandCount > 0) {
            expectedHandsRef.current = 1;
          } else {
            expectedHandsRef.current = 1;
          }
          initializationCompleteRef.current = true;
          accept = false; // Don't accept the init frame itself
          if (DEBUG_HANDS) console.log("Inferred expectedHands via warmup =", expectedHandsRef.current, {
            oneHandCount,
            twoHandCount,
            recentCounts,
          });
        }
      } else if (initializationCompleteRef.current && expectedHandsRef.current !== null) {
        // AUTO MODE: TRACKING / GRACE / RECOVERY PHASES

        // Update history ring buffer (for debug/telemetry only)
        detectionHistoryRef.current[historyIndexRef.current] = detectedHandsCountRaw;
        historyIndexRef.current = (historyIndexRef.current + 1) % HISTORY_SIZE;

        const currentHandCount = detectedHandsCountRaw;
        const isMatching = currentHandCount === expectedHandsRef.current;

        if (isMatching) {
          // TRACKING: Hand count matches expectation
          // Reset all grace/recovery counters
          graceCounterRef.current = 0;
          isRecoveringRef.current = false;
          recoveryTimeoutRef.current = 0;
          recoveryConfirmRef.current = 0;
          accept = true;
        } else if (!isRecoveringRef.current) {
          // GRACE PERIOD: Mismatch & not in recovery yet
          graceCounterRef.current++;

          if (graceCounterRef.current <= GRACE_FRAMES) {
            // Still in grace period: don't accept, but don't pause
            accept = false;
            if (DEBUG_HANDS) console.debug("Grace period", graceCounterRef.current, "/", GRACE_FRAMES);
          } else {
            // Grace period exceeded: enter recovery state, pause capture
            isRecoveringRef.current = true;
            recoveryTimeoutRef.current = 0;
            recoveryConfirmRef.current = 0;
            accept = false;
            if (DEBUG_HANDS) console.warn("Grace period exceeded, entering recovery");
          }
        } else if (isRecoveringRef.current) {
          // RECOVERY: Wait for hands to return
          // Track two separate counts:
          // - recoveryTimeoutRef: total frames in recovery (for timeout detection)
          // - recoveryConfirmRef: CONSECUTIVE matching frames (for resume confirmation)

          recoveryTimeoutRef.current++;

          if (currentHandCount === expectedHandsRef.current) {
            // Hands match this frame!
            recoveryConfirmRef.current++;

            if (recoveryConfirmRef.current >= RECOVERY_CONFIRM) {
              // Confirmed! Resume capture (3 consecutive matching frames)
              isRecoveringRef.current = false;
              graceCounterRef.current = 0;
              recoveryTimeoutRef.current = 0;
              recoveryConfirmRef.current = 0;
              accept = true;
              if (DEBUG_HANDS) console.log("Recovery successful, resuming capture");
            } else {
              // Still building up consecutive matches
              accept = false;
              if (DEBUG_HANDS) console.debug("Recovery progress", recoveryConfirmRef.current, "/", RECOVERY_CONFIRM);
            }
          } else {
            // Hands DON'T match this frame
            recoveryConfirmRef.current = 0; // RESET consecutive match counter on mismatch

            if (recoveryTimeoutRef.current >= RECOVERY_TIMEOUT) {
              // Recovery timeout exceeded (hands missing for 3+ frames)
              // DO NOT auto-switch expectations (prevents mode drift from temporary occlusion)
              // Remain in recovery state, pause capture
              accept = false;
              if (DEBUG_HANDS) console.warn("Recovery timeout exceeded, waiting for hands to reappear");
            } else {
              // Still within recovery window, waiting for hands
              accept = false;
            }
          }
        }
      } else {
        // Fallback (should not reach here in normal operation)
        accept = false;
      }

      // Auto mode should not stall on transient hand-count drops.
      // The backend zero-fills missing hand slots, so as long as at least one
      // hand is visible we can keep sampling without blocking the recording.
      if (userChoice == null && initializationCompleteRef.current && detectedHandsCountRaw > 0) {
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
        left_hand: rawLeft ? rawLeft.map(mirrorLandmarkX) : [],
        right_hand: rawRight ? rawRight.map(mirrorLandmarkX) : [],
        timestamp_ms,
        fallback_used: false,
        confidence: typeof confidence === "number" ? confidence : undefined,
      };

      // PHASE 1A: Only append to dataset after initialization is complete
      // (Warmup frames during first 5 frames are not appended)
      if (accept && initializationCompleteRef.current) {
        framesRef.current.push(frameEntry);
        setFrames([...framesRef.current]);
      }

      if (framesRef.current.length >= FIXED_TARGET_FRAMES) {
        recordingRef.current = false;
        setRecording(false);
        setMode("IDLE");

        const capturedFrames = [...framesRef.current];
        const quality = computeQuality(capturedFrames);
        const newCompleted = completedCapturesRef.current + 1;

        onSampleCaptureRef.current(capturedFrames, labelRef.current, userRef.current, {
          quality_info: quality,
          dialect: dialectRef.current,
          language: languageRef.current,
          hands_used: expectedHandsOptionRef.current ?? expectedHandsRef.current,
        });

        completedCapturesRef.current = newCompleted;
        setCompletedCaptures(newCompleted);
        setCurrentCaptureIndex(newCompleted);

        if (newCompleted < FIXED_CAPTURE_COUNT) {
          setFrames([]); framesRef.current = [];
          expectedHandsRef.current = expectedHandsOptionRef.current;
          lastFrameTimeRef.current = 0;
          // PHASE 1A: Reset temporal stabilization refs for next capture
          initializationCompleteRef.current = false;
          initFrameCountRef.current = 0;
          detectionHistoryRef.current = [0, 0, 0, 0, 0, 0, 0];
          historyIndexRef.current = 0;
          graceCounterRef.current = 0;
          isRecoveringRef.current = false;
          recoveryTimeoutRef.current = 0;
          recoveryConfirmRef.current = 0;
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
            // PHASE 1A: Reset temporal stabilization refs when done
            initializationCompleteRef.current = false;
            initFrameCountRef.current = 0;
            detectionHistoryRef.current = [0, 0, 0, 0, 0, 0, 0];
            historyIndexRef.current = 0;
            graceCounterRef.current = 0;
            isRecoveringRef.current = false;
            recoveryTimeoutRef.current = 0;
            recoveryConfirmRef.current = 0;
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
    if (canvas) { canvas.width = CAPTURE_FRAME_WIDTH; canvas.height = CAPTURE_FRAME_HEIGHT; }

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
      width: CAPTURE_FRAME_WIDTH,
      height: CAPTURE_FRAME_HEIGHT,
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
        if (!recordingRef.current && labelRef.current && userRef.current && !connectionIssueRef.current) {
          setFrames([]); framesRef.current = [];
          expectedHandsRef.current = expectedHandsOptionRef.current;
          setCurrentCaptureIndex(0); setCompletedCaptures(0); completedCapturesRef.current = 0;
          setCountdown(3); setMode("COUNTDOWN");
          setTimeout(() => { setRecording(true); recordingRef.current = true; setMode("RECORD"); }, 3000);
        } else if (recordingRef.current) {
          const collected = framesRef.current.length || 0;
          const required = targetFramesRef.current || 0;
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

  useEffect(() => {
    // Chặn cuộn trên body
    const originalOverflow = document.body.style.overflow;
    const originalHeight = document.body.style.height;

    document.body.style.overflow = 'hidden';
    document.body.style.height = '100dvh';

    return () => {
      // Trả lại trạng thái cũ khi đóng full screen
      document.body.style.overflow = originalOverflow;
      document.body.style.height = originalHeight;
    };
  }, []);

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------
  if (!isOpen) return null;

  return (
    <div ref={rootRef} className="fixed inset-0 h-[100dvh] w-screen z-[9999] bg-black flex flex-col overflow-hidden">
      {/* QC notice — phải nằm TRONG root vì element-fullscreen che toast global */}
      {visibleNotice && (
        <div className="fixed bottom-4 right-4 z-[10001] max-w-sm pointer-events-none">
          <div
            className={`pointer-events-auto rounded-lg border px-4 py-3 text-sm shadow-xl backdrop-blur-md ${
              visibleNotice.kind === "error"
                ? "bg-red-900/85 border-red-500 text-red-100"
                : "bg-yellow-900/85 border-yellow-500 text-yellow-100"
            }`}
            role="status"
            aria-live="polite"
          >
            <div className="flex items-start gap-2">
              <span>{visibleNotice.kind === "error" ? "⛔" : "⚠️"}</span>
              <span className="leading-snug">{visibleNotice.message}</span>
              <button
                onClick={() => setVisibleNotice(null)}
                className="ml-auto -mr-1 -mt-1 p-1 opacity-70 hover:opacity-100"
                aria-label="Đóng thông báo"
              >
                ✕
              </button>
            </div>
          </div>
        </div>
      )}
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
              <button onClick={() => { setCameraError(null); window.location.reload(); }} className="flex-1 bg-ctu-blue hover:bg-ctu-navy-mid text-white font-semibold py-3 px-4 rounded-lg transition-colors">Làm mới Trang</button>
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
                    disabled={recording || lockedHands !== null}
                    className={`px-3 py-1 text-sm ${expectedHandsOption === v ? "bg-gray-700 text-white" : "text-gray-300 hover:bg-gray-700"} ${lockedHands !== null ? "opacity-60 cursor-not-allowed" : ""}`}
                  >
                    {v === null ? "Auto" : v}
                  </button>
                ))}
              </div>
              {lockedHands !== null && (
                <span className="text-xs text-ctu-yellow" title="Nhãn này đã được ghi nhận cần số tay cố định — không thể thay đổi khi thu.">
                  🔒 Cố định theo nhãn ({lockedHands} tay)
                </span>
              )}
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
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row pt-0 sm:pt-20 overflow-hidden">
        {/* Camera Feed */}
        <div className="flex-1 relative flex items-center justify-center bg-gray-900 w-full min-h-[42svh] sm:min-h-[50vh] lg:h-full overflow-hidden">
          <video ref={videoRef} autoPlay muted playsInline className="hidden" />
          <canvas
            ref={canvasRef}
            width={CAPTURE_FRAME_WIDTH}
            height={CAPTURE_FRAME_HEIGHT}
            className="block w-full h-full max-w-full max-h-full object-cover sm:object-contain border border-gray-600 rounded-lg bg-gray-950"
            style={{ minHeight: "200px" }}
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
                <div className="relative w-56 h-56 sm:w-80 sm:h-80">
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
                <div className="absolute -top-10 sm:-top-12 left-1/2 transform -translate-x-1/2 bg-gray-800/80 backdrop-blur-sm text-white px-3 sm:px-4 py-2 rounded-lg text-xs sm:text-sm font-medium">🎯 Đặt vị trí vào khung</div>
                <div className="absolute -bottom-7 sm:-bottom-8 left-1/2 transform -translate-x-1/2 bg-gray-800/70 backdrop-blur-sm text-white px-3 py-1 rounded-lg text-[11px] sm:text-xs text-center">Thấy phần trên cơ thể và hai tay</div>
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
              <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 sm:p-8 w-full max-w-[calc(100vw-2rem)] sm:max-w-lg">
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
            <div className="absolute top-20 sm:top-24 left-3 sm:left-6 flex items-center space-x-3 bg-red-500 text-white px-3 sm:px-4 py-2 rounded-full shadow-lg">
              <div className="w-3 h-3 bg-white rounded-full animate-pulse"></div>
              <span className="font-medium">ĐANG GHI</span>
              {FIXED_CAPTURE_COUNT > 1 && <span className="text-sm">({completedCaptures + 1}/{FIXED_CAPTURE_COUNT})</span>}
            </div>
          )}

          {recording && (
            <div className="absolute bottom-3 sm:bottom-6 left-1/2 transform -translate-x-1/2 bg-black/50 backdrop-blur-sm rounded-full px-4 sm:px-6 py-2 max-w-[calc(100vw-2rem)]">
              <div className="text-white text-sm">📊 {frames.length} khung đã chụp</div>
            </div>
          )}
        </div>

        {/* Control Panel */}
        <div className="w-full lg:w-96 bg-gray-900 border-l border-gray-700 flex flex-col max-h-[60%] lg:max-h-none flex-shrink-0">
          <div className="flex-1 p-2.5 sm:p-4 lg:p-5 space-y-2 sm:space-y-3 overflow-y-auto">
            {/* Connectivity / save warning — blocks new captures while shown */}
            {connectionIssue && (
              <div className="flex items-start gap-2 bg-red-900/40 border border-red-500/50 rounded-lg px-3 py-2 text-xs sm:text-sm text-red-100">
                <span className="text-base leading-none">⚠️</span>
                <div>
                  <div className="font-semibold">Kết nối/lưu server đang gặp sự cố</div>
                  <div className="text-red-200/90 mt-0.5">{connectionIssue} Vui lòng tạm ngưng thu để tránh mất dữ liệu.</div>
                </div>
              </div>
            )}

            {/* Session capture list — collapsed by default */}
            <CapturedWordsSummary summary={capturedSummary} />

            {/* --- Compact Settings Card --- */}
            <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 rounded-xl p-2.5 sm:p-4 border border-blue-500/20 space-y-2 sm:space-y-3">
              {/* Label input */}
              <div>
                <label className="block text-[11px] sm:text-xs font-medium text-blue-300 mb-1">📝 Nhãn *</label>
                <div className="relative">
                  <input type="text" value={label} onChange={(e) => { setLabel(e.target.value); setLabelConfirmed(false); }} onFocus={() => setLabelFocused(true)} onBlur={() => setTimeout(() => setLabelFocused(false), 150)} placeholder="vd: xin chào, cảm ơn" className="w-full pr-10 px-2.5 py-1.5 sm:px-3 sm:py-2 bg-gray-800/80 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm" disabled={recording || countdown > 0} />
                  <div className="absolute inset-y-0 right-1.5 flex items-center">
                    <SpeechInputButton onText={(text) => setLabel(text)} title="Giọng nói" className="h-7 w-7" />
                  </div>
                </div>
                {labelFocused && !catalogLoading && !catalogError && labelSuggestions.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {labelSuggestions.map((s) => (
                      <button type="button" key={s} onMouseDown={(e) => e.preventDefault()} onClick={() => { setLabel(s); setLabelConfirmed(true); setServerLabelSuggestions([]); setLabelFocused(false); }} className="rounded-full border border-blue-500/30 bg-blue-950/50 px-2 py-px text-[10px] text-blue-200 hover:bg-blue-800 hover:text-white" disabled={recording || countdown > 0}>{s}</button>
                    ))}
                  </div>
                )}
                {normalizedLabel && !catalogLoading && !catalogError && (
                  <div className="mt-1 text-[10px] sm:text-xs text-blue-200/80">
                    {labelExists ? (
                      <span className="text-green-300">✓ Đã có {labelSamplesCount} mẫu</span>
                    ) : (
                      <span className="text-yellow-300">⚠ Nhãn mới ({currentCatalogLabelCount} nhãn hiện có)</span>
                    )}
                  </div>
                )}
              </div>
              {/* User input */}
              <div>
                <label className="block text-[11px] sm:text-xs font-medium text-blue-300 mb-1">👤 Người thực hiện *</label>
                <div className="relative">
                  <input type="text" value={user} onChange={(e) => { setUser(sanitizeCollectorName(e.target.value)); setCollectorConfirmed(false); }} onFocus={() => setCollectorFocused(true)} onBlur={() => setTimeout(() => setCollectorFocused(false), 150)} placeholder="Ví dụ: Trân" className="w-full pr-10 px-2.5 py-1.5 sm:px-3 sm:py-2 bg-gray-800/80 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm" disabled={recording || countdown > 0} />
                  <div className="absolute inset-y-0 right-1.5 flex items-center">
                    <SpeechInputButton onText={(text) => setUser(text)} title="Giọng nói" className="h-7 w-7" />
                  </div>
                </div>
                {collectorFocused && collectorSuggestions.length > 0 && (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {collectorSuggestions.map((name) => (
                      <button type="button" key={name} onMouseDown={(e) => e.preventDefault()} onClick={() => { setUser(name); setCollectorConfirmed(true); setCollectorSuggestions([]); setCollectorFocused(false); }} className="rounded-full border border-blue-500/30 bg-blue-950/50 px-2 py-px text-[10px] text-blue-200 hover:bg-blue-800 hover:text-white">{name}</button>
                    ))}
                  </div>
                )}
              </div>
              {/* Language / Dialect — searchable compact dropdowns */}
              <div className="grid grid-cols-2 gap-1.5 sm:gap-2">
                <SearchableSelect
                  label="🌐 Ngôn ngữ"
                  value={language}
                  options={languageList}
                  displayFn={displayLanguageLabel}
                  onChange={(v) => {
                    const key = normalizeLanguageKey(v);
                    setLanguage(key);
                    setPreference("languageSelected", key);
                    const availableDialectsForLanguage = Array.from(
                      new Set(
                        catalogRows
                          .filter((row) => normalizeLanguageKey(row.language) === key)
                          .map((row) => displayDialectLabel(row.dialect))
                          .filter((item): item is string => Boolean(item))
                      )
                    );
                    if (availableDialectsForLanguage.length > 0 && !availableDialectsForLanguage.includes(dialect)) {
                      const fallbackDialect = availableDialectsForLanguage[0];
                      setDialect(fallbackDialect);
                      setPreference("dialectSelected", fallbackDialect);
                    }
                  }}
                  disabled={recording || countdown > 0}
                />
                <SearchableSelect
                  label="🧭 Phương ngữ"
                  value={dialect}
                  options={[...dialectList, "Khác (+)"]}
                  displayFn={(v) => v}
                  onChange={(v) => {
                    if (v === "Khác (+)") { setShowAddDialectModal(true); }
                    else { setDialect(v); setPreference("dialectSelected", v); }
                  }}
                  disabled={recording || countdown > 0}
                />
              </div>
              <div className="text-[10px] text-blue-200/60">
                {catalogLoading ? "Đang tải..." : `${displayLanguageLabel(language)} / ${displayDialectLabel(dialect)} • ${currentCatalogLabelCount} nhãn`}
              </div>
            </div>

            <AddDialectModal isOpen={showAddDialectModal} onClose={() => setShowAddDialectModal(false)} onAdd={(name) => {
              const updated = Array.from(new Set([...dialectList, name]));
              setDialectList(updated); setDialect(name);
              setPreference("dialectSelected", name);
            }} />

            {/* Status — desktop only */}
            <div className="bg-gray-800 rounded-lg p-3 hidden sm:block">
              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between text-gray-400"><span>Lần chụp:</span><span className="text-white">{currentCaptureIndex + 1}/{FIXED_CAPTURE_COUNT}</span></div>
                {frames.length > 0 && (
                  <div className="w-full bg-gray-700 rounded-full h-1.5">
                    <div className="bg-blue-600 h-1.5 rounded-full transition-all duration-300" style={{ width: `${Math.min((frames.length / FIXED_TARGET_FRAMES) * 100, 100)}%` }} />
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
          <div className="p-3 sm:p-4 lg:p-6 border-t border-gray-700 space-y-2 sm:space-y-3 bg-gray-900/95">
            {countdown > 0 ? (
              <div className="w-full py-3 bg-yellow-600 text-white rounded-lg text-center font-medium text-sm sm:text-base">Bắt đầu sau {countdown}...</div>
            ) : !recording ? (
              <Button
                onClick={handleQuickCapture}
                disabled={!label || !user || !isReady || !!connectionIssue}
                className="w-full py-3 sm:py-4 text-sm sm:text-base font-medium"
                variant="primary"
                title={connectionIssue ? "Đang gặp sự cố kết nối/lưu server — tạm ngưng thu" : undefined}
              >
                <svg className="w-4 h-4 sm:w-5 sm:h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                {FIXED_CAPTURE_COUNT > 1 ? `Bắt đầu chụp (${FIXED_CAPTURE_COUNT}x)` : "Bắt đầu chụp"} (Enter)
              </Button>
            ) : paused ? (
              <div className="text-center py-3 text-gray-400 text-sm">
                <span className="text-yellow-500 font-medium">⏸ Đã tạm dừng</span>
                <p className="text-sm mt-1">Xem các tùy chọn trên màn hình</p>
              </div>
            ) : (
              <>
                <Button onClick={handlePause} className="w-full py-3 sm:py-4 text-sm sm:text-base font-medium bg-yellow-600 hover:bg-yellow-500" variant="secondary">
                  <svg className="w-4 h-4 sm:w-5 sm:h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                  Tạm dừng (Space)
                </Button>
                <Button onClick={handleStop} className="w-full py-3 text-sm sm:text-base" variant="danger" disabled={frames.length < FIXED_TARGET_FRAMES} title={frames.length < FIXED_TARGET_FRAMES ? `Cần ${FIXED_TARGET_FRAMES} khung trước khi dừng` : undefined}>
                  <svg className="w-4 h-4 sm:w-5 sm:h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9h6v6H9z" /></svg>
                  Dừng và lưu
                </Button>
              </>
            )}
            <Button onClick={handleClose} className="w-full py-3 text-sm sm:text-base" variant="secondary">Thoát toàn màn hình</Button>
          </div>

          {/* Tips */}
          <div className="hidden sm:block bg-gray-800 border-t border-gray-700 p-4">
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

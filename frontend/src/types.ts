export interface Label {
  class_idx: number;
  label_original: string;
  slug: string;
}

export interface SampleFrame {
  timestamp: number;
  landmarks: number[];
}

export interface Sample {
  sample_id?: string; // used by SamplesPage
  id?: number; // used by SessionPanel
  label?: string;
  dialect?: string;
  file_path?: string;
  created_at?: string;
  session_id?: string;
  user?: string;
  uploaded?: boolean;
  frames?: number; // count of frames in the sample
}

export interface SessionStats {
  totalSamples: number;
  totalFrames: number;
  avgFrames: number;
  labelsCount: Record<string, number>;
}

export interface QualityWarning {
  code: string;
  message?: string;
  detail?: Record<string, unknown>;
}

export interface UploadQuality {
  completeness?: number;
  left_hand_ratio?: number;
  right_hand_ratio?: number;
  both_hands_ratio?: number;
  any_hand_ratio?: number;
  jitter_p95?: number;
  hands_required?: number | null;
  warnings?: QualityWarning[];
  [k: string]: unknown;
}

export type UploadResult = {
  success: boolean;
  id?: string | number;
  message?: string;
  task_id?: string;
  status?: string;
  filename?: string;
  total_frames?: number;
  detail?: string;
  quality?: UploadQuality;
  [k: string]: unknown;
};

// MediaPipe landmark types for pose detection
export interface MediaPipeLandmark {
  x: number;
  y: number;
  z?: number;
  visibility?: number;
}

export interface CameraUploadPayload {
  user: string;
  label: string;
  dialect?: string;
  language?: string;
  session_id: string;
  /** 1 | 2 — persisted on the class at first capture (first-capture-wins). */
  hands_required?: number;
  /** Client-side quality snapshot; informational only, server recomputes. */
  quality_info?: QualityInfo;
  frames: Array<{
    timestamp: number;
    landmarks: {
      left_hand?: MediaPipeLandmark[];
      right_hand?: MediaPipeLandmark[];
    };
  }>;
}

export interface CameraInfo {
  userAgent?: string;
  deviceMemory?: number | null;
  hardwareConcurrency?: number | null;
  screen?: { width: number; height: number } | null;
  frameIntervalMs?: number | null;
}

export interface QualityInfo {
  framesCollected: number;
  framesAccepted?: number; // after simple client-side filter
  avgPoseLandmarksPerFrame?: number;
  percentFramesWithHands?: number;
  percentFramesWithBothHands?: number;
  confidenceSummary?: { min?: number; max?: number; avg?: number };
}

/**
 * Shape returned by GET /jobs/{job_id} (backend/app/routers/jobs.py).
 *
 * These are raw Celery states, not a custom vocabulary. The previous type here
 * declared jobId/progress/message/startTime/endTime — none of which the
 * endpoint has ever returned; it was written against an imagined API.
 */
export type CeleryJobState =
  | "PENDING"
  | "STARTED"
  | "SUCCESS"
  | "FAILURE"
  | "RETRY"
  | "REVOKED";

export type JobStatus = {
  job_id: string;
  status: CeleryJobState | string;
  /** Task return value; only populated once status is SUCCESS. */
  result?: unknown;
  /** Present only on FAILURE. */
  traceback?: string | null;
  error?: string | null;
  [k: string]: unknown;
};

/** True once the job will not change again — stop polling. */
export function isJobFinished(status: string | undefined): boolean {
  return status === "SUCCESS" || status === "FAILURE" || status === "REVOKED";
}

export interface Session {
  session_id: string;
  user: string;
  labels: string[];
  samples_count: number;
  created_at: string;
}

// New types for classes API (BE modern endpoints)
export interface ClassRow {
  class_uid: string;
  class_idx: number | string; // BE returns string (sometimes empty ""), FE will normalize
  slug: string;
  label_original: string;
  language?: string;
  dialect?: string;
  is_common_global?: boolean | string; // BE returns "0"/"1" strings
  is_common_language?: boolean | string; // BE returns "0"/"1" strings
  folder_name?: string;
  created_at?: string;
  migrated_at?: string | null;
  hands_required?: number | string | null; // BE returns ""/"1"/"2" strings, FE normalizes
  /** Vùng miền của ký hiệu — trục RIÊNG với `dialect`.
   *
   * Hai nhãn cùng `slug` + `language` + `dialect` mà khác `region` là hai lớp
   * hợp lệ, khác nhau (khoá duy nhất ở cơ sở dữ liệu gồm cả năm cột). Bỏ qua
   * trường này là hiện ra hai dòng trông giống hệt nhau. */
  region?: string;
}

export interface ClassesListResponse {
  count: number;
  items: ClassRow[];
}

export interface ClassStatsRow {
  class_uid: string;
  class_idx?: number;
  slug?: string;
  label_original?: string;
  // Backend uses `count` for samples; keep `samples_count` as legacy alias
  count: number;
  samples_count?: number;
}

export interface ClassStatsResponse {
  total_classes: number;
  max_count: number;
  distribution: ClassStatsRow[];
}

export interface Filters {
  user: string;
  label: string;
  date: string;
}

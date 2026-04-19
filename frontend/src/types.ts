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

export type UploadResult = {
  success: boolean;
  id?: string | number;
  message?: string;
  task_id?: string;
  status?: string;
  filename?: string;
  total_frames?: number;
  detail?: string;
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
  session_id: string;
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
  confidenceSummary?: { min?: number; max?: number; avg?: number };
}

export type JobStatus = {
  jobId?: string;
  status?: string;
  progress?: number;
  message?: string;
  startTime?: string;
  endTime?: string;
  [k: string]: unknown;
};

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

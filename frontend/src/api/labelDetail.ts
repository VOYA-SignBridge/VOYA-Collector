import axiosClient, { getApiBaseURL } from "./axiosClient";
import type { FramesData } from "../components/viewer/handData";

export interface LabelSession {
  session_id: string;
  user_id: string;
  username: string;
  created_at: string;
  sample_count: number;
  original_sample_uid: string;
  seq_len: number;
  fps: number;
  source_type: string;
  has_preview: boolean;
  /** Server-computed (by auth_user_id, NOT by name): this recording is the
   *  caller's own. */
  is_owner: boolean;
  /** Caller may download/delete this recording (owner or admin). */
  can_manage: boolean;
}

export interface LabelSessionsResponse {
  class_uid: string;
  label_original: string;
  slug: string;
  language: string;
  dialect: string;
  count: number;
  sessions: LabelSession[];
}

/** Same base-path normalization the axios interceptor applies to relative URLs
 *  — needed for plain <video src> / <a href> that bypass axios. */
export function apiPath(path: string): string {
  let base = getApiBaseURL().replace(/\/+$/, "");
  if (base.endsWith("/api")) base = base.slice(0, -4);
  return base + path;
}

export const getLabelSessions = async (classUid: string): Promise<LabelSessionsResponse> => {
  const res = await axiosClient.get(`/classes/${encodeURIComponent(classUid)}/sessions`);
  return res.data as LabelSessionsResponse;
};

export const getSessionFrames = async (
  classUid: string,
  sessionId: string,
): Promise<FramesData> => {
  const res = await axiosClient.get(
    `/classes/${encodeURIComponent(classUid)}/sessions/${encodeURIComponent(sessionId)}/frames`,
  );
  return res.data as FramesData;
};

export type PreviewStatus = "ready" | "rendering";

/** 200 = preview.mp4 cached on the server, 202 = render task just enqueued. */
export const getPreviewStatus = async (
  classUid: string,
  sessionId: string,
): Promise<PreviewStatus> => {
  const res = await axiosClient.get(
    `/classes/${encodeURIComponent(classUid)}/sessions/${encodeURIComponent(sessionId)}/preview`,
  );
  return res.status === 202 ? "rendering" : "ready";
};

export const previewVideoUrl = (classUid: string, sessionId: string): string =>
  apiPath(
    `/classes/${encodeURIComponent(classUid)}/sessions/${encodeURIComponent(sessionId)}/preview.mp4`,
  );

/** Original .npz download (existing dataset endpoint). */
export const sampleDownloadUrl = (sampleUid: string): string =>
  apiPath(`/dataset/samples/${encodeURIComponent(sampleUid)}/data`);

export interface DeleteSessionResult {
  success: boolean;
  session_id: string;
  deleted_count: number;
  failed: { sample_uid: string; error: string }[];
}

/** Soft-delete a whole recording (session) to Trash. The backend enforces
 *  ownership by auth_user_id (owner or admin) and logs the action. */
export const deleteLabelSession = async (
  classUid: string,
  sessionId: string,
): Promise<DeleteSessionResult> => {
  const res = await axiosClient.delete(
    `/classes/${encodeURIComponent(classUid)}/sessions/${encodeURIComponent(sessionId)}`,
  );
  return res.data as DeleteSessionResult;
};

export interface ReassignSessionResult {
  success: boolean;
  session_id: string;
  target_class_ref: string;
  moved_count: number;
  failed: { sample_uid: string; error: string }[];
}

/** Move a whole recording (session) to a different existing label/class (it was
 *  recorded under the wrong label). Backend enforces ownership + logs it.
 *  targetClassRef may be a class_uid or class_idx. */
export const reassignLabelSession = async (
  classUid: string,
  sessionId: string,
  targetClassRef: string,
): Promise<ReassignSessionResult> => {
  const res = await axiosClient.post(
    `/classes/${encodeURIComponent(classUid)}/sessions/${encodeURIComponent(sessionId)}/reassign`,
    { target_class_ref: targetClassRef },
  );
  return res.data as ReassignSessionResult;
};


// --------------------------------------------------------------------------- xuất xứ

/** Một ô có thể chưa từng được ghi nhận. `null` mang nghĩa đó, và giao diện
 *  phải hiện nó khác với số 0 hay chuỗi rỗng. */
export interface SessionProvenance {
  class_uid: string;
  session_id: string;
  sample_count: number;
  origin: {
    source_type: string | null;
    collection_campaign: string | null;
    created_at: string | null;
    gdrive_synced: string | null;
  };
  context: {
    label_original: string;
    slug: string;
    language: string;
    dialect: string;
    signer_id: string | null;
    signer_name: string | null;
    contributor_label: string | null;
    tenant_id: string | null;
  };
  derivation: {
    raw_landmarks_available: string | null;
    normalization_version: string | null;
    preprocess_contract_version: string | null;
    fps_original: number | null;
    fps_processed: number | null;
    sequence_length_original: number | null;
    seq_len: number | null;
    file_path: string | null;
    storage_url: string | null;
    checksum: string | null;
  };
  quality: {
    completeness: number | null;
    jitter: number | null;
    left_hand_ratio: number | null;
    right_hand_ratio: number | null;
    both_hands_ratio: number | null;
    quality_flags: string | null;
    quality_status: string | null;
  };
  samples: {
    sample_uid: string | null;
    augment_id: string | null;
    seq_len: number | null;
    completeness: number | null;
    jitter: number | null;
    file_path: string | null;
    checksum: string | null;
    storage_url: string | null;
  }[];
}

export const getSessionProvenance = async (
  classUid: string,
  sessionId: string,
): Promise<SessionProvenance> => {
  const res = await axiosClient.get(
    `/classes/${encodeURIComponent(classUid)}/sessions/${encodeURIComponent(sessionId)}/provenance`,
  );
  return res.data as SessionProvenance;
};

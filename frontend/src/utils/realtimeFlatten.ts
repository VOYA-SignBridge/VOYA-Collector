import type { MediaPipeLandmark } from "../types";

/**
 * Realtime semantic encoding constants.
 *
 * Vector layout MUST be:
 *   [MP_LeftHand(63), MP_RightHand(63)]
 * where each hand is 21 landmarks × (x,y,z).
 */
export const REALTIME_LANDMARKS_PER_HAND = 21;
export const REALTIME_COORDS_PER_LANDMARK = 3;
export const REALTIME_DIMS_PER_HAND =
  REALTIME_LANDMARKS_PER_HAND * REALTIME_COORDS_PER_LANDMARK; // 63
export const REALTIME_FEATURE_DIM = REALTIME_DIMS_PER_HAND * 2; // 126

export type MediaPipeHandLabel = "Left" | "Right";

export interface MediaPipeHandedness {
  label?: string;
  score?: number;
}

/**
 * Minimal shape of MediaPipe Hands results we care about.
 * (Deliberately not importing MediaPipe types to keep this utility portable.)
 */
export interface MediaPipeHandsLikeResults {
  multiHandLandmarks?: MediaPipeLandmark[][];
  multiHandedness?: MediaPipeHandedness[];
}

const isFiniteNumber = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);

const safeCoord = (v: unknown): number => (isFiniteNumber(v) ? v : 0);

const normalizeLabel = (v: unknown): MediaPipeHandLabel | null => {
  if (typeof v !== "string") return null;
  if (v === "Left" || v === "Right") return v;
  return null;
};

const ensureOutBuffer = (out?: Float32Array): Float32Array => {
  if (out && out.length === REALTIME_FEATURE_DIM) {
    out.fill(0);
    return out;
  }
  return new Float32Array(REALTIME_FEATURE_DIM);
};

type SelectedHand = {
  landmarks: MediaPipeLandmark[];
  score: number;
} | null;

/**
 * Selects the best landmarks array for a given MediaPipe handedness label.
 *
 * Deterministic policy:
 * - If multiple candidates exist, choose the highest `score` if provided.
 * - If scores are missing/invalid, the first encountered candidate wins.
 */
const selectHandByLabel = (
  allLandmarks: MediaPipeLandmark[][],
  handedness: MediaPipeHandedness[] | undefined,
  desired: MediaPipeHandLabel
): SelectedHand => {
  let best: SelectedHand = null;

  for (let i = 0; i < allLandmarks.length; i++) {
    const lms = allLandmarks[i];
    if (!Array.isArray(lms) || lms.length === 0) continue;

    const label = normalizeLabel(handedness?.[i]?.label);
    if (label !== desired) continue;

    const scoreRaw = handedness?.[i]?.score;
    const score = isFiniteNumber(scoreRaw) ? scoreRaw : 0;

    if (!best) {
      best = { landmarks: lms, score };
      // If we don't have scores, we keep the first match to be stable.
      continue;
    }

    // Prefer higher score if available.
    if (score > best.score) {
      best = { landmarks: lms, score };
    }
  }

  return best;
};

const writeHand63 = (
  out: Float32Array,
  offset: number,
  landmarks: MediaPipeLandmark[] | undefined
) => {
  if (!landmarks || landmarks.length === 0) return;

  // Write exactly 21 landmarks. Missing indices are left as zeros.
  for (let i = 0; i < REALTIME_LANDMARKS_PER_HAND; i++) {
    const lm = landmarks[i];
    if (!lm) continue;

    const base = offset + i * REALTIME_COORDS_PER_LANDMARK;
    out[base + 0] = safeCoord(lm.x);
    out[base + 1] = safeCoord(lm.y);
    out[base + 2] = safeCoord(lm.z);
  }
};

/**
 * flattenRealtimeHands
 *
 * Deterministically encodes RAW MediaPipe Hands results into a fixed-shape
 * Float32Array(126) using:
 *   [MP_LeftHand(63), MP_RightHand(63)]
 *
 * Semantic guarantees:
 * - No mirroring
 * - No swapping
 * - No normalization
 * - Handedness labels used ONLY for stable slot assignment
 *
 * Missing hand policy:
 * - If "Left" or "Right" hand is missing, its 63 dims remain zero.
 * - If coordinates are missing/NaN/undefined, they are zero-filled.
 *
 * Performance:
 * - Optional `out` parameter allows buffer reuse; otherwise allocates a new
 *   Float32Array(126).
 */
export function flattenRealtimeHands(
  results: MediaPipeHandsLikeResults | null | undefined,
  out?: Float32Array
): Float32Array {
  const vec = ensureOutBuffer(out);

  const allLandmarks = results?.multiHandLandmarks;
  if (!allLandmarks || !Array.isArray(allLandmarks) || allLandmarks.length === 0) {
    return vec;
  }

  const handedness = results?.multiHandedness;

  const left = selectHandByLabel(allLandmarks, handedness, "Left");
  const right = selectHandByLabel(allLandmarks, handedness, "Right");

  writeHand63(vec, 0, left?.landmarks);
  writeHand63(vec, REALTIME_DIMS_PER_HAND, right?.landmarks);

  return vec;
}

import type { MediaPipeLandmark } from "../types";
import { assignHandSlots, wristOf, type HandAnchors, type HandDetection } from "./handIdentity";
import { MIRROR_SERVING_PAYLOAD } from "../config/handTracking";

/**
 * Realtime semantic encoding constants.
 *
 * Vector layout MUST be:
 *   [User_LeftHand(63), User_RightHand(63)]
 * where MediaPipe raw handedness is swapped into anatomical slots.
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

const writeHand63 = (
  out: Float32Array,
  offset: number,
  landmarks: MediaPipeLandmark[] | undefined,
  mirrorX: boolean
) => {
  if (!landmarks || landmarks.length === 0) return;

  // Write exactly 21 landmarks. Missing indices are left as zeros.
  for (let i = 0; i < REALTIME_LANDMARKS_PER_HAND; i++) {
    const lm = landmarks[i];
    if (!lm) continue;

    const base = offset + i * REALTIME_COORDS_PER_LANDMARK;
    const x = safeCoord(lm.x);
    out[base + 0] = mirrorX ? 1 - x : x;
    out[base + 1] = safeCoord(lm.y);
    out[base + 2] = safeCoord(lm.z);
  }
};

/**
 * Turns raw MediaPipe results into detections carrying person-perspective labels.
 *
 * MediaPipe is trained on mirrored selfie images but receives the raw webcam
 * frame, so its labels are from the CAMERA's point of view — the opposite of the
 * person's. Swapping here means everything downstream reasons in anatomical
 * terms, exactly as the capture modal does when recording.
 */
const toDetections = (
  allLandmarks: MediaPipeLandmark[][],
  handedness: MediaPipeHandedness[] | undefined
): HandDetection[] => {
  const out: HandDetection[] = [];
  for (let i = 0; i < allLandmarks.length; i++) {
    const lms = allLandmarks[i];
    if (!Array.isArray(lms) || lms.length === 0) continue;

    const rawLabel = normalizeLabel(handedness?.[i]?.label);
    const scoreRaw = handedness?.[i]?.score;
    out.push({
      landmarks: lms,
      label: rawLabel ? (rawLabel === "Left" ? "Right" : "Left") : undefined,
      score: isFiniteNumber(scoreRaw) ? scoreRaw : 0,
    });
  }
  return out;
};

export interface FlattenRealtimeOptions {
  /**
   * Caller-owned identity state, carried across frames. Mutated in place with
   * each slot's latest wrist position. Omit it and every frame is resolved in
   * isolation — which is what the old label-only encoder effectively did, and
   * why left/right could swap mid-sequence inside the rolling window.
   */
  anchors?: HandAnchors;
  /** Frame timestamp in ms; defaults to Date.now(). */
  now?: number;
  /**
   * Mirror the x axis. Defaults to MIRROR_SERVING_PAYLOAD — see that constant
   * for why serving does not simply follow how capture records.
   */
  mirrorX?: boolean;
}

/**
 * flattenRealtimeHands
 *
 * Deterministically encodes RAW MediaPipe Hands results into a fixed-shape
 * Float32Array(126) using:
 *   [User_LeftHand(63), User_RightHand(63)]
 *
 * Semantic guarantees:
 * - Slot assignment goes through the same resolver the capture modal uses, so
 *   two same-labelled hands never collapse into one slot and a mid-sequence
 *   label flip cannot invert the two halves of the vector.
 * - x mirroring follows MIRROR_SERVING_PAYLOAD, which is currently NOT the same
 *   as how capture records — see that constant for the corpus split behind it.
 * - No normalization (the realtime service applies the shared normalization).
 *
 * Missing hand policy:
 * - If the left or right hand is missing, its 63 dims remain zero.
 * - If coordinates are missing/NaN/undefined, they are zero-filled.
 *
 * Performance:
 * - Optional `out` parameter allows buffer reuse; otherwise allocates a new
 *   Float32Array(126).
 */
export function flattenRealtimeHands(
  results: MediaPipeHandsLikeResults | null | undefined,
  out?: Float32Array,
  options?: FlattenRealtimeOptions
): Float32Array {
  const vec = ensureOutBuffer(out);

  const allLandmarks = results?.multiHandLandmarks;
  if (!allLandmarks || !Array.isArray(allLandmarks) || allLandmarks.length === 0) {
    return vec;
  }

  const mirrorX = options?.mirrorX ?? MIRROR_SERVING_PAYLOAD;
  const now = options?.now ?? Date.now();
  const anchors = options?.anchors ?? {};

  const detections = toDetections(allLandmarks, results?.multiHandedness);
  const assignment = assignHandSlots(detections, anchors, now);

  // Refresh whichever slots were filled so the next frame can keep identity.
  if (assignment.left?.length) {
    const w = wristOf(assignment.left);
    anchors.left = { x: w.x, y: w.y, t: now };
  }
  if (assignment.right?.length) {
    const w = wristOf(assignment.right);
    anchors.right = { x: w.x, y: w.y, t: now };
  }

  writeHand63(vec, 0, assignment.left, mirrorX);
  writeHand63(vec, REALTIME_DIMS_PER_HAND, assignment.right, mirrorX);

  return vec;
}

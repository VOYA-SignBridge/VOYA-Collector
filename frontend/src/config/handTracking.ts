/**
 * Canonical hand-extraction contract.
 *
 * Every place that turns webcam frames into landmarks — the capture modal that
 * RECORDS training data, and the realtime/test paths that SERVE a trained model
 * — must extract under identical settings. When they drift, the model is served
 * inputs whose distribution differs from what it was trained on (train/serve
 * skew) and accuracy silently degrades with nothing in the logs to show for it.
 *
 * These constants previously lived inline in three components and had already
 * drifted apart:
 *
 *   capture   modelComplexity 1, minDetection 0.70, minTracking 0.75
 *   realtime  modelComplexity 0, minDetection 0.60, minTracking 0.65
 *   test      modelComplexity 0, minDetection 0.50, minTracking 0.50
 *
 * Keep this file as the only definition. Import it; do not re-declare.
 */

const parseBoolEnv = (value: unknown, fallback: boolean) => {
  if (typeof value !== "string") return fallback;
  const v = value.trim().toLowerCase();
  if (v === "1" || v === "true" || v === "yes" || v === "on") return true;
  if (v === "0" || v === "false" || v === "no" || v === "off") return false;
  return fallback;
};

/** Pinned to the @mediapipe/hands version in package.json. */
export const MP_HANDS_VERSION = "0.4.1675469240";

/**
 * MediaPipe Hands options shared by capture, realtime and model testing.
 *
 * modelComplexity 1 (the "full" landmark model) is what recorded the existing
 * training corpus, and what backend/app/processing/keypoints_adapter.py uses for
 * uploaded video. Complexity 0 is a different, lighter network that predicts
 * measurably different landmark positions — cheaper per frame, but only valid
 * for serving if the corpus had been recorded with it too.
 *
 * 0.5 / 0.5 are MediaPipe's own defaults and match the backend extractor. Higher
 * tracking thresholds make MediaPipe discard the tracked ROI and fall back to
 * palm detection as soon as confidence dips — which is exactly what happens when
 * a hand rotates edge-on or is occluded, so the hand is lost instead of tracked.
 */
export const HAND_TRACKING_OPTIONS = {
  maxNumHands: 2,
  modelComplexity: 1,
  refineLandmarks: true,
  minDetectionConfidence: 0.5,
  minTrackingConfidence: 0.5,
} as const;

/**
 * Whether the capture modal mirrors the x axis of the samples it RECORDS.
 *
 * It writes `x -> 1 - x` into every saved sample when VITE_MIRROR_PREVIEW is on
 * (the default). This is the *payload* mirror and is independent of any
 * CSS/canvas mirror used to show the user a selfie-style preview.
 */
export const MIRROR_LANDMARK_PAYLOAD = parseBoolEnv(
  import.meta.env.VITE_MIRROR_PREVIEW,
  true,
);

/**
 * Whether SERVING (realtime + model testing) mirrors the x axis.
 *
 * Deliberately NOT tied to MIRROR_LANDMARK_PAYLOAD, because the stored corpus is
 * not self-consistent. Measuring the sign of wrist-relative x across all 930
 * stored samples (normalization only translates and scales, so the sign
 * survives) shows two incompatible conventions split by date:
 *
 *     2026-05  n=464   35.1% positive
 *     2026-06  n=117   90.6% positive
 *     2026-07  n= 43  100.0% positive
 *
 * The boundary is commit 34cdfbe (2026-05-12), which introduced SWAP_HANDEDNESS
 * and mirrorLandmarkX in the capture modal. Samples recorded before it use the
 * opposite convention to samples recorded after it, and roughly half the corpus
 * sits on each side.
 *
 * Nothing reconciles them later: live-capture landmarks are stored verbatim, and
 * `normalize_single_hand` only subtracts the wrist and divides by span — a mirror
 * negates normalized x rather than cancelling. Mirror augmentation is also off
 * (CANONICALIZE_MIRROR=1), so the models never learned mirror invariance.
 *
 * Trained on that mixture, a model cannot be served correctly in both
 * orientations. Serving unmirrored empirically matches the promoted models, so
 * that is what we do until the corpus is canonicalized.
 *
 * TODO: once every sample has been rewritten into one convention and models have
 * been retrained, delete this and use MIRROR_LANDMARK_PAYLOAD for serving too —
 * recording and serving agreeing is the invariant we actually want.
 */
export const MIRROR_SERVING_PAYLOAD = false;

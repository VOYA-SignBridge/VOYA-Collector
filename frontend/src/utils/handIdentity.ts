import type { MediaPipeLandmark } from "../types";

/**
 * Stable left/right hand identity across frames.
 *
 * MediaPipe's handedness classifier runs per-frame with no temporal state, which
 * produces two failure modes when its label is trusted verbatim:
 *
 *   1. When two hands overlap it often labels BOTH the same. A label-only
 *      assignment then overwrites one slot and leaves the other empty, so a hand
 *      that WAS detected disappears from the recorded sample entirely.
 *   2. When a hand rotates palm <-> back the label flips, writing left_hand /
 *      right_hand inverted partway through a single recorded sample.
 *
 * The resolver keeps a per-slot anchor (the wrist of the last frame that slot was
 * filled) and uses it to enforce continuity. The label still decides on first
 * acquisition and whenever spatial evidence is ambiguous — position overrides it
 * only when the evidence is unambiguous, so an ordinary clean one-hand capture
 * resolves exactly as a label-only assignment would.
 */

/** Last known wrist position for one slot, with the time it was recorded. */
export type HandAnchor = { x: number; y: number; t: number };

/**
 * One detected hand. `label` is the person-perspective label — callers must
 * apply any camera-mirroring correction (SWAP_HANDEDNESS) before passing it in.
 */
export type HandDetection = {
  landmarks: MediaPipeLandmark[];
  label?: string;
  score: number;
};

export type HandAnchors = { left?: HandAnchor; right?: HandAnchor };

export type HandAssignment = {
  left?: MediaPipeLandmark[];
  right?: MediaPipeLandmark[];
};

/**
 * An anchor older than this is treated as gone, so a hand re-entering the frame
 * is matched by label rather than glued to where the old one used to be.
 */
export const HAND_ANCHOR_MAX_AGE_MS = 400;

/**
 * Normalized frame units. Beyond this a detection is not considered a
 * continuation of the anchored hand.
 */
export const HAND_ANCHOR_MATCH_RADIUS = 0.28;

/**
 * How much better the spatial evidence must be before it may override the label.
 * Prevents oscillation when both options are near-equal.
 */
export const HAND_SWAP_MARGIN = 0.06;

/** Wrist is landmark 0 of MediaPipe's 21-point hand model. */
export const wristOf = (lms: MediaPipeLandmark[]) => ({
  x: lms[0]?.x ?? 0.5,
  y: lms[0]?.y ?? 0.5,
});

const wristDistance = (a: { x: number; y: number }, b: { x: number; y: number }) =>
  Math.hypot(a.x - b.x, a.y - b.y);

/** Resolve detections into anatomical left/right slots. */
export function assignHandSlots(
  detections: HandDetection[],
  anchors: HandAnchors,
  now: number,
): HandAssignment {
  if (detections.length === 0) return {};

  const stillFresh = (a?: HandAnchor) =>
    a && now - a.t <= HAND_ANCHOR_MAX_AGE_MS ? a : undefined;
  const leftAnchor = stillFresh(anchors.left);
  const rightAnchor = stillFresh(anchors.right);

  if (detections.length === 1) {
    const only = detections[0];
    const wrist = wristOf(only.landmarks);
    const toLeft = leftAnchor ? wristDistance(wrist, leftAnchor) : Infinity;
    const toRight = rightAnchor ? wristDistance(wrist, rightAnchor) : Infinity;

    // Trust position only when at least one anchor is a genuine match AND one
    // option is clearly better than the other.
    if (toLeft <= HAND_ANCHOR_MATCH_RADIUS || toRight <= HAND_ANCHOR_MATCH_RADIUS) {
      if (toLeft + HAND_SWAP_MARGIN < toRight) return { left: only.landmarks };
      if (toRight + HAND_SWAP_MARGIN < toLeft) return { right: only.landmarks };
    }
    if (only.label === "Left") return { left: only.landmarks };
    if (only.label === "Right") return { right: only.landmarks };
    return {};
  }

  // Two or more detections: keep the two most confident.
  const sorted = [...detections].sort((p, q) => q.score - p.score);
  const primary = sorted[0];
  const secondary = sorted[1];
  const primaryWrist = wristOf(primary.landmarks);
  const secondaryWrist = wristOf(secondary.landmarks);

  // Both slots anchored — pick the pairing that best preserves continuity.
  if (leftAnchor && rightAnchor) {
    const keepCost =
      wristDistance(primaryWrist, leftAnchor) + wristDistance(secondaryWrist, rightAnchor);
    const swapCost =
      wristDistance(primaryWrist, rightAnchor) + wristDistance(secondaryWrist, leftAnchor);
    if (Math.abs(keepCost - swapCost) > HAND_SWAP_MARGIN) {
      return keepCost < swapCost
        ? { left: primary.landmarks, right: secondary.landmarks }
        : { left: secondary.landmarks, right: primary.landmarks };
    }
  }

  // No usable anchors, or the two pairings are equally plausible: fall back to
  // the labels. The more confident detection keeps its label and the other takes
  // the opposite slot — so even when MediaPipe reports the same label twice, two
  // detected hands always produce two filled slots.
  if (primary.label === "Right") {
    return { left: secondary.landmarks, right: primary.landmarks };
  }
  if (primary.label === "Left") {
    return { left: primary.landmarks, right: secondary.landmarks };
  }
  // Neither detection carried a usable label — order by horizontal position so
  // the result is at least deterministic instead of arbitrary.
  return primaryWrist.x <= secondaryWrist.x
    ? { left: primary.landmarks, right: secondary.landmarks }
    : { left: secondary.landmarks, right: primary.landmarks };
}

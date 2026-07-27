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

export type AssignOptions = {
  /**
   * Force a lone detection into this slot. Set once a clip is known to be
   * one-handed: the physical hand cannot change anatomical identity mid-clip,
   * so no per-frame label may move it.
   */
  pinnedSlot?: "left" | "right";

  /**
   * The clip is declared one-handed but no slot is pinned yet. Keep only the
   * most confident detection so a bystander hand — the signer's resting other
   * hand, someone behind them — cannot fill the second slot.
   *
   * Without this, a declared-one-handed clip that never shows exactly one
   * detection can deadlock: the caller pins a slot only after seeing a
   * single-hand frame, while the extra detection keeps producing two.
   */
  forceSingle?: boolean;
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

/**
 * Match radius when only ONE slot is live. Deliberately much wider than
 * HAND_ANCHOR_MATCH_RADIUS: that value has to discriminate between two
 * competing hands, whereas here there is nothing to confuse the detection with,
 * so the only job is to reject a detection that cannot physically be the same
 * hand. A fast sign easily moves the wrist more than 0.28 of the frame between
 * two processed frames -- treating that as a different hand is what let a
 * flipped per-frame label swap the hand mid-clip. Crossing more than half the
 * frame in one frame interval is still rejected as a reacquisition.
 */
export const HAND_ANCHOR_SOLO_RADIUS = 0.55;

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
  options: AssignOptions = {},
): HandAssignment {
  if (detections.length === 0) return {};

  const stillFresh = (a?: HandAnchor) =>
    a && now - a.t <= HAND_ANCHOR_MAX_AGE_MS ? a : undefined;
  const leftAnchor = stillFresh(anchors.left);
  const rightAnchor = stillFresh(anchors.right);

  // A declared one-handed clip has one hand by definition. Drop the extra
  // detections here so the rest of the function sees the lone-hand case, which
  // is also what lets the caller pin a slot on the very first frame.
  if (options.forceSingle && !options.pinnedSlot && detections.length > 1) {
    detections = [[...detections].sort((p, q) => q.score - p.score)[0]];
  }

  if (detections.length === 1) {
    const only = detections[0];

    // A clip known to be one-handed has exactly one answer, whatever the
    // per-frame classifier says.
    if (options.pinnedSlot) {
      return options.pinnedSlot === "left"
        ? { left: only.landmarks }
        : { right: only.landmarks };
    }

    const wrist = wristOf(only.landmarks);

    // Exactly one slot is live: nothing competes for this detection, so judge it
    // against the wider solo radius and keep the identity. Only a jump too large
    // to be the same hand falls through to the label.
    if (leftAnchor && !rightAnchor) {
      if (wristDistance(wrist, leftAnchor) <= HAND_ANCHOR_SOLO_RADIUS) {
        return { left: only.landmarks };
      }
    } else if (rightAnchor && !leftAnchor) {
      if (wristDistance(wrist, rightAnchor) <= HAND_ANCHOR_SOLO_RADIUS) {
        return { right: only.landmarks };
      }
    }

    const toLeft = leftAnchor ? wristDistance(wrist, leftAnchor) : Infinity;
    const toRight = rightAnchor ? wristDistance(wrist, rightAnchor) : Infinity;

    // Both slots live: trust position only when at least one anchor is a
    // genuine match AND one option is clearly better than the other.
    if (toLeft <= HAND_ANCHOR_MATCH_RADIUS || toRight <= HAND_ANCHOR_MATCH_RADIUS) {
      if (toLeft + HAND_SWAP_MARGIN < toRight) return { left: only.landmarks };
      if (toRight + HAND_SWAP_MARGIN < toLeft) return { right: only.landmarks };
    }
    if (only.label === "Left") return { left: only.landmarks };
    if (only.label === "Right") return { right: only.landmarks };
    return {};
  }

  // Two hands but the clip is pinned one-handed: keep the most confident
  // detection in the pinned slot rather than inventing a second hand from a
  // spurious detection.
  if (options.pinnedSlot) {
    const best = [...detections].sort((p, q) => q.score - p.score)[0];
    return options.pinnedSlot === "left"
      ? { left: best.landmarks }
      : { right: best.landmarks };
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

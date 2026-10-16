/**
 * Shared motion-data helpers for the Phase 2 viewers (2D skeleton + 3D hands).
 *
 * The backend serves each session's ORIGINAL sample as a (frames × 126) matrix:
 * 126 = 2 hands × 21 MediaPipe landmarks × (x, y, z).
 *
 * COORDINATE SPACE — this comment previously claimed "normalized image space
 * ([0,1])". That is wrong, and the mistake caused two rendering bugs. What the
 * .npz actually stores (and GET /classes/{uid}/sessions/{id}/frames returns
 * verbatim, rounded to 5 dp) is the WRIST-CENTRED feature vector written at
 * upload time: measured over the dataset, x/y run about [-1.3, 1.3], and each
 * hand is centred on ITS OWN wrist, so landmark 0 of both hands sits at the
 * origin.
 *
 * Two consequences the viewers must respect:
 *
 *  1. (0,0,0) is a LEGITIMATE position — it is the wrist. It cannot be used as
 *     a "missing landmark" sentinel. It previously was, and because the API
 *     rounds to 5 dp the wrist's float residue (~2.6e-7) became exactly 0, so
 *     the wrist and the three palm-base connections ([0,1], [0,5], [0,17])
 *     were dropped in 100% of frames (19127/19127 measured). Presence is a
 *     property of the whole 63-value block, never of one landmark.
 *
 *  2. Because each hand is centred on its own wrist, the data carries NO
 *     information about where the hands are relative to each other. Fitting
 *     both hands with one shared transform draws them on top of one another.
 *     Lay them out side by side instead — see computeHandFit.
 */

export type HandSide = "left" | "right";

/** MediaPipe Hands topology — mirrors HAND_CONNECTIONS in the backend renderer. */
export const HAND_CONNECTIONS: ReadonlyArray<readonly [number, number]> = [
  [0, 1], [1, 2], [2, 3], [3, 4],          // thumb
  [0, 5], [5, 6], [6, 7], [7, 8],          // index
  [5, 9], [9, 10], [10, 11], [11, 12],     // middle
  [9, 13], [13, 14], [14, 15], [15, 16],   // ring
  [13, 17], [17, 18], [18, 19], [19, 20],  // pinky
  [0, 17],                                  // palm edge
];

export const LANDMARKS_PER_HAND = 21;
export const DIMS_PER_HAND = LANDMARKS_PER_HAND * 3; // 63
export const FRAME_DIM = DIMS_PER_HAND * 2; // 126

export const LEFT_COLOR = "#FF6B35";
export const RIGHT_COLOR = "#38BDF8";

export interface FramesData {
  class_uid: string;
  session_id: string;
  sample_uid: string;
  frames: number;
  dim: number;
  fps: number;
  /**
   * Which array the backend served.
   *
   * "raw"        — as recorded: the hands keep the distance and the depth they
   *                actually had.
   * "normalized" — the model's input. Each hand was moved onto its own wrist
   *                and its x,y divided by its own span while z was left alone,
   *                so the hands carry no relative position and render flat.
   *                Older samples have nothing else stored.
   */
  landmark_source?: "raw" | "normalized";
  sequence: number[][];
  /**
   * MediaPipe `world_landmarks`, in metres about each hand's geometric centre.
   * Same shape as `sequence`; present only for samples recorded after the
   * capture side started reading it.
   *
   * Sent ALONGSIDE `sequence` rather than replacing it because neither array is
   * sufficient alone: world landmarks are hand-centred, so they hold true shape
   * and depth but say nothing about where the hands were relative to each
   * other, while `sequence` holds the position but carries a depth that is a
   * relative regression rather than a measurement.
   */
  sequence_world?: number[][];
}

/**
 * Per-hand depth for one frame, in the same units as that hand's own x,y.
 *
 * This is the whole reason `sequence_world` is fetched. The z in `sequence` is
 * MediaPipe's image-space depth: documented as "roughly the same scale as x",
 * but x there spans the WHOLE IMAGE while the hand occupies a fraction of it,
 * so relative to the hand the depth is compressed several-fold. Measured across
 * 18046 frames of this corpus, a hand's z-span is a median 0.203 of its own
 * width — hands come out looking like cardboard, and no scale factor applied
 * afterwards fixes it, because the ratio between fingers is wrong too, not just
 * the overall magnitude.
 *
 * World landmarks are metric, so the ratio is right by construction. They are
 * rescaled — not translated or rotated — onto the hand's on-screen size, which
 * keeps the recorded proportion of depth to width while letting the existing
 * 2D fit go on deciding where the hand sits.
 *
 * Returns null when the sample predates world landmarks, and the caller falls
 * back to the flat depth rather than inventing one.
 */
export function handDepth(
  worldFrame: number[] | undefined,
  side: HandSide,
): { z: number[]; scale: number } | null {
  if (!worldFrame) return null;
  const offset = side === "left" ? 0 : DIMS_PER_HAND;
  const z: number[] = [];
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
  for (let i = 0; i < LANDMARKS_PER_HAND; i++) {
    const x = worldFrame[offset + i * 3];
    const y = worldFrame[offset + i * 3 + 1];
    const zi = worldFrame[offset + i * 3 + 2];
    if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(zi)) return null;
    z.push(zi);
    if (x < xMin) xMin = x;
    if (x > xMax) xMax = x;
    if (y < yMin) yMin = y;
    if (y > yMax) yMax = y;
  }
  // An all-zero block is a hand MediaPipe did not report, not a flat hand.
  const span = Math.max(xMax - xMin, yMax - yMin);
  if (!Number.isFinite(span) || span < 1e-9) return null;
  return { z, scale: 1 / span };
}

/**
 * The 21 (x,y,z) triples of one hand in one frame, or null when undetected.
 *
 * Presence is decided on the WHOLE block: MediaPipe emits a hand's 21
 * landmarks all together or not at all, so a single non-zero value means the
 * hand was tracked and every one of its landmarks — the wrist at the origin
 * included — is real.
 *
 * A hand with NO spatial extent is also treated as absent. 3.3% of stored
 * samples carry a left hand written as 21 identical points at (1.0, 0.0) — a
 * constant placeholder, not a recording. It passed the "any non-zero" test, so
 * it counted as a hand: it drew 21 dots stacked on one pixel, and worse, it
 * dragged the shared bounding box out to x=1.0 and squashed the real hand
 * beside it into a sliver. Twenty-one coincident landmarks are not a hand.
 */
export function handPoints(frame: number[], side: HandSide): number[] | null {
  const offset = side === "left" ? 0 : DIMS_PER_HAND;
  let anyNonZero = false;
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
  for (let i = 0; i < LANDMARKS_PER_HAND; i++) {
    const x = frame[offset + i * 3];
    const y = frame[offset + i * 3 + 1];
    const z = frame[offset + i * 3 + 2];
    if (x !== 0 || y !== 0 || z !== 0) anyNonZero = true;
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    if (x < xMin) xMin = x;
    if (x > xMax) xMax = x;
    if (y < yMin) yMin = y;
    if (y > yMax) yMax = y;
  }
  if (!anyNonZero) return null;
  const extent = Math.max(xMax - xMin, yMax - yMin);
  if (!Number.isFinite(extent) || extent < 1e-6) return null;
  return frame.slice(offset, offset + DIMS_PER_HAND);
}

/**
 * How wide one hand ends up on screen, in unit-square units, under `fit`.
 *
 * The bridge between the two arrays: depth arrives as a multiple of the hand's
 * own width, and this is what that width actually is once the layout has
 * placed and scaled the hand. Without it the depth would be correct in metres
 * and wrong on screen by whatever zoom the fit applied.
 */
export function handWidth(points: number[], fit: FitTransform): number {
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;
  for (let i = 0; i < LANDMARKS_PER_HAND; i++) {
    const [ux, uy] = fit.toUnit(points[i * 3], points[i * 3 + 1]);
    if (!Number.isFinite(ux) || !Number.isFinite(uy)) continue;
    if (ux < xMin) xMin = ux;
    if (ux > xMax) xMax = ux;
    if (uy < yMin) yMin = uy;
    if (uy > yMax) yMax = uy;
  }
  if (!Number.isFinite(xMin)) return 0;
  return Math.max(xMax - xMin, yMax - yMin);
}

export interface FitTransform {
  /** Map a data-space (x, y) into the unit square [0,1]² with margin applied. */
  toUnit: (x: number, y: number) => [number, number];
  /** Uniform scale factor from data units to unit-square units. */
  scale: number;
}

/**
 * Whole-sequence bounding-box fit (same approach as the server renderer):
 * fitting once keeps playback steady, and works for raw [0,1] MediaPipe
 * coords and normalized features alike. Zero triples (missing landmarks)
 * are excluded so they can't skew the box.
 */
export function computeFit(sequence: number[][], margin = 0.1): FitTransform {
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;

  for (const frame of sequence) {
    for (let base = 0; base + 2 < Math.min(frame.length, FRAME_DIM); base += 3) {
      const x = frame[base], y = frame[base + 1], z = frame[base + 2];
      if (x === 0 && y === 0 && z === 0) continue;
      if (x < xMin) xMin = x;
      if (x > xMax) xMax = x;
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    }
  }

  if (!Number.isFinite(xMin)) {
    // Entire sequence empty — identity-ish mapping so callers still render.
    xMin = 0; xMax = 1; yMin = 0; yMax = 1;
  }

  const span = Math.max(xMax - xMin, yMax - yMin, 1e-6);
  const usable = 1 - 2 * margin;
  const scale = usable / span;
  const xOff = (1 - (xMax - xMin) * scale) / 2;
  const yOff = (1 - (yMax - yMin) * scale) / 2;

  return {
    toUnit: (x: number, y: number) => [
      (x - xMin) * scale + xOff,
      (y - yMin) * scale + yOff,
    ],
    scale,
  };
}

/**
 * Display-only stabiliser: centred median-of-3 over each landmark coordinate.
 *
 * Measured over 250 samples of the real dataset, playback suffers from two
 * distinct problems — ordinary tracking jitter (median per-frame movement
 * 0.0218) and outlier spikes where a landmark jumps ~13x that in a single
 * frame (p99 0.1374, affecting 21% of hand sequences). A median is the right
 * tool for the second: it discards a lone bad frame outright instead of
 * averaging it in.
 *
 * Effect on the same 250 samples: jitter -61% (0.0218 -> 0.0085), spikes -35%
 * (0.1374 -> 0.0887), while moving positions by only 0.0072 — less than one
 * frame of normal motion, so gestures are not distorted.
 *
 * Why a CENTRED filter rather than an adaptive causal one (One Euro et al.):
 * playback is not real time. The whole sequence is already in memory, so we
 * can look ahead and pay ZERO lag. A causal filter must trade smoothness
 * against lag precisely because it cannot.
 *
 * This never touches stored or served data — it runs on a copy at render time.
 * The .npz keeps raw landmarks, and the model keeps seeing what it was trained
 * on.
 */
export function stabilizeSequence(sequence: number[][]): number[][] {
  if (sequence.length < 3) return sequence;

  const out = sequence.map((f) => f.slice());
  const med3 = (a: number, b: number, c: number) =>
    a < b ? (b < c ? b : a < c ? c : a) : b < c ? (a < c ? a : c) : b;

  for (const side of ["left", "right"] as HandSide[]) {
    const offset = side === "left" ? 0 : DIMS_PER_HAND;
    const present = sequence.map((f) => handPoints(f, side) !== null);

    for (let t = 1; t < sequence.length - 1; t++) {
      // Only smooth inside a run where the hand is continuously tracked —
      // blending across a gap would drag the hand toward where it was before
      // it vanished.
      if (!present[t - 1] || !present[t] || !present[t + 1]) continue;
      for (let d = 0; d < DIMS_PER_HAND; d++) {
        const i = offset + d;
        out[t][i] = med3(sequence[t - 1][i], sequence[t][i], sequence[t + 1][i]);
      }
    }
  }
  return out;
}

/** Which hands appear anywhere in the sequence. */
export function handsPresent(sequence: number[][]): { left: boolean; right: boolean } {
  let left = false;
  let right = false;
  for (const frame of sequence) {
    if (!left && handPoints(frame, "left")) left = true;
    if (!right && handPoints(frame, "right")) right = true;
    if (left && right) break;
  }
  return { left, right };
}

/**
 * Per-hand fit, computed over the whole sequence so playback does not breathe.
 *
 * Differs from computeFit in the two ways that matter for wrist-centred data:
 *
 *  - Only frames where THIS hand was tracked contribute, and within them every
 *    landmark counts, wrist included. computeFit cannot do this: looking at one
 *    (0,0,0) triple it cannot tell an absent hand's padding from a real wrist.
 *  - The result is placed inside `column` (a horizontal slice of the canvas),
 *    so two hands can be drawn side by side instead of stacked on the origin.
 *
 * Non-finite values are ignored rather than allowed to poison the bounding box:
 * one stray Infinity would otherwise collapse the whole skeleton to a dot.
 */
export function computeHandFit(
  sequence: number[][],
  side: HandSide,
  column: { start: number; end: number } = { start: 0, end: 1 },
  margin = 0.1
): FitTransform {
  let xMin = Infinity, xMax = -Infinity, yMin = Infinity, yMax = -Infinity;

  for (const frame of sequence) {
    const pts = handPoints(frame, side);
    if (!pts) continue;
    for (let i = 0; i < LANDMARKS_PER_HAND; i++) {
      const x = pts[i * 3];
      const y = pts[i * 3 + 1];
      if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
      if (x < xMin) xMin = x;
      if (x > xMax) xMax = x;
      if (y < yMin) yMin = y;
      if (y > yMax) yMax = y;
    }
  }

  if (!Number.isFinite(xMin)) {
    xMin = 0; xMax = 1; yMin = 0; yMax = 1;
  }

  const width = Math.max(column.end - column.start, 1e-6);
  // Uniform scale on both axes, so a hand is never stretched. The limiting
  // axis is whichever needs more room once the column narrows the x budget.
  const span = Math.max(xMax - xMin, yMax - yMin, 1e-6);
  const usable = 1 - 2 * margin;
  const scale = (usable * Math.min(width, 1)) / span;

  const xOff = column.start + (width - (xMax - xMin) * scale) / 2;
  const yOff = (1 - (yMax - yMin) * scale) / 2;

  return {
    toUnit: (x: number, y: number) => [
      (x - xMin) * scale + xOff,
      (y - yMin) * scale + yOff,
    ],
    scale,
  };
}

/**
 * Horizontal slices for the hands actually present: two columns when both
 * hands appear, one full-width column when only one does.
 */
export function handColumns(sequence: number[][]): {
  left: { start: number; end: number };
  right: { start: number; end: number };
  both: boolean;
} {
  const { left, right } = handsPresent(sequence);
  const both = left && right;
  return both
    ? { left: { start: 0, end: 0.5 }, right: { start: 0.5, end: 1 }, both }
    : { left: { start: 0, end: 1 }, right: { start: 0, end: 1 }, both };
}

/**
 * Distance between the two wrists across the sequence, in units of the
 * combined hand size — 0 when the two hands share an origin.
 *
 * Returns null when the two hands are never present in the same frame.
 */
export function wristSeparation(sequence: number[][]): number | null {
  const dists: number[] = [];
  let min = Infinity;
  let max = -Infinity;

  for (const frame of sequence) {
    const l = handPoints(frame, "left");
    const r = handPoints(frame, "right");
    if (!l || !r) continue;
    const dx = l[0] - r[0];
    const dy = l[1] - r[1];
    if (!Number.isFinite(dx) || !Number.isFinite(dy)) continue;
    dists.push(Math.hypot(dx, dy));
    for (const pts of [l, r]) {
      for (let i = 0; i < LANDMARKS_PER_HAND; i++) {
        const x = pts[i * 3];
        const y = pts[i * 3 + 1];
        if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
        if (x === 0 && y === 0 && pts[i * 3 + 2] === 0) continue;
        if (x < min) min = x;
        if (x > max) max = x;
        if (y < min) min = y;
        if (y > max) max = y;
      }
    }
  }

  if (dists.length === 0) return null;
  const span = Math.max(max - min, 1e-6);
  dists.sort((a, b) => a - b);
  const median = dists[Math.floor(dists.length / 2)];
  return median / span;
}

/**
 * Below this, the two wrists are literally the same point, so the recording
 * carries no information about where the hands were relative to each other.
 *
 * Deliberately tiny. Wrist-centred data scores EXACTLY 0.0000 — 178 of 178
 * measured samples, at every percentile — so no tolerance is needed to catch
 * it, only enough to absorb the API's 5-decimal rounding (~3e-5 once divided
 * by the hand span).
 *
 * Being generous here is what breaks real recordings: the closest genuine
 * two-hand sample scores 0.0154, and an earlier 0.05 threshold pulled two
 * samples with genuinely touching hands into opposite columns — inventing a
 * separation the signer never made. 0.005 sits 150x above rounding noise and
 * 3x below the closest real pair.
 */
const COINCIDENT_WRIST_RATIO = 0.005;

export interface HandLayout {
  /** "shared" keeps the hands where they were recorded; "columns" places each
   *  hand in its own half because the recording did not keep their positions. */
  mode: "shared" | "columns";
  left: FitTransform;
  right: FitTransform;
}

/**
 * How to place the two hands on the canvas — decided PER SAMPLE, because the
 * stored data does not use one convention.
 *
 * Two conventions are on disk. Most recordings are wrist-centred: normalization
 * subtracts each hand's own wrist, so both hands sit on the origin and drawing
 * them with one shared fit stacks them into a single tangled shape joined at the
 * middle. But ~11% of samples keep raw image coordinates, where the hands
 * already hold their true relative position and size.
 *
 * Forcing every sample into two columns fixes the first group and quietly
 * corrupts the second: it would move hands that were correctly placed and
 * rescale each one independently, destroying real spatial information. So the
 * layout is chosen from the data instead of assumed.
 */
export function handLayout(sequence: number[][]): HandLayout {
  const { left, right } = handsPresent(sequence);

  if (!left || !right) {
    // One hand: nothing to separate, and a shared fit gives it the whole canvas.
    const fit = computeFit(sequence);
    return { mode: "shared", left: fit, right: fit };
  }

  const sep = wristSeparation(sequence);
  if (sep !== null && sep < COINCIDENT_WRIST_RATIO) {
    const cols = handColumns(sequence);
    return {
      mode: "columns",
      left: computeHandFit(sequence, "left", cols.left),
      right: computeHandFit(sequence, "right", cols.right),
    };
  }

  // The recording knows where the hands were — keep it. One fit for both is
  // what preserves their distance and their relative size.
  const fit = computeFit(sequence);
  return { mode: "shared", left: fit, right: fit };
}

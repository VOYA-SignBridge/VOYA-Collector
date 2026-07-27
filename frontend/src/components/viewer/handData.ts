/**
 * Shared motion-data helpers for the Phase 2 viewers (2D skeleton + 3D hands).
 *
 * The backend serves each session's ORIGINAL sample as a (frames × 126) matrix:
 * 126 = 2 hands × 21 MediaPipe landmarks × (x, y, z), x/y in normalized image
 * space ([0,1], y pointing DOWN). A hand that was not detected in a frame is
 * stored as 63 zeros — viewers must hide it, never draw a collapsed fist at
 * the origin.
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
  sequence: number[][];
}

/** The 21 (x,y,z) triples of one hand in one frame, or null when undetected. */
export function handPoints(frame: number[], side: HandSide): number[] | null {
  const offset = side === "left" ? 0 : DIMS_PER_HAND;
  let anyNonZero = false;
  for (let i = offset; i < offset + DIMS_PER_HAND; i++) {
    if (frame[i] !== 0) {
      anyNonZero = true;
      break;
    }
  }
  return anyNonZero ? frame.slice(offset, offset + DIMS_PER_HAND) : null;
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

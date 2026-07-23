// Centralized capture defaults for the simplified public uploader.
// Change these values here to affect the Fullscreen capture modal behavior.
export const TARGET_FRAMES = 60;

// Default number of takes recorded per capture run. Adjustable in the capture
// modal: takes recorded back to back in one sitting share signer, lighting,
// framing and pose, so they are near-duplicates rather than independent
// samples. More takes grow the file count without growing dataset diversity.
export const CAPTURE_COUNT = 5;
export const MIN_CAPTURE_COUNT = 1;
export const MAX_CAPTURE_COUNT = 10;

/**
 * Coerce arbitrary user input into a valid take count.
 * Returns null for input that is not yet a usable number, so callers can let
 * someone clear the field mid-edit instead of fighting them on every keystroke.
 */
export function clampCaptureCount(value: string | number): number | null {
  const n = typeof value === "number" ? value : parseInt(value.trim(), 10);
  if (!Number.isFinite(n)) return null;
  return Math.min(MAX_CAPTURE_COUNT, Math.max(MIN_CAPTURE_COUNT, Math.trunc(n)));
}
// Sampling FPS used by the capture pipeline (how many frames per second we store).
// The render/camera may run faster (we request up to 30/60 FPS), but we sample at
// this rate to build training-friendly datasets and control upload size.
export const SAMPLE_FPS = 30;
export const FRAME_INTERVAL_MS = Math.round(1000 / SAMPLE_FPS);

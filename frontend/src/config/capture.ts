// Centralized capture defaults for the simplified public uploader.
// Change these values here to affect the Fullscreen capture modal behavior.
export const TARGET_FRAMES = 60;
export const CAPTURE_COUNT = 5;
// Sampling FPS used by the capture pipeline (how many frames per second we store).
// The render/camera may run faster (we request up to 30/60 FPS), but we sample at
// this rate to build training-friendly datasets and control upload size.
export const SAMPLE_FPS = 30;
export const FRAME_INTERVAL_MS = Math.round(1000 / SAMPLE_FPS);

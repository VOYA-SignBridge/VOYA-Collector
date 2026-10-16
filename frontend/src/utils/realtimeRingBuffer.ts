import { REALTIME_FEATURE_DIM } from "./realtimeFlatten";

/**
 * Production-safe ring buffer for realtime inference sequences.
 *
 * Stores the latest N frames (default 60), each of fixed shape Float32Array(126).
 *
 * Design goals:
 * - Fixed-size typed backing store (min GC)
 * - Validates frame length and finiteness (avoid silent corruption)
 * - Overwrites oldest frames when full
 * - Snapshot returns a deterministic number[][] with shape (N, 126)
 *   in chronological order (oldest → newest)
 */
export class RealtimeRingBuffer {
  readonly capacity: number;
  readonly featureDim: number;
  readonly minReadyFrames: number;

  private readonly store: Float32Array;
  private writeIndex: number;
  private count: number;

  constructor(options?: { capacity?: number; featureDim?: number; minReadyFrames?: number }) {
    const capacity = options?.capacity ?? 60;
    const featureDim = options?.featureDim ?? REALTIME_FEATURE_DIM;
    const minReadyFrames = options?.minReadyFrames ?? capacity;

    if (!Number.isInteger(capacity) || capacity <= 0) {
      throw new Error(`Invalid capacity: ${capacity}`);
    }
    if (!Number.isInteger(featureDim) || featureDim <= 0) {
      throw new Error(`Invalid featureDim: ${featureDim}`);
    }
    if (!Number.isInteger(minReadyFrames) || minReadyFrames <= 0 || minReadyFrames > capacity) {
      throw new Error(`Invalid minReadyFrames: ${minReadyFrames} (must be 1..${capacity})`);
    }

    this.capacity = capacity;
    this.featureDim = featureDim;
    this.minReadyFrames = minReadyFrames;
    this.store = new Float32Array(this.capacity * this.featureDim);
    this.writeIndex = 0;
    this.count = 0;
  }

  /** Returns true when at least `minReadyFrames` frames have been appended. */
  isReady(): boolean {
    return this.count >= this.minReadyFrames;
  }

  /** Number of frames currently held (0..capacity). */
  size(): number {
    return Math.min(this.count, this.capacity);
  }

  /** Clears buffer contents and resets chronology. */
  clear(): void {
    this.store.fill(0);
    this.writeIndex = 0;
    this.count = 0;
  }

  /**
   * Appends a frame into the buffer.
   *
   * Safety rules:
   * - Rejects invalid frame length.
   * - Rejects any non-finite values (NaN/Infinity) to avoid semantic corruption.
   *
   * Copies frame data into internal storage so callers cannot mutate history.
   */
  append(frameInput: ArrayLike<number>): void {
    // Robustness: accept ArrayLike (e.g., number[], Float64Array) and normalize.
    // Fast-path keeps caller's Float32Array without extra allocation.
    const frame = frameInput instanceof Float32Array
      ? frameInput
      : Float32Array.from(frameInput);

    if (frame.length !== this.featureDim) {
      throw new Error(
        `Invalid frame length: expected ${this.featureDim}, got ${frame.length}`
      );
    }

    // Validate finiteness: reject NaN/Infinity early (prevents silent corruption).
    for (let i = 0; i < frame.length; i++) {
      const v = frame[i];
      if (!Number.isFinite(v)) {
        throw new Error(`Invalid frame value at index ${i}: ${String(v)}`);
      }
    }

    const offset = this.writeIndex * this.featureDim;
    this.store.set(frame, offset);

    this.writeIndex = (this.writeIndex + 1) % this.capacity;
    this.count++;
  }

  /**
   * Creates a transport-safe snapshot with deterministic shape: (capacity, featureDim).
   *
   * Chronology guarantee:
   * - Rows are ordered oldest → newest.
    * - When buffer is not ready (size < capacity), the oldest missing rows are zero-filled.
    *
    * Important: the realtime request scheduler SHOULD NOT send inference requests
    * until `isReady()` is true. The zero-fill behavior exists only to guarantee
    * stable shape for debugging and defensive programming.
   *
   * Safety guarantee:
   * - Does not expose internal mutable storage.
   */
  snapshot(): number[][] {
    const out: number[][] = new Array(this.capacity);

    const currentSize = this.size();
    const missing = this.capacity - currentSize;

    // Prepare zero row for missing prefix (copy to avoid shared array mutations).
    const zeroRow = new Array(this.featureDim).fill(0);

    // 1) Missing prefix (if not ready): deterministic zero-fill.
    for (let i = 0; i < missing; i++) {
      out[i] = zeroRow.slice();
    }

    // 2) Existing frames in chronological order.
    if (currentSize === 0) return out;

    if (!this.isReady()) {
      // Not ready: frames live contiguously in [0..currentSize-1] in chronological order.
      for (let i = 0; i < currentSize; i++) {
        out[missing + i] = this.readFrameAsNumberArray(i);
      }
      return out;
    }

    // Ready: oldest frame is at writeIndex (next write position).
    for (let i = 0; i < this.capacity; i++) {
      const srcFrameIndex = (this.writeIndex + i) % this.capacity;
      out[i] = this.readFrameAsNumberArray(srcFrameIndex);
    }

    return out;
  }

  private readFrameAsNumberArray(frameIndex: number): number[] {
    const row = new Array<number>(this.featureDim);
    const base = frameIndex * this.featureDim;
    for (let j = 0; j < this.featureDim; j++) {
      row[j] = this.store[base + j];
    }
    return row;
  }
}

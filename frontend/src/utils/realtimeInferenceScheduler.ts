/**
 * Realtime inference request scheduler.
 *
 * Hard rules enforced:
 * - Debounce triggers (default 200ms)
 * - ONLY ONE request may be in-flight at a time
 * - If a request is in-flight when the debounce fires => SKIP (no queue, no abort)
 * - Only send when the sequence provider is ready
 * - Safe disposal: no callbacks after dispose()
 *
 * This utility is framework-agnostic and React-independent.
 */

export type RealtimeSchedulerStatus =
  | "idle"
  | "debouncing"
  | "in_flight";

export type RealtimeSkipReason =
  | "not_ready"
  | "in_flight"
  | "disposed"
  | "invalid_snapshot";

export interface RealtimeSequenceProvider {
  /** True when a full inference window exists (e.g., 60 frames). */
  isReady(): boolean;
  /** Snapshot of shape (seqLen, featureDim) used for API transport. */
  snapshot(): number[][];
}

export interface RealtimeInferenceSchedulerOptions<TPrediction> {
  /** Provides readiness + deterministic snapshot extraction. */
  provider: RealtimeSequenceProvider;

  /**
   * Perform the inference request.
   * Must not mutate provider/buffer.
   */
  request: (frames: number[][]) => Promise<TPrediction>;

  /** Debounce interval in ms. Default: 200. */
  debounceMs?: number;

  /** Expected fixed shape. Defaults align with VOYA contract (60,126). */
  expectedSeqLen?: number;
  expectedFeatureDim?: number;

  /**
   * Snapshot validation mode.
   * - "shape": check only (fast, relies on upstream validation)
   * - "sampled": shape + sampled finite checks (default)
   * - "full": shape + full finite scan (slow; useful for debugging)
   *
   * Note: if your provider is backed by RealtimeRingBuffer.append(), non-finite
   * values are already rejected at ingestion time.
   */
  snapshotValidation?: "shape" | "sampled" | "full";

  /** Called when a prediction is received (only if not disposed). */
  onPrediction: (prediction: TPrediction) => void;

  /** Called on network/backend errors (only if not disposed). */
  onError?: (error: unknown) => void;

  /** Optional status updates (idle/debouncing/in_flight). */
  onStatusChange?: (status: RealtimeSchedulerStatus) => void;

  /** Optional: observe skipped sends for debugging/telemetry. */
  onSkip?: (reason: RealtimeSkipReason) => void;
}

const clampInt = (v: unknown, fallback: number): number => {
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(0, Math.floor(n));
};

const validateSnapshotShape = (
  frames: number[][],
  expectedSeqLen: number,
  expectedFeatureDim: number,
  mode: "shape" | "sampled" | "full"
): boolean => {
  if (!Array.isArray(frames) || frames.length !== expectedSeqLen) return false;

  // Always verify row shapes (cheap and prevents obvious corruption).
  for (let i = 0; i < frames.length; i++) {
    const row = frames[i];
    if (!Array.isArray(row) || row.length !== expectedFeatureDim) return false;
  }

  if (mode === "shape") return true;

  const isFiniteNumber = (v: unknown): v is number =>
    typeof v === "number" && Number.isFinite(v);

  if (mode === "full") {
    for (let i = 0; i < frames.length; i++) {
      const row = frames[i];
      for (let j = 0; j < row.length; j++) {
        if (!isFiniteNumber(row[j])) return false;
      }
    }
    return true;
  }

  // mode === "sampled": deterministic sampling (fast) to catch unexpected NaNs.
  const rowIndices: number[] = [0, Math.floor(expectedSeqLen / 2), expectedSeqLen - 1];
  if (expectedSeqLen > 4) rowIndices.push(1, expectedSeqLen - 2);
  const colIndices: number[] = [0, 1, 2, Math.floor(expectedFeatureDim / 2), expectedFeatureDim - 1];

  for (const i of rowIndices) {
    const row = frames[i];
    if (!row) return false;
    for (const j of colIndices) {
      const v = row[j];
      if (!isFiniteNumber(v)) return false;
    }
  }
  return true;
};

export class RealtimeInferenceScheduler<TPrediction> {
  private readonly provider: RealtimeSequenceProvider;
  private readonly request: (frames: number[][]) => Promise<TPrediction>;
  private readonly onPrediction: (prediction: TPrediction) => void;
  private readonly onError?: (error: unknown) => void;
  private readonly onStatusChange?: (status: RealtimeSchedulerStatus) => void;
  private readonly onSkip?: (reason: RealtimeSkipReason) => void;

  private readonly debounceMs: number;
  private readonly expectedSeqLen: number;
  private readonly expectedFeatureDim: number;

  private timer: ReturnType<typeof setTimeout> | null = null;
  private inFlight = false;
  private disposed = false;
  private status: RealtimeSchedulerStatus = "idle";

  // Defensive-only: ignore late async completions after dispose.
  // This is not a concurrency state machine; strict no-overlap is enforced via `inFlight`.
  private disposeEpoch = 0;

  private readonly snapshotValidation: "shape" | "sampled" | "full";

  constructor(options: RealtimeInferenceSchedulerOptions<TPrediction>) {
    this.provider = options.provider;
    this.request = options.request;
    this.onPrediction = options.onPrediction;
    this.onError = options.onError;
    this.onStatusChange = options.onStatusChange;
    this.onSkip = options.onSkip;

    this.debounceMs = clampInt(options.debounceMs, 200);
    this.expectedSeqLen = clampInt(options.expectedSeqLen, 60);
    this.expectedFeatureDim = clampInt(options.expectedFeatureDim, 126);
    this.snapshotValidation = options.snapshotValidation ?? "sampled";

    if (this.debounceMs < 1) {
      throw new Error(`Invalid debounceMs: ${this.debounceMs}`);
    }
    if (this.expectedSeqLen <= 0 || this.expectedFeatureDim <= 0) {
      throw new Error(
        `Invalid expected shape: (${this.expectedSeqLen}, ${this.expectedFeatureDim})`
      );
    }

    this.setStatus("idle");
  }

  /** Schedules an inference attempt after the debounce interval. */
  trigger(): void {
    if (this.disposed) {
      this.onSkip?.("disposed");
      return;
    }

    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }

    this.setStatus("debouncing");

    this.timer = setTimeout(() => {
      this.timer = null;
      void this.fire();
    }, this.debounceMs);
  }

  /** Cancels any pending debounce and prevents future callbacks. */
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;

    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }

    // Increment epoch so any late completions can be ignored.
    this.disposeEpoch++;

    this.setStatus("idle");
  }

  /** True when a request is currently in-flight. */
  isInFlight(): boolean {
    return this.inFlight;
  }

  /** Current internal status (idle/debouncing/in_flight). */
  getStatus(): RealtimeSchedulerStatus {
    return this.status;
  }

  private setStatus(next: RealtimeSchedulerStatus) {
    if (this.status === next) return;
    this.status = next;
    if (!this.disposed) this.onStatusChange?.(next);
  }

  private async fire(): Promise<void> {
    if (this.disposed) {
      this.onSkip?.("disposed");
      return;
    }

    // Hard rule: skip if a request is already running.
    if (this.inFlight) {
      this.onSkip?.("in_flight");
      this.setStatus("idle");
      return;
    }

    // Hard rule: only send when provider is ready.
    if (!this.provider.isReady()) {
      this.onSkip?.("not_ready");
      this.setStatus("idle");
      return;
    }

    const frames = this.provider.snapshot();
    const ok = validateSnapshotShape(
      frames,
      this.expectedSeqLen,
      this.expectedFeatureDim,
      this.snapshotValidation
    );
    if (!ok) {
      this.onSkip?.("invalid_snapshot");
      this.setStatus("idle");
      return;
    }

    this.inFlight = true;
    this.setStatus("in_flight");

    // Defensive-only: if dispose() happens mid-request, ignore completion.
    const epochAtStart = this.disposeEpoch;

    try {
      const prediction = await this.request(frames);

      // Ignore if disposed or a newer epoch exists (defensive).
      if (this.disposed || epochAtStart !== this.disposeEpoch) return;

      this.onPrediction(prediction);
    } catch (err: unknown) {
      if (this.disposed || epochAtStart !== this.disposeEpoch) return;
      this.onError?.(err);
    } finally {
      // Always drop inFlight; status updates are suppressed after dispose.
      this.inFlight = false;
      if (!this.disposed && epochAtStart === this.disposeEpoch) this.setStatus("idle");
    }
  }
}

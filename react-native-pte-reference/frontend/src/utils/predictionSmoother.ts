/**
 * Prediction smoothing engine.
 *
 * Goals:
 * - Reduce flicker via label majority vote over recent history
 * - Stabilize confidence via EMA
 * - Deterministic, lightweight, framework-agnostic
 * - No mutation of backend responses (stores only derived state)
 */

export interface SmoothedPrediction {
  label: string;
  confidence: number;
  /** Number of samples currently contributing to label vote (<= historySize). */
  samples: number;
}

export interface PredictionSmootherOptions {
  /** Majority-vote history length for labels. Default: 5. */
  historySize?: number;
  /** EMA alpha for confidence smoothing. Default: 0.5. */
  emaAlpha?: number;
  /** Optional clamp for confidence output. Default: [0, 1]. */
  clampConfidence?: { min: number; max: number };
}

const isFiniteNumber = (v: unknown): v is number =>
  typeof v === "number" && Number.isFinite(v);

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

export class PredictionSmoother {
  private readonly historySize: number;
  private readonly alpha: number;
  private readonly clampMin: number;
  private readonly clampMax: number;

  private readonly labels: (string | null)[];
  private writeIndex = 0;
  private count = 0;

  private emaConfidence: number | null = null;

  // Cache primitives only (avoid exposing a shared mutable object reference).
  private cachedLabel: string | null = null;
  private cachedConfidence: number | null = null;
  private cachedSamples: number | null = null;

  constructor(options?: PredictionSmootherOptions) {
    const historySize = options?.historySize ?? 5;
    if (!Number.isInteger(historySize) || historySize <= 0) {
      throw new Error(`Invalid historySize: ${historySize}`);
    }

    const alphaRaw = options?.emaAlpha ?? 0.5;
    const alpha = typeof alphaRaw === "number" ? alphaRaw : Number(alphaRaw);
    if (!Number.isFinite(alpha) || alpha <= 0 || alpha >= 1) {
      throw new Error(`Invalid emaAlpha: ${alphaRaw} (must be in (0,1))`);
    }

    const clampMin = options?.clampConfidence?.min ?? 0;
    const clampMax = options?.clampConfidence?.max ?? 1;
    if (!isFiniteNumber(clampMin) || !isFiniteNumber(clampMax) || clampMin >= clampMax) {
      throw new Error(`Invalid clampConfidence: [${String(clampMin)}, ${String(clampMax)}]`);
    }

    this.historySize = historySize;
    this.alpha = alpha;
    this.clampMin = clampMin;
    this.clampMax = clampMax;

    this.labels = new Array<string | null>(this.historySize).fill(null);
  }

  /** Clears label history and confidence EMA. */
  reset(): void {
    this.labels.fill(null);
    this.writeIndex = 0;
    this.count = 0;
    this.emaConfidence = null;
    this.cachedLabel = null;
    this.cachedConfidence = null;
    this.cachedSamples = null;
  }

  /** Push a new raw backend prediction into the smoother. */
  pushPrediction(label: string, confidence: number): void {
    const cleanLabel = typeof label === "string" ? label.trim() : "";
    if (!cleanLabel) {
      // Ignore invalid labels to avoid polluting vote history.
      return;
    }
    if (!isFiniteNumber(confidence)) {
      // Ignore invalid confidence.
      return;
    }

    // Guard: if confidence is outside expected bounds, skip this update.
    // We clamp AFTER EMA to avoid biasing the smoothing math.
    if (confidence < this.clampMin || confidence > this.clampMax) {
      return;
    }

    // Label history ring write.
    this.labels[this.writeIndex] = cleanLabel;
    this.writeIndex = (this.writeIndex + 1) % this.historySize;
    this.count = Math.min(this.count + 1, this.historySize);

    // EMA confidence.
    if (this.emaConfidence == null) {
      this.emaConfidence = confidence;
    } else {
      this.emaConfidence = this.alpha * confidence + (1 - this.alpha) * this.emaConfidence;
    }

    // Invalidate cached primitives.
    this.cachedLabel = null;
    this.cachedConfidence = null;
    this.cachedSamples = null;
  }

  /**
   * Returns current smoothed prediction.
   *
   * Label smoothing: majority vote over last N labels.
   * Tie-breaking (deterministic): if multiple labels tie for max count,
   * choose the newest label among the tied labels.
   */
  getSmoothed(): SmoothedPrediction | null {
    if (this.count === 0 || this.emaConfidence == null) return null;
    // If we already computed cached primitives for the current state, we can
    // reuse them but still return a fresh object (no shared reference).
    if (this.cachedLabel && this.cachedConfidence != null && this.cachedSamples != null) {
      return {
        label: this.cachedLabel,
        confidence: this.cachedConfidence,
        samples: this.cachedSamples,
      };
    }

    // Count labels. Use Map to handle arbitrary label strings.
    const counts = new Map<string, number>();

    // Also track newest occurrence index for deterministic tie-breaking.
    // We consider "newest" in time order, not array index order.
    const newestRank = new Map<string, number>();

    // Iterate in chronological order oldest -> newest for stable ranking.
    // Oldest is at writeIndex when buffer is full; otherwise oldest at 0.
    const start = this.count < this.historySize ? 0 : this.writeIndex;

    for (let t = 0; t < this.count; t++) {
      const idx = (start + t) % this.historySize;
      const lbl = this.labels[idx];
      if (!lbl) continue;

      counts.set(lbl, (counts.get(lbl) ?? 0) + 1);
      // Higher t means newer.
      newestRank.set(lbl, t);
    }

    let bestLabel: string | null = null;
    let bestCount = -1;
    let bestNewest = -1;

    for (const [lbl, c] of counts.entries()) {
      const newest = newestRank.get(lbl) ?? -1;
      if (c > bestCount) {
        bestLabel = lbl;
        bestCount = c;
        bestNewest = newest;
      } else if (c === bestCount) {
        // Tie: prefer newest among tied.
        if (newest > bestNewest) {
          bestLabel = lbl;
          bestNewest = newest;
        }
      }
    }

    if (!bestLabel) return null;

    const smoothedConfidence = clamp(this.emaConfidence, this.clampMin, this.clampMax);

    // Cache primitives only.
    this.cachedLabel = bestLabel;
    this.cachedConfidence = smoothedConfidence;
    this.cachedSamples = this.count;

    // Return a fresh object to avoid exposing shared mutable references.
    return {
      label: bestLabel,
      confidence: smoothedConfidence,
      samples: this.count,
    };
  }
}

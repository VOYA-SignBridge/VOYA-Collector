export class LowPassFilter {
  private yPrev: number | null = null;
  private a: number;

  constructor(alpha: number) {
    this.a = alpha;
  }

  filter(value: number) {
    if (this.yPrev === null) {
      this.yPrev = value;
      return value;
    }
    const y = this.a * value + (1 - this.a) * this.yPrev;
    this.yPrev = y;
    return y;
  }

  setAlpha(alpha: number) {
    this.a = alpha;
  }
}

export class OneEuroFilter {
  private xFilter: LowPassFilter;
  private dxFilter: LowPassFilter;
  private lastTime: number | null = null;
  private lastValue: number | null = null;

  freq: number;
  minCutoff: number;
  beta: number;
  dCutoff: number;

  constructor(freq = 30, minCutoff = 1.0, beta = 0.01, dCutoff = 1.0) {
    this.freq = freq;
    this.minCutoff = minCutoff;
    this.beta = beta;
    this.dCutoff = dCutoff;
    this.xFilter = new LowPassFilter(this.alpha(this.minCutoff));
    this.dxFilter = new LowPassFilter(this.alpha(this.dCutoff));
  }

  private alpha(cutoff: number) {
    const te = 1.0 / (this.freq || 30);
    const tau = 1.0 / (2 * Math.PI * cutoff);
    return 1.0 / (1.0 + tau / te);
  }

  reset() {
    this.xFilter = new LowPassFilter(this.alpha(this.minCutoff));
    this.dxFilter = new LowPassFilter(this.alpha(this.dCutoff));
    this.lastTime = null;
  }

  filter(value: number, timestampMs?: number) {
    const t = timestampMs != null ? timestampMs / 1000 : null;
    if (this.lastTime == null && t == null) {
      this.lastTime = t || performance.now() / 1000;
      return value;
    }

    const now = t ?? performance.now() / 1000;
    const dt = now - (this.lastTime ?? now);
    this.lastTime = now;
    if (dt <= 0) return value;

  this.freq = 1.0 / dt;

  // approximate derivative using lastValue (previous filtered value)
  const prev = this.lastValue ?? value;
  const dx = (value - prev) * this.freq;
  const edx = this.dxFilter.filter(dx);

    // adapt cutoff
    const cutoff = this.minCutoff + this.beta * Math.abs(edx);
    const a = this.alpha(cutoff);
    this.xFilter.setAlpha(a);

    const filtered = this.xFilter.filter(value);
    this.lastValue = filtered;
    return filtered;
  }
}

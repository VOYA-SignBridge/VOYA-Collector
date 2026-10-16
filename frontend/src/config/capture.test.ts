import { describe, it, expect } from "vitest";
import {
  clampCaptureCount,
  CAPTURE_COUNT,
  MIN_CAPTURE_COUNT,
  MAX_CAPTURE_COUNT,
} from "./capture";

describe("clampCaptureCount", () => {
  it("keeps values already inside the range", () => {
    expect(clampCaptureCount(1)).toBe(1);
    expect(clampCaptureCount(5)).toBe(5);
    expect(clampCaptureCount("3")).toBe(3);
  });

  it("clamps to the range instead of rejecting", () => {
    expect(clampCaptureCount(0)).toBe(MIN_CAPTURE_COUNT);
    expect(clampCaptureCount(-7)).toBe(MIN_CAPTURE_COUNT);
    expect(clampCaptureCount(999)).toBe(MAX_CAPTURE_COUNT);
  });

  // The field is a free-text input; returning null lets the caller restore the
  // last committed value rather than silently substituting a number.
  it("returns null for input that is not a usable number", () => {
    expect(clampCaptureCount("")).toBeNull();
    expect(clampCaptureCount("   ")).toBeNull();
    expect(clampCaptureCount("abc")).toBeNull();
    expect(clampCaptureCount(NaN)).toBeNull();
    expect(clampCaptureCount(Infinity)).toBeNull();
  });

  it("truncates fractional input rather than rounding up past the max", () => {
    expect(clampCaptureCount("4.9")).toBe(4);
    expect(clampCaptureCount(2.7)).toBe(2);
  });

  it("tolerates surrounding whitespace", () => {
    expect(clampCaptureCount("  6 ")).toBe(6);
  });

  it("ships a default that is inside its own range", () => {
    expect(CAPTURE_COUNT).toBeGreaterThanOrEqual(MIN_CAPTURE_COUNT);
    expect(CAPTURE_COUNT).toBeLessThanOrEqual(MAX_CAPTURE_COUNT);
  });
});

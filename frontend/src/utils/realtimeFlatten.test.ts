import { describe, it, expect } from "vitest";
import {
  flattenRealtimeHands,
  REALTIME_DIMS_PER_HAND,
  REALTIME_FEATURE_DIM,
  type MediaPipeHandsLikeResults,
} from "./realtimeFlatten";
import type { HandAnchors } from "./handIdentity";
import { MIRROR_SERVING_PAYLOAD } from "../config/handTracking";
import type { MediaPipeLandmark } from "../types";

/** 21 landmarks whose wrist is at (x, y); remaining points fan out from it. */
const handAt = (x: number, y: number): MediaPipeLandmark[] =>
  Array.from({ length: 21 }, (_, i) => ({
    x: i === 0 ? x : x + i * 0.002,
    y: i === 0 ? y : y + i * 0.003,
    z: i * 0.001,
  }));

const results = (
  hands: Array<{ lms: MediaPipeLandmark[]; label?: string; score?: number }>,
): MediaPipeHandsLikeResults => ({
  multiHandLandmarks: hands.map((h) => h.lms),
  multiHandedness: hands.map((h) => ({ label: h.label, score: h.score ?? 0.9 })),
});

const leftSlot = (v: Float32Array) => v.slice(0, REALTIME_DIMS_PER_HAND);
const rightSlot = (v: Float32Array) => v.slice(REALTIME_DIMS_PER_HAND);
const isAllZero = (a: Float32Array) => a.every((n) => n === 0);

describe("flattenRealtimeHands", () => {
  it("returns a zeroed vector of the right shape when nothing is detected", () => {
    const v = flattenRealtimeHands(null);
    expect(v.length).toBe(REALTIME_FEATURE_DIM);
    expect(isAllZero(v)).toBe(true);
  });

  it("reuses the provided output buffer and clears stale values", () => {
    const buf = new Float32Array(REALTIME_FEATURE_DIM).fill(7);
    const v = flattenRealtimeHands(null, buf);
    expect(v).toBe(buf);
    expect(isAllZero(v)).toBe(true);
  });

  // MediaPipe is trained on mirrored selfie frames but sees the raw webcam feed,
  // so its "Right" is the person's left.
  it("maps MediaPipe 'Right' into the user's left slot", () => {
    const lms = handAt(0.3, 0.4);
    const v = flattenRealtimeHands(results([{ lms, label: "Right" }]), undefined, {
      mirrorX: false,
      now: 1000,
    });

    expect(isAllZero(leftSlot(v))).toBe(false);
    expect(isAllZero(rightSlot(v))).toBe(true);
    expect(v[0]).toBeCloseTo(0.3, 6);
  });

  // Serving orientation is what silently breaks a promoted model, so pin both the
  // constant and the encoder default. If the corpus is ever canonicalized and this
  // is flipped on purpose, update both together — deliberately, not by accident.
  it("serves unmirrored by default while the corpus is split", () => {
    expect(MIRROR_SERVING_PAYLOAD).toBe(false);

    const lms = handAt(0.3, 0.4);
    const v = flattenRealtimeHands(results([{ lms, label: "Right" }]), undefined, {
      now: 1000,
    });

    // x passes through untouched; 0.7 would mean a mirror was applied.
    expect(v[0]).toBeCloseTo(0.3, 6);
  });

  it("mirrors x when the corpus was recorded mirrored", () => {
    const lms = handAt(0.3, 0.4);
    const v = flattenRealtimeHands(results([{ lms, label: "Right" }]), undefined, {
      mirrorX: true,
      now: 1000,
    });

    // x -> 1 - x, y and z untouched.
    expect(v[0]).toBeCloseTo(0.7, 6);
    expect(v[1]).toBeCloseTo(0.4, 6);
    expect(v[2]).toBeCloseTo(0, 6);
  });

  // The old label-only encoder called selectHandByLabel("Left") and
  // selectHandByLabel("Right") independently, so two same-labelled hands filled
  // one slot and left the other 63 dims zero.
  it("fills both slots when MediaPipe reports the same label twice", () => {
    const a = handAt(0.35, 0.5);
    const b = handAt(0.65, 0.5);
    const v = flattenRealtimeHands(
      results([
        { lms: a, label: "Left", score: 0.95 },
        { lms: b, label: "Left", score: 0.6 },
      ]),
      undefined,
      { mirrorX: false, now: 1000 },
    );

    expect(isAllZero(leftSlot(v))).toBe(false);
    expect(isAllZero(rightSlot(v))).toBe(false);
  });

  it("keeps slot identity across frames when the label flips mid-sequence", () => {
    const anchors: HandAnchors = {};
    const opts = (now: number) => ({ anchors, mirrorX: false, now });

    // Frame 1: hands at rest, labels correct.
    const v1 = flattenRealtimeHands(
      results([
        { lms: handAt(0.7, 0.5), label: "Left" }, // -> user's right
        { lms: handAt(0.3, 0.5), label: "Right" }, // -> user's left
      ]),
      undefined,
      opts(1000),
    );
    const leftX1 = leftSlot(v1)[0];
    const rightX1 = rightSlot(v1)[0];
    expect(leftX1).toBeCloseTo(0.3, 6);
    expect(rightX1).toBeCloseTo(0.7, 6);

    // Frame 2: hands barely moved, but MediaPipe flipped BOTH labels.
    const v2 = flattenRealtimeHands(
      results([
        { lms: handAt(0.69, 0.5), label: "Right" },
        { lms: handAt(0.31, 0.5), label: "Left" },
      ]),
      undefined,
      opts(1033),
    );

    // Slots must still follow the hands, not the labels.
    expect(leftSlot(v2)[0]).toBeCloseTo(0.31, 6);
    expect(rightSlot(v2)[0]).toBeCloseTo(0.69, 6);
  });

  it("resolves each frame independently when no anchors are supplied", () => {
    // Without anchors the encoder has no memory, so a flipped label does move
    // the hand to the other slot. This documents why callers must pass anchors.
    const withoutAnchors = flattenRealtimeHands(
      results([{ lms: handAt(0.7, 0.5), label: "Left" }]),
      undefined,
      { mirrorX: false, now: 1000 },
    );
    expect(isAllZero(rightSlot(withoutAnchors))).toBe(false);

    const flipped = flattenRealtimeHands(
      results([{ lms: handAt(0.7, 0.5), label: "Right" }]),
      undefined,
      { mirrorX: false, now: 1033 },
    );
    expect(isAllZero(leftSlot(flipped))).toBe(false);
  });

  it("zero-fills non-finite coordinates rather than writing NaN", () => {
    const broken = handAt(0.4, 0.4);
    broken[3] = { x: NaN, y: undefined as unknown as number, z: Infinity };

    const v = flattenRealtimeHands(results([{ lms: broken, label: "Right" }]), undefined, {
      mirrorX: false,
      now: 1000,
    });

    expect(v.every((n) => Number.isFinite(n))).toBe(true);
    const base = 3 * 3;
    expect(v[base + 0]).toBe(0);
    expect(v[base + 1]).toBe(0);
    expect(v[base + 2]).toBe(0);
  });

  it("advances anchors so a hand tracked over many frames stays in one slot", () => {
    const anchors: HandAnchors = {};
    const slots: string[] = [];

    for (let f = 0; f < 30; f++) {
      // Label deliberately alternates every frame — the worst case.
      const label = f % 2 === 0 ? "Right" : "Left";
      const v = flattenRealtimeHands(
        results([{ lms: handAt(0.3 + f * 0.004, 0.5), label } as const]),
        undefined,
        { anchors, mirrorX: false, now: 1000 + f * 33 },
      );
      slots.push(isAllZero(leftSlot(v)) ? "right" : "left");
    }

    // First frame has no anchor and follows the label; every later frame must
    // stay locked to the slot it established.
    expect(new Set(slots.slice(1))).toEqual(new Set(["left"]));
  });
});

import { describe, it, expect } from "vitest";
import {
  assignHandSlots,
  HAND_ANCHOR_MAX_AGE_MS,
  type HandDetection,
} from "./handIdentity";
import type { MediaPipeLandmark } from "../types";

/** A 21-point hand whose wrist sits at (x, y); the rest is filler. */
const handAt = (x: number, y: number): MediaPipeLandmark[] =>
  Array.from({ length: 21 }, (_, i) =>
    i === 0 ? { x, y, z: 0 } : { x: x + i * 0.001, y: y + i * 0.001, z: 0 },
  );

const detection = (
  x: number,
  y: number,
  label?: string,
  score = 0.9,
): HandDetection => ({ landmarks: handAt(x, y), label, score });

const NOW = 10_000;

describe("assignHandSlots", () => {
  it("returns nothing when there are no detections", () => {
    expect(assignHandSlots([], {}, NOW)).toEqual({});
  });

  it("uses the label on first acquisition, with no anchors", () => {
    const d = detection(0.3, 0.5, "Left");
    expect(assignHandSlots([d], {}, NOW)).toEqual({ left: d.landmarks });

    const r = detection(0.7, 0.5, "Right");
    expect(assignHandSlots([r], {}, NOW)).toEqual({ right: r.landmarks });
  });

  it("drops an unlabelled lone hand when there is nothing to anchor it to", () => {
    expect(assignHandSlots([detection(0.5, 0.5, undefined)], {}, NOW)).toEqual({});
  });

  // Bug 1: MediaPipe labelling both overlapping hands the same used to overwrite
  // one slot, silently dropping a hand that had in fact been detected.
  it("never collapses two detections into one slot when both carry the same label", () => {
    const a = detection(0.45, 0.5, "Left", 0.95);
    const b = detection(0.55, 0.5, "Left", 0.6);

    const result = assignHandSlots([a, b], {}, NOW);

    expect(result.left).toBeDefined();
    expect(result.right).toBeDefined();
    // The more confident detection keeps the label it was given.
    expect(result.left).toBe(a.landmarks);
    expect(result.right).toBe(b.landmarks);
  });

  it("keeps both hands even when neither detection carries a label", () => {
    const leftish = detection(0.2, 0.5, undefined, 0.8);
    const rightish = detection(0.8, 0.5, undefined, 0.7);

    const result = assignHandSlots([leftish, rightish], {}, NOW);

    expect(result.left).toBe(leftish.landmarks);
    expect(result.right).toBe(rightish.landmarks);
  });

  // Bug 2: a label flip mid-clip used to invert left_hand / right_hand inside a
  // single recorded sample.
  it("holds identity through a label flip when the anchors disagree with the label", () => {
    const anchors = {
      left: { x: 0.3, y: 0.5, t: NOW },
      right: { x: 0.7, y: 0.5, t: NOW },
    };
    // Both hands stayed put, but MediaPipe flipped both labels this frame.
    const nearLeft = detection(0.31, 0.5, "Right", 0.9);
    const nearRight = detection(0.69, 0.5, "Left", 0.85);

    const result = assignHandSlots([nearLeft, nearRight], anchors, NOW + 33);

    expect(result.left).toBe(nearLeft.landmarks);
    expect(result.right).toBe(nearRight.landmarks);
  });

  it("follows the anchors when two hands genuinely cross over", () => {
    const anchors = {
      left: { x: 0.3, y: 0.5, t: NOW },
      right: { x: 0.7, y: 0.5, t: NOW },
    };
    // The left hand moved right and vice versa; labels agree with the motion.
    const movedRight = detection(0.68, 0.5, "Right", 0.9);
    const movedLeft = detection(0.32, 0.5, "Left", 0.9);

    const result = assignHandSlots([movedRight, movedLeft], anchors, NOW + 33);

    expect(result.left).toBe(movedLeft.landmarks);
    expect(result.right).toBe(movedRight.landmarks);
  });

  it("assigns a lone hand to the slot it continues, not the slot its label claims", () => {
    const anchors = { right: { x: 0.7, y: 0.5, t: NOW } };
    // Same hand, one frame later, but the label flipped.
    const stillThere = detection(0.71, 0.51, "Left", 0.9);

    const result = assignHandSlots([stillThere], anchors, NOW + 33);

    expect(result.right).toBe(stillThere.landmarks);
    expect(result.left).toBeUndefined();
  });

  it("falls back to the label once an anchor has aged out", () => {
    const anchors = { right: { x: 0.7, y: 0.5, t: NOW } };
    const reappeared = detection(0.71, 0.51, "Left", 0.9);

    const result = assignHandSlots(
      [reappeared],
      anchors,
      NOW + HAND_ANCHOR_MAX_AGE_MS + 1,
    );

    expect(result.left).toBe(reappeared.landmarks);
    expect(result.right).toBeUndefined();
  });

  it("ignores an anchor that is far away and trusts the label instead", () => {
    const anchors = { left: { x: 0.1, y: 0.1, t: NOW } };
    // Well outside HAND_ANCHOR_MATCH_RADIUS of the only anchor.
    const faraway = detection(0.9, 0.9, "Right", 0.9);

    const result = assignHandSlots([faraway], anchors, NOW + 33);

    expect(result.right).toBe(faraway.landmarks);
    expect(result.left).toBeUndefined();
  });

  it("keeps only the two most confident detections when more are reported", () => {
    const a = detection(0.2, 0.5, "Left", 0.99);
    const b = detection(0.8, 0.5, "Right", 0.95);
    const spurious = detection(0.5, 0.9, "Left", 0.2);

    const result = assignHandSlots([a, spurious, b], {}, NOW);

    expect(result.left).toBe(a.landmarks);
    expect(result.right).toBe(b.landmarks);
  });

  it("is stable frame over frame for an ordinary steady one-hand capture", () => {
    let anchors: { left?: { x: number; y: number; t: number }; right?: { x: number; y: number; t: number } } = {};
    const seen: string[] = [];

    for (let frame = 0; frame < 30; frame++) {
      const t = NOW + frame * 33;
      // A right hand drifting slowly across the frame.
      const d = detection(0.6 + frame * 0.005, 0.5, "Right", 0.9);
      const result = assignHandSlots([d], anchors, t);
      seen.push(result.right ? "right" : result.left ? "left" : "none");
      if (result.right) {
        anchors = { ...anchors, right: { x: 0.6 + frame * 0.005, y: 0.5, t } };
      }
    }

    expect(new Set(seen)).toEqual(new Set(["right"]));
  });
});

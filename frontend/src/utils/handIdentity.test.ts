import { describe, it, expect } from "vitest";
import {
  assignHandSlots,
  sourceOf,
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

  it("keeps a lone hand in its slot when the label flips mid-clip", () => {
    // The reported bug: one-handed signing, MediaPipe flips its per-frame label
    // (typically as the palm rotates), and the hand jumps to the other half of
    // the 126-dim vector for the rest of the sample.
    const anchors = { right: { x: 0.6, y: 0.5, t: NOW } };
    const flipped = detection(0.62, 0.5, "Left", 0.88);

    expect(assignHandSlots([flipped], anchors, NOW + 33)).toEqual({
      right: flipped.landmarks,
    });
  });

  it("keeps a lone hand in its slot across fast motion that exceeds the two-hand radius", () => {
    // 0.36 of the frame in one interval: far beyond HAND_ANCHOR_MATCH_RADIUS
    // (0.28) but well within reach of a real hand during a dynamic sign. With
    // one slot live this must stay the same hand, not fall through to a label
    // that may have flipped.
    const anchors = { right: { x: 0.2, y: 0.5, t: NOW } };
    const moved = detection(0.55, 0.6, "Left", 0.95);

    expect(assignHandSlots([moved], anchors, NOW + 33)).toEqual({
      right: moved.landmarks,
    });
  });

  it("still rejects a jump too large to be the same hand", () => {
    // Across the whole frame in one interval is a different hand, or a
    // reacquisition — the label is the better evidence there.
    const anchors = { right: { x: 0.1, y: 0.1, t: NOW } };
    const teleported = detection(0.95, 0.95, "Left", 0.9);

    expect(assignHandSlots([teleported], anchors, NOW + 33)).toEqual({
      left: teleported.landmarks,
    });
  });

  it("still uses the label once the only anchor has aged out", () => {
    const anchors = { right: { x: 0.6, y: 0.5, t: NOW } };
    const later = NOW + HAND_ANCHOR_MAX_AGE_MS + 1;
    const d = detection(0.3, 0.5, "Left", 0.9);

    expect(assignHandSlots([d], anchors, later)).toEqual({ left: d.landmarks });
  });

  it("still arbitrates by position when both slots are live", () => {
    // The distance gate must survive for genuine two-handed captures.
    const anchors = {
      left: { x: 0.3, y: 0.5, t: NOW },
      right: { x: 0.7, y: 0.5, t: NOW },
    };
    const nearLeft = detection(0.32, 0.5, "Right", 0.9);

    expect(assignHandSlots([nearLeft], anchors, NOW + 33)).toEqual({
      left: nearLeft.landmarks,
    });
  });

  describe("pinned slot (clip known to be one-handed)", () => {
    it("overrides a contradicting label", () => {
      const d = detection(0.3, 0.5, "Left", 0.99);
      expect(assignHandSlots([d], {}, NOW, { pinnedSlot: "right" })).toEqual({
        right: d.landmarks,
      });
    });

    it("overrides a contradicting anchor", () => {
      const anchors = { left: { x: 0.3, y: 0.5, t: NOW } };
      const d = detection(0.3, 0.5, "Left", 0.99);
      expect(assignHandSlots([d], anchors, NOW + 33, { pinnedSlot: "right" })).toEqual({
        right: d.landmarks,
      });
    });

    it("resolves to one hand from the first frame when the clip is declared one-handed", () => {
      // The deadlock this exists to break: a bystander hand keeps two detections
      // coming, the frame resolves to two slots, the expected-count check
      // rejects it, and the caller never sees the single-hand frame it needs to
      // pin a slot — so capture stalls forever.
      const signing = detection(0.6, 0.5, "Right", 0.95);
      const bystander = detection(0.15, 0.5, "Left", 0.7);

      const result = assignHandSlots([signing, bystander], {}, NOW, { forceSingle: true });

      expect(result.right).toBe(signing.landmarks);
      expect(result.left).toBeUndefined();
    });

    it("forceSingle does not override an already pinned slot", () => {
      const a = detection(0.6, 0.5, "Right", 0.95);
      const b = detection(0.2, 0.5, "Left", 0.9);

      const result = assignHandSlots([a, b], {}, NOW, {
        pinnedSlot: "left",
        forceSingle: true,
      });

      expect(result.left).toBe(a.landmarks);
      expect(result.right).toBeUndefined();
    });

    it("leaves two-handed clips alone", () => {
      const a = detection(0.2, 0.5, "Left", 0.95);
      const b = detection(0.8, 0.5, "Right", 0.9);

      const result = assignHandSlots([a, b], {}, NOW, { forceSingle: false });

      expect(result.left).toBe(a.landmarks);
      expect(result.right).toBe(b.landmarks);
    });

    it("keeps only the most confident hand when a spurious second is detected", () => {
      const real = detection(0.6, 0.5, "Right", 0.95);
      const spurious = detection(0.1, 0.9, "Left", 0.4);

      const result = assignHandSlots([real, spurious], {}, NOW, { pinnedSlot: "right" });

      expect(result).toEqual({ right: real.landmarks });
    });
  });
});

/**
 * World landmarks ride on the detection, and reading them back for a resolved
 * slot depends on one thing: that the resolver hands the caller the SAME array
 * object it was given, not a copy. That is currently true of every return path,
 * but nothing was stopping a later refactor from mapping or slicing on the way
 * out — which would detach each hand's metric 3D shape from its hand silently,
 * with left/right swapped and no error anywhere.
 */
describe("sourceOf — truy ngược khe về đúng bàn tay đã phát hiện", () => {
  it("giữ nguyên tham chiếu mảng landmarks qua assignHandSlots", () => {
    const left = detection(0.3, 0.5, "Left");
    const right = detection(0.7, 0.5, "Right");
    const out = assignHandSlots([left, right], {}, NOW);
    // Đẳng thức tham chiếu, không phải đẳng thức giá trị — đó mới là điều
    // khiến sourceOf dùng được.
    expect(out.left).toBe(left.landmarks);
    expect(out.right).toBe(right.landmarks);
  });

  it("trả về đúng detection mang world landmarks của khe đó", () => {
    const left = { ...detection(0.3, 0.5, "Left"), world: handAt(0.01, 0.02) };
    const right = { ...detection(0.7, 0.5, "Right"), world: handAt(0.03, 0.04) };
    const out = assignHandSlots([left, right], {}, NOW);
    expect(sourceOf([left, right], out.left)?.world).toBe(left.world);
    expect(sourceOf([left, right], out.right)?.world).toBe(right.world);
  });

  it("đi theo khe khi nhãn bị đảo, không đi theo thứ tự MediaPipe", () => {
    // MediaPipe gán nhãn "Right" cho detection tự tin hơn, nên nó về khe phải;
    // world landmarks phải đi cùng nó chứ không ở lại chỉ số 0.
    const first = { ...detection(0.7, 0.5, "Right"), score: 0.9, world: handAt(0.05, 0.06) };
    const second = { ...detection(0.3, 0.5, "Right"), score: 0.4, world: handAt(0.07, 0.08) };
    const out = assignHandSlots([first, second], {}, NOW);
    expect(out.right).toBe(first.landmarks);
    expect(sourceOf([first, second], out.right)?.world).toBe(first.world);
    expect(sourceOf([first, second], out.left)?.world).toBe(second.world);
  });

  it("trả undefined khi khe rỗng", () => {
    expect(sourceOf([], undefined)).toBeUndefined();
  });
});

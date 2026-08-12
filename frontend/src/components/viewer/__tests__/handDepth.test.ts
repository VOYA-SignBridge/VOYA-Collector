import { describe, it, expect } from "vitest";
import { computeFit, handDepth, handWidth, DIMS_PER_HAND, FRAME_DIM } from "../handData";

/**
 * Why a second landmark array exists at all.
 *
 * MediaPipe emits two per hand. `landmarks` — what `sequence` is built from —
 * is 2.5D: x,y are image coordinates and z is a depth the model regresses
 * relative to the wrist, documented as "roughly the same scale as x". But x
 * there spans the whole image while a hand covers a fraction of it, so measured
 * against the hand itself the depth is compressed: across 18046 frames of this
 * corpus a hand's z-span is a median 0.203 of its own width.
 *
 * `world_landmarks` is metric, in metres about the hand's geometric centre, so
 * the proportion between depth and width is right by construction. These tests
 * pin the conversion that carries that proportion onto the screen.
 */

const zeroFrame = () => new Array<number>(FRAME_DIM).fill(0);

/**
 * A hand `width` wide and `depth` deep, in whatever units the caller means.
 * Laid out so the extents are exact rather than approximate, which is what
 * lets the assertions below be equalities instead of ranges.
 */
function hand(
  frame: number[],
  base: number,
  { cx, cy, width, depth }: { cx: number; cy: number; width: number; depth: number },
) {
  for (let i = 0; i < 21; i++) {
    const t = i / 20;
    frame[base + i * 3] = cx + (t - 0.5) * width;
    frame[base + i * 3 + 1] = cy + (t - 0.5) * width;
    frame[base + i * 3 + 2] = (t - 0.5) * depth;
  }
}

describe("handDepth — chiều sâu theo mét, quy về bề rộng bàn tay", () => {
  it("trả null khi mẫu không có world landmarks", () => {
    // Mẫu cũ không khôi phục được: hệ số thật không được lưu ở đâu cả.
    expect(handDepth(undefined, "left")).toBeNull();
  });

  it("trả null cho khối toàn số 0 — đó là tay không thu được, không phải tay phẳng", () => {
    expect(handDepth(zeroFrame(), "left")).toBeNull();
  });

  it("đo được đúng tỉ lệ sâu/rộng đã thu", () => {
    // Bàn tay rộng 0.08 m, sâu 0.04 m → sâu bằng đúng nửa bề rộng.
    const frame = zeroFrame();
    hand(frame, 0, { cx: 0, cy: 0, width: 0.08, depth: 0.04 });
    const d = handDepth(frame, "left")!;
    expect(d).not.toBeNull();

    const zs = d.z.map((z) => z * d.scale);
    const zSpan = Math.max(...zs) - Math.min(...zs);
    // scale đưa mét về đơn vị "bề rộng bàn tay", nên span phải ra đúng 0.5.
    expect(zSpan).toBeCloseTo(0.5, 5);
  });

  it("không phụ thuộc vào việc bàn tay to hay nhỏ trong ảnh", () => {
    // Cùng một tỉ lệ hình học, hai kích cỡ khác nhau → cùng một kết quả.
    const small = zeroFrame();
    hand(small, 0, { cx: 0, cy: 0, width: 0.06, depth: 0.03 });
    const big = zeroFrame();
    hand(big, 0, { cx: 0, cy: 0, width: 0.12, depth: 0.06 });

    const spanOf = (f: number[]) => {
      const d = handDepth(f, "left")!;
      const zs = d.z.map((z) => z * d.scale);
      return Math.max(...zs) - Math.min(...zs);
    };
    expect(spanOf(small)).toBeCloseTo(spanOf(big), 5);
  });

  it("đọc đúng tay phải, không lẫn sang tay trái", () => {
    const frame = zeroFrame();
    hand(frame, DIMS_PER_HAND, { cx: 0, cy: 0, width: 0.08, depth: 0.08 });
    expect(handDepth(frame, "left")).toBeNull();
    const d = handDepth(frame, "right")!;
    const zs = d.z.map((z) => z * d.scale);
    expect(Math.max(...zs) - Math.min(...zs)).toBeCloseTo(1.0, 5);
  });
});

describe("world landmarks sửa được cái dẹp mà z ảnh không sửa nổi", () => {
  it("chiều sâu vẽ ra sâu hơn hẳn so với dùng z của ảnh", () => {
    // Dựng đúng tình huống thật: bàn tay chiếm ~15% bề ngang ảnh, còn z ảnh
    // chỉ trải một khoảng nhỏ — đúng con số đo được trên corpus.
    const imageFrame = zeroFrame();
    hand(imageFrame, 0, { cx: 0.5, cy: 0.5, width: 0.15, depth: 0.03 });
    const fit = computeFit([imageFrame]);
    const pts = imageFrame.slice(0, DIMS_PER_HAND);
    const onScreen = handWidth(pts, fit);

    // Đường cũ: z ảnh nhân với scale của phép fit.
    const legacyZ = pts.map((_, i) => (i % 3 === 2 ? pts[i] * fit.scale : 0)).filter((_, i) => i % 3 === 2);
    const legacySpan = Math.max(...legacyZ) - Math.min(...legacyZ);

    // Đường mới: cùng bàn tay ấy nhưng đo bằng world landmarks (sâu = 60% rộng).
    const worldFrame = zeroFrame();
    hand(worldFrame, 0, { cx: 0, cy: 0, width: 0.09, depth: 0.054 });
    const d = handDepth(worldFrame, "left")!;
    const worldZ = d.z.map((z) => z * d.scale * onScreen);
    const worldSpan = Math.max(...worldZ) - Math.min(...worldZ);

    // Tỉ lệ sâu/rộng trên màn hình phải bằng đúng cái đã thu, 0.6.
    expect(worldSpan / onScreen).toBeCloseTo(0.6, 5);
    // Và sâu hơn hẳn đường cũ — đây là toàn bộ lý do đi lấy mảng thứ hai.
    expect(worldSpan).toBeGreaterThan(legacySpan * 2);
  });
});

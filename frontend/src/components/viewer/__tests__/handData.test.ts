import { describe, it, expect } from "vitest";
import { computeFit, handPoints, FRAME_DIM, DIMS_PER_HAND } from "../handData";

const zeroFrame = () => new Array<number>(FRAME_DIM).fill(0);

describe("handData — trích xuất bàn tay từ frame 126 chiều", () => {
  it("trả về null cho bàn tay không được phát hiện (toàn số 0)", () => {
    const frame = zeroFrame();
    // Chỉ tay phải có dữ liệu
    frame[DIMS_PER_HAND] = 0.5;
    expect(handPoints(frame, "left")).toBeNull();
    expect(handPoints(frame, "right")).not.toBeNull();
  });

  it("cắt đúng 63 giá trị cho mỗi bàn tay", () => {
    const frame = zeroFrame().map((_, i) => i + 1);
    const left = handPoints(frame, "left")!;
    const right = handPoints(frame, "right")!;
    expect(left).toHaveLength(63);
    expect(right).toHaveLength(63);
    expect(left[0]).toBe(1);
    expect(right[0]).toBe(DIMS_PER_HAND + 1);
  });
});

describe("computeFit — khớp khung hình theo bounding box toàn chuỗi", () => {
  it("map dữ liệu vào trong hình vuông đơn vị (có lề)", () => {
    const frame = zeroFrame();
    // hai điểm góc: (0.2, 0.3) và (0.8, 0.7)
    frame[0] = 0.2; frame[1] = 0.3; frame[2] = 0.1;
    frame[3] = 0.8; frame[4] = 0.7; frame[5] = 0.1;
    const fit = computeFit([frame]);

    const [x1, y1] = fit.toUnit(0.2, 0.3);
    const [x2, y2] = fit.toUnit(0.8, 0.7);
    for (const v of [x1, y1, x2, y2]) {
      expect(v).toBeGreaterThanOrEqual(0.05);
      expect(v).toBeLessThanOrEqual(0.95);
    }
    expect(x2).toBeGreaterThan(x1);
    expect(y2).toBeGreaterThan(y1);
  });

  it("không sập với chuỗi rỗng hoàn toàn (mọi frame đều mất tay)", () => {
    const fit = computeFit([zeroFrame(), zeroFrame()]);
    const [x, y] = fit.toUnit(0.5, 0.5);
    expect(Number.isFinite(x)).toBe(true);
    expect(Number.isFinite(y)).toBe(true);
  });

  it("điểm 0 (mất landmark) không làm lệch bounding box", () => {
    const frame = zeroFrame();
    frame[0] = 0.6; frame[1] = 0.6; frame[2] = 0.01;
    frame[3] = 0.62; frame[4] = 0.62; frame[5] = 0.01;
    const fit = computeFit([frame]);
    // Nếu (0,0) bị tính vào bbox thì scale sẽ nhỏ hơn nhiều lần
    const [x] = fit.toUnit(0.6, 0.6);
    const [x2] = fit.toUnit(0.62, 0.62);
    expect(Math.abs(x2 - x)).toBeGreaterThan(0.1);
  });
});

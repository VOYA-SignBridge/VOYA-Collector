import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import Skeleton2DPlayer from "../Skeleton2DPlayer";
import { FRAME_DIM, DIMS_PER_HAND, type FramesData } from "../handData";

/** Stub CanvasRenderingContext2D ghi lại các lệnh vẽ để assert hành vi. */
function makeCtxStub() {
  return {
    fillRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillStyle: "",
    strokeStyle: "",
    lineWidth: 0,
    lineCap: "butt",
  };
}

const makeData = (sequence: number[][]): FramesData => ({
  class_uid: "c",
  session_id: "s",
  sample_uid: "u",
  frames: sequence.length,
  dim: FRAME_DIM,
  fps: 15,
  sequence,
});

describe("Skeleton2DPlayer — vẽ đúng những gì có trong dữ liệu", () => {
  let ctx: ReturnType<typeof makeCtxStub>;

  beforeEach(() => {
    ctx = makeCtxStub();
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
      ctx as unknown as CanvasRenderingContext2D,
    );
  });

  afterEach(() => vi.restoreAllMocks());

  it("frame chỉ có tay phải → vẽ đúng 21 điểm (không vẽ tay trái bị mất)", () => {
    const frame = new Array<number>(FRAME_DIM).fill(0);
    for (let i = DIMS_PER_HAND; i < FRAME_DIM; i++) frame[i] = 0.4 + (i % 7) * 0.01;
    render(<Skeleton2DPlayer data={makeData([frame])} frame={0} />);

    expect(ctx.fillRect).toHaveBeenCalled(); // nền
    expect(ctx.arc).toHaveBeenCalledTimes(21); // CHỈ tay phải
  });

  it("frame mất cả hai tay (toàn 0) → chỉ vẽ nền, không vẽ điểm nào", () => {
    const frame = new Array<number>(FRAME_DIM).fill(0);
    render(<Skeleton2DPlayer data={makeData([frame])} frame={0} />);

    expect(ctx.fillRect).toHaveBeenCalledTimes(1);
    expect(ctx.arc).not.toHaveBeenCalled();
    expect(ctx.stroke).not.toHaveBeenCalled();
  });

  it("cả hai tay đều có → 42 điểm + đủ 42 đường nối (21 connection × 2)", () => {
    const frame = new Array<number>(FRAME_DIM).fill(0).map((_, i) => 0.3 + (i % 11) * 0.02);
    render(<Skeleton2DPlayer data={makeData([frame])} frame={0} />);

    expect(ctx.arc).toHaveBeenCalledTimes(42);
    expect(ctx.stroke).toHaveBeenCalledTimes(42);
  });

  it("frame index vượt biên (ngoài sequence) → không crash, không vẽ", () => {
    const frame = new Array<number>(FRAME_DIM).fill(0.5);
    render(<Skeleton2DPlayer data={makeData([frame])} frame={99} />);
    expect(ctx.arc).not.toHaveBeenCalled();
  });

  it("render canvas với testid ổn định cho E2E", () => {
    render(<Skeleton2DPlayer data={makeData([[...new Array(FRAME_DIM).fill(0)]])} frame={0} />);
    expect(screen.getByTestId("skeleton-2d-canvas")).toBeInTheDocument();
  });
});

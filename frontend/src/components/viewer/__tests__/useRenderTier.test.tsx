import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useRenderTier, initialTier, ECO_MODE_KEY } from "../useRenderTier";

function setHardware(cores?: number, memGb?: number) {
  Object.defineProperty(navigator, "hardwareConcurrency", {
    value: cores,
    configurable: true,
  });
  Object.defineProperty(navigator, "deviceMemory", {
    value: memGb,
    configurable: true,
  });
}

describe("initialTier — chọn tầng khởi đầu theo phần cứng", () => {
  beforeEach(() => localStorage.clear());

  it("máy mạnh → 3D", () => {
    expect(initialTier({ hardwareConcurrency: 8, deviceMemory: 8 })).toBe("3d");
  });

  it("máy yếu (ít nhân / ít RAM) → 2D", () => {
    expect(initialTier({ hardwareConcurrency: 2, deviceMemory: 8 })).toBe("2d");
    expect(initialTier({ hardwareConcurrency: 8, deviceMemory: 2 })).toBe("2d");
  });

  it("Eco mode → video (server render)", () => {
    localStorage.setItem(ECO_MODE_KEY, "1");
    expect(initialTier({ hardwareConcurrency: 16, deviceMemory: 16 })).toBe("video");
  });
});

describe("useRenderTier — hạ cấp mềm khi FPS tụt kéo dài (máy nóng bị throttle)", () => {
  let now = 0;

  beforeEach(() => {
    localStorage.clear();
    setHardware(8, 8);
    now = 0;
    vi.spyOn(performance, "now").mockImplementation(() => now);
  });

  afterEach(() => vi.restoreAllMocks());

  /** Giả lập 1 giây render ở mức fps cho trước. */
  const simulateSecond = (reportFps: () => void, fps: number) => {
    for (let i = 0; i < fps; i++) {
      now += 1000 / fps;
      reportFps();
    }
  };

  it("FPS thấp (<24) liên tục 3 giây → hạ 3D xuống 2D, và không tự nâng lại", () => {
    const { result } = renderHook(() => useRenderTier());
    expect(result.current.tier).toBe("3d");

    act(() => {
      simulateSecond(result.current.reportFps, 10);
      simulateSecond(result.current.reportFps, 10);
    });
    // Mới 2 giây chậm — chưa hạ
    expect(result.current.tier).toBe("3d");

    act(() => {
      simulateSecond(result.current.reportFps, 10);
    });
    expect(result.current.tier).toBe("2d");
    expect(result.current.downgraded).toBe(true);

    // FPS phục hồi cũng KHÔNG tự nâng ngược lại (tránh dao động 3D↔2D)
    act(() => {
      simulateSecond(result.current.reportFps, 60);
      simulateSecond(result.current.reportFps, 60);
    });
    expect(result.current.tier).toBe("2d");
  });

  it("FPS chậm không liên tục (xen kẽ giây nhanh) → không hạ cấp", () => {
    const { result } = renderHook(() => useRenderTier());
    act(() => {
      simulateSecond(result.current.reportFps, 10);
      simulateSecond(result.current.reportFps, 10);
      simulateSecond(result.current.reportFps, 60); // reset chuỗi giây chậm
      simulateSecond(result.current.reportFps, 10);
      simulateSecond(result.current.reportFps, 10);
    });
    expect(result.current.tier).toBe("3d");
  });

  it("người dùng chọn thủ công sẽ thắng auto", () => {
    const { result } = renderHook(() => useRenderTier());
    act(() => result.current.setChoice("video"));
    expect(result.current.tier).toBe("video");
    act(() => result.current.setChoice("3d"));
    expect(result.current.tier).toBe("3d");
  });

  it("bật Eco lưu vào localStorage và chuyển sang video", () => {
    const { result } = renderHook(() => useRenderTier());
    act(() => result.current.setEco(true));
    expect(result.current.tier).toBe("video");
    expect(localStorage.getItem(ECO_MODE_KEY)).toBe("1");
  });
});

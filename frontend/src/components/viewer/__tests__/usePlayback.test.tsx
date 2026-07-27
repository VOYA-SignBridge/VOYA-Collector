import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { usePlayback } from "../usePlayback";

/**
 * Đồng hồ playback dùng requestAnimationFrame + performance.now.
 * Test điều khiển thời gian bằng fake timers (rAF polyfill trong
 * vitest.setup.ts chạy trên setTimeout nên advanceTimersByTime là đủ).
 */
describe("usePlayback — đồng hồ phát theo thời gian thực", () => {
  beforeEach(() => {
    vi.useFakeTimers({
      toFake: [
        "setTimeout",
        "clearTimeout",
        "requestAnimationFrame",
        "cancelAnimationFrame",
        "performance",
      ],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("tự phát: sau ~1 giây ở 15fps thì tiến ~15 khung hình", () => {
    const { result } = renderHook(() => usePlayback(60, 15));
    expect(result.current.playing).toBe(true);
    expect(result.current.frame).toBe(0);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    // 1s × 15fps = 15 khung (chấp nhận sai số lượng tử hóa rAF 16ms)
    expect(result.current.frame).toBeGreaterThanOrEqual(12);
    expect(result.current.frame).toBeLessThanOrEqual(16);
  });

  it("tốc độ hiển thị (rAF nhanh/chậm) KHÔNG đổi tốc độ phát — chỉ speed mới đổi", () => {
    const { result } = renderHook(() => usePlayback(600, 15));
    act(() => result.current.setSpeed(2));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    // 1s × 15fps × 2x = ~30 khung
    expect(result.current.frame).toBeGreaterThanOrEqual(25);
    expect(result.current.frame).toBeLessThanOrEqual(33);
  });

  it("phát hết thì lặp lại từ đầu (loop)", () => {
    const { result } = renderHook(() => usePlayback(30, 15)); // 2 giây/vòng
    act(() => {
      vi.advanceTimersByTime(2500);
    });
    // 2.5s × 15 = 37.5 khung → vượt 30 → quay vòng về ~7 (phải > 0 và < 15)
    expect(result.current.frame).toBeGreaterThan(0);
    expect(result.current.frame).toBeLessThan(15);
  });

  it("pause dừng hẳn; play tiếp tục từ vị trí cũ", () => {
    const { result } = renderHook(() => usePlayback(60, 15));
    act(() => {
      vi.advanceTimersByTime(500);
    });
    const before = result.current.frame;

    act(() => result.current.toggle()); // pause
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(result.current.frame).toBe(before);

    act(() => result.current.toggle()); // play
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(result.current.frame).toBeGreaterThan(before);
  });

  it("seek kẹp biên [0, frameCount-1] (Boundary Value Analysis)", () => {
    const { result } = renderHook(() => usePlayback(60, 15));
    act(() => result.current.seek(-10));
    expect(result.current.frame).toBe(0);
    act(() => result.current.seek(9999));
    expect(result.current.frame).toBe(59);
    act(() => result.current.seek(30.4));
    expect(result.current.frame).toBe(30);
  });

  it("đổi sequence (frameCount thay đổi) → tua về 0", () => {
    const { result, rerender } = renderHook(
      ({ count }) => usePlayback(count, 15),
      { initialProps: { count: 60 } },
    );
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.frame).toBeGreaterThan(0);

    rerender({ count: 90 });
    expect(result.current.frame).toBe(0);
    expect(result.current.frameRef.current).toBe(0);
  });

  it("frameCount = 0 hoặc 1 (session rỗng/1 khung) → không chạy vòng lặp, không crash", () => {
    const zero = renderHook(() => usePlayback(0, 15));
    const one = renderHook(() => usePlayback(1, 15));
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(zero.result.current.frame).toBe(0);
    expect(one.result.current.frame).toBe(0);
  });
});

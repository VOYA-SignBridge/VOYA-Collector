import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { secondsFromRetryError, useResendCountdown } from '../useResendCountdown';

/**
 * Đồng hồ chờ giữa hai lần xin mã.
 *
 * Ràng buộc thật sự quan trọng: con số phải tính từ **đồng hồ tường**, không
 * phải từ một bộ đếm giảm dần mỗi nhịp. Bộ đếm giảm dần sai trong đúng những
 * tình huống người dùng hay rơi vào — chuyển tab (trình duyệt hạ nhịp timer
 * của tab nền xuống một lần mỗi phút) và khoá màn hình (timer dừng hẳn). Test
 * dưới đây mô phỏng đúng chuyện đó: cho đồng hồ nhảy 40 giây nhưng chỉ phát ra
 * MỘT nhịp timer.
 */

describe('useResendCountdown', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('bắt đầu từ số giây được đưa vào', () => {
    const { result } = renderHook(() => useResendCountdown());
    act(() => result.current.startFrom(60));
    expect(result.current.secondsLeft).toBe(60);
  });

  it('bám đồng hồ tường, không đếm theo số nhịp timer', () => {
    const { result } = renderHook(() => useResendCountdown());
    act(() => result.current.startFrom(60));

    // Tab ngủ 40 giây rồi tỉnh lại: thời gian trôi thật 40 giây, nhưng chỉ có
    // một nhịp chạy. Bộ đếm giảm dần sẽ báo còn 59; đúng phải là 20.
    act(() => {
      vi.advanceTimersByTime(40_000);
    });
    expect(result.current.secondsLeft).toBe(20);
  });

  it('dừng ở 0 chứ không chạy xuống âm', () => {
    const { result } = renderHook(() => useResendCountdown());
    act(() => result.current.startFrom(5));
    act(() => {
      vi.advanceTimersByTime(30_000);
    });
    expect(result.current.secondsLeft).toBe(0);
  });

  it('số giây không hợp lệ thì coi như không phải chờ', () => {
    const { result } = renderHook(() => useResendCountdown());
    act(() => result.current.startFrom(0));
    expect(result.current.secondsLeft).toBe(0);
    act(() => result.current.startFrom(Number.NaN));
    expect(result.current.secondsLeft).toBe(0);
  });

  it('clear() mở khoá ngay', () => {
    const { result } = renderHook(() => useResendCountdown());
    act(() => result.current.startFrom(60));
    act(() => result.current.clear());
    expect(result.current.secondsLeft).toBe(0);
  });
});

describe('secondsFromRetryError', () => {
  const err = (detail: unknown) => ({ response: { status: 429, data: { detail } } });

  it('bóc được con số máy chủ nêu trong câu chữ', () => {
    expect(secondsFromRetryError(err('vui lòng đợi 47 giây trước khi yêu cầu mã mới')).valueOf())
      .toBe(47);
  });

  it('không bóc được thì trả null, không đoán bừa', () => {
    // Đoán một con số ở đây sẽ khoá nút lâu hơn hoặc ngắn hơn thực tế; cả hai
    // đều tệ hơn là để người gọi dùng thời gian chờ mặc định.
    expect(secondsFromRetryError(err('quá nhiều yêu cầu'))).toBeNull();
    expect(secondsFromRetryError(err([{ msg: 'field required' }]))).toBeNull();
    expect(secondsFromRetryError({})).toBeNull();
    expect(secondsFromRetryError(null)).toBeNull();
  });
});

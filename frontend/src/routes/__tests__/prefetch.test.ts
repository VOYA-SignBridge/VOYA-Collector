import { describe, it, expect, vi, beforeEach } from 'vitest';
import { prefetchProps, prefetchRoute } from '../prefetch';

/**
 * Nạp trước tuyến.
 *
 * Hai tính chất được ghim, và cái thứ hai là cái dễ hỏng khi có người "dọn
 * dẹp" tệp này về sau:
 *
 *   1. Một tuyến lạ KHÔNG được ném lỗi. Bảng tra cố ý không đầy đủ.
 *   2. Lỗi nạp bị **nuốt**. Đây là việc đầu cơ — người dùng chưa yêu cầu gì.
 *      Để nó nổi lên thành `unhandledrejection` là biến một tối ưu vô hình
 *      thành một hộp lỗi trên màn hình của người chỉ vừa rê chuột qua.
 */

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('prefetchRoute', () => {
  it('không ném với tuyến không có trong bảng', () => {
    expect(() => prefetchRoute('/khong-ton-tai')).not.toThrow();
  });

  it('không ném với chuỗi rỗng', () => {
    expect(() => prefetchRoute('')).not.toThrow();
  });

  it('gọi hai lần cùng một tuyến vẫn an toàn', () => {
    expect(() => {
      prefetchRoute('/labels');
      prefetchRoute('/labels');
    }).not.toThrow();
  });
});

describe('prefetchProps', () => {
  it('phủ cả chuột, bàn phím và cảm ứng', () => {
    /** Thiếu `onFocus` thì người dùng bàn phím — nhóm ít được hưởng lợi từ
     * những tối ưu kiểu này nhất — không được nạp trước lần nào. */
    const props = prefetchProps('/upload');
    expect(typeof props.onMouseEnter).toBe('function');
    expect(typeof props.onFocus).toBe('function');
    expect(typeof props.onTouchStart).toBe('function');
  });

  it('kích hoạt được mà không ném', () => {
    const props = prefetchProps('/admin/tenants');
    expect(() => props.onMouseEnter()).not.toThrow();
  });
});

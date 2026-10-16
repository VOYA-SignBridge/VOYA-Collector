/**
 * `toast` từ `useToast()` phải giữ NGUYÊN danh tính khi danh sách toast đổi.
 *
 * Đây là bất biến mà 23 chỗ trên 7 trang đang dựa vào khi viết
 * `useCallback(..., [toast])`. Mất nó là vòng gọi API (TEN-02).
 */
import { act, renderHook } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ReactNode } from "react";

import { ToastProvider, useToast } from "../useToast";

const wrapper = ({ children }: { children: ReactNode }) => (
  <ToastProvider>{children}</ToastProvider>
);

describe("useToast — danh tính ổn định", () => {
  it("thêm một toast KHÔNG đổi object `toast`", () => {
    const { result } = renderHook(() => useToast(), { wrapper });
    const before = result.current.toast;

    act(() => result.current.toast.error("lỗi 1"));

    expect(result.current.toasts).toHaveLength(1);
    expect(result.current.toast).toBe(before);
  });

  it("render lại nhiều lần vẫn cùng một `toast`", () => {
    const { result, rerender } = renderHook(() => useToast(), { wrapper });
    const first = result.current.toast;
    rerender();
    rerender();
    expect(result.current.toast).toBe(first);
  });
});

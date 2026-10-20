import { renderHook, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";

/**
 * Huy hiệu là TRẠNG THÁI, pop-up là SỰ KIỆN — và trộn hai thứ đó là cách hỏng
 * quen thuộc nhất của loại tính năng này.
 *
 * Ba tính chất được ghim ở đây, cả ba đều là "im lặng khi phải im":
 *
 *   1. Lần đo ĐẦU không nổ pop-up nào. Mở console lên mà nhận năm cái pop-up
 *      cho năm việc có từ hôm qua là báo sai — không có gì "vừa xảy ra".
 *   2. Con số GIỮ NGUYÊN không nổ pop-up. Nếu nổ thì mỗi 30 giây lại một cái
 *      y hệt, và người ta tắt hết thông báo trong hai ngày.
 *   3. Con số GIẢM không nổ pop-up. Việc vừa được làm xong không phải tin cần
 *      cắt ngang ai.
 */

const get = vi.fn();
const info = vi.fn();

vi.mock("../../api/axiosClient", () => ({
  default: { get: (...args: unknown[]) => get(...args) },
}));

vi.mock("../useToast", () => ({
  useToast: () => ({ toast: { info, success: vi.fn(), error: vi.fn(), warning: vi.fn() } }),
}));

import { useAdminAttention } from "../useAdminAttention";

const reply = (counts: Record<string, number>) => ({ data: { counts } });

describe("useAdminAttention — huy hiệu và pop-up", () => {
  beforeEach(() => {
    get.mockReset();
    info.mockReset();
    // jsdom báo `navigator.language === "en-US"`, nên nếu không ghim thì mọi
    // khẳng định về chữ tiếng Việt chạy trong ngôn ngữ tiếng Anh và đỏ vì một
    // lý do không liên quan gì tới điều đang được kiểm.
    window.localStorage.setItem("voya.lang", "vi");
  });

  it("lần đo đầu tiên KHÔNG nổ pop-up nào, dù có việc đang chờ", async () => {
    get.mockResolvedValue(reply({ "/admin/support": 3, "/admin/legal": 1 }));

    const { result } = renderHook(() => useAdminAttention());

    await waitFor(() => expect(result.current.counts["/admin/support"]).toBe(3));
    expect(info).not.toHaveBeenCalled();
  });

  it("nổ pop-up khi con số TĂNG, và nói rõ tăng bao nhiêu", async () => {
    get.mockResolvedValueOnce(reply({ "/admin/support": 1 }))
       .mockResolvedValueOnce(reply({ "/admin/support": 4 }));

    const { result } = renderHook(() => useAdminAttention());
    await waitFor(() => expect(result.current.counts["/admin/support"]).toBe(1));

    await result.current.refresh();

    await waitFor(() => expect(info).toHaveBeenCalledTimes(1));
    const msg = info.mock.calls[0][0] as string;
    // "3 việc mới", không phải "4" — người trực cần biết cái gì VỪA tới, chứ
    // tổng thì huy hiệu đã nói rồi.
    expect(msg).toContain("3");
    expect(msg).toContain("Hỗ trợ");
  });

  it("con số giữ nguyên thì im", async () => {
    get.mockResolvedValue(reply({ "/admin/support": 2 }));

    const { result } = renderHook(() => useAdminAttention());
    await waitFor(() => expect(result.current.counts["/admin/support"]).toBe(2));

    await result.current.refresh();
    await result.current.refresh();

    expect(info).not.toHaveBeenCalled();
  });

  it("con số giảm thì im — việc vừa xong không phải tin cắt ngang", async () => {
    get.mockResolvedValueOnce(reply({ "/admin/support": 5 }))
       .mockResolvedValueOnce(reply({ "/admin/support": 0 }));

    const { result } = renderHook(() => useAdminAttention());
    await waitFor(() => expect(result.current.counts["/admin/support"]).toBe(5));

    await result.current.refresh();

    await waitFor(() => expect(result.current.counts["/admin/support"]).toBe(0));
    expect(info).not.toHaveBeenCalled();
  });

  it("một lượt hỏi hụt KHÔNG xoá trắng huy hiệu đang có", async () => {
    // Mất mạng chốc lát, token vừa xoay: con số cũ vẫn đúng hơn là con số 0.
    // Về 0 nghĩa là "đã xong hết", và đó là một lời nói dối.
    get.mockResolvedValueOnce(reply({ "/admin/support": 7 }))
       .mockRejectedValueOnce(new Error("network"));

    const { result } = renderHook(() => useAdminAttention());
    await waitFor(() => expect(result.current.counts["/admin/support"]).toBe(7));

    await result.current.refresh();

    expect(result.current.counts["/admin/support"]).toBe(7);
    expect(info).not.toHaveBeenCalled();
  });

  it("không gọi máy chủ khi bị tắt", async () => {
    get.mockResolvedValue(reply({}));
    renderHook(() => useAdminAttention(false));
    expect(get).not.toHaveBeenCalled();
  });
});

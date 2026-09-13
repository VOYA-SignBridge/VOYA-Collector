/**
 * TEN-02 — vòng gọi API khi tải danh sách tổ chức lỗi.
 *
 * Tệp test chính của trang giả lập `useToast` bằng một object mới mỗi lần gọi
 * — tức là nó KHÔNG thể thấy lỗi này, và cũng không thấy được bản sửa. Ở đây
 * dùng `ToastProvider` THẬT và đếm số lần API bị gọi, đúng như điều kiện
 * nghiệm thu của kế hoạch UX 13/09: "không lặp gọi API do render".
 *
 * Cơ chế lỗi (trước bản sửa `useToast`):
 *   fetchTenants lỗi → toast.error → toasts đổi → context đổi → `toast` là
 *   object mới → `loadTenants` (deps [toast]) đổi → effect chạy lại →
 *   fetchTenants lỗi → …
 */
import "@testing-library/jest-dom/vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../api/tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../api/tenants")>()),
  fetchTenants: vi.fn(),
  fetchMembers: vi.fn(),
  fetchInvitations: vi.fn(),
  fetchExports: vi.fn(),
  fetchPurgePreview: vi.fn(),
}));

import AdminTenantsPage from "../AdminTenantsPage";
import { ToastProvider } from "../../hooks/useToast";
import { fetchTenants } from "../../api/tenants";

beforeEach(() => {
  vi.clearAllMocks();
});

describe("AdminTenantsPage + ToastProvider thật — TEN-02", () => {
  it("API lỗi thì gọi ĐÚNG MỘT lần, không lặp theo toast", async () => {
    (fetchTenants as any).mockRejectedValue(new Error("network down"));

    render(
      <ToastProvider>
        <AdminTenantsPage />
      </ToastProvider>,
    );

    await waitFor(() => expect(fetchTenants).toHaveBeenCalledTimes(1));
    // Cho vòng lặp (nếu còn) đủ thời gian để lộ ra: vài vòng render + effect.
    await new Promise((r) => setTimeout(r, 150));
    expect(fetchTenants).toHaveBeenCalledTimes(1);
    // Và đúng MỘT thông báo lỗi, không phải một hàng dài.
    const alerts = screen.queryAllByText(/Không tải được danh sách tổ chức/);
    expect(alerts.length).toBeLessThanOrEqual(1);
  });
});

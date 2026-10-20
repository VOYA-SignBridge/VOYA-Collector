/**
 * `OrgLayout` — TEN-01: đường dẫn `/org/:tenantId` chỉ là nhãn; phạm vi thật
 * nằm ở `users.active_tenant_id`. Vỏ phải đối chiếu hai thứ trước khi dựng
 * trang con, vì một người thuộc cả A và B mở liên kết A trong khi máy chủ ở B
 * sẽ ghi vào B dưới tiêu đề A — không tầng nào báo.
 */
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/tenants")>()),
  listMyTenants: vi.fn(),
  fetchMyTenant: vi.fn(),
  switchTenant: vi.fn(),
}));

import OrgLayout from "../OrgLayout";
import { I18nProvider } from "../../../i18n";
import { fetchMyTenant, listMyTenants, switchTenant } from "../../../api/tenants";

const A = { tenant_id: "truong-a", display_name: "Trường A", tenant_type: "ORGANIZATION", role: "editor", joined_at: null, is_home: true };
const B = { tenant_id: "truong-b", display_name: "Trường B", tenant_type: "ORGANIZATION", role: "editor", joined_at: null, is_home: false };

function show(path = "/org/truong-a") {
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/org/:tenantId" element={<OrgLayout />}>
            <Route index element={<p>TRANG CON</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  (listMyTenants as any).mockResolvedValue([A, B]);
});

describe("OrgLayout — đối chiếu ngữ cảnh máy chủ (TEN-01)", () => {
  it("URL khớp tổ chức máy chủ đang dùng → dựng trang con", async () => {
    (fetchMyTenant as any).mockResolvedValue({ tenant_id: "truong-a" });
    show();
    expect(await screen.findByText("TRANG CON")).toBeInTheDocument();
    expect(screen.queryByTestId("org-context-mismatch")).toBeNull();
  });

  it("URL là A nhưng máy chủ đang ở B → CHẶN trang con, nêu rõ dữ liệu sẽ vào B", async () => {
    (fetchMyTenant as any).mockResolvedValue({ tenant_id: "truong-b" });
    show("/org/truong-a");

    const panel = await screen.findByTestId("org-context-mismatch");
    expect(panel).toHaveTextContent("Trường A");
    expect(panel).toHaveTextContent("Trường B");
    expect(screen.queryByText("TRANG CON")).toBeNull();
    // Membership A hợp lệ — trước bản sửa chính trường hợp này im lặng.
    expect(screen.getByRole("button", { name: /Chuyển sang Trường A/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ở lại Trường B/ })).toHaveAttribute("href", "/org/truong-b");
  });

  it("bấm 'Chuyển sang A' gọi switchTenant với ĐÚNG tổ chức trên liên kết", async () => {
    (fetchMyTenant as any).mockResolvedValue({ tenant_id: "truong-b" });
    (switchTenant as any).mockResolvedValue({ tenant_id: "truong-a", is_home: true });
    const reload = vi.fn();
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { ...window.location, reload },
    });
    show("/org/truong-a");

    fireEvent.click(await screen.findByRole("button", { name: /Chuyển sang Trường A/ }));
    await waitFor(() => expect(switchTenant).toHaveBeenCalledWith("truong-a"));
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  it("không xác nhận được ngữ cảnh (API /me lỗi) → chặn, có 'Thử lại'", async () => {
    (fetchMyTenant as any).mockRejectedValueOnce(new Error("offline"));
    show();
    expect(await screen.findByTestId("org-context-unverified")).toBeInTheDocument();
    expect(screen.queryByText("TRANG CON")).toBeNull();

    (fetchMyTenant as any).mockResolvedValue({ tenant_id: "truong-a" });
    fireEvent.click(screen.getByRole("button", { name: "Thử lại" }));
    expect(await screen.findByText("TRANG CON")).toBeInTheDocument();
  });

  it("không phải thành viên của tổ chức trên liên kết → không có nút chuyển", async () => {
    (listMyTenants as any).mockResolvedValue([B]);
    (fetchMyTenant as any).mockResolvedValue({ tenant_id: "truong-b" });
    show("/org/truong-a");
    const panel = await screen.findByTestId("org-context-mismatch");
    expect(panel).toHaveTextContent("không phải thành viên");
    expect(screen.queryByRole("button", { name: /Chuyển sang/ })).toBeNull();
  });
});

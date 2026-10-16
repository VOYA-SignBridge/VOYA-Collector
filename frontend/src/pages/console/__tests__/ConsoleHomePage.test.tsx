/**
 * Tổng quan tổ chức — người mở trang không nhất thiết là quản trị viên.
 * Ba việc chính đứng đầu, hướng dẫn 1-2-3 nói bằng chữ thường, thuật ngữ
 * "Workspace/Project" không xuất hiện.
 */
import "@testing-library/jest-dom/vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/billing", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/billing")>()),
  fetchBillingSummary: vi.fn(),
}));
vi.mock("../../../api/workspaces", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/workspaces")>()),
  getScopeSummary: vi.fn(),
}));
vi.mock("../../../api/tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/tenants")>()),
  fetchMyTenant: vi.fn(),
}));

import ConsoleHomePage from "../ConsoleHomePage";
import { I18nProvider } from "../../../i18n";
import { fetchBillingSummary } from "../../../api/billing";
import { getScopeSummary } from "../../../api/workspaces";
import { fetchMyTenant } from "../../../api/tenants";

function show() {
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={["/org/truong-a"]}>
        <Routes>
          <Route path="/org/:tenantId" element={<ConsoleHomePage />} />
        </Routes>
      </MemoryRouter>
    </I18nProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchBillingSummary).mockResolvedValue({ plan: { display_name: "Gói Plus" }, usage: {} } as never);
  vi.mocked(getScopeSummary).mockResolvedValue({ workspaces: 2, projects: 3, workspace_members: 1, project_members: 0 } as never);
  vi.mocked(fetchMyTenant).mockResolvedValue({ tenant_id: "truong-a", display_name: "Trường A", my_role: "editor" } as never);
});

describe("ConsoleHomePage", () => {
  it("ba việc chính là liên kết tương đối tới upload / realtime / labels", async () => {
    show();
    expect(await screen.findByRole("link", { name: /Đóng góp dữ liệu/ })).toHaveAttribute("href", "/org/truong-a/upload");
    expect(screen.getByRole("link", { name: /Nhận dạng thử/ })).toHaveAttribute("href", "/org/truong-a/realtime");
    expect(screen.getByRole("link", { name: /Thư viện nhãn/ })).toHaveAttribute("href", "/org/truong-a/labels");
  });

  it("hướng dẫn bắt đầu: tên tổ chức, vai và hệ quả của vai, bằng chữ thường", async () => {
    show();
    const guide = await screen.findByTestId("getting-started");
    expect(guide).toHaveTextContent("Trường A");
    expect(guide).toHaveTextContent("Biên tập viên");
    expect(guide).toHaveTextContent(/Tạo và sửa nhãn/);
    expect(screen.queryByText(/Workspace/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Project\b/)).not.toBeInTheDocument();
    expect(screen.getByText("Nhóm & lớp")).toBeInTheDocument();
  });

  it("gói cước lỗi thì ba việc chính và hướng dẫn vẫn còn", async () => {
    vi.mocked(fetchBillingSummary).mockRejectedValue(new Error("403"));
    vi.mocked(getScopeSummary).mockRejectedValue(new Error("403"));
    show();
    expect(await screen.findByRole("link", { name: /Đóng góp dữ liệu/ })).toBeInTheDocument();
    expect(screen.getByTestId("getting-started")).toHaveTextContent("Trường A");
    expect(screen.queryByText("Gói dịch vụ & hạn mức")).not.toBeInTheDocument();
  });
});

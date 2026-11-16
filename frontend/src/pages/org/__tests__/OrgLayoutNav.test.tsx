/**
 * Thanh bên của MỘT tổ chức: ba công cụ dữ liệu (Quản lý dữ liệu, Người ký, Hàng
 * đợi xử lý) chỉ là việc làm thỉnh thoảng, nên gập lại thành một nhóm "DỮ LIỆU"
 * thay vì nằm ngang hàng với việc hằng ngày — và tự mở khi đang ở trong một mục.
 */
import "@testing-library/jest-dom/vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({ user: { is_admin: true } as { is_admin: boolean } | null }));
vi.mock("../../../hooks/useAuth", () => ({ useAuth: () => ({ user: auth.user }) }));

vi.mock("../../../api/tenants", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../api/tenants")>()),
  listMyTenants: vi.fn(),
  fetchMyTenant: vi.fn(),
  switchTenant: vi.fn(),
}));

import OrgLayout from "../OrgLayout";
import { I18nProvider } from "../../../i18n";
import { fetchMyTenant, listMyTenants } from "../../../api/tenants";

const A = { tenant_id: "truong-a", display_name: "Trường A", tenant_type: "ORGANIZATION", role: "admin", joined_at: null, is_home: true };

function show(path: string) {
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/org/:tenantId" element={<OrgLayout />}>
            <Route index element={<p>TRANG CON</p>} />
            <Route path="data" element={<p>TRANG DU LIEU</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </I18nProvider>,
  );
}

const dataGroup = () => screen.getByText("DỮ LIỆU").closest("details") as HTMLDetailsElement;

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = { is_admin: true };
  (listMyTenants as any).mockResolvedValue([A]);
  (fetchMyTenant as any).mockResolvedValue({ tenant_id: "truong-a" });
});

describe("OrgLayout — nhóm DỮ LIỆU gập lại", () => {
  it("quản trị: nhóm có mặt nhưng đang gập khi ở trang tổng quan", async () => {
    show("/org/truong-a");
    await screen.findByText("TRANG CON");
    expect(dataGroup().open).toBe(false);
  });

  it("đang ở một mục của nhóm thì nhóm tự mở", async () => {
    show("/org/truong-a/data");
    await screen.findByText("TRANG DU LIEU");
    expect(dataGroup().open).toBe(true);
    expect(within(dataGroup()).getByRole("link", { name: "Quản lý dữ liệu" })).toBeInTheDocument();
  });

  it("việc hằng ngày vẫn hiện sẵn, không nằm trong nhóm gập", async () => {
    show("/org/truong-a");
    await screen.findByText("TRANG CON");
    expect(screen.getByRole("link", { name: "Đóng góp dữ liệu" }).closest("details")).toBeNull();
    expect(screen.getByRole("link", { name: "Thành viên" }).closest("details")).toBeNull();
  });

  it("người không có quyền: không có nhóm rỗng nào", async () => {
    auth.user = { is_admin: false };
    show("/org/truong-a");
    await screen.findByText("TRANG CON");
    expect(screen.queryByText("DỮ LIỆU")).not.toBeInTheDocument();
  });
});

import "@testing-library/jest-dom/vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import CommunitySwitchHint from "../CommunitySwitchHint";
import * as tenants from "../../api/tenants";

vi.mock("../../api/tenants", () => ({
  fetchMyTenant: vi.fn(),
  listMyTenants: vi.fn(),
  switchTenant: vi.fn(),
}));

const MINE = [
  { tenant_id: "truong-b", display_name: "Trường B", tenant_type: "ORGANIZATION", role: "admin", joined_at: null, is_home: true },
  { tenant_id: "default", display_name: "VOYA", tenant_type: "COMMUNITY", role: null, joined_at: null, is_home: false },
];

describe("CommunitySwitchHint — gợi ý chuyển sang kho cộng đồng", () => {
  beforeEach(() => vi.clearAllMocks());

  it("đang ở tổ chức riêng + là thành viên cộng đồng → hiện nút chuyển", async () => {
    vi.mocked(tenants.fetchMyTenant).mockResolvedValue({ tenant_id: "truong-b", display_name: "Trường B" } as never);
    vi.mocked(tenants.listMyTenants).mockResolvedValue(MINE as never);
    vi.mocked(tenants.switchTenant).mockResolvedValue({ tenant_id: "default", is_home: false });
    const reload = vi.fn();
    Object.defineProperty(window, "location", { value: { ...window.location, reload }, writable: true });

    render(<CommunitySwitchHint reason="Nhãn này không có trong tổ chức của bạn" />);
    const btn = await screen.findByRole("button", { name: "Chuyển sang VOYA" });
    expect(screen.getByTestId("community-switch-hint").textContent).toContain("Bạn đang làm việc tại Trường B");
    fireEvent.click(btn);
    await waitFor(() => expect(tenants.switchTenant).toHaveBeenCalledWith("default"));
    await waitFor(() => expect(reload).toHaveBeenCalled());
  });

  it("đã ở cộng đồng → không hiện gì", async () => {
    vi.mocked(tenants.fetchMyTenant).mockResolvedValue({ tenant_id: "default", display_name: "VOYA" } as never);
    vi.mocked(tenants.listMyTenants).mockResolvedValue(MINE as never);
    render(<CommunitySwitchHint />);
    await waitFor(() => expect(tenants.listMyTenants).toHaveBeenCalled());
    expect(screen.queryByTestId("community-switch-hint")).not.toBeInTheDocument();
  });

  it("không phải thành viên cộng đồng → không hiện gì", async () => {
    vi.mocked(tenants.fetchMyTenant).mockResolvedValue({ tenant_id: "truong-b", display_name: "Trường B" } as never);
    vi.mocked(tenants.listMyTenants).mockResolvedValue([MINE[0]] as never);
    render(<CommunitySwitchHint />);
    await waitFor(() => expect(tenants.listMyTenants).toHaveBeenCalled());
    expect(screen.queryByTestId("community-switch-hint")).not.toBeInTheDocument();
  });
});

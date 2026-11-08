import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, within, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Layout from "../Layout";
import { fetchQueue } from "../../api/moderation";

const state = vi.hoisted(() => ({ user: { id: "user-1", username: "Tester", can_moderate: false, tenant_admin: false } }));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ user: state.user }), hasSessionHint: () => true }));
vi.mock("../../hooks/usePresence", () => ({ usePresence: vi.fn() }));
vi.mock("../../hooks/useIdleLogout", () => ({ useIdleLogout: vi.fn() }));
vi.mock("../../api/auth", () => ({ logout: vi.fn(), isTenantAdmin: (user: typeof state.user) => user.tenant_admin }));
vi.mock("../../api/axiosClient", () => ({ clearAuthToken: vi.fn() }));
vi.mock("../../api/moderation", () => ({ fetchQueue: vi.fn().mockResolvedValue({ count: 4 }) }));
vi.mock("../../routes/prefetch", () => ({ prefetchProps: () => ({}) }));
vi.mock("../../i18n", () => ({ useI18n: () => ({ t: (value: string) => value }) }));
vi.mock("../NotificationBell", () => ({ default: () => null }));
vi.mock("../WorkingContextChip", () => ({ default: () => null }));
vi.mock("../LanguageSwitcher", () => ({ default: () => null }));
vi.mock("../WarningBanner", () => ({ default: () => null }));
vi.mock("../Footer", () => ({ default: () => null }));

function openAt(path = "/") {
  render(<MemoryRouter initialEntries={[path]}><Layout><p>Content</p></Layout></MemoryRouter>);
  fireEvent.click(screen.getByRole("button", { name: "Mở hoặc đóng thanh điều hướng" }));
  return screen.getByRole("navigation", { name: "Điều hướng chính" });
}

describe("Layout navigation", () => {
  beforeEach(() => {
    state.user.can_moderate = false;
    state.user.tenant_admin = false;
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1280 });
  });
  afterEach(cleanup);

  it("groups links without removing ordinary user destinations", () => {
    const nav = openAt();
    expect(within(nav).getAllByRole("link")).toHaveLength(10);
    expect(within(nav).getByRole("region", { name: "Dữ liệu" })).toBeInTheDocument();
    expect(within(nav).getByRole("region", { name: "Công cụ" })).toBeInTheDocument();
    expect(within(nav).getByRole("region", { name: "Cá nhân" })).toBeInTheDocument();
    expect(within(nav).getByRole("link", { name: "Tổ chức" })).toHaveAttribute("href", "/settings/organization");
    expect(within(nav).queryByRole("link", { name: /Kiểm duyệt/ })).not.toBeInTheDocument();
  });

  it.each(["/settings/support", "/settings/organization", "/settings/profile"])("has exactly one current link on %s", (path) => {
    const nav = openAt(path);
    const active = within(nav).getAllByRole("link").filter((link) => link.getAttribute("aria-current") === "page");
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveAttribute("href", path === "/settings/profile" ? "/settings" : path);
  });

  it("retains moderator badge and tenant admin entry", async () => {
    state.user.can_moderate = true;
    state.user.tenant_admin = true;
    const nav = openAt();
    await waitFor(() => expect(fetchQueue).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.getByRole("link", { name: /Kiểm duyệt/ }).textContent).toBe("Kiểm duyệt4"));
    expect(within(nav).getByRole("link", { name: "Tổ chức" })).toHaveAttribute("href", "/org");
  });

  it("keeps desktop navigation open, closes with Escape and restores focus", () => {
    const nav = openAt();
    fireEvent.click(within(nav).getByRole("link", { name: "Thư viện nhãn" }));
    const toggle = screen.getByRole("button", { name: "Mở hoặc đóng thanh điều hướng" });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(toggle).toHaveFocus();
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(document.getElementById("main-sidebar")).toHaveAttribute("inert");
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
  });

  it("focuses the mobile drawer and closes after choosing a destination", () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    const nav = openAt();
    expect(screen.getByRole("button", { name: "Đóng thanh bên" })).toHaveFocus();
    fireEvent.click(within(nav).getByRole("link", { name: "Đóng góp dữ liệu" }));
    expect(screen.getByRole("button", { name: "Mở hoặc đóng thanh điều hướng" })).toHaveAttribute("aria-expanded", "false");
  });
});

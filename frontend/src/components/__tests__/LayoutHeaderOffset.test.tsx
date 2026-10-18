import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Layout from "../Layout";

// Từ `lg` thanh bên là một cột static rộng `lg:w-64` (z-50) nằm TRÊN header
// `fixed` (z-40). Header trải từ `left-0` thì nút ☰ và tên trang nằm dưới cột ấy
// (18/10/2026: chỉ còn chữ "je" lòi ra cạnh thanh bên). jsdom không tính media
// query nên kiểm class: mở thì header lùi đúng `lg:left-64`, đóng thì không.

const state = vi.hoisted(() => ({ user: { id: "user-1", username: "Tester", can_moderate: false, tenant_admin: false } }));
vi.mock("../../contexts/AuthContext", () => ({ useAuth: () => ({ user: state.user }), hasSessionHint: () => true }));
vi.mock("../../hooks/usePresence", () => ({ usePresence: vi.fn() }));
vi.mock("../../hooks/useIdleLogout", () => ({ useIdleLogout: vi.fn() }));
vi.mock("../../api/auth", () => ({ logout: vi.fn(), isTenantAdmin: () => false }));
vi.mock("../../api/axiosClient", () => ({ clearAuthToken: vi.fn() }));
vi.mock("../../api/moderation", () => ({ fetchQueue: vi.fn().mockResolvedValue({ count: 0 }) }));
vi.mock("../../routes/prefetch", () => ({ prefetchProps: () => ({}) }));
vi.mock("../../i18n", () => ({ useI18n: () => ({ t: (value: string) => value }) }));
vi.mock("../NotificationBell", () => ({ default: () => null }));
vi.mock("../WorkingContextChip", () => ({ default: () => null }));
vi.mock("../LanguageSwitcher", () => ({ default: () => null }));
vi.mock("../WarningBanner", () => ({ default: () => null }));
vi.mock("../Footer", () => ({ default: () => null }));

describe("Layout header vs. docked sidebar", () => {
  afterEach(cleanup);

  it("starts the header after the sidebar column only while the sidebar is open", () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1280 });
    render(<MemoryRouter><Layout><p>Content</p></Layout></MemoryRouter>);
    const header = screen.getByRole("banner");
    const toggle = screen.getByRole("button", { name: "Mở hoặc đóng thanh điều hướng" });

    expect(header).toHaveClass("left-0");
    expect(header).not.toHaveClass("lg:left-64");

    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(header).toHaveClass("lg:left-64");
    // Phải trùng bề rộng cột thanh bên, nếu không header lại hở hoặc bị đè một khúc.
    expect(document.getElementById("main-sidebar")).toHaveClass("lg:w-64");

    fireEvent.click(toggle);
    expect(header).not.toHaveClass("lg:left-64");
  });

  it("keeps the sidebar content stuck to the viewport while the page scrolls", () => {
    // Nội dung thanh bên là `lg:sticky`; một tổ tiên `overflow-hidden` biến chính
    // nó thành vùng cuộn của sticky, nên kéo trang xuống thì nội dung trôi mất,
    // chỉ còn nền (18/10/2026). Chỉ được cắt tràn khi thanh bên đã thu về 0.
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 1280 });
    render(<MemoryRouter><Layout><p>Content</p></Layout></MemoryRouter>);
    const aside = document.getElementById("main-sidebar");
    fireEvent.click(screen.getByRole("button", { name: "Mở hoặc đóng thanh điều hướng" }));
    expect(aside).toHaveClass("lg:overflow-visible");
  });

  it("does not put sign-out in the sidebar", () => {
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    render(<MemoryRouter><Layout><p>Content</p></Layout></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "Mở hoặc đóng thanh điều hướng" }));
    const aside = document.getElementById("main-sidebar") as HTMLElement;
    expect(within(aside).queryByRole("button", { name: "Đăng xuất" })).toBeNull();
    // …nhưng màn hẹp vẫn còn một lối đăng xuất (ở header).
    expect(screen.getAllByRole("button", { name: "Đăng xuất" }).length).toBeGreaterThan(0);
  });
});

/**
 * `SettingsLayout` — trung tâm Cài đặt.
 *
 * Hai tính chất được ghim:
 *
 * 1. **Mỗi mục là một route thật.** `/settings/security` phải chia sẻ được,
 *    đánh dấu được, quay-lại được — và thông báo bảo mật trỏ tới trang này
 *    bằng đường dẫn. Một tab lưu trong `useState` làm hỏng cả bốn.
 * 2. **Tích hợp chỉ hiện với quản trị viên.** Máy chủ đòi vai biên tập; hiện
 *    mục đó cho người không có quyền là mời họ bấm vào một trang chắc chắn
 *    403 — một ngõ cụt có sẵn nhãn.
 */

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import SettingsLayout from "../SettingsLayout";
import { I18nProvider } from "../../../i18n";

const mockUser = vi.hoisted(() => ({ current: null as { is_admin: boolean } | null }));

vi.mock("../../../contexts/AuthContext", () => ({
  useAuth: () => ({ user: mockUser.current }),
}));

function renderSettings(isAdmin: boolean, lang: "vi" | "en" = "vi") {
  mockUser.current = { is_admin: isAdmin };
  window.localStorage.setItem("voya.lang", lang);
  return render(
    <MemoryRouter initialEntries={["/settings/account"]}>
      <I18nProvider>
        <SettingsLayout />
      </I18nProvider>
    </MemoryRouter>,
  );
}

describe("SettingsLayout", () => {
  it("mỗi mục là một liên kết có href, không phải một tab trong state", () => {
    renderSettings(true);
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/settings/security");
    expect(hrefs).toContain("/settings/contact");
    expect(hrefs).toContain("/settings/support");
    expect(hrefs).toContain("/settings/language");
  });

  it("gom đủ 8 mục cho quản trị viên", () => {
    renderSettings(true);
    expect(screen.getAllByRole("link")).toHaveLength(8);
  });

  it("giấu Tích hợp với người dùng thường — trang đó chắc chắn 403", () => {
    renderSettings(false);
    expect(screen.queryByText("Tích hợp")).not.toBeInTheDocument();
    expect(screen.getAllByRole("link")).toHaveLength(7);
  });

  it("dịch nhãn mục sang tiếng Anh", () => {
    renderSettings(false, "en");
    expect(screen.getByText("Security")).toBeInTheDocument();
    expect(screen.queryByText("Bảo mật")).not.toBeInTheDocument();
  });
});

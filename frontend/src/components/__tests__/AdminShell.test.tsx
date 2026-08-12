/**
 * `AdminShell` — vỏ của console quản trị.
 *
 * Ba tính chất được ghim ở đây, và cả ba đều là *yêu cầu của người dùng* chứ
 * không phải chi tiết cài đặt:
 *
 * 1. Console phải trông KHÁC hẳn ứng dụng thường (nền tối + phù hiệu), nếu
 *    không thì việc tách chế độ chẳng để làm gì.
 * 2. Phải có ĐÚNG MỘT lối ra, luôn nhìn thấy. Vào một chế độ mà không thấy
 *    đường ra là cách nhanh nhất khiến người ta ngại bấm vào.
 * 3. Vỏ này KHÔNG phải hàng rào quyền. Bài test cuối nói thẳng điều đó ra để
 *    không ai đọc mã rồi tưởng đã có kiểm soát truy cập ở đây.
 */

import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import AdminShell from "../AdminShell";
import { I18nProvider } from "../../i18n";

const renderShell = (lang: "vi" | "en" = "vi") => {
  window.localStorage.setItem("voya.lang", lang);
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <I18nProvider>
        <AdminShell>
          <p>Nội dung trang quản trị</p>
        </AdminShell>
      </I18nProvider>
    </MemoryRouter>,
  );
};

describe("AdminShell", () => {
  it("gắn phù hiệu console để không lẫn với ứng dụng thường", () => {
    renderShell();
    expect(screen.getByText("Console quản trị")).toBeInTheDocument();
  });

  it("có đúng MỘT lối thoát về ứng dụng", () => {
    renderShell();
    const exits = screen.getAllByRole("button", { name: /Thoát về ứng dụng/ });
    expect(exits).toHaveLength(1);
  });

  it("dựng đủ 12 mục điều hướng, mỗi mục là một liên kết thật", () => {
    renderShell();
    // Đếm liên kết thay vì so từng nhãn: mục mới thêm vào sẽ làm con số này
    // đổi, và đó là lúc người thêm phải quyết định xem 12 mục còn đúng không.
    const links = screen.getAllByRole("link");
    expect(links).toHaveLength(12);
    expect(links.map((a) => a.getAttribute("href"))).toContain("/admin/support");
  });

  it("dựng nội dung trang bên trong vỏ", () => {
    renderShell();
    expect(screen.getByText("Nội dung trang quản trị")).toBeInTheDocument();
  });

  it("dịch nhãn điều hướng sang tiếng Anh", () => {
    renderShell("en");
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.queryByText("Tổng quan")).not.toBeInTheDocument();
  });

  it("KHÔNG phải hàng rào quyền — quyền do máy chủ quyết ở từng endpoint", () => {
    // Dựng được vỏ mà không cần bất kỳ thông tin đăng nhập nào. Đó là chủ ý:
    // `ProtectedRoute requireAdmin` và `require_admin` phía máy chủ mới là chỗ
    // chặn. Nếu một ngày bài test này đỏ vì vỏ tự kiểm quyền, hãy kiểm tra xem
    // việc kiểm đó có nhân đôi một luật đã nằm ở nơi khác không.
    renderShell();
    expect(screen.getByText("Nội dung trang quản trị")).toBeInTheDocument();
  });
});

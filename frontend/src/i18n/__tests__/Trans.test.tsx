/**
 * `<Trans>` — câu có chỗ nhấn mạnh ở giữa, dịch NGUYÊN CÂU.
 *
 * Bài test đáng giá nhất ở đây là bài thứ hai: **chỗ nhấn mạnh phải đi theo bản
 * dịch**, không đứng yên ở vị trí của tiếng Việt. Đó chính là thứ cách làm cũ
 * (bọc `t()` quanh từng mảnh JSX) không làm được, và cũng là thứ không ai nhìn
 * thấy khi chỉ xem giao diện tiếng Việt — mảnh câu ghép lại vẫn ra đúng câu gốc.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { I18nProvider, Trans } from "../index";

/** Đặt ngôn ngữ trước khi provider đọc `localStorage` lúc khởi tạo. */
function renderIn(lang: "vi" | "en", node: React.ReactNode) {
  window.localStorage.setItem("voya.lang", lang);
  return render(<I18nProvider>{node}</I18nProvider>);
}

describe("<Trans>", () => {
  it("dựng câu tiếng Việt với chỗ nhấn mạnh đúng vị trí", () => {
    renderIn(
      "vi",
      <p data-testid="p">
        <Trans
          k="Những tệp bạn đã đóng góp {trangthai}. Muốn xoá, hãy dùng Thùng rác hoặc yêu cầu xoá tài khoản."
          vars={{ trangthai: <strong>không bị xoá</strong> }}
        />
      </p>,
    );
    expect(screen.getByTestId("p")).toHaveTextContent(
      "Những tệp bạn đã đóng góp không bị xoá. Muốn xoá, hãy dùng Thùng rác hoặc yêu cầu xoá tài khoản.",
    );
    expect(screen.getByText("không bị xoá").tagName).toBe("STRONG");
  });

  it("chỗ nhấn mạnh DI CHUYỂN theo trật tự từ của bản dịch", () => {
    // Tiếng Việt: "… đóng góp {trangthai}. Muốn xoá…"  → biến ở giữa câu.
    // Tiếng Anh:  "The files you contributed {trangthai}. To delete…"
    // Hai vị trí khác nhau trong câu, và `<Trans>` phải theo bản dịch chứ không
    // theo bản gốc.
    renderIn(
      "en",
      <p data-testid="p">
        <Trans
          k="Mỗi dòng ghi lại bạn đã đồng ý với {ban}, không phải một ô đánh dấu. Bấm vào số hiệu bản để đọc lại đúng bản mình đã ký."
          vars={{ ban: <strong>which version</strong> }}
        />
      </p>,
    );
    const text = screen.getByTestId("p").textContent ?? "";
    expect(text).toContain("Each row records which version you agreed to");
    // Nếu `<Trans>` chèn theo vị trí của bản GỐC thì câu sẽ mở đầu bằng phần
    // nhấn mạnh; phép kiểm này chặn đúng lỗi đó.
    expect(text.startsWith("Each row records")).toBe(true);
  });

  it("giữ nguyên {tên} khi thiếu biến, thay vì để lại chỗ trống câm", () => {
    renderIn("vi", <p data-testid="p"><Trans k="Chặn {ip}. Người dùng sẽ thấy thông báo kèm lý do bên dưới." /></p>);
    expect(screen.getByTestId("p")).toHaveTextContent("Chặn {ip}.");
  });

  it("nhận cả chuỗi thường làm biến, không chỉ phần tử React", () => {
    renderIn(
      "vi",
      <p data-testid="p">
        <Trans k="đến {khi}" vars={{ khi: "10/08/2026" }} />
      </p>,
    );
    expect(screen.getByTestId("p")).toHaveTextContent("đến 10/08/2026");
  });
});

/**
 * Khung đa ngôn ngữ.
 *
 * Tính chất được ghim kỹ nhất là cái dễ bị bỏ nhất: **`<html lang>` phải đổi
 * theo**. Trình đọc màn hình chọn giọng đọc theo thuộc tính đó; để nguyên
 * `lang="vi"` rồi hiện chữ tiếng Anh nghĩa là người khiếm thị nghe tiếng Anh
 * đọc bằng bộ phát âm tiếng Việt. WCAG 3.1.1.
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import LanguageSwitcher from "../../components/LanguageSwitcher";
import { I18nProvider, useI18n } from "../index";

function Probe() {
  const { t, lang } = useI18n();
  return (
    <div>
      <span data-testid="lang">{lang}</span>
      <span data-testid="known">{t("Đăng xuất")}</span>
      <span data-testid="unknown">{t("Một câu chưa ai dịch")}</span>
      {/* Khoá THẬT của sản phẩm, không phải khoá bịa riêng cho test: công
          cụ đo coi khoá chỉ xuất hiện trong `__tests__` là "không ai dùng"
          và lượt dọn rác sẽ xoá nó — làm bài test này đỏ vì một lý do không
          liên quan gì tới cơ chế nó đang kiểm. */}
      <span data-testid="vars">{t("Thông báo, {n} chưa đọc", { n: 4 })}</span>
    </div>
  );
}

const renderAll = () =>
  render(
    <I18nProvider>
      <LanguageSwitcher />
      <Probe />
    </I18nProvider>,
  );

/** jsdom báo `navigator.language = "en-US"`. Ghim ngôn ngữ trình duyệt cho từng
 *  test thay vì để môi trường quyết định — nếu không, bốn test dưới đây đổi kết
 *  quả tuỳ máy chạy, và đó là kiểu đỏ giả tốn nhiều giờ nhất để chẩn đoán. */
function setBrowserLanguage(value: string) {
  Object.defineProperty(window.navigator, "language", {
    value, configurable: true,
  });
}

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.lang = "";
  setBrowserLanguage("vi-VN");
});

describe("I18nProvider", () => {
  it("mặc định tiếng Việt và đặt <html lang> ngay từ lần vẽ đầu", () => {
    renderAll();
    expect(screen.getByTestId("lang")).toHaveTextContent("vi");
    expect(document.documentElement.lang).toBe("vi");
  });

  it("tiếng Việt trả về chính khoá — nó là bản GỐC, không phải bản dịch", () => {
    renderAll();
    expect(screen.getByTestId("known")).toHaveTextContent("Đăng xuất");
  });

  it("đổi sang tiếng Anh thì dịch VÀ đổi <html lang>", () => {
    renderAll();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "en" } });

    expect(screen.getByTestId("known")).toHaveTextContent("Sign out");
    expect(document.documentElement.lang).toBe("en");
  });

  it("chuỗi chưa dịch hiển thị nguyên tiếng Việt, KHÔNG hiện mã khoá", () => {
    renderAll();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "en" } });

    // Đây là lý do khoá là câu tiếng Việt chứ không phải `auth.logout.button`:
    // thiếu bản dịch thì người dùng thấy một câu đọc được, không phải một mã lỗi.
    expect(screen.getByTestId("unknown")).toHaveTextContent("Một câu chưa ai dịch");
  });

  it("thay biến trong chuỗi", () => {
    renderAll();
    expect(screen.getByTestId("vars")).toHaveTextContent("Thông báo, 4 chưa đọc");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "en" } });
    expect(screen.getByTestId("vars")).toHaveTextContent("Notifications, 4 unread");
  });

  it("nhớ lựa chọn giữa các phiên", () => {
    renderAll();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "en" } });
    expect(window.localStorage.getItem("voya.lang")).toBe("en");
  });


  it("suy ngôn ngữ từ trình duyệt khi người dùng chưa chọn bao giờ", () => {
    setBrowserLanguage("en-GB");
    renderAll();
    expect(screen.getByTestId("lang")).toHaveTextContent("en");
    expect(document.documentElement.lang).toBe("en");
  });

  it("trình duyệt ngôn ngữ khác vi/en thì rơi về tiếng Việt", () => {
    setBrowserLanguage("fr-FR");
    renderAll();
    expect(screen.getByTestId("lang")).toHaveTextContent("vi");
  });

  it("lựa chọn đã lưu THẮNG ngôn ngữ trình duyệt", () => {
    window.localStorage.setItem("voya.lang", "en");
    setBrowserLanguage("vi-VN");
    renderAll();
    expect(screen.getByTestId("lang")).toHaveTextContent("en");
  });

  it("giá trị rác trong localStorage không làm hỏng gì", () => {
    window.localStorage.setItem("voya.lang", "klingon");
    renderAll();
    expect(screen.getByTestId("lang")).toHaveTextContent("vi");
  });

  it("dùng ngoài provider thì trả TIẾNG VIỆT, không ném", () => {
    /**
     * Hợp đồng này đã ĐỔI, và đây là lý do — không phải một lần nới lỏng.
     *
     * Bản đầu cho `useI18n` ném khi nằm ngoài provider, lập luận: một nhánh
     * component ngoài provider sẽ hiện tiếng Việt kể cả khi người dùng chọn
     * tiếng Anh, mà không có gì cho thấy là sai.
     *
     * Lập luận ấy đúng khi `t()` được gọi ở vài chỗ. Nó đổ khi `t()` có mặt
     * khắp ứng dụng: lúc đó **mọi** bài test dựng một component đơn lẻ đều phải
     * bọc provider, nếu không thì vỡ — và cái vỡ đó không nói gì về component
     * đang kiểm. Một cơ chế bắt buộc phải có mặt ở mọi chỗ thì không được phép
     * là cơ chế có thể ném.
     *
     * Đánh đổi được giữ lại ở chỗ khác: `setLang` ngoài provider kêu một tiếng
     * `console.warn` ở chế độ phát triển. Tín hiệu còn, nhưng nó không đánh sập
     * gì. Còn trong sản phẩm thì `App.tsx` bọc toàn bộ cây, nên đường này chỉ
     * chạy trong test.
     */
    expect(() => render(<Probe />)).not.toThrow();
    expect(screen.getByTestId("lang")).toHaveTextContent("vi");
  });

  it("t() ngoài provider trả về chính khoá, kể cả khi có bản dịch EN", () => {
    /** Nguyên tắc 2: khoá LÀ câu tiếng Việt. Nhờ vậy một cây nằm ngoài provider
     *  vẫn đọc được bình thường thay vì hiện ra mã khoá giữa giao diện. */
    render(<Probe />);
    expect(screen.getByTestId("known")).toHaveTextContent("Đăng xuất");
  });
});

describe("LanguageSwitcher", () => {
  it("hiện tên mỗi ngôn ngữ BẰNG CHÍNH ngôn ngữ đó", () => {
    renderAll();
    // Người đang lạc trong giao diện họ không đọc được vẫn nhận ra tiếng mẹ đẻ.
    expect(screen.getByRole("option", { name: "Tiếng Việt" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "English" })).toBeInTheDocument();
  });

  it("có nhãn cho trình đọc màn hình", () => {
    renderAll();
    expect(screen.getByRole("combobox", { name: /Ngôn ngữ/ })).toBeInTheDocument();
  });
});

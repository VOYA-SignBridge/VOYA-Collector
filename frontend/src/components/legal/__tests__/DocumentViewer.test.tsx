/**
 * `DocumentViewer` — ba đường hiển thị một bản văn pháp lý.
 *
 * Bài test quan trọng nhất là bài cuối cùng: **đường markdown cũ không được
 * hỏng**. Bốn văn bản đang có hiệu lực trên máy chạy thật mang thân markdown và
 * đã có chữ ký trỏ vào băm của thân đó. Một thành phần mới làm trắng màn hình
 * của chúng là làm mất khả năng đọc lại thứ người ta đã ký.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import DocumentViewer from "../DocumentViewer";
import type { LegalDocumentContent } from "../../../api/legal";
import { I18nProvider } from "../../../i18n";

const base: LegalDocumentContent = {
  kind: "terms",
  version: "2.0",
  title: "Điều khoản sử dụng",
  language: "vi",
  body: "# Điều khoản\n\nNội dung markdown.",
  body_format: "markdown",
  content_hash: "a".repeat(64),
  effective_from: "2026-08-01T00:00:00Z",
  requires_reconsent: false,
  change_summary: "",
  has_file: false,
  file_name: null,
  file_mime: null,
  file_size: null,
} as LegalDocumentContent;

const show = (doc: LegalDocumentContent) => {
  // jsdom báo `navigator.language === "en-US"`, nên KHÔNG đặt gì ở đây là chạy
  // bằng tiếng Anh. Ghim tiếng Việt: bài test này kiểm cách chọn đường hiển
  // thị, không kiểm bản dịch.
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <DocumentViewer doc={doc} />
    </I18nProvider>,
  );
};

describe("DocumentViewer", () => {
  it("PDF được nhúng thẳng, và có nội dung dự phòng kèm nút tải", () => {
    const { container } = show({
      ...base,
      body: "",
      body_format: "file",
      has_file: true,
      file_name: "dieu-khoan-v2.pdf",
      file_mime: "application/pdf",
      file_size: 245_760,
    } as LegalDocumentContent);

    const embed = container.querySelector("object");
    expect(embed).not.toBeNull();
    expect(embed?.getAttribute("type")).toBe("application/pdf");

    // Nội dung dự phòng phải TỒN TẠI trong DOM, không chỉ là một ghi chú trong
    // mã: đó là thứ duy nhất người dùng di động thấy khi trình duyệt từ chối
    // dựng PDF, và không có sự kiện nào báo cho JavaScript biết chuyện đó.
    expect(
      screen.getByText(/Trình duyệt của bạn không mở được tệp PDF/),
    ).toBeInTheDocument();
  });

  it("DOCX hiện thẻ siêu dữ liệu + nút tải, KHÔNG cố dựng nội dung", () => {
    const { container } = show({
      ...base,
      body: "",
      body_format: "file",
      has_file: true,
      file_name: "quy-che.docx",
      file_mime:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      file_size: 51_200,
    } as LegalDocumentContent);

    expect(screen.getByText("quy-che.docx")).toBeInTheDocument();
    expect(screen.getByText(/50 KB/)).toBeInTheDocument();
    // Một bản dựng "gần giống" của tài liệu sắp ký là hướng hỏng tệ nhất, nên
    // ở đây không được có khung nhúng nào.
    expect(container.querySelector("object")).toBeNull();
    expect(container.querySelector("iframe")).toBeNull();
  });

  it("liên kết tải về mang đúng số hiệu bản đang xem", () => {
    show({
      ...base,
      version: "3.1",
      body: "",
      body_format: "file",
      has_file: true,
      file_name: "v3.pdf",
      file_mime: "application/pdf",
      file_size: 1024,
    } as LegalDocumentContent);

    // Đọc lại đúng bản mình đã ký chỉ có nghĩa nếu `version` đi theo liên kết.
    const link = screen.getAllByRole("link", { name: /Tải bản gốc/ })[0];
    expect(link.getAttribute("href")).toContain("version=3.1");
    expect(link.getAttribute("href")).toContain("download=true");
  });

  it("ĐƯỜNG MARKDOWN CŨ KHÔNG HỎNG — bốn văn bản đã công bố vẫn đọc được", () => {
    const { container } = show(base);
    expect(screen.getByText("Điều khoản")).toBeInTheDocument();
    expect(screen.getByText("Nội dung markdown.")).toBeInTheDocument();
    expect(container.querySelector(".prose-legal")).not.toBeNull();
    expect(container.querySelector("object")).toBeNull();
  });
});

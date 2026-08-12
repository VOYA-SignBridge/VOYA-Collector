/**
 * `UploadDocumentForm` — tải một bản văn pháp lý lên và công bố.
 *
 * Bốn thao tác ở đây KHÔNG hoàn tác được, nên các bài test bám vào đúng chỗ dễ
 * gây hại nhất chứ không phải chỗ dễ kiểm nhất:
 *
 * * nút công bố phải KHOÁ khi thiếu tệp hoặc thiếu số hiệu — bấm nhầm là công
 *   bố một bản văn không rút lại được;
 * * `requires_reconsent` phải đi đúng xuống API — bật nhầm là đá mọi người
 *   đang dùng ra màn hình chấp thuận;
 * * ngày hiệu lực bỏ trống phải gửi `null`, không phải chuỗi rỗng;
 * * lỗi `sudo_required` từ máy chủ phải hiện NGUYÊN VĂN, không nuốt thành "có
 *   lỗi xảy ra" — người dùng cần biết họ phải nhập lại mật khẩu.
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import UploadDocumentForm from "../UploadDocumentForm";
import { I18nProvider } from "../../../i18n";

const uploadDocument = vi.hoisted(() => vi.fn());

vi.mock("../../../api/legal", async () => {
  const actual = await vi.importActual<typeof import("../../../api/legal")>(
    "../../../api/legal",
  );
  return { ...actual, uploadDocument };
});

function show() {
  window.localStorage.setItem("voya.lang", "vi");
  return render(
    <I18nProvider>
      <UploadDocumentForm />
    </I18nProvider>,
  );
}

const pdf = () => new File([new Uint8Array([37, 80, 68, 70])], "dieu-khoan.pdf", {
  type: "application/pdf",
});

const fileBox = () => document.querySelector('input[type="file"]') as HTMLInputElement;
const publishButton = () => screen.getByRole("button", { name: /Tải lên và công bố/ });

beforeEach(() => {
  uploadDocument.mockReset();
  uploadDocument.mockResolvedValue({
    published: { version: "2026-08-10" },
    current: { version: "2026-08-10" },
  });
});

describe("UploadDocumentForm", () => {
  it("khoá nút công bố khi chưa chọn tệp", () => {
    show();
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), {
      target: { value: "2026-08-10" },
    });
    expect(publishButton()).toBeDisabled();
  });

  it("khoá nút công bố khi thiếu số hiệu — số hiệu là vĩnh viễn", () => {
    show();
    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    expect(publishButton()).toBeDisabled();
  });

  it("gửi đủ siêu dữ liệu, và effective_from rỗng thành null", async () => {
    show();
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), {
      target: { value: "2026-08-10" },
    });
    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    fireEvent.click(publishButton());

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1));
    const sent = uploadDocument.mock.calls[0][0];
    expect(sent.kind).toBe("terms");
    expect(sent.version).toBe("2026-08-10");
    expect(sent.file.name).toBe("dieu-khoan.pdf");
    // Chuỗi rỗng và `null` KHÔNG giống nhau ở phía máy chủ: một cái là "hiệu
    // lực ngay", cái kia là một ngày không phân tích được.
    expect(sent.effective_from).toBeNull();
    expect(sent.requires_reconsent).toBe(false);
  });

  it("ô 'yêu cầu đồng ý lại' đi đúng xuống API", async () => {
    show();
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), {
      target: { value: "3.0" },
    });
    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(publishButton());

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1));
    expect(uploadDocument.mock.calls[0][0].requires_reconsent).toBe(true);
  });

  it("phân biệt 'đã công bố' với 'đã lên lịch'", async () => {
    uploadDocument.mockResolvedValue({
      published: { version: "4.0" },
      current: { version: "3.0" },
    });
    show();
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), {
      target: { value: "4.0" },
    });
    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    fireEvent.click(publishButton());

    // Nói "đã công bố" về một bản còn nằm chờ là nói sai về hiệu lực pháp lý.
    expect(
      await screen.findByText(/Đã lên lịch bản 4.0/),
    ).toBeInTheDocument();
  });

  it("hiện NGUYÊN VĂN lỗi sudo_required thay vì 'có lỗi xảy ra'", async () => {
    uploadDocument.mockRejectedValue({
      response: { data: { detail: "Thao tác này cần xác thực lại mật khẩu." } },
    });
    show();
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), {
      target: { value: "5.0" },
    });
    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    fireEvent.click(publishButton());

    expect(
      await screen.findByText("Thao tác này cần xác thực lại mật khẩu."),
    ).toBeInTheDocument();
  });
});

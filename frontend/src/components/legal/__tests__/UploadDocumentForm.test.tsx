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

  it("ngày hiệu lực đi kèm OFFSET múi giờ và có dòng xem trước — LEG-04", async () => {
    // Máy chủ chạy UTC. Bản trước gửi "2026-08-20T09:00" trần, nên 09:00 người
    // dùng gõ ở Việt Nam thành 16:00 giờ Việt Nam khi có hiệu lực — lệch 7 giờ
    // trên một mốc pháp lý. Chuỗi gửi đi PHẢI mang offset.
    show();
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), {
      target: { value: "2026-08-20" },
    });
    const dt = document.querySelector('input[type="datetime-local"]') as HTMLInputElement;
    fireEvent.change(dt, { target: { value: "2026-08-20T09:00" } });

    const preview = screen.getByTestId("effective-from-preview");
    expect(preview.textContent).toContain("09:00");
    expect(preview.textContent).toContain("UTC");

    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    fireEvent.click(publishButton());

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(1));
    const sent = uploadDocument.mock.calls[0][0];
    expect(sent.effective_from).toMatch(/^2026-08-20T09:00:00[+-]\d{2}:\d{2}$/);
    expect(new Date(sent.effective_from).getTime())
      .toBe(new Date("2026-08-20T09:00").getTime());
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

  // Hình dạng THẬT của máy chủ (`legal_admin._require_sudo`), không phải chuỗi.
  const SUDO_403 = {
    response: {
      status: 403,
      data: { detail: { code: "sudo_required", message: "Công bố văn bản pháp lý cần xác thực lại bằng mật khẩu.", ttl_seconds: 300 } },
    },
  };

  it("bị đòi nâng quyền → hỏi mật khẩu → GỬI LẠI cùng tệp, không bắt chọn lại — LEG-05", async () => {
    uploadDocument
      .mockRejectedValueOnce(SUDO_403)
      .mockResolvedValueOnce({ published: { version: "6.0" }, current: { version: "6.0" } });
    const ensureSudo = vi.fn().mockResolvedValue(true);

    window.localStorage.setItem("voya.lang", "vi");
    render(
      <I18nProvider>
        <UploadDocumentForm ensureSudo={ensureSudo} />
      </I18nProvider>,
    );
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), { target: { value: "6.0" } });
    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    fireEvent.click(publishButton());

    await waitFor(() => expect(uploadDocument).toHaveBeenCalledTimes(2));
    expect(ensureSudo).toHaveBeenCalledTimes(1);
    // Lần hai gửi ĐÚNG những gì lần một gửi.
    expect(uploadDocument.mock.calls[1][0]).toEqual(uploadDocument.mock.calls[0][0]);
    expect(await screen.findByText(/Đã công bố bản 6.0/)).toBeInTheDocument();
  });

  it("huỷ hoặc sai mật khẩu → KHÔNG gửi lại, biểu mẫu giữ nguyên tệp", async () => {
    uploadDocument.mockRejectedValueOnce(SUDO_403);
    const ensureSudo = vi.fn().mockResolvedValue(false);

    window.localStorage.setItem("voya.lang", "vi");
    render(
      <I18nProvider>
        <UploadDocumentForm ensureSudo={ensureSudo} />
      </I18nProvider>,
    );
    fireEvent.change(screen.getByPlaceholderText("2026-08-10"), { target: { value: "6.0" } });
    fireEvent.change(fileBox(), { target: { files: [pdf()] } });
    fireEvent.click(publishButton());

    expect(await screen.findByText(/Chưa xác thực lại được/)).toBeInTheDocument();
    expect(uploadDocument).toHaveBeenCalledTimes(1);
    // Tệp và số hiệu còn nguyên: bấm lại là gửi được, không phải làm lại từ đầu.
    expect((screen.getByPlaceholderText("2026-08-10") as HTMLInputElement).value).toBe("6.0");
    expect(publishButton()).not.toBeDisabled();
  });
});

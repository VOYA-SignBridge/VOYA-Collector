/**
 * SOT-01 — hộp khoá riêng hiện một lần. Hai lối mất khoá của bản cũ được khoá
 * lại ở đây: đóng vì bấm nền, và "Đã copy" báo khi chưa chép được gì.
 */
import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import PrivateKeyModal from "../PrivateKeyModal";
import { I18nProvider } from "../../../i18n";

const KEY = "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----";

function show(onClose = vi.fn()) {
  window.localStorage.setItem("voya.lang", "vi");
  render(
    <I18nProvider>
      <PrivateKeyModal name="may-ghi-1" privateKey={KEY} onClose={onClose} />
    </I18nProvider>,
  );
  return onClose;
}

const originalClipboard = navigator.clipboard;

function setClipboard(value: unknown) {
  Object.defineProperty(navigator, "clipboard", { configurable: true, value });
}

beforeEach(() => vi.clearAllMocks());
afterEach(() => setClipboard(originalClipboard));

describe("PrivateKeyModal", () => {
  it("bấm ra NỀN không đóng — khoá chỉ hiện một lần", () => {
    const onClose = show();
    fireEvent.click(screen.getByTestId("private-key-backdrop"));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("nút đóng KHOÁ cho tới khi đã sao chép được hoặc tự xác nhận đã lưu", async () => {
    setClipboard({ writeText: vi.fn().mockResolvedValue(undefined) });
    const onClose = show();
    const close = screen.getByRole("button", { name: "Đã lưu, đóng" });
    expect(close).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Sao chép" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Đã sao chép" })).toBeInTheDocument());
    expect(close).toBeEnabled();

    fireEvent.click(close);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("clipboard bị TỪ CHỐI thì nói thẳng, KHÔNG báo đã sao chép", async () => {
    setClipboard({ writeText: vi.fn().mockRejectedValue(new Error("NotAllowedError")) });
    show();
    fireEvent.click(screen.getByRole("button", { name: "Sao chép" }));

    expect(await screen.findByText(/không cho sao chép tự động/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Đã sao chép" })).toBeNull();
    expect(screen.getByRole("button", { name: "Đã lưu, đóng" })).toBeDisabled();
  });

  it("KHÔNG có navigator.clipboard (HTTP thường) → cùng thông báo, không sập", async () => {
    setClipboard(undefined);
    show();
    fireEvent.click(screen.getByRole("button", { name: "Sao chép" }));
    expect(await screen.findByText(/không cho sao chép tự động/)).toBeInTheDocument();
  });

  it("đường thủ công: tải về tệp .key và tự xác nhận đã lưu", () => {
    setClipboard(undefined);
    const onClose = show();
    const link = screen.getByRole("link", { name: /Tải về tệp/ });
    expect(link).toHaveAttribute("download", "may-ghi-1.key");
    expect(decodeURIComponent(link.getAttribute("href") || "")).toContain("BEGIN PRIVATE KEY");

    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Đã lưu, đóng" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("là hộp thoại thật: role, aria-modal, tiêu đề, focus vào khoá", () => {
    show();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName(/may-ghi-1/);
    expect(document.activeElement).toBe(screen.getByRole("textbox", { name: "Khoá riêng" }));
  });
});

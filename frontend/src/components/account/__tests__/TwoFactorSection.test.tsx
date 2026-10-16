/**
 * Xác thực hai bước trên trang tài khoản.
 *
 * Tính chất quan trọng nhất ở đây không phải "bấm được nút", mà là **đăng ký dở
 * KHÔNG được hiện thành đã bật**. Nếu màn hình nói "Đang bật" ngay sau khi cấp
 * bí mật, người dùng sẽ đóng tab và tin rằng tài khoản đã được bảo vệ — trong
 * khi thực tế chưa có gì, và lần đăng nhập sau không hỏi mã.
 */

import "@testing-library/jest-dom/vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../../api/account", async () => {
  const actual = await vi.importActual<typeof import("../../../api/account")>(
    "../../../api/account",
  );
  return {
    ...actual,
    fetchTwoFactorStatus: vi.fn(),
    beginTwoFactorEnrollment: vi.fn(),
    confirmTwoFactor: vi.fn(),
    disableTwoFactor: vi.fn(),
    regenerateRecoveryCodes: vi.fn(),
  };
});

import * as api from "../../../api/account";
import TwoFactorSection from "../TwoFactorSection";

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const OFF: api.TwoFactorStatus = {
  enabled: false, pending: false, confirmed_at: null, recovery_codes_left: 0,
};
const ON: api.TwoFactorStatus = {
  enabled: true, pending: false,
  confirmed_at: "2026-08-10T02:00:00Z", recovery_codes_left: 9,
};

beforeEach(() => {
  vi.clearAllMocks();
  mocked.beginTwoFactorEnrollment.mockResolvedValue({
    secret: "ABCDEFGHIJKLMNOP",
    secret_grouped: "ABCD EFGH IJKL MNOP",
    uri: "otpauth://totp/x",
  });
  mocked.confirmTwoFactor.mockResolvedValue(["aaaaa-bbbbb", "ccccc-ddddd"]);
});

describe("TwoFactorSection", () => {
  it("hiện Chưa bật khi tài khoản chưa dùng 2FA", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(OFF);
    render(<TwoFactorSection />);

    expect(await screen.findByText("Chưa bật")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Bật xác thực hai bước/ }),
    ).toBeInTheDocument();
  });

  it("đăng ký dở KHÔNG được hiện thành đã bật", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(OFF);
    render(<TwoFactorSection />);

    fireEvent.click(await screen.findByRole("button", { name: /Bật xác thực hai bước/ }),);
    await screen.findByText("ABCD EFGH IJKL MNOP");

    // Vẫn "Chưa bật" — đây là tính chất được kiểm, không phải chi tiết phụ.
    expect(screen.getByText("Chưa bật")).toBeInTheDocument();
  });

  it("hiện bí mật theo nhóm 4 ký tự để gõ tay được", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(OFF);
    render(<TwoFactorSection />);

    fireEvent.click(await screen.findByRole("button", { name: /Bật xác thực hai bước/ }),);
    expect(await screen.findByText("ABCD EFGH IJKL MNOP")).toBeInTheDocument();
  });

  it("nút xác nhận khoá cho tới khi đủ 6 chữ số", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(OFF);
    render(<TwoFactorSection />);

    fireEvent.click(await screen.findByRole("button", { name: /Bật xác thực hai bước/ }),);
    const confirm = await screen.findByRole("button", { name: "Xác nhận" });
    expect(confirm).toBeDisabled();

    fireEvent.change(await screen.findByLabelText(/Nhập mã 6 chữ số/), { target: { value: "123456" } });
    expect(confirm).toBeEnabled();
  });

  it("ô nhập mã bỏ ký tự không phải chữ số", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(OFF);
    render(<TwoFactorSection />);

    fireEvent.click(await screen.findByRole("button", { name: /Bật xác thực hai bước/ }),);
    const input = (await screen.findByLabelText(/Nhập mã 6 chữ số/)) as HTMLInputElement;
    fireEvent.change(input, { target: { value: "12ab34cd56" } });
    expect(input.value).toBe("123456");
  });

  it("xác nhận xong thì hiện mã khôi phục kèm cảnh báo lần-duy-nhất", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValueOnce(OFF).mockResolvedValue(ON);
    render(<TwoFactorSection />);

    fireEvent.click(await screen.findByRole("button", { name: /Bật xác thực hai bước/ }),);
    fireEvent.change(await screen.findByLabelText(/Nhập mã 6 chữ số/), { target: { value: "123456" } });
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận" }));

    expect(await screen.findByText("aaaaa-bbbbb")).toBeInTheDocument();
    expect(screen.getByText(/lần duy nhất chúng hiển thị/)).toBeInTheDocument();
  });

  it("mã sai thì báo lỗi và không bật", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(OFF);
    mocked.confirmTwoFactor.mockRejectedValue({
      response: { data: { detail: "Mã không đúng." } },
    });
    render(<TwoFactorSection />);

    fireEvent.click(await screen.findByRole("button", { name: /Bật xác thực hai bước/ }),);
    fireEvent.change(await screen.findByLabelText(/Nhập mã 6 chữ số/), { target: { value: "000000" } });
    fireEvent.click(screen.getByRole("button", { name: "Xác nhận" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Mã không đúng.");
  });

  it("đã bật thì hiện số mã khôi phục còn lại", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(ON);
    render(<TwoFactorSection />);

    expect(await screen.findByText("Đang bật")).toBeInTheDocument();
    expect(screen.getByText(/Còn 9 mã chưa dùng/)).toBeInTheDocument();
  });

  it("tắt 2FA đòi mật khẩu VÀ một bước xác nhận riêng", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(ON);
    mocked.disableTwoFactor.mockResolvedValue(undefined);
    render(<TwoFactorSection />);

    const off = await screen.findByRole("button", { name: /Tắt xác thực hai bước/ });
    // Chưa nhập mật khẩu: bấm lần một chỉ mở bước xác nhận, chưa gọi API.
    fireEvent.click(off);
    expect(mocked.disableTwoFactor).not.toHaveBeenCalled();

    const confirmOff = screen.getByRole("button", { name: "Xác nhận tắt" });
    expect(confirmOff).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Mật khẩu hiện tại"), { target: { value: "mat khau" } });
    fireEvent.click(confirmOff);
    await waitFor(() => expect(mocked.disableTwoFactor).toHaveBeenCalledWith("mat khau"));
  });

  it("cấp lại mã khôi phục cũng đòi mật khẩu", async () => {
    mocked.fetchTwoFactorStatus.mockResolvedValue(ON);
    mocked.regenerateRecoveryCodes.mockResolvedValue(["eeeee-fffff"]);
    render(<TwoFactorSection />);

    const btn = await screen.findByRole("button", { name: /Cấp lại mã khôi phục/ });
    expect(btn).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Mật khẩu hiện tại"), { target: { value: "mat khau" } });
    fireEvent.click(btn);
    expect(await screen.findByText("eeeee-fffff")).toBeInTheDocument();
  });
});

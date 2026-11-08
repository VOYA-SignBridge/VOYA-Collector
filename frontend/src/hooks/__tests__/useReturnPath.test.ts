/**
 * Nút "← Quay lại" của Cài đặt phải về TRANG VỪA XEM ngoài khu Cài đặt —
 * không phải lùi một bước lịch sử, không phải một trang đăng nhập.
 */
import { beforeEach, describe, expect, it } from "vitest";

import { getReturnPath, rememberReturnPath } from "../useReturnPath";

describe("useReturnPath", () => {
  beforeEach(() => window.sessionStorage.clear());

  it("mặc định về Trang chủ khi chưa xem trang nào", () => {
    expect(getReturnPath()).toBe("/");
  });

  it("nhớ trang cuối cùng NGOÀI /settings, kể cả query", () => {
    rememberReturnPath("/labels?dialect=hoa-de");
    rememberReturnPath("/settings/account");
    rememberReturnPath("/settings/security");
    expect(getReturnPath()).toBe("/labels?dialect=hoa-de");
  });

  it("không coi trang đăng nhập / khôi phục là chỗ để quay về", () => {
    rememberReturnPath("/training");
    rememberReturnPath("/login");
    rememberReturnPath("/reset-password?token=x");
    expect(getReturnPath()).toBe("/training");
  });

  it("từ chối giá trị lạ trong sessionStorage", () => {
    window.sessionStorage.setItem("voya.settings.returnTo", "//evil.example");
    expect(getReturnPath()).toBe("/");
  });
});

import { describe, expect, it } from "vitest";

import { canEditTenant } from "../auth";

/**
 * Nút biên tập phải đi theo đúng phép kiểm của máy chủ: vai ở tổ chức ĐANG LÀM
 * VIỆC (`can_edit_tenant`), không phải `tenant_role` của tổ chức nhà.
 */
describe("canEditTenant", () => {
  it("quản trị nền tảng luôn được", () => {
    expect(canEditTenant({ is_admin: true } as never)).toBe(true);
  });

  it("biên tập viên ở tổ chức đang làm việc được", () => {
    expect(canEditTenant({ is_admin: false, can_edit_tenant: true } as never)).toBe(true);
  });

  it("là admin ở tổ chức nhà nhưng không có vai ở nơi đang làm việc thì không", () => {
    expect(
      canEditTenant({ is_admin: false, tenant_role: "admin", can_edit_tenant: false } as never),
    ).toBe(false);
  });

  it("chưa đăng nhập thì không", () => {
    expect(canEditTenant(null)).toBe(false);
  });
});

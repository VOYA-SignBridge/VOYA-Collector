import { describe, expect, it } from "vitest";

import { memberIdentity, memberOptionLabel } from "../tenants";

/**
 * Vì sao email đứng trước tên: kho này có `Trâm` và `Trân` là HAI người khác
 * nhau, và `Minh` xuất hiện ở ba tài khoản. Người quản trị đang chọn ai để cấp
 * quyền cần một thứ duy nhất, và email là thứ duy nhất trong ba trường.
 */
describe("memberIdentity", () => {
  it("email lam dong chinh, ten lam dong phu", () => {
    expect(memberIdentity({ username: "Trân", email: "tran@ctu.edu.vn" })).toEqual({
      primary: "tran@ctu.edu.vn",
      secondary: "Trân",
    });
  });

  it("khong co email thi dung ten, va KHONG co dong phu", () => {
    expect(memberIdentity({ username: "Khoa", email: null })).toEqual({
      primary: "Khoa",
      secondary: null,
    });
  });

  it("ten trung email thi khong lap lai o dong phu", () => {
    const r = memberIdentity({ username: "a@b.vn", email: "a@b.vn" });
    expect(r.secondary).toBeNull();
  });

  it("khoang trang thua khong tao ra mot danh tinh gia", () => {
    expect(memberIdentity({ username: "   ", email: "  " }).primary).toBe("—");
  });

  it("UUID tran KHONG BAO GIO lot ra nguyen ven", () => {
    // Ba man hinh truoc ban nay roi thang ra chuoi 36 ky tu: no khong giup ai
    // nhan ra nguoi nao va du dai de pha bo cuc hang.
    const r = memberIdentity({ user_id: "eeeaeb8b-a832-4d1d-bac7-ebdd819fc644" });
    expect(r.primary).toBe("eeeaeb8b…");
    expect(r.primary.length).toBeLessThan(12);
  });

  it("khong co gi ca thi ra dau gach, khong ra 'undefined'", () => {
    expect(memberIdentity({}).primary).toBe("—");
  });
});

describe("memberOptionLabel", () => {
  it("gop hai dong thanh mot, vi <option> khong dung duoc hai dong", () => {
    expect(memberOptionLabel({ username: "Trân", email: "tran@ctu.edu.vn" }))
      .toBe("tran@ctu.edu.vn — Trân");
  });

  it("chi mot manh thi khong co dau gach thua", () => {
    expect(memberOptionLabel({ username: "Khoa" })).toBe("Khoa");
  });
});

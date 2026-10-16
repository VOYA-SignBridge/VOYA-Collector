import { describe, expect, it } from "vitest";
import { extractHeadings, slugify } from "./markdownOutline";

describe("markdownOutline", () => {
  it("bỏ dấu tiếng Việt, đ → d, khoảng trắng → gạch nối", () => {
    expect(slugify("Phạm vi áp dụng")).toBe("pham-vi-ap-dung");
    expect(slugify("Điều khoản & trách nhiệm")).toBe("dieu-khoan-trach-nhiem");
    expect(slugify("**Bảo mật** `dữ liệu`")).toBe("bao-mat-du-lieu");
  });

  it("hai tiêu đề trùng nhau ra hai id khác nhau, theo thứ tự", () => {
    const md = ["## Phạm vi", "text", "## Phạm vi", "## Khác"].join(String.fromCharCode(10));
    expect(extractHeadings(md).map((h) => h.id)).toEqual(["pham-vi", "pham-vi-2", "khac"]);
  });

  it("cấp sâu hơn 3 gộp về 3; văn bản không tiêu đề → rỗng", () => {
    const md = ["#### Sâu"].join("");
    expect(extractHeadings(md)[0].level).toBe(3);
    expect(extractHeadings("chỉ có đoạn văn")).toEqual([]);
  });
});

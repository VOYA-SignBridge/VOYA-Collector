import { describe, expect, it } from "vitest";
import {
  browserTimeZoneLabel,
  describeEffectiveFrom,
  localInputToOffsetIso,
} from "./effectiveFrom";

/** Offset thật của máy chạy test, dạng `+07:00`, để bài kiểm không phụ thuộc TZ. */
function offsetOf(d: Date): string {
  const offMin = -d.getTimezoneOffset();
  const sign = offMin >= 0 ? "+" : "-";
  const abs = Math.abs(offMin);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`;
}

describe("localInputToOffsetIso — LEG-04", () => {
  it("giữ nguyên giờ-trên-tường người gõ và GẮN offset của trình duyệt", () => {
    const iso = localInputToOffsetIso("2026-08-20T09:00");
    expect(iso).toBe(`2026-08-20T09:00:00${offsetOf(new Date("2026-08-20T09:00"))}`);
  });

  it("thời điểm tuyệt đối khớp với cách trình duyệt hiểu ô nhập", () => {
    const iso = localInputToOffsetIso("2026-08-20T09:00")!;
    expect(new Date(iso).getTime()).toBe(new Date("2026-08-20T09:00").getTime());
  });

  it("KHÔNG bao giờ gửi chuỗi naive — chính lỗi lệch 7 giờ", () => {
    const iso = localInputToOffsetIso("2026-08-20T09:00")!;
    expect(iso).toMatch(/[+-]\d{2}:\d{2}$/);
  });

  it("trống = hiệu lực ngay = null; rác = null", () => {
    expect(localInputToOffsetIso("")).toBeNull();
    expect(localInputToOffsetIso("   ")).toBeNull();
    expect(localInputToOffsetIso("khong-phai-ngay")).toBeNull();
  });
});

describe("describeEffectiveFrom", () => {
  it("nêu giờ, ngày VÀ múi giờ — không được mập mờ", () => {
    const s = describeEffectiveFrom("2026-08-20T09:00")!;
    expect(s).toContain("09:00");
    expect(s).toContain("20/08/2026");
    expect(s).toContain("UTC");
  });

  it("trống thì không có gì để xem trước", () => {
    expect(describeEffectiveFrom("")).toBeNull();
  });

  it("nhãn múi giờ luôn có phần UTC±HH:MM", () => {
    expect(browserTimeZoneLabel()).toMatch(/UTC[+-]\d{2}:\d{2}/);
  });
});

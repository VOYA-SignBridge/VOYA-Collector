import { dangNhap, expect, test } from "./helpers";

/**
 * Giọng đọc thật: gọi dịch vụ đọc của Microsoft qua backend tạm. Không giả lập, vì
 * lỗi từng gặp (edge-tts 403) chỉ lộ ra khi gọi thật.
 */

test.use({ video: "on", screenshot: "on", trace: "on" });

test("1. Đọc được thành tiếng một câu tiếng Việt", async ({ page }) => {
  await dangNhap(page, "iso_user_a", "default");
  const r = await page.evaluate(async () => {
    const res = await fetch("/api/v1/tts/speak?text=" + encodeURIComponent("xin chào"), { credentials: "include" });
    return { status: res.status, loai: res.headers.get("content-type"), byte: (await res.arrayBuffer()).byteLength };
  });
  expect(r.status, JSON.stringify(r)).toBe(200);
  expect(r.loai).toContain("audio");
  expect(r.byte).toBeGreaterThan(1000);
});

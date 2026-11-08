import { readFileSync } from "node:fs";

import type { Page } from "@playwright/test";

import { dangNhap, expect, goiApi, test } from "./helpers";

/**
 * Thu thập dữ liệu bằng tài khoản không có vai: tải video thật cho worker xử lý,
 * và thu từ camera qua trình duyệt (camera giả phát clip tay thật, xem
 * `playwright.config.ts`). Chạy từ bảng điều khiển trên môi trường tạm.
 */

const VIDEO = process.env.E2E_VIDEO || "";

test.use({ video: "on", screenshot: "on", trace: "on" });

/** Tải video lên rồi đợi worker xong; trả về kết quả worker. */
async function taiVaXuLy(page: Page, truong: Record<string, string>) {
  const csrf = (await page.context().cookies()).find((c) => c.name === "voya_csrf")?.value ?? "";
  const tai = await page.request.post("/api/v1/upload/video", {
    headers: { "X-CSRF-Token": csrf },
    multipart: {
      file: { name: "clip.mp4", mimeType: "video/mp4", buffer: readFileSync(VIDEO) },
      language: "vn", dialect: "hoa-de", ...truong,
    },
  });
  expect(tai.status(), await tai.text()).toBe(200);
  const xuLy = await goiApi(page, "POST", "/api/v1/upload/video/process", { upload_uid: (await tai.json()).upload_uid });
  expect(xuLy.status, JSON.stringify(xuLy.json)).toBe(200);
  const job = xuLy.json.results[0].job_id;

  let ketQua: { saved?: unknown[]; status?: string; message?: string } = {};
  await expect.poll(async () => {
    const r = await goiApi(page, "GET", `/jobs/${job}`);
    ketQua = r.json?.result?.result ?? {};
    return r.json?.status;
  }, { timeout: 150_000, intervals: [3000] }).toBe("SUCCESS");
  return ketQua;
}

test("1. Tải video lên và worker tách được mẫu", async ({ page }) => {
  test.setTimeout(240_000);
  test.skip(!VIDEO, "thieu E2E_VIDEO");
  await dangNhap(page, "iso_user_a", "default");
  const ketQua = await taiVaXuLy(page, { label: "video kiem thu" });
  expect(ketQua.saved?.length ?? 0, JSON.stringify(ketQua)).toBeGreaterThan(0);
});

test("3. Lớp đã đủ mẫu thì worker nói rõ lý do, không đổ cho bàn tay", async ({ page }) => {
  test.setTimeout(240_000);
  test.skip(!VIDEO, "thieu E2E_VIDEO");
  await dangNhap(page, "iso_user_a", "default");
  const lop = await goiApi(page, "GET", "/classes/list?language=vn&dialect=hoa-de");
  const day = lop.json.items.find((c: { slug: string }) => c.slug === "rang-muoi");
  const ketQua = await taiVaXuLy(page, { label: day.label_original, class_uid: day.class_uid });
  expect(ketQua.status).toBe("skipped_cap");
  expect(ketQua.message).toContain("đã đủ");
});

test("2. Thu camera qua trình duyệt lưu được một mẫu", async ({ page }) => {
  test.setTimeout(300_000);
  await dangNhap(page, "iso_user_a", "default");
  const lop = await goiApi(page, "GET", "/classes/list?language=vn&dialect=hoa-de");
  expect(lop.status, JSON.stringify(lop.json)).toBe(200);
  const nhan = lop.json.items[0];

  await page.goto("/upload?tab=capture");
  await page.getByRole("button", { name: /Mở chế độ Toàn màn hình/ }).click();
  await page.getByPlaceholder("vd: xin chào, cảm ơn").fill(nhan.label_original);

  // MediaPipe chạy bằng phần mềm trong trình duyệt tự động: thu đủ khung mất ~90 giây.
  const chup = page.getByRole("button", { name: /Bắt đầu chụp/ });
  // Nút chỉ mở khi đã nhận dạng được, và lúc đó phải thấy hình chứ không phải màn đen.
  await expect(page.getByTestId("capture-loading")).toBeHidden({ timeout: 120_000 });
  await expect(chup).toBeEnabled();
  const doSang = await page.locator("canvas").first().evaluate((c: HTMLCanvasElement) => {
    const d = c.getContext("2d")!.getImageData(0, 0, c.width, c.height).data;
    let tong = 0;
    for (let i = 0; i < d.length; i += 4000) tong += d[i] + d[i + 1] + d[i + 2];
    return tong / (d.length / 4000) / 3;
  });
  expect(doSang, "khung hinh khong duoc den").toBeGreaterThan(10);
  const luu = page.waitForResponse(
    (r) => r.url().includes("/upload/camera") && r.request().method() === "POST", { timeout: 200_000 });
  await chup.click();
  const r = await luu;
  expect(r.status(), await r.text()).toBe(200);
  const mau = await r.json();
  expect(mau.success).toBe(true);
  expect(mau.total_samples).toBeGreaterThan(0);
});

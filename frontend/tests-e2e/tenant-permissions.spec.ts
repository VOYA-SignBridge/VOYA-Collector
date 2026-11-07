import type { Page } from "@playwright/test";

import { dangNhap, expect, goiApi, test } from "./helpers";

/**
 * Quyền theo tổ chức, kiểm bằng trình duyệt thật. Chạy từ nút "Xem trình duyệt
 * chạy thật" của bảng điều khiển VOYA, trên môi trường tạm (`scripts/kiem_thu.py`)
 * với mã đang có trong repo. KHÔNG chạy trên stack thật: kịch bản 2 promote model.
 *
 * Tài khoản là của `scripts/seed_isolation_fixture.py`. Hai tài khoản này là
 * biên tập viên ở iso_a, iso_b và không có vai ở `default`, nên chuyển sang
 * `default` là thành viên thường.
 *
 * Phần chặn thử bằng API thẳng, vì giấu một cái nút không phải là chặn.
 */

const KHUNG = Array.from({ length: 60 }, () => Array(126).fill(0));

test.use({
  video: "on",
  screenshot: "on",
  trace: "on",
  launchOptions: { slowMo: Number(process.env.E2E_SLOWMO || 0) },
});

/** Mở job hoàn thành đầu tiên trong lịch sử, trả về id của nó. */
async function moJob(page: Page): Promise<string> {
  await page.goto("/training");
  const jobs = await goiApi(page, "GET", "/api/v1/training/jobs");
  const job = jobs.json.find((j: { status: string }) => j.status === "completed");
  await page.locator(`tr[title="Job ${job.id}"]`).click();
  return job.id;
}

test.describe.serial("Quyền theo tổ chức", () => {
  let jobCuaA = "";

  test("1. Thành viên thường không promote được model của người khác, kể cả gọi thẳng API", async ({ page }) => {
    await dangNhap(page, "iso_user_a", "default");
    await page.goto("/training");
    const toi = await goiApi(page, "GET", "/api/v1/auth/me");
    const jobs = await goiApi(page, "GET", "/api/v1/training/jobs");
    const job = jobs.json.find((j: { status: string; auth_user_id: string }) =>
      j.status === "completed" && j.auth_user_id !== toi.json.id)?.id;
    expect(job, "phai co job hoan thanh cua nguoi khac").toBeTruthy();
    await page.locator(`tr[title="Job ${job}"]`).click();
    await expect(page.getByRole("button", { name: "Kiểm tra model (Realtime)" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Đưa vào Realtime" })).toHaveCount(0);
    const r = await goiApi(page, "POST", `/api/v1/training/jobs/${job}/promote`);
    expect(r.status).toBe(403);
  });

  test("2. Biên tập viên tự đưa model vào Realtime và nhận dạng được", async ({ page }) => {
    await dangNhap(page, "iso_user_a", "iso_a");
    jobCuaA = await moJob(page);
    page.once("dialog", (d) => d.accept());
    await page.getByRole("button", { name: "Đưa vào Realtime" }).click();
    await expect(page.getByText(/Đã đưa vào Realtime lúc/)).toBeVisible({ timeout: 30_000 });

    const ds = await goiApi(page, "GET", "/api/v1/realtime/models");
    const ids: string[] = ds.json.map((m: { id: string }) => m.id);
    expect(ids).toContain("hoa-de@iso_a");
    expect(ids).toContain("hoa-de"); // slot chung vẫn còn

    const nhanDang = await goiApi(page, "POST", "/api/v1/realtime/predict", { model_id: "hoa-de@iso_a", frames: KHUNG });
    expect(nhanDang.status).toBe(200);
  });

  test("3. Tổ chức khác không thấy, không gọi, không promote được model của iso_a", async ({ page }) => {
    await dangNhap(page, "iso_user_b", "iso_b");
    const ds = await goiApi(page, "GET", "/api/v1/realtime/models");
    expect(ds.json.map((m: { id: string }) => m.id)).not.toContain("hoa-de@iso_a");
    const goi = await goiApi(page, "POST", "/api/v1/realtime/predict", { model_id: "hoa-de@iso_a", frames: KHUNG });
    expect(goi.status).toBe(404);
    const promote = await goiApi(page, "POST", `/api/v1/training/jobs/${jobCuaA}/promote`);
    expect(promote.status).toBe(404);
  });

  test("4. Biên tập viên sửa được nhãn của tổ chức mình", async ({ page }) => {
    await dangNhap(page, "iso_user_a", "iso_a");
    const taoNhan = await goiApi(page, "POST", "/classes/register", {
      label: "Nhãn kiểm thử", language: "vn", dialect: "hoa-de", is_common_language: false,
    });
    expect(taoNhan.status, JSON.stringify(taoNhan.json)).toBe(200);

    await page.goto("/labels");
    await expect(page.getByRole("button", { name: /Tạo nhãn mới/ }).first()).toBeVisible();
    await page.getByRole("button", { name: "Sửa" }).first().click();
    await page.locator("label", { hasText: /^Tên nhãn$/ }).locator("xpath=following-sibling::input").fill("Nhãn đã sửa");
    await page.getByRole("button", { name: "Lưu thay đổi" }).click();
    await expect(page.getByText("Nhãn đã sửa").first()).toBeVisible();
  });

  test("5. Thành viên thường chỉ đề xuất được nhãn, không sửa được", async ({ page }) => {
    await dangNhap(page, "iso_user_a", "default");
    await page.goto("/labels");
    await expect(page.getByRole("button", { name: /Đề xuất nhãn mới/ }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Sửa" })).toHaveCount(0);
    const r = await goiApi(page, "DELETE", "/classes/khong-ton-tai");
    expect(r.status).toBe(403);
  });

  test("6. Biên tập viên có lối vào Hàng đợi xử lý ở khu Tổ chức", async ({ page }) => {
    await dangNhap(page, "iso_user_a", "iso_a");
    await page.goto("/org/iso_a");
    await page.getByRole("navigation", { name: "Mục của tổ chức" }).getByRole("link", { name: "Hàng đợi xử lý" }).click();
    await expect(page).toHaveURL(/\/org\/iso_a\/processing/);
    await expect(page.getByText("Worker đang phục vụ", { exact: true })).toBeVisible();
  });

  test("7. Thành viên thường không thấy các mục quản lý đó", async ({ page }) => {
    await dangNhap(page, "iso_user_a", "default");
    await page.goto("/org/default");
    const nav = page.getByRole("navigation", { name: "Mục của tổ chức" });
    await expect(nav.getByRole("link", { name: "Thành viên" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Hàng đợi xử lý" })).toHaveCount(0);
  });
});

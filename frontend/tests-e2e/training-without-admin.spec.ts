import { dangNhap, expect, goiApi, test } from "./helpers";

/**
 * Huấn luyện trọn chuỗi bằng tài khoản KHÔNG có vai ở `default`: chuẩn bị dữ liệu,
 * chạy trainer thật, đọc kết quả. Chạy từ bảng điều khiển trên môi trường tạm.
 */

test.use({ video: "on", screenshot: "on", trace: "on" });

test("1. Thành viên thường tự chuẩn bị dữ liệu và huấn luyện xong một model", async ({ page, browser }) => {
  test.setTimeout(420_000);
  await dangNhap(page, "iso_user_a", "default");

  const chuanBi = await goiApi(page, "POST", "/api/v1/training/dataset/prepare", { dialects: ["hoa-de"] });
  expect(chuanBi.status, JSON.stringify(chuanBi.json)).toBe(200);

  await expect.poll(async () => {
    const r = await goiApi(page, "GET", `/api/v1/training/dataset/prepare/${chuanBi.json.run_id}`);
    return r.json?.status === "failed" ? `failed: ${r.json.error}` : r.json?.status;
  }, { timeout: 180_000, intervals: [3000] }).toBe("completed");

  const ds = await goiApi(page, "GET", "/api/v1/training/splits/operational");
  const tap = ds.json.find((s: { dialects: string[] }) => s.dialects.join() === "hoa-de");
  expect(tap, "phai co tap chia hoa-de").toBeTruthy();
  expect(tap.personal, "thanh vien dung tap cua rieng minh").toBe(true);

  const nguoiKhac = await (await browser.newContext()).newPage();
  await dangNhap(nguoiKhac, "iso_user_b", "default");
  const dsKhac = await goiApi(nguoiKhac, "GET", "/api/v1/training/splits/operational");
  expect(dsKhac.json.map((s: { split_id: string }) => s.split_id)).not.toContain(tap.split_id);
  const ghimTrom = await goiApi(nguoiKhac, "POST", "/api/v1/training/start", {
    model_type: "tcn", dialects: ["hoa-de"], languages: ["vn"], epochs: 1,
    run_purpose: "operational", operational_split_id: tap.split_id,
  });
  expect(ghimTrom.status, "khong ghim duoc tap rieng cua nguoi khac").toBe(400);

  const chay = await goiApi(page, "POST", "/api/v1/training/start", {
    model_type: "tcn", dialects: ["hoa-de"], languages: ["vn"], epochs: 1,
    run_purpose: "operational", operational_split_id: tap.split_id,
  });
  expect(chay.status, JSON.stringify(chay.json)).toBe(200);

  await expect.poll(async () => {
    const r = await goiApi(page, "GET", `/api/v1/training/jobs/${chay.json.id}`);
    return r.json?.status === "failed" ? `failed: ${r.json.error_message}` : r.json?.status;
  }, { timeout: 200_000, intervals: [3000] }).toBe("completed");

  await page.goto("/training");
  await expect(page.locator(`tr[title="Job ${chay.json.id}"]`)).toBeVisible();
});

test("2. Thành viên thường bấm qua toàn bộ giao diện huấn luyện, không bị đòi quyền", async ({ page }) => {
  test.setTimeout(180_000);
  const biChan: string[] = [];
  page.on("response", (r) => {
    if ([401, 403].includes(r.status()) && /training|classes|dataset|vocabulary|tts/.test(r.url())) {
      biChan.push(`${r.status()} ${r.request().method()} ${new URL(r.url()).pathname}`);
    }
  });
  await dangNhap(page, "iso_user_a", "default");
  await page.goto("/training");
  await page.getByRole("button", { name: "Bắt đầu huấn luyện mới" }).click();

  await expect(page.getByRole("heading", { name: "Dữ Liệu", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Tiếp theo →" }).click();

  await expect(page.getByRole("heading", { name: "Chọn Dialect", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "hoa-de", exact: true }).click();
  await page.getByRole("button", { name: "Tiếp theo →" }).click();

  await expect(page.getByRole("heading", { name: "Chia Tập", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Tiếp theo →" })).toBeEnabled({ timeout: 20_000 });
  await page.getByRole("button", { name: "Tiếp theo →" }).click();

  await expect(page.getByRole("heading", { name: "Tăng Cường", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Tiếp theo →" }).click();

  await expect(page.getByRole("heading", { name: "Cấu Hình", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Bắt đầu huấn luyện" }).click();

  await expect(page.getByRole("heading", { name: "Huấn Luyện", exact: true })).toBeVisible({ timeout: 20_000 });
  const huy = page.getByRole("button", { name: /Hu(ỷ|ủy) huấn luyện/ });
  await expect(huy).toBeVisible({ timeout: 15_000 });
  await huy.click();

  expect(biChan, "khong duoc co loi quyen trong luong huan luyen").toEqual([]);
  await expect(page.getByText(/quyền admin|quyền quản trị|Admin privileges/i)).toHaveCount(0);
});

test("3. Thành viên dùng model của riêng mình trong Realtime, người khác không thấy", async ({ page, browser }) => {
  test.setTimeout(120_000);
  await dangNhap(page, "iso_user_a", "default");
  await page.goto("/training");
  const toi = await goiApi(page, "GET", "/api/v1/auth/me");
  const ds = await goiApi(page, "GET", "/api/v1/training/jobs");
  const cuaToi = ds.json.find((j: { auth_user_id: string; status: string }) => j.auth_user_id === toi.json.id && j.status === "completed");
  expect(cuaToi, "phai co job hoan thanh cua chinh minh").toBeTruthy();

  await page.locator(`tr[title="Job ${cuaToi.id}"]`).click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Đưa vào Realtime" }).click();
  await expect(page.getByText(/Đã đưa vào Realtime lúc/)).toBeVisible({ timeout: 30_000 });

  const models = await goiApi(page, "GET", "/api/v1/realtime/models");
  const cuaRieng = models.json.find((m: { id: string }) => m.id.includes("~"));
  expect(cuaRieng, JSON.stringify(models.json)).toBeTruthy();
  const khung = Array.from({ length: 60 }, () => Array(126).fill(0));
  const toiGoi = await goiApi(page, "POST", "/api/v1/realtime/predict", { model_id: cuaRieng.id, frames: khung });
  expect(toiGoi.status).toBe(200);

  const nguoiKhac = await (await browser.newContext()).newPage();
  await dangNhap(nguoiKhac, "iso_user_b", "default");
  const hoKhong = await goiApi(nguoiKhac, "GET", "/api/v1/realtime/models");
  expect(hoKhong.json.map((m: { id: string }) => m.id)).not.toContain(cuaRieng.id);
  const hoGoi = await goiApi(nguoiKhac, "POST", "/api/v1/realtime/predict", { model_id: cuaRieng.id, frames: khung });
  expect(hoGoi.status).toBe(404);
});

test("4. Model riêng chỉ chủ thấy; muốn dùng chung thì quản trị viên duyệt", async ({ page, browser }) => {
  test.setTimeout(180_000);
  await dangNhap(page, "iso_user_a", "default");
  const toi = await goiApi(page, "GET", "/api/v1/auth/me");
  const ds = await goiApi(page, "GET", "/api/v1/training/jobs");
  const job = ds.json.find((j: { auth_user_id: string; status: string; config: { personal: boolean } }) =>
    j.auth_user_id === toi.json.id && j.status === "completed" && j.config.personal);
  expect(job, "phai co job rieng da hoan thanh").toBeTruthy();

  const khac = await (await browser.newContext()).newPage();
  await dangNhap(khac, "iso_user_b", "default");
  expect((await goiApi(khac, "GET", `/api/v1/training/jobs/${job.id}`)).status).toBe(404);
  const dsKhac = await goiApi(khac, "GET", "/api/v1/training/jobs");
  expect(dsKhac.json.map((j: { id: string }) => j.id)).not.toContain(job.id);
  expect((await goiApi(khac, "POST", `/api/v1/training/jobs/${job.id}/cancel`)).status).toBe(404);
  expect((await goiApi(khac, "DELETE", `/api/v1/training/jobs/${job.id}`)).status).toBe(404);

  const quanTri = await (await browser.newContext()).newPage();
  await dangNhap(quanTri, "iso_admin_a", "default");
  expect((await goiApi(quanTri, "GET", `/api/v1/training/jobs/${job.id}`)).status, "chua de nghi thi quan tri chua thay").toBe(404);

  await page.goto("/training");
  await page.locator(`tr[title="Job ${job.id}"]`).click();
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "Đề nghị dùng chung" }).click();
  await expect(page.getByText(/đang chờ quản trị viên xét duyệt/)).toBeVisible({ timeout: 20_000 });

  // Đọc nhiều lượt: hai tiến trình backend, mỗi tiến trình một cache.
  for (let i = 0; i < 6; i++) {
    expect((await goiApi(khac, "GET", `/api/v1/training/jobs/${job.id}`)).status).toBe(404);
    expect((await goiApi(quanTri, "GET", `/api/v1/training/jobs/${job.id}`)).status).toBe(200);
  }

  const tuChoi = await goiApi(quanTri, "POST", `/api/v1/training/jobs/${job.id}/review/reject`, { reason: "chua on" });
  expect(tuChoi.status, JSON.stringify(tuChoi.json)).toBe(200);
  expect((await goiApi(quanTri, "GET", `/api/v1/training/jobs/${job.id}`)).status, "tu choi xong la rieng lai").toBe(404);
  const conDung = await goiApi(page, "GET", `/api/v1/training/jobs/${job.id}`);
  expect(conDung.json.config.personal).toBe(true);

  expect((await goiApi(page, "POST", `/api/v1/training/jobs/${job.id}/review`)).status).toBe(200);
  await quanTri.goto("/training");
  await quanTri.locator(`tr[title="Job ${job.id}"]`).click();
  quanTri.once("dialog", (d) => d.accept());
  await quanTri.getByRole("button", { name: "Duyệt dùng chung" }).click();
  await expect.poll(async () => (await goiApi(khac, "GET", `/api/v1/training/jobs/${job.id}`)).status,
    { timeout: 30_000 }).toBe(200);
  const daDuyet = await goiApi(quanTri, "GET", `/api/v1/training/jobs/${job.id}`);
  expect(daDuyet.json.config.personal).toBe(false);
  expect(daDuyet.json.config.review_requested_at).toBeNull();
  const models = await goiApi(khac, "GET", "/api/v1/realtime/models");
  expect(models.json.map((m: { id: string }) => m.id)).toContain("hoa-de");
});

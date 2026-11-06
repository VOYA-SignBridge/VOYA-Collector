import { test as goc, expect, type Page } from "@playwright/test";

export { expect };

const API = /^\/(api|auth|classes|dataset|upload\/(camera|video))/;
const TOI_DA_KY_TU = 600;
const BI_MAT = /("?(?:password|token|secret|csrf|api_key)\w*"?\s*:\s*)"[^"]*"/gi;

/** `test` của dự án: tự ghi mọi phản hồi API của ca vào báo cáo. */
export const test = goc.extend<{ ghiApi: void }>({
  ghiApi: [async ({ page }, use, testInfo) => {
    const ds: Record<string, unknown>[] = [];
    const cho: Promise<void>[] = [];
    page.on("response", (r) => {
      const url = new URL(r.url());
      if (!API.test(url.pathname)) return;
      cho.push((async () => {
        const loai = r.headers()["content-type"] ?? "";
        const than = /json|text/.test(loai) ? await r.text().catch(() => "") : `<${loai}>`;
        ds.push({
          phuong_thuc: r.request().method(),
          duong_dan: url.pathname + url.search,
          gui: (r.request().postData() ?? "").replace(BI_MAT, '$1"***"').slice(0, 300),
          ma: r.status(),
          tra_ve: than.replace(BI_MAT, '$1"***"').slice(0, TOI_DA_KY_TU),
        });
      })());
    });
    await use();
    await Promise.all(cho);
    await testInfo.attach("ket-qua-api", { body: JSON.stringify(ds), contentType: "application/json" });
  }, { auto: true }],
});

/** Mật khẩu của tài khoản do `scripts/seed_isolation_fixture.py` gieo. */
const MAT_KHAU = "IsoProbe!2026";

/** Gọi API bằng phiên của trang, kèm CSRF như axiosClient. */
export async function goiApi(page: Page, method: string, url: string, body?: unknown) {
  return page.evaluate(async ({ method, url, body }) => {
    const csrf = document.cookie.match(/voya_csrf=([^;]+)/)?.[1] ?? "";
    const res = await fetch(url, {
      method,
      credentials: "include",
      headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return { status: res.status, json: await res.json().catch(() => null) };
  }, { method, url, body });
}

/** Đăng nhập rồi chuyển sang tổ chức cần làm việc. */
export async function dangNhap(page: Page, ten: string, tenant: string) {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập hoặc email").fill(ten);
  await page.getByLabel("Mật khẩu").fill(MAT_KHAU);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  await expect(page.getByRole("banner").getByRole("button", { name: "Đăng xuất" })).toBeVisible({ timeout: 20_000 });
  const r = await goiApi(page, "POST", "/api/v1/tenants/switch", { tenant_id: tenant });
  expect(r.status, "chuyen to chuc").toBe(200);
}

import { test, expect, type Page } from "@playwright/test";

/**
 * Browser E2E for the five paths named in the thesis's own verification
 * limitation (Chapter 5, §5.7/§8.4): "the browser path is manually verified
 * and is not covered by a Playwright regression suite." These five specs
 * are that regression suite.
 *
 * Runs against the deployed stack (docker compose, nginx on localhost), with
 * a real recorded sign-language clip fed in as a fake camera device
 * (see playwright.config.ts) so MediaPipe Hands genuinely detects a hand
 * rather than running against a blank/synthetic frame.
 *
 * Requires ADMIN_USERNAME / ADMIN_PASSWORD in the environment (the same
 * credentials the deployed backend was seeded with — see .env).
 */

const ADMIN_USERNAME = process.env.ADMIN_USERNAME;
const ADMIN_PASSWORD = process.env.ADMIN_PASSWORD;

test.beforeAll(() => {
  if (!ADMIN_USERNAME || !ADMIN_PASSWORD) {
    throw new Error(
      "ADMIN_USERNAME / ADMIN_PASSWORD must be set in the environment running " +
        "these tests (they are not committed to the repo)."
    );
  }
});

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Tên đăng nhập hoặc email").fill(ADMIN_USERNAME!);
  await page.getByLabel("Mật khẩu").fill(ADMIN_PASSWORD!);
  await page.getByRole("button", { name: "Đăng nhập" }).click();
  // LoginPage swaps to a full-screen LoadingScreen, then the router lands on
  // the destination route. The header's "Đăng xuất" button only renders for an
  // authenticated session (guests get "Đăng nhập"), so it is the concrete,
  // page-independent signal that the token round-trip actually succeeded.
  // (The old "Đã đăng nhập" badge was replaced by the working-context chip in
  // the 09/2026 UX pass.)
  await expect(page.getByRole("banner").getByRole("button", { name: "Đăng xuất" })).toBeVisible({ timeout: 15_000 });
}

test.describe("Golden-path browser E2E", () => {
  test("1. login redirects into an authenticated workspace", async ({ page }) => {
    await login(page);

    // The sidebar is collapsed off-canvas on load (translated out of view, so
    // Playwright still reports its links "visible" but cannot click them).
    // Open it through the header toggle, then follow the real link.
    await page.getByRole("button", { name: "Mở hoặc đóng thanh điều hướng" }).click();
    await page.getByRole("link", { name: "Huấn luyện model" }).click();
    await expect(page.getByRole("heading", { name: "Huấn Luyện Mô Hình", exact: true })).toBeVisible();
    // Confirms the session is real (backend accepted the token), not just a
    // client-side route change: the history list is fetched from the API.
    await expect(page.getByRole("button", { name: "Bắt đầu huấn luyện mới" })).toBeVisible();
  });

  test("2. select a partition and submit a training job", async ({ page }) => {
    await login(page);
    await page.goto("/training");

    await page.getByRole("button", { name: "Bắt đầu huấn luyện mới" }).click();

    // The wizard on this branch runs 1 Dữ Liệu → 2 Chọn Dialect → 3 Chia Tập
    // → 4 Tăng Cường → 5 Cấu Hình → 6 Huấn Luyện → 7 Kết Quả (the upstream
    // feature-v2 suite assumed a dialect-first order with a separate
    // "Chuẩn Bị Dữ Liệu" step that was never merged here).

    // Step 1 — Dữ Liệu: dataset stats, informational.
    await expect(page.getByRole("heading", { name: "Dữ Liệu", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Tiếp theo →" }).click();

    // Step 2 — Chọn Dialect. Hòa Đê already has a published deployment split.
    await expect(page.getByRole("heading", { name: "Chọn Dialect", exact: true })).toBeVisible();
    // Dialect cards are named by slug (what samples.csv and the model_id use).
    await page.getByRole("button", { name: "hoa-de", exact: true }).click();
    await page.getByRole("button", { name: "Tiếp theo →" }).click();

    // Step 3 — Chia Tập (informational).
    await expect(page.getByRole("heading", { name: "Chia Tập", exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Tiếp theo →" })).toBeEnabled({ timeout: 20_000 });
    await page.getByRole("button", { name: "Tiếp theo →" }).click();

    // Step 4 — Tăng Cường (informational).
    await expect(page.getByRole("heading", { name: "Tăng Cường", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Tiếp theo →" }).click();

    // Step 5 — Cấu Hình. Default hyperparameters are fine: this test verifies
    // the submit → persist → dispatch → monitor path, not a full training run.
    await expect(page.getByRole("heading", { name: "Cấu Hình", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Bắt đầu huấn luyện" }).click();

    // Step 6 — Huấn Luyện: a persisted job now exists and the trainer queue
    // picked it up (or it's still queued) — either way a cancel control is
    // live, proving the backend round-trip succeeded end to end.
    await expect(page.getByRole("heading", { name: "Huấn Luyện", exact: true })).toBeVisible({
      timeout: 20_000,
    });
    // "Huỷ" (u + combining hook) in the UI — match either Unicode form.
    const cancelButton = page.getByRole("button", { name: /Hu(ỷ|ủy) huấn luyện/ });
    await expect(cancelButton).toBeVisible({ timeout: 15_000 });

    // Clean up: cancel immediately rather than occupying the single GPU
    // trainer slot for a full run neither this test nor the thesis needs.
    await cancelButton.click();
  });

  test("3. open a completed job and see its evaluation", async ({ page }) => {
    await login(page);
    await page.goto("/training");

    const completedRow = page.locator("tr", { has: page.getByText("Hoàn thành") }).first();
    await expect(completedRow).toBeVisible({ timeout: 15_000 });
    await completedRow.click();

    // A completed job opens straight to Step 7 — Kết Quả.
    await expect(page.getByRole("heading", { name: "Kết Quả", exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Huấn luyện hoàn tất" })).toBeVisible();
    // The F1 tile is real evaluation data returned by
    // GET /training/jobs/{id}/evaluation, not a placeholder.
    await expect(page.getByText("Điểm F1", { exact: true })).toBeVisible();
  });

  test("4. candidate trial returns a live prediction from the camera", async ({ page }) => {
    await login(page);
    await page.goto("/training");

    const completedRow = page.locator("tr", { has: page.getByText("Hoàn thành") }).first();
    await expect(completedRow).toBeVisible({ timeout: 15_000 });
    await completedRow.click();

    await page.getByRole("button", { name: /Kiểm tra model \(Realtime\)/ }).click();

    // The fake camera feeds a real recorded sign-language clip (see
    // playwright.config.ts), so MediaPipe should detect a hand and the
    // job-scoped candidate-trial endpoint should return a real label.
    await expect(page.getByText("Độ tin cậy:")).toBeVisible({ timeout: 90_000 });
  });

  test("5. real-time recognition returns a live prediction", async ({ page }) => {
    await login(page);
    await page.goto("/realtime");

    await expect(page.getByText("Kết quả nhận diện")).toBeVisible();
    // Nothing is pre-selected on load — the two <select>s aren't <label
    // for>-linked, so target them by DOM order (language, then model) as
    // coded in RealtimeRuntime.tsx. Picking a model flips autoStart on.
    const selects = page.locator("select");
    await selects.nth(0).selectOption({ label: "Tiếng Việt" });
    // Picking the language may auto-select the first model and start the
    // camera at once, which disables both selects while frames are in
    // flight; only pick a model explicitly when the select is still open.
    const modelSelect = selects.nth(1);
    try {
      await modelSelect.selectOption({ label: "Hòa đê (hoa-de)" }, { timeout: 10_000 });
    } catch {
      // Already running with a model picked — the assertion below is what matters.
      await expect(page.getByRole("button", { name: "Dừng nhận diện" })).toBeVisible();
    }

    await expect(page.getByText("Độ tin cậy:")).toBeVisible({ timeout: 90_000 });
  });
});

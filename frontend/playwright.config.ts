import { defineConfig, devices } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Golden-path browser E2E for the training-and-recognition subsystem.
// Runs against the deployed stack (nginx on localhost) rather than a
// separate dev server: it is meant to verify the same build users get,
// not a hot-reloaded source tree.
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FAKE_VIDEO = path.resolve(__dirname, "tests-e2e/fixtures/sample-hand.y4m");

export default defineConfig({
  testDir: "./tests-e2e",
  // Candidate trial / real-time recognition need a real 60-frame buffer to
  // fill from the fake camera before a prediction request fires.
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false, // shares one login session / one GPU trainer slot
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "playwright-report" }]],
  use: {
    // NGINX_HTTP_PORT in .env — 80 now that the port-80 Windows service
    // (IIS) that used to squat it is disabled.
    baseURL: process.env.E2E_BASE_URL || "http://localhost",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        permissions: ["camera"],
        launchOptions: {
          args: [
            "--use-fake-device-for-media-stream",
            "--use-fake-ui-for-media-stream",
            `--use-file-for-fake-video-capture=${FAKE_VIDEO}`,
          ],
        },
      },
    },
  ],
});

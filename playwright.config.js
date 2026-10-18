import { defineConfig, devices } from "@playwright/test";

// RoadGuard rider-app E2E. These tests drive the real ES-module frontend against the
// real ASGI server, but every `/api/v1/*` call is intercepted in the browser and
// labelled `mock` — no OSRM/Nominatim/network dependency, no real model run. The point
// is the FRONTEND nav state machine + layout, not the provider (that is covered offline
// by tests/test_api_routes.py and by the live benchmark script).
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"]],
  timeout: 30_000,
  use: {
    baseURL: "http://127.0.0.1:8181",
    trace: "off",
    headless: true,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command:
      "python -m uvicorn app.main:app --host 127.0.0.1 --port 8181",
    cwd: ".",
    env: {
      ROADGUARD_ENV: "test",
      ROADGUARD_DB_PATH: "data/e2e_playwright.sqlite3",
      ROADGUARD_REQUIRE_MODEL: "false",
    },
    url: "http://127.0.0.1:8181/",
    reuseExistingServer: !process.env.CI,
    timeout: 30_000,
  },
});

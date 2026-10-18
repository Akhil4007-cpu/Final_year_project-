import { test, expect } from "@playwright/test";
import { installAdminMocks } from "./_harness.js";

// Admin-console E2E. Every /api/v1/* response is MOCKED and labelled `mock`. These verify
// the console's auth/role gating, tab switching, moderation wiring and diagnostics render —
// the server-side role gate itself is already covered by tests/test_api.py.

async function openAdmin(page, me) {
  const seen = await installAdminMocks(page.context(), { me });
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/admin");
  return { seen, errors };
}

async function loginAsAdmin(page) {
  await expect(page.locator("#login-view")).toBeVisible();
  await page.fill("#login-email", "admin@example.test");
  await page.fill("#login-password", "correcthorsebattery");
  await page.click("#login-submit");
  await expect(page.locator("#console-view")).toBeVisible();
}

test("signed-out boot shows the login gate, and admin login reveals the console (mock)", async ({ page }) => {
  const { seen, errors } = await openAdmin(page, "401");
  await expect(page.locator("#denied-view")).toBeHidden();
  await expect(page.locator("#console-view")).toBeHidden();
  await loginAsAdmin(page);
  await expect(page.locator("#tab-overview")).toBeVisible();
  await expect(page.locator("#overview-stats")).not.toContainText("Loading");
  // Login POST carried the identity/CSRF client header.
  expect(seen.loginClientHeader).toBe("web");
  expect(errors).toEqual([]);
});

test("non-admin role is denied the console", async ({ page }) => {
  await openAdmin(page, "rider");
  await expect(page.locator("#denied-view")).toBeVisible();
  await expect(page.locator("#console-view")).toBeHidden();
  await expect(page.locator("#login-view")).toBeHidden();
});

test("tab switching shows only the selected panel and renders the hazards list (mock)", async ({ page }) => {
  await openAdmin(page, "admin");
  await expect(page.locator("#console-view")).toBeVisible();
  await page.click('.admin-nav button[data-tab="hazards"]');
  await expect(page.locator("#tab-hazards")).toBeVisible();
  await expect(page.locator("#tab-overview")).toBeHidden();
  await expect(page.locator("#hazards-content")).toContainText("Deep pothole near the junction.");
  await expect(page.locator('.admin-nav button[data-tab="hazards"]')).toHaveAttribute("aria-current", "page");
});

test("moderating an open hazard posts the action + note and shows a confirmation toast (mock)", async ({ page }) => {
  const { seen } = await openAdmin(page, "admin");
  await page.click('.admin-nav button[data-tab="hazards"]');
  await expect(page.locator("#hazards-content")).toContainText("Deep pothole");
  await page.locator('#hazards-content button:has-text("Verify")').first().click();
  await expect(page.locator("#moderate-dialog")).toBeVisible();
  await expect(page.locator("#moderate-title")).toContainText("Verify hazard report");
  await page.fill("#moderate-note", "confirmed on the ground");
  await page.click("#moderate-submit");
  expect(seen.moderateMethod).toBe("POST");
  expect(seen.moderateBody).toMatchObject({ action: "verify", note: "confirmed on the ground" });
  await expect(page.locator("#toast")).toContainText("verified.");
  await expect(page.locator("#moderate-dialog")).toBeHidden();
});

test("system tab renders diagnostics from the mocked provider (mock)", async ({ page }) => {
  const { errors } = await openAdmin(page, "admin");
  await page.click('.admin-nav button[data-tab="system"]');
  await expect(page.locator("#tab-system")).toBeVisible();
  await expect(page.locator("#system-content")).toContainText("RoadGuard AI");
  expect(errors).toEqual([]);
});

import { test, expect } from "@playwright/test";
import {
  analyzePayload,
  buildGeometry,
  installGeolocation,
  installMocks,
  seedSettings,
} from "./_harness.js";

// All /api/v1/* responses here are MOCKED and labelled `mock` — this suite verifies the
// rider frontend's navigation state machine, layout, and alert-cue playback only.

const PTS = buildGeometry(8);

async function openApp(page, { analyze = "scored", authed = false, advisoryBand = null } = {}) {
  const seen = await installMocks(page.context(), { analyze: analyze === "scored" ? analyzePayload({ pts: PTS, advisoryBand }) : analyze, authed });
  await installGeolocation(page.context());
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await expect(page.locator("#search-input")).toBeVisible();
  await expect(page.locator("#gps-chip")).toBeVisible();
  return { seen, errors };
}

test("startup renders shell, map, GPS chip and search with no app JS errors", async ({ page }) => {
  const { errors } = await openApp(page);
  await expect(page.locator("#search-input")).toBeVisible();
  const chip = page.locator("#gps-chip");
  await expect(chip).toHaveAttribute("data-state", /off|locating|gps_unavailable|ready/);
  await expect(page.locator("#advisory-banner")).toBeHidden();
  await expect(page.locator("#nav-hud")).toBeHidden();
  // Only 401 on /auth/me (signed out) is expected; assert no uncaught JS errors.
  expect(errors).toEqual([]);
});

test("search → route analysis renders the scored route panel (mock)", async ({ page }) => {
  const { seen } = await openApp(page, { advisoryBand: "moderate" });
  await page.click("#locate-button");
  await page.evaluate((p) => window.__feedFix(p[0][0], p[0][1], 10), PTS);
  await page.fill("#search-input", "Charminar");
  await page.click("#search-submit");
  await expect(page.locator("#search-results .result-button")).toHaveCount(1);
  await page.click("#search-results .result-button");
  await expect(page.locator("#route-panel")).toBeVisible();
  await expect(page.locator("#route-eyebrow")).toContainText("OSRM");
  await expect(page.locator("#route-band")).toContainText("Moderate");
  await expect(page.locator("#route-score-value")).not.toHaveText("—");
  await expect(page.locator("#start-nav")).toBeEnabled();
  await expect(page.locator("#start-nav")).toContainText("Start advisories");

  // Prove the browser sent the CSRF/identity client header on the analyze POST.
  expect(seen.analyzeMethod).toBe("POST");
  expect(seen.analyzeClientHeader).toBe("web");
  expect(seen.analyzeBody).toMatchObject({
    origin: { lat: PTS[0][0], lon: PTS[0][1] },
    destination: { lat: 17.3616, lon: 78.4747 },
    alternatives: true,
  });
});

test("navigation lifecycle: start → arrive → trip summary", async ({ page }) => {
  await openApp(page, { advisoryBand: "moderate" });
  await page.click("#locate-button");
  // Single fix at the final vertex: nav begins with remaining ≈ 0 → destination reached.
  const end = PTS[PTS.length - 1];
  await page.evaluate(([lat, lon]) => window.__feedFix(lat, lon, 10), end);
  await page.fill("#search-input", "Charminar");
  await page.click("#search-submit");
  await page.click("#search-results .result-button");
  await expect(page.locator("#start-nav")).toBeEnabled();
  await page.click("#start-nav");
  await expect(page.locator("#nav-hud")).toBeVisible();
  await expect(page.locator("#route-panel")).toBeHidden();
  await expect(page.locator("#search-panel")).toBeHidden();
  await expect(page.locator("#nav-instruction")).toContainText("Destination reached");
  await page.click("#nav-end");
  await expect(page.locator("#trip-sheet")).toBeVisible();
  await expect(page.locator("#trip-content")).toContainText("Distance navigated");
});

test("live GPS → staged advisory cue fires, with assertive escalation on high band", async ({ page }) => {
  await seedSettings(page.context(), { visual: true, haptic: true, audio: false });
  await openApp(page, { advisoryBand: "high" });
  await page.click("#locate-button");
  // A single fix placed exactly on the curve vertex (index 3) → progress lands inside the
  // advisory window, ahead=false → "in the curve" → high band escalates to assertive.
  const curve = PTS[3];
  await page.evaluate(([lat, lon]) => window.__feedFix(lat, lon, 8), curve);
  await page.fill("#search-input", "Charminar");
  await page.click("#search-submit");
  await page.click("#search-results .result-button");
  await expect(page.locator("#start-nav")).toBeEnabled();
  await page.click("#start-nav");
  const banner = page.locator("#advisory-banner");
  await expect(banner).toBeVisible();
  await expect(banner).toHaveAttribute("data-band", "high");
  await expect(page.locator("#nav-instruction")).toContainText("Curve in progress");
  // assertive live region is populated only for high-band "in the curve now".
  await expect(page.locator("#alert-announce")).not.toHaveText("");
});

test("hazard report submits as unverified and shows the honest toast (mock, authed)", async ({ page }) => {
  await openApp(page, { authed: true });
  await page.click("#locate-button");
  await page.evaluate(([lat, lon]) => window.__feedFix(lat, lon, 10), PTS[0]);
  await page.click("#report-button");
  await expect(page.locator("#report-sheet")).toBeVisible();
  await page.selectOption("#report-category", "pothole");
  await page.fill("#report-description", "Deep pothole near the junction.");
  await page.click("#report-submit");
  await expect(page.locator("#toast")).toContainText("unverified");
  await expect(page.locator("#report-sheet")).toBeHidden();
});

test("insufficient evidence → never invents a route", async ({ page }) => {
  await openApp(page, { analyze: "insufficient" });
  await page.click("#locate-button");
  await page.evaluate(([lat, lon]) => window.__feedFix(lat, lon, 10), PTS[0]);
  await page.fill("#search-input", "Charminar");
  await page.click("#search-submit");
  await page.click("#search-results .result-button");
  await expect(page.locator("#route-panel")).toBeVisible();
  await expect(page.locator("#route-eyebrow")).toContainText("Route unavailable");
  await expect(page.locator("#route-title")).toContainText("No drivable route found");
  await expect(page.locator("#route-score-value")).toHaveText("Not scored");
  await expect(page.locator("#coverage-text")).toContainText("No fallback route is invented.");
  await expect(page.locator("#start-nav")).toContainText("Retry");
});

test("provider failure → graceful unavailable state, no crash", async ({ page }) => {
  const { errors } = await openApp(page, { analyze: "provider" });
  await page.click("#locate-button");
  await page.evaluate(([lat, lon]) => window.__feedFix(lat, lon, 10), PTS[0]);
  await page.fill("#search-input", "Charminar");
  await page.click("#search-submit");
  await page.click("#search-results .result-button");
  await expect(page.locator("#route-title")).toContainText("Routing provider unavailable");
  await expect(page.locator("#comparison-note")).toBeVisible();
  await expect(page.locator("#search-input")).toBeVisible();
  expect(errors).toEqual([]);
});

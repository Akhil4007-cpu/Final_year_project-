import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { analyzePayload, installGeolocation, installMocks, seedSettings } from "./_harness.js";

// Rider-UI screenshots for the Review 2 pack. Every /api/v1/* response here is MOCKED
// and labelled `mock`: the shapes, bands and advisories are the harness's, NOT a live
// OSRM result. What is real is the shipped frontend, rendered at 390 px width.
// The live pipeline output is recorded separately in docs/real_route_check.json
// (labelled `live`, no screenshots — a live run cannot be pinned for CI).
// Captures freeze CSS animations: `pulse`/`alert-pulse` are infinite, so without
// `animations: "disabled"` every run caught a different phase and the PNGs were not
// reproducible byte-for-byte (measured: 45,593 vs 45,626 bytes across two runs).

const OUT_DIR = path.resolve("docs/screenshots");

// Three distinct route shapes so the map, panel and advisory views differ.
const ROUTES = {
  overview: {
    file: "rider-1-route-overview-390.png",
    pts: [
      [17.42, 78.45],
      [17.418, 78.451],
      [17.416, 78.455],
      [17.413, 78.459],
      [17.409, 78.461],
      [17.405, 78.46],
      [17.401, 78.457],
      [17.397, 78.456],
    ],
    band: "moderate",
    speedKmh: null,
  },
  curve: {
    file: "rider-2-advisory-moderate-390.png",
    pts: [
      [17.43, 78.44],
      [17.428, 78.44],
      [17.426, 78.441],
      [17.424, 78.445],
      [17.421, 78.449],
      [17.418, 78.45],
      [17.415, 78.449],
      [17.412, 78.446],
    ],
    band: "moderate",
    speedKmh: 45,
  },
  sharp: {
    file: "rider-3-advisory-high-speed-above-390.png",
    pts: [
      [17.38, 78.47],
      [17.377, 78.47],
      [17.374, 78.471],
      [17.371, 78.476],
      [17.368, 78.481],
      [17.365, 78.482],
      [17.362, 78.48],
      [17.359, 78.477],
    ],
    band: "high",
    speedKmh: 90,
  },
};

async function openAndAnalyse(page, route) {
  await installMocks(page.context(), {
    analyze: analyzePayload({ pts: route.pts, advisoryBand: route.band }),
  });
  await installGeolocation(page.context());
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto("/");
  await expect(page.locator("#search-input")).toBeVisible();
  await page.click("#locate-button");
  await page.evaluate(([lat, lon]) => window.__feedFix(lat, lon, 10), route.pts[1]);
  await page.fill("#search-input", "Charminar");
  await page.click("#search-submit");
  await page.click("#search-results .result-button");
  await expect(page.locator("#route-panel")).toBeVisible();
  // Let the "Requesting your location…" toast expire so it does not sit on the capture.
  await expect(page.locator("#toast")).toBeHidden({ timeout: 8000 });
  return errors;
}

async function settleBanner(page) {
  const banner = page.locator("#advisory-banner");
  await expect(banner).toBeVisible();
  // The advisory has a 220 ms rise (opacity) animation; capture only the settled frame.
  await expect(banner).toHaveCSS("opacity", "1");
}

// Leaflet recentres on the rider with its own JS pan animation, which
// `animations: "disabled"` does not touch (it only freezes CSS animations). A fixed sleep
// was not enough — the map pane was still moving when some captures fired, so the same
// test produced different pixels over the map on consecutive runs. Poll the pane's
// transform until it stops changing instead.
async function settleMap(page) {
  await page.waitForFunction(
    () => {
      const pane = document.querySelector(".leaflet-map-pane");
      if (!pane) return true;
      const state = (window.__mapSettle = window.__mapSettle || { last: null, stable: 0 });
      const now = getComputedStyle(pane).transform;
      state.stable = now === state.last ? state.stable + 1 : 0;
      state.last = now;
      return state.stable >= 6;
    },
    undefined,
    { timeout: 15000, polling: 100 },
  );
}

test.beforeAll(() => {
  mkdirSync(OUT_DIR, { recursive: true });
});

test("route 1 at 390 px: analysed route panel", async ({ page }) => {
  const route = ROUTES.overview;
  const errors = await openAndAnalyse(page, route);
  await expect(page.locator("#route-band")).toContainText("Moderate");
  await settleMap(page);
  await page.screenshot({ path: path.join(OUT_DIR, route.file), fullPage: true, animations: "disabled" });
  expect(errors).toEqual([]);
  expect(existsSync(path.join(OUT_DIR, route.file))).toBe(true);
});

test("routes 2 and 3 at 390 px: navigation advisory states", async ({ page }) => {
  await seedSettings(page.context(), { visual: true, haptic: true, audio: false });
  const errors = [];

  const mid = ROUTES.curve;
  errors.push(...(await openAndAnalyse(page, mid)));
  await page.click("#start-nav");
  await page.evaluate(
    ([lat, lon, speed]) => window.__feedFix(lat, lon, 8, 0, speed),
    [mid.pts[3][0], mid.pts[3][1], mid.speedKmh],
  );
  await expect(page.locator("#advisory-banner")).toHaveAttribute("data-band", "moderate");
  await settleBanner(page);
  await settleMap(page);
  await page.screenshot({ path: path.join(OUT_DIR, mid.file), fullPage: true, animations: "disabled" });

  const sharp = ROUTES.sharp;
  errors.push(...(await openAndAnalyse(page, sharp)));
  await page.click("#start-nav");
  await page.evaluate(
    ([lat, lon, speed]) => window.__feedFix(lat, lon, 8, 0, speed),
    [sharp.pts[3][0], sharp.pts[3][1], sharp.speedKmh],
  );
  await expect(page.locator("#advisory-banner")).toHaveAttribute("data-band", "high");
  await expect(page.locator("#advisory-speed")).toHaveAttribute("data-status", "above");
  await settleBanner(page);
  await settleMap(page);
  await page.screenshot({ path: path.join(OUT_DIR, sharp.file), fullPage: true, animations: "disabled" });

  expect(errors).toEqual([]);
  for (const route of [mid, sharp]) {
    expect(existsSync(path.join(OUT_DIR, route.file))).toBe(true);
  }
});

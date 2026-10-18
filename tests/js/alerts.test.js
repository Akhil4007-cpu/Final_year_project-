import { test } from "node:test";
import assert from "node:assert/strict";

import {
  alertIntensity,
  alertStage,
  cuePattern,
  detectCapabilities,
  lateralDemandG,
  normaliseSpeedKmh,
  planAlert,
  speedAwareness,
} from "../../app/web/alerts.js";

test("detectCapabilities: android-like device has haptic + audio + notify", () => {
  const caps = detectCapabilities({
    hasVibrate: true,
    AudioContext: function () {},
    Notification: function () {},
  });
  assert.equal(caps.visual, true);
  assert.equal(caps.haptic, true);
  assert.equal(caps.audio, true);
  assert.equal(caps.notify, true);
});

test("detectCapabilities: iOS Safari has no vibration but has audio", () => {
  const caps = detectCapabilities({
    hasVibrate: false,
    webkitAudioContext: function () {},
    Notification: false,
  });
  assert.equal(caps.haptic, false);
  assert.equal(caps.audio, true);
  assert.equal(caps.notify, false);
});

test("alertIntensity escalates with band and proximity", () => {
  assert.equal(alertIntensity("low", true), "low");
  assert.equal(alertIntensity("moderate", true), "low");
  assert.equal(alertIntensity("moderate", false), "medium");
  assert.equal(alertIntensity("high", true), "medium");
  assert.equal(alertIntensity("high", false), "high");
});

test("cuePattern is monotonic: higher intensity has >= pulses", () => {
  const low = cuePattern("low").vibrate.length;
  const med = cuePattern("medium").vibrate.length;
  const high = cuePattern("high").vibrate.length;
  assert.ok(low <= med && med <= high);
});

test("planAlert: full-capability device fires vibrate + audio when opted in", () => {
  const plan = planAlert({
    band: "high",
    ahead: false,
    settings: { visual: true, audio: true, haptic: true },
    capabilities: { visual: true, audio: true, haptic: true, notify: true },
  });
  assert.equal(plan.intensity, "high");
  assert.equal(plan.fired.haptic, true);
  assert.equal(plan.fired.audio, true);
  assert.equal(plan.assertive, true);
  assert.equal(plan.fallbacks.length, 0);
});

test("planAlert: iOS (no haptic) falls back to audio when audio is on", () => {
  const plan = planAlert({
    band: "moderate",
    ahead: false,
    settings: { visual: true, audio: true, haptic: true },
    capabilities: { visual: true, audio: true, haptic: false, notify: false },
  });
  assert.equal(plan.fired.haptic, false);
  assert.equal(plan.fired.audio, true); // fallback kept the rider informed
  assert.ok(plan.fallbacks.some((f) => f.from === "haptic" && f.to === "audio"));
});

test("planAlert: iOS with audio off degrades haptic to visual-only, not silence", () => {
  const plan = planAlert({
    band: "high",
    ahead: false,
    settings: { visual: true, audio: false, haptic: true },
    capabilities: { visual: true, audio: true, haptic: false, notify: false },
  });
  assert.equal(plan.fired.haptic, false);
  assert.equal(plan.fired.visual, true);
  assert.equal(plan.fired.audio, false); // audio was not opted in
  assert.ok(plan.fallbacks.some((f) => f.to === "visual"));
});

test("planAlert: reduced motion disables firing the visual emphasis cue", () => {
  const plan = planAlert({
    band: "moderate",
    ahead: true,
    settings: { visual: true, audio: false, haptic: true },
    capabilities: { visual: true, audio: false, haptic: true, notify: false },
    reducedMotion: true,
  });
  assert.equal(plan.channels.visual, true); // banner still shows
  assert.equal(plan.fired.visual, false); // but no flashing
  assert.ok(plan.fallbacks.some((f) => f.reason === "reduced-motion"));
});

test("planAlert: audio unavailable falls back to visual and records reason", () => {
  const plan = planAlert({
    band: "high",
    ahead: true,
    settings: { visual: true, audio: true, haptic: false },
    capabilities: { visual: true, audio: false, haptic: false, notify: false },
  });
  assert.equal(plan.fired.audio, false);
  assert.ok(plan.fallbacks.some((f) => f.from === "audio" && f.reason === "no-audio-support"));
});

test("planAlert: default settings (audio off) never fire audio", () => {
  const plan = planAlert({
    band: "high",
    ahead: false,
    settings: { visual: true, audio: false, haptic: true },
    capabilities: { visual: true, audio: true, haptic: true, notify: true },
  });
  assert.equal(plan.fired.audio, false);
});

test("alertStage toggles between approach and in_curve", () => {
  assert.equal(alertStage(true), "approach");
  assert.equal(alertStage(false), "in_curve");
});

/* ------------------------------------------------ speed-aware advisory note */

test("normaliseSpeedKmh: only genuine measurements survive", () => {
  assert.equal(normaliseSpeedKmh(null), null);
  assert.equal(normaliseSpeedKmh(undefined), null);
  assert.equal(normaliseSpeedKmh(""), null);
  assert.equal(normaliseSpeedKmh("abc"), null);
  assert.equal(normaliseSpeedKmh(Number.NaN), null);
  assert.equal(normaliseSpeedKmh(-5), null);
  assert.equal(normaliseSpeedKmh(300), null); // above the 270 km/h plausibility ceiling
  assert.equal(normaliseSpeedKmh(0), 0); // stationary is a real measurement
  assert.equal(normaliseSpeedKmh(45), 45);
});

test("lateralDemandG: v²/R expressed in g, null instead of a silent zero", () => {
  // 45 km/h = 12.5 m/s; R = 50 m → a = 3.125 m/s² → 0.3186 g
  const demand = lateralDemandG(45, 50);
  assert.ok(demand !== null && Math.abs(demand - 3.125 / 9.80665) < 1e-9);
  assert.equal(lateralDemandG(45, null), null);
  assert.equal(lateralDemandG(45, 0), null);
  assert.equal(lateralDemandG(null, 50), null);
  assert.equal(lateralDemandG(0, 50), 0);
});

test("speedAwareness: unmeasured speed discloses the assumed band", () => {
  const note = speedAwareness({ speed_kmh: null, radius_m: 50, scored_speed_kmh: 45 });
  assert.equal(note.status, "speed_unavailable");
  assert.equal(note.demand_g, null);
  assert.match(note.message, /not measured/);
  assert.ok(note.message.includes("Scored at the 45 km/h band"));
});

test("speedAwareness: implausible speed is treated as unmeasured, not as 0 km/h", () => {
  const note = speedAwareness({ speed_kmh: 400, radius_m: 50, scored_speed_kmh: 45 });
  assert.equal(note.status, "speed_unavailable");
});

test("speedAwareness: above-band speed raises the reported lateral demand", () => {
  const note = speedAwareness({ speed_kmh: 90, radius_m: 100, scored_speed_kmh: 45 });
  assert.equal(note.status, "above");
  // (25 m/s)²/100 ÷ g vs (12.5 m/s)²/100 ÷ g → ratio exactly 4
  assert.ok(Math.abs(note.ratio - 4) < 1e-9);
  assert.ok(Math.abs(note.demand_g - 6.25 / 9.80665) < 1e-9);
  assert.ok(note.message.includes("90 km/h"));
  assert.match(note.message, /g lateral/);
});

test("speedAwareness: below-band and matching speeds are labelled as such", () => {
  const below = speedAwareness({ speed_kmh: 30, radius_m: 100, scored_speed_kmh: 45 });
  assert.equal(below.status, "below");
  assert.ok(Math.abs(below.ratio - (30 / 45) ** 2) < 1e-9);
  const matching = speedAwareness({ speed_kmh: 45, radius_m: 100, scored_speed_kmh: 45 });
  assert.equal(matching.status, "matching");
  assert.ok(Math.abs(matching.ratio - 1) < 1e-9);
  // just under the mismatch threshold stays "matching"
  assert.equal(speedAwareness({ speed_kmh: 48.2, radius_m: 100, scored_speed_kmh: 45 }).status, "matching");
  assert.equal(speedAwareness({ speed_kmh: 49, radius_m: 100, scored_speed_kmh: 45 }).status, "above");
});

test("speedAwareness: missing radius falls back and says the band was kept", () => {
  const note = speedAwareness({ speed_kmh: 70, radius_m: null, scored_speed_kmh: 45 });
  assert.equal(note.status, "radius_unavailable");
  assert.match(note.message, /No reliable mapped radius/);
  assert.ok(note.message.includes("stayed on the 45 km/h band"));
});

test("speedAwareness: never emits a safe-speed instruction or an accident claim", () => {
  const cases = [
    { speed_kmh: null, radius_m: 50, scored_speed_kmh: 45 },
    { speed_kmh: 120, radius_m: 40, scored_speed_kmh: 45 },
    { speed_kmh: 20, radius_m: 40, scored_speed_kmh: 45 },
    { speed_kmh: 60, radius_m: null, scored_speed_kmh: null },
  ];
  for (const input of cases) {
    const text = speedAwareness(input).message.toLowerCase();
    assert.ok(!text.includes("safe"));
    assert.ok(!text.includes("speed limit"));
    assert.ok(!text.includes("recommended"));
    if (text.includes("accident probability")) assert.ok(text.includes("not an accident probability"));
  }
});

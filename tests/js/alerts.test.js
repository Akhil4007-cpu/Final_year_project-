import { test } from "node:test";
import assert from "node:assert/strict";

import {
  alertIntensity,
  alertStage,
  cuePattern,
  detectCapabilities,
  planAlert,
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

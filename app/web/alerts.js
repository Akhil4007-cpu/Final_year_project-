// Staged-alert decision logic for the rider app.
//
// This module is intentionally DOM- and browser-global-free: every function takes
// plain values and returns plain values so it can be unit-tested with `node --test`
// without a browser or an npm toolchain. The DOM glue in app.js feeds real browser
// capability flags and user settings in here and plays back the returned plan.

// The advisory banner itself is always shown; these channels are the *extra* cues.
export const CHANNELS = ["visual", "audio", "haptic", "notify"];

// Detect which alert channels this device can actually deliver.
// `env` is injected (no globals) so it is testable: pass presence booleans.
export function detectCapabilities(env = {}) {
  const hasVibrate = Boolean(env.hasVibrate);
  const hasAudio = Boolean(env.AudioContext || env.webkitAudioContext);
  const hasNotify = Boolean(env.Notification);
  // iOS Safari exposes no navigator.vibrate; audio also needs a user gesture to
  // start (handled by the caller via an unlock), but the capability itself exists.
  return {
    visual: true, // a web page can always paint
    haptic: hasVibrate,
    audio: hasAudio,
    notify: hasNotify,
  };
}

// Map advisory band + approach distance to a single alert intensity.
// Pure: no side effects, deterministic.
export function alertIntensity(band, ahead) {
  if (band === "high") return ahead ? "medium" : "high";
  if (band === "moderate") return ahead ? "low" : "medium";
  // low / unrecognised bands never escalate past a gentle cue
  return "low";
}

// A haptic + audio pattern per intensity. Durations in ms, tones in Hz.
const CUE_PATTERNS = {
  low: { vibrate: [30], tones: [{ freq: 660, dur: 120 }] },
  medium: { vibrate: [60, 40, 60], tones: [{ freq: 740, dur: 130 }] },
  high: { vibrate: [120, 60, 120, 60, 160], tones: [{ freq: 880, dur: 160 }, { freq: 620, dur: 160 }] },
};

export function cuePattern(intensity) {
  return CUE_PATTERNS[intensity] || CUE_PATTERNS.low;
}

// Decide what to actually fire, honouring the user's per-channel settings, the
// detected capabilities, and graceful fallback when a channel is unavailable.
//
//   settings: { visual, audio, haptic } — booleans the rider toggled.
//   capabilities: output of detectCapabilities().
//   reducedMotion: boolean — suppresses visual flashing (banner text always shown).
//   intensity: output of alertIntensity().
//
// Returns { channels, fired, fallbacks, assertive, pattern }.
export function planAlert({ band, ahead, settings, capabilities, reducedMotion = false }) {
  const intensity = alertIntensity(band, ahead);
  const pattern = cuePattern(intensity);
  const fallbacks = [];

  const want = {
    visual: settings.visual !== false,
    audio: settings.audio === true,
    haptic: settings.haptic !== false,
  };

  const channels = { visual: false, audio: false, haptic: false };

  // Visual emphasis (banner flash / colour pulse). Reduced motion disables the
  // animation but never hides the advisory — banner text is separate.
  if (want.visual) {
    channels.visual = true;
    if (reducedMotion) fallbacks.push({ from: "visual-emphasis", to: "static-banner", reason: "reduced-motion" });
  }

  // Haptic: vibrate if requested and supported. iOS Safari has no vibrate → fall
  // back to an audible cue if audio is on, else record the silent degradation.
  if (want.haptic) {
    if (capabilities.haptic) {
      channels.haptic = true;
    } else {
      fallbacks.push({ from: "haptic", to: capabilities.audio && want.audio ? "audio" : "visual", reason: "no-vibration-support" });
      if (capabilities.audio && want.audio && !channels.audio) channels.audio = true;
    }
  }

  // Audio: only if the rider opted in (default off) and the device can play it.
  if (want.audio) {
    if (capabilities.audio) {
      channels.audio = true;
    } else {
      fallbacks.push({ from: "audio", to: "visual", reason: "no-audio-support" });
    }
  }

  const fired = {
    visual: channels.visual && !reducedMotion,
    audio: channels.audio,
    haptic: channels.haptic,
  };

  return {
    intensity,
    pattern,
    channels,
    fired,
    fallbacks,
    // High-band "in the curve now" is escalated to an assertive live region so
    // screen readers interrupt rather than queue the advisory.
    assertive: band === "high" && ahead === false,
  };
}

// Two distinct stages per advisory so a cue fires only when the rider crosses
// from "approaching" into "in the curve", not on every GPS fix.
export function alertStage(ahead) {
  return ahead ? "approach" : "in_curve";
}

// --- Speed-aware advisory note -------------------------------------------------
//
// The score/band itself is computed server-side at a *speed band* — either the one
// the rider picked or a road-class assumption (`speed_source` in the API payload).
// Neither is a measured rider speed. These functions add the missing comparison: if
// the device reports a ground speed, the same lateral-acceleration physics the
// baseline uses (a = v²/R) is re-evaluated at that speed and compared with the demand
// implied by the band the advisory was scored at.
//
// This is a geometry/physics comparison only. It deliberately never tells the rider
// what speed to ride at, is not a legal limit, and is not a probability of a crash
// (master plan R4).

export const STANDARD_GRAVITY = 9.80665; // m/s², used to report demand in g

// Same plausibility ceiling as the GPS jump-rejection gate in app.js (75 m/s).
export const MAX_PLAUSIBLE_SPEED_KMH = 270;

// Fractional distance from the scored band before the note is shown as a mismatch.
export const SPEED_MISMATCH_RATIO = 1.15;
export const SPEED_UNDERUSE_RATIO = 0.87;

// Reject anything the device did not genuinely measure: non-finite, negative or
// implausible speeds return null so callers can fall back and *say* they did.
// `null`/`undefined`/`""` are "not measured" — never a silent 0 km/h.
export function normaliseSpeedKmh(speed_kmh) {
  if (speed_kmh === null || speed_kmh === undefined || speed_kmh === "") return null;
  const value = Number(speed_kmh);
  if (!Number.isFinite(value) || value < 0 || value > MAX_PLAUSIBLE_SPEED_KMH) return null;
  return value;
}

// v²/R expressed in g. Null when either input is unusable (never a silent 0).
export function lateralDemandG(speed_kmh, radius_m) {
  const speed = normaliseSpeedKmh(speed_kmh);
  const radius = Number(radius_m);
  if (speed === null || !Number.isFinite(radius) || radius <= 0) return null;
  const metresPerSecond = speed / 3.6;
  return (metresPerSecond * metresPerSecond) / radius / STANDARD_GRAVITY;
}

// Build the speed-aware note for one advisory.
//
//   speed_kmh         — ground speed from the GPS fix (may be null/invalid)
//   radius_m          — section radius used by the advisory (may be null)
//   scored_speed_kmh  — the band the backend actually scored at (from the payload)
//
// Returns { status, message, demand_g, scored_demand_g, ratio }. `status` is one of
// "above" | "below" | "matching" | "speed_unavailable" | "radius_unavailable";
// the last two are the disclosed fallbacks, never a silent reuse of the band.
export function speedAwareness({ speed_kmh, radius_m, scored_speed_kmh }) {
  const measured = normaliseSpeedKmh(speed_kmh);
  const band = normaliseSpeedKmh(scored_speed_kmh);
  const bandText = band === null ? "an assumed speed band" : `the ${Math.round(band)} km/h band`;
  if (measured === null) {
    return {
      status: "speed_unavailable",
      demand_g: null,
      scored_demand_g: null,
      ratio: null,
      message: `Speed not measured by this device. Scored at ${bandText}, not your actual speed.`,
    };
  }
  const radius = Number(radius_m);
  const demand = lateralDemandG(measured, radius);
  if (demand === null) {
    return {
      status: "radius_unavailable",
      demand_g: null,
      scored_demand_g: null,
      ratio: null,
      message: `You are at ~${Math.round(measured)} km/h (GPS). No reliable mapped radius for this section, so the advisory stayed on ${bandText}.`,
    };
  }
  const scoredDemand = lateralDemandG(band, radius);
  const ratio = scoredDemand === null || scoredDemand === 0 ? null : demand / scoredDemand;
  const measuredText = `~${Math.round(measured)} km/h (GPS)`;
  let status = "matching";
  if (ratio !== null && ratio >= SPEED_MISMATCH_RATIO) status = "above";
  else if (ratio !== null && ratio <= SPEED_UNDERUSE_RATIO) status = "below";
  const scoredText = scoredDemand === null ? "n/a" : `${scoredDemand.toFixed(2)} g`;
  if (status === "above") {
    return {
      status,
      demand_g: demand,
      scored_demand_g: scoredDemand,
      ratio,
      message: `At ${measuredText} this ${Math.round(radius)} m curve needs ${demand.toFixed(2)} g lateral — ${ratio.toFixed(2)}× the ${scoredText} scored band. Geometry indicator, not an accident probability.`,
    };
  }
  if (status === "below") {
    return {
      status,
      demand_g: demand,
      scored_demand_g: scoredDemand,
      ratio,
      message: `At ${measuredText} this ${Math.round(radius)} m curve needs ${demand.toFixed(2)} g lateral — ${ratio.toFixed(2)}× the ${scoredText} scored band. Geometry indicator, not an accident probability.`,
    };
  }
  return {
    status,
    demand_g: demand,
    scored_demand_g: scoredDemand,
    ratio,
    message: `At ${measuredText} the lateral demand (${demand.toFixed(2)} g) matches ${bandText} this advisory was scored at.`,
  };
}

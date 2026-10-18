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

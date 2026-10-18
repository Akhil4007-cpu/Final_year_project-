// Rider alert-channel preferences, persisted in localStorage when available.
//
// normalizeSettings / mergeSettings are pure. loadSettings/saveSettings take an
// injected storage object (window.localStorage in the app, a plain map in tests)
// and never throw — storage can be absent (private mode) or contain bad JSON.

export const DEFAULT_SETTINGS = { visual: true, audio: false, haptic: true };

const KEYS = ["visual", "audio", "haptic"];
const STORAGE_KEY = "roadguard.alertSettings.v1";

function toBool(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}

// Coerce any object into a valid settings shape. Unknown/missing keys fall back to
// defaults; non-boolean values are discarded rather than trusted.
export function normalizeSettings(raw) {
  const base = { ...DEFAULT_SETTINGS };
  if (!raw || typeof raw !== "object") return base;
  for (const key of KEYS) {
    if (Object.prototype.hasOwnProperty.call(raw, key)) {
      base[key] = toBool(raw[key], base[key]);
    }
  }
  return base;
}

export function mergeSettings(current, patch) {
  return normalizeSettings({ ...current, ...(patch || {}) });
}

// Accepts an object with getItem/setItem (e.g. localStorage) or null/undefined.
export function loadSettings(storage) {
  if (!storage || typeof storage.getItem !== "function") {
    return { settings: { ...DEFAULT_SETTINGS }, persisted: false };
  }
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (raw == null) return { settings: { ...DEFAULT_SETTINGS }, persisted: false };
    return { settings: normalizeSettings(JSON.parse(raw)), persisted: true };
  } catch (error) {
    return { settings: { ...DEFAULT_SETTINGS }, persisted: false };
  }
}

export function saveSettings(storage, settings) {
  if (!storage || typeof storage.setItem !== "function") return false;
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(normalizeSettings(settings)));
    return true;
  } catch (error) {
    return false;
  }
}

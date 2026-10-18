import { test } from "node:test";
import assert from "node:assert/strict";

import {
  DEFAULT_SETTINGS,
  loadSettings,
  mergeSettings,
  normalizeSettings,
  saveSettings,
} from "../../app/web/settings.js";

function fakeStorage(initial = {}) {
  const map = new Map(Object.entries(initial));
  return {
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => map.set(k, v),
    _map: map,
  };
}

const KEY = "roadguard.alertSettings.v1";

test("normalizeSettings: keeps valid booleans", () => {
  const s = normalizeSettings({ visual: false, audio: true, haptic: false });
  assert.deepEqual(s, { visual: false, audio: true, haptic: false });
});

test("normalizeSettings: discards non-boolean and unknown keys", () => {
  const s = normalizeSettings({ visual: "yes", audio: 1, haptic: null, bogus: true });
  assert.equal(s.visual, DEFAULT_SETTINGS.visual);
  assert.equal(s.audio, DEFAULT_SETTINGS.audio);
  assert.equal(s.haptic, DEFAULT_SETTINGS.haptic);
  assert.equal("bogus" in s, false);
});

test("normalizeSettings: null / non-object returns defaults", () => {
  assert.deepEqual(normalizeSettings(null), DEFAULT_SETTINGS);
  assert.deepEqual(normalizeSettings("nope"), DEFAULT_SETTINGS);
});

test("mergeSettings: patch over current, still normalised", () => {
  const m = mergeSettings({ visual: true, audio: false, haptic: true }, { audio: true, junk: 5 });
  assert.deepEqual(m, { visual: true, audio: true, haptic: true });
});

test("loadSettings: empty storage returns defaults, persisted false", () => {
  const { settings, persisted } = loadSettings(fakeStorage());
  assert.deepEqual(settings, DEFAULT_SETTINGS);
  assert.equal(persisted, false);
});

test("loadSettings: reads a stored valid payload", () => {
  const storage = fakeStorage({ [KEY]: JSON.stringify({ visual: true, audio: true, haptic: false }) });
  const { settings, persisted } = loadSettings(storage);
  assert.equal(persisted, true);
  assert.equal(settings.audio, true);
  assert.equal(settings.haptic, false);
});

test("loadSettings: corrupt JSON degrades to defaults without throwing", () => {
  const storage = fakeStorage({ [KEY]: "{ not json" });
  const { settings, persisted } = loadSettings(storage);
  assert.deepEqual(settings, DEFAULT_SETTINGS);
  assert.equal(persisted, false);
});

test("loadSettings: a throwing getItem degrades to defaults", () => {
  const storage = { getItem() { throw new Error("SecurityError"); } };
  const { settings, persisted } = loadSettings(storage);
  assert.deepEqual(settings, DEFAULT_SETTINGS);
  assert.equal(persisted, false);
});

test("loadSettings: null storage (private mode) returns defaults", () => {
  const { settings, persisted } = loadSettings(null);
  assert.deepEqual(settings, DEFAULT_SETTINGS);
  assert.equal(persisted, false);
});

test("saveSettings: round-trips through load", () => {
  const storage = fakeStorage();
  const ok = saveSettings(storage, { visual: false, audio: true, haptic: true });
  assert.equal(ok, true);
  const { settings, persisted } = loadSettings(storage);
  assert.equal(persisted, true);
  assert.deepEqual(settings, { visual: false, audio: true, haptic: true });
});

test("saveSettings: sanitises before writing", () => {
  const storage = fakeStorage();
  saveSettings(storage, { visual: "on", audio: true, haptic: 0 });
  const saved = JSON.parse(storage._map.get(KEY));
  assert.deepEqual(saved, { visual: DEFAULT_SETTINGS.visual, audio: true, haptic: DEFAULT_SETTINGS.haptic });
});

test("saveSettings: returns false when storage absent or throwing", () => {
  assert.equal(saveSettings(null, { visual: true }), false);
  const storage = { setItem() { throw new Error("QuotaExceeded"); } };
  assert.equal(saveSettings(storage, { visual: true }), false);
});

"""Static smoke tests for the rider staged-alerts frontend.

The pure alert logic is unit-tested in tests/js (node --test); those are not part of the
Python-only CI job, so this file keeps the pytest suite authoritative about the presence
and wiring of the feature in the shipped frontend. These assert on file contents, not a
browser, so they run anywhere.
"""

from __future__ import annotations

from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "app" / "web"


def _read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def test_alert_modules_exist_and_are_pure():
    alerts = _read("alerts.js")
    settings = _read("settings.js")
    assert "export function detectCapabilities" in alerts
    assert "export function planAlert" in alerts
    assert "export function alertStage" in alerts
    assert "export function normalizeSettings" in settings
    assert "export function loadSettings" in settings
    # The two node-test spec files that exercise them without a browser must exist.
    js = Path(__file__).resolve().parents[1] / "tests" / "js"
    assert (js / "alerts.test.js").is_file()
    assert (js / "settings.test.js").is_file()


def test_app_wires_capabilities_settings_and_cues():
    app = _read("app.js")
    assert 'from "./alerts.js"' in app
    assert 'from "./settings.js"' in app
    # capability-governed cue playback, guarded for iOS Safari (no vibrate)
    assert "navigator.vibrate" in app
    assert "webkitAudioContext" in app
    assert "AudioContext" in app
    # cue fires once per advisory stage crossing, not every GPS fix
    assert "cueStageKey" in app
    assert "planAlert(" in app
    # settings persisted to localStorage, reduced-motion respected
    assert "loadSettings(window.localStorage)" in app
    assert "saveSettings(window.localStorage" in app
    assert "prefers-reduced-motion" in app


def test_html_has_settings_sheet_and_assertive_live_region():
    html = _read("index.html")
    assert 'id="settings-button"' in html
    assert 'id="settings-sheet"' in html
    for control in ("setting-visual", "setting-audio", "setting-haptic", "test-audio-button"):
        assert f'id="{control}"' in html
    assert 'id="alert-announce"' in html
    assert 'role="alert"' in html and 'aria-live="assertive"' in html


def test_settings_copy_is_advisory_not_accident_claim():
    html = _read("index.html").lower()
    assert "not an accident warning" in html
    assert "safe route" not in html
    assert "prevents accidents" not in html

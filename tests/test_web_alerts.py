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


def test_speed_aware_advisory_is_wired():
    """TASK 2: the advisory must compare the device's measured ground speed."""
    alerts = _read("alerts.js")
    app = _read("app.js")
    html = _read("index.html")
    assert "export function speedAwareness" in alerts
    assert "export function lateralDemandG" in alerts
    assert "export function normaliseSpeedKmh" in alerts
    # the same v²/R physics as the backend baseline, expressed in g
    assert "STANDARD_GRAVITY" in alerts
    # client captures coords.speed and renders the note inside the advisory banner
    assert "coords.speed" in app
    assert "speedAwareness({" in app
    assert 'id="advisory-speed"' in html
    # an absent speed must never read as 0 km/h
    assert "coords.speed === null || coords.speed === undefined" in app


def test_speed_note_is_a_disclosure_not_an_instruction():
    """No 'safe speed'/speed-limit wording; the fallback has to be explicit."""
    alerts = _read("alerts.js").lower()
    app = _read("app.js").lower()
    for phrase in ("safe speed", "speed limit", "recommended speed", "you can safely"):
        assert phrase not in alerts
        assert phrase not in app
    assert "speed_unavailable" in alerts
    assert "radius_unavailable" in alerts


def test_route_deviation_detection_is_wired():
    """TASK 2 (F14): deviation was implemented but had no automated coverage."""
    app = _read("app.js")
    html = _read("index.html")
    assert "nav.deviations" in app
    assert "route_deviation" in app
    assert "Off the analysed route" in app
    assert 'id="router-note"' in html
    # threshold scales with reported accuracy and is clamped
    assert "Math.max(55, Math.min(120, fix.accuracy * 1.6))" in app

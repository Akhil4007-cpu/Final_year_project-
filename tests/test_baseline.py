from __future__ import annotations

from types import SimpleNamespace

from app.baseline import (
    BASELINE_VERSION,
    LABEL_VERSION,
    challenge_score,
    baseline_for_section,
    score_band,
)


def test_challenge_score_zero_without_radius():
    assert challenge_score(radius_m=None, speed_kmh=50.0) == 0.0


def test_challenge_score_zero_for_invalid_radius():
    assert challenge_score(radius_m=0.0, speed_kmh=50.0) == 0.0
    assert challenge_score(radius_m=-5.0, speed_kmh=50.0) == 0.0


def test_tighter_radius_scores_higher():
    tight = challenge_score(radius_m=60.0, speed_kmh=50.0)
    wide = challenge_score(radius_m=400.0, speed_kmh=50.0)
    assert tight > wide


def test_higher_speed_scores_higher():
    slow = challenge_score(radius_m=120.0, speed_kmh=30.0)
    fast = challenge_score(radius_m=120.0, speed_kmh=70.0)
    assert fast > slow


def test_challenge_score_within_bounds():
    for radius in (5.0, 50.0, 500.0, 5000.0):
        for speed in (5.0, 50.0, 120.0):
            score = challenge_score(radius_m=radius, speed_kmh=speed)
            assert 0.0 <= score <= 100.0


def test_score_band_thresholds():
    assert score_band(None) == "unavailable"
    assert score_band(10.0) == "low"
    assert score_band(34.9) == "low"
    assert score_band(45.0) == "moderate"
    assert score_band(59.9) == "moderate"
    assert score_band(60.0) == "high"
    assert score_band(90.0) == "high"


def _section(**kw):
    base = dict(
        evidence="scored",
        kind="curve",
        min_radius_m=80.0,
        radius_m=100.0,
        curve_length_m=60.0,
        transition_abruptness=0.5,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_baseline_for_section_none_when_not_scored():
    assert baseline_for_section(_section(evidence="insufficient_evidence")) is None


def test_baseline_for_section_zero_for_straight():
    assert baseline_for_section(_section(kind="straight")) == 0.0


def test_baseline_for_section_returns_curve_score():
    score = baseline_for_section(_section(), speed_kmh=50.0)
    assert score is not None
    assert 0.0 <= score <= 100.0


def test_versions_are_stable_strings():
    assert LABEL_VERSION == "label_v1"
    assert BASELINE_VERSION == "physics_v2r_v1"

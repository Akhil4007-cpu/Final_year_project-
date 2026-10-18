from __future__ import annotations

from types import SimpleNamespace

from app.advisory import (
    ADVISORY_CLEAR_AFTER_M,
    ADVISORY_COOLDOWN_S,
    ADVISORY_LEAD_M,
    ADVISORY_MIN_SCORE,
    build_advisories,
)


def _section(index, kind, score, start, length=40.0, *, evidence="scored", status="baseline_fallback",
             low=None, high=None):
    return SimpleNamespace(
        index=index,
        kind=kind,
        evidence=evidence,
        display_score=score,
        baseline_score=score,
        start_distance_m=start,
        length_m=length,
        uncertainty_low=low,
        uncertainty_high=high,
        model_status=status,
    )


def test_only_curves_above_threshold_produce_advisories():
    sections = [
        _section(0, "curve", 80.0, 100.0),
        _section(1, "curve", 20.0, 500.0),
        _section(2, "straight", 90.0, 900.0),
        _section(3, "curve", 90.0, 1200.0, evidence="insufficient_evidence"),
    ]
    advisories = build_advisories(sections)
    assert [a["id"] for a in advisories] == ["curve-0"]


def test_threshold_boundary_inclusive():
    sections = [_section(0, "curve", ADVISORY_MIN_SCORE, 100.0)]
    assert len(build_advisories(sections)) == 1


def test_advisories_sorted_by_distance():
    sections = [
        _section(5, "curve", 70.0, 900.0),
        _section(2, "curve", 65.0, 300.0),
    ]
    advisories = build_advisories(sections)
    starts = [a["start_distance_m"] for a in advisories]
    assert starts == sorted(starts)


def test_advisory_carries_lead_clear_cooldown_and_band():
    advisories = build_advisories([_section(0, "curve", 81.0, 411.6)])
    advisory = advisories[0]
    assert advisory["lead_m"] == ADVISORY_LEAD_M
    assert advisory["clear_after_m"] == ADVISORY_CLEAR_AFTER_M
    assert advisory["cooldown_s"] == ADVISORY_COOLDOWN_S
    assert advisory["band"] == "high"
    assert "Advisory only" in advisory["message"]


def test_advisory_provenance_reflects_model_status():
    model = build_advisories([_section(0, "curve", 70.0, 10.0, status="model_estimate")])[0]
    fallback = build_advisories([_section(0, "curve", 70.0, 10.0, status="baseline_fallback")])[0]
    assert model["provenance"] == "model_estimate"
    assert fallback["provenance"] == "computed_geometry"


def test_advisory_includes_uncertainty_when_present():
    advisory = build_advisories([_section(0, "curve", 70.0, 10.0, low=55.0, high=85.0)])[0]
    assert advisory["uncertainty"] == {"low": 55.0, "high": 85.0}

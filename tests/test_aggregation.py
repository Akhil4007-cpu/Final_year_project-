from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.aggregation import (
    COMPARABLE_SCORE_GAP,
    MAX_COMPARABLE_COVERAGE_SPREAD,
    MIN_ROUTE_COVERAGE,
    aggregate_sections,
    compare_routes,
)


def _section(length_m, baseline, display, *, evidence="scored", status="baseline_fallback",
             ood=False, low=None, high=None):
    return SimpleNamespace(
        evidence=evidence,
        length_m=length_m,
        baseline_score=baseline,
        display_score=display,
        model_status=status,
        ood=ood,
        uncertainty_low=low,
        uncertainty_high=high,
    )


def test_low_coverage_is_insufficient():
    sections = [_section(100.0, 40.0, 40.0), _section(400.0, None, None, evidence="insufficient_evidence")]
    result = aggregate_sections(sections, total_length_m=500.0, model_available=False)
    assert result["state"] == "insufficient_evidence"
    assert result["score"] is None
    assert result["band"] == "unavailable"


def test_scored_route_weighted_average():
    sections = [_section(100.0, 20.0, 20.0), _section(100.0, 40.0, 40.0)]
    result = aggregate_sections(sections, total_length_m=200.0, model_available=False)
    assert result["state"] == "scored"
    assert result["coverage"] == pytest.approx(1.0)
    assert result["score"] == pytest.approx(30.0)


def test_missing_length_never_scored_as_zero():
    # Half the route has no usable geometry; coverage 0.5 < 0.6 -> not scored.
    sections = [_section(50.0, 10.0, 10.0), _section(50.0, None, None, evidence="insufficient_evidence")]
    result = aggregate_sections(sections, total_length_m=100.0, model_available=False)
    assert result["state"] == "insufficient_evidence"
    assert result["missing_length_m"] == pytest.approx(50.0)


def test_coverage_threshold_boundary():
    sections = [_section(60.0, 30.0, 30.0), _section(40.0, None, None, evidence="insufficient_evidence")]
    result = aggregate_sections(sections, total_length_m=100.0, model_available=False)
    assert result["coverage"] == pytest.approx(MIN_ROUTE_COVERAGE)
    assert result["state"] == "scored"


def test_uncertainty_band_only_for_model_estimates():
    sections = [_section(100.0, 30.0, 35.0, status="model_estimate", low=25.0, high=45.0)]
    result = aggregate_sections(sections, total_length_m=100.0, model_available=True)
    assert result["uncertainty"] == {"low": 25.0, "high": 45.0}
    assert result["model_used_sections"] == 1


def _route(rid, score, coverage, state="scored"):
    return {"id": rid, "summary": {"state": state, "score": score, "coverage": coverage}}


def test_compare_requires_two_routes():
    result = compare_routes([_route("a", 30.0, 0.9)])
    assert result["state"] == "insufficient_evidence"


def test_compare_rejects_unscored_route():
    result = compare_routes([_route("a", 30.0, 0.9), _route("b", None, 0.2, state="insufficient_evidence")])
    assert result["state"] == "insufficient_evidence"


def test_compare_rejects_coverage_spread():
    result = compare_routes([_route("a", 30.0, 0.95), _route("b", 31.0, 0.65)])
    assert result["state"] == "insufficient_evidence"
    assert MAX_COMPARABLE_COVERAGE_SPREAD < 0.31


def test_comparable_when_gap_small_no_recommendation():
    result = compare_routes([_route("a", 30.0, 0.9), _route("b", 33.0, 0.9)])
    assert result["state"] == "comparable"
    assert result["best_route_id"] is None
    assert result["lowest_geometry_challenge_route_id"] == "a"
    assert "not an accident-risk ranking" in result["ranking_basis"]


def test_ranked_when_gap_large():
    result = compare_routes([_route("a", 30.0, 0.9), _route("b", 60.0, 0.9)])
    assert result["state"] == "ranked"
    assert result["best_route_id"] == "a"
    assert result["score_gap"] == pytest.approx(30.0)
    assert COMPARABLE_SCORE_GAP <= 30.0

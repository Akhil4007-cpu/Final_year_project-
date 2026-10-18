from __future__ import annotations

from typing import Any, Iterable

from app.baseline import score_band

MIN_ROUTE_COVERAGE = 0.60
COMPARABLE_SCORE_GAP = 5.0
MAX_COMPARABLE_COVERAGE_SPREAD = 0.15


def aggregate_sections(
    sections: Iterable[Any],
    *,
    total_length_m: float,
    model_available: bool,
) -> dict[str, Any]:
    sections = list(sections)
    eligible = [
        section
        for section in sections
        if section.evidence == "scored"
        and section.baseline_score is not None
        and section.display_score is not None
    ]
    eligible_length = sum(max(0.0, section.length_m) for section in eligible)
    total = max(0.0, float(total_length_m))
    coverage = (eligible_length / total) if total > 0 else 0.0
    missing_length = max(0.0, total - eligible_length)
    scored = coverage >= MIN_ROUTE_COVERAGE and eligible_length > 0

    model_used_sections = sum(
        1 for section in eligible if section.model_status == "model_estimate"
    )
    fallback_sections = sum(
        1 for section in eligible if section.model_status == "baseline_fallback"
    )
    ood_sections = sum(1 for section in eligible if section.ood)
    result: dict[str, Any] = {
        "state": "scored" if scored else "insufficient_evidence",
        "coverage": round(coverage, 4),
        "scored_length_m": round(eligible_length, 2),
        "total_length_m": round(total, 2),
        "missing_length_m": round(missing_length, 2),
        "score": None,
        "band": "unavailable",
        "baseline_score": None,
        "uncertainty": None,
        "uncertainty_coverage": 0.0,
        "model_available": model_available,
        "model_used_sections": model_used_sections,
        "fallback_sections": fallback_sections,
        "ood_sections": ood_sections,
        "provenance": ["computed_geometry"],
        "reason": None,
    }
    if not scored:
        result["reason"] = (
            "No eligible segments were scored."
            if eligible_length == 0
            else f"Coverage {coverage:.0%} is below the {MIN_ROUTE_COVERAGE:.0%} threshold."
        )
        return result

    baseline_weighted = (
        sum(section.baseline_score * section.length_m for section in eligible)
        / eligible_length
    )
    result["baseline_score"] = round(baseline_weighted, 2)
    display_weighted = (
        sum(section.display_score * section.length_m for section in eligible)
        / eligible_length
    )
    result["score"] = round(display_weighted, 2)
    result["band"] = score_band(display_weighted)
    if model_used_sections:
        result["provenance"].append("model_estimate")
    if fallback_sections:
        result["provenance"].append("computed_geometry")
    if (
        model_available
        and model_used_sections
        and all(
            section.uncertainty_low is not None and section.uncertainty_high is not None
            for section in eligible
            if section.model_status == "model_estimate"
        )
    ):
        band_sections = [
            section for section in eligible if section.model_status == "model_estimate"
        ]
        band_length = sum(section.length_m for section in band_sections)
        if band_length > 0:
            low = (
                sum(section.uncertainty_low * section.length_m for section in band_sections)
                / band_length
            )
            high = (
                sum(section.uncertainty_high * section.length_m for section in band_sections)
                / band_length
            )
            result["uncertainty"] = {
                "low": round(max(0.0, low), 2),
                "high": round(min(100.0, high), 2),
            }
            result["uncertainty_coverage"] = round(band_length / eligible_length, 4)
    return result


def compare_routes(routes: list[dict[str, Any]]) -> dict[str, Any]:
    if len(routes) < 2:
        return {
            "state": "insufficient_evidence",
            "reason": "At least two routes are required for comparison.",
            "best_route_id": None,
        }
    if any(route["summary"]["state"] != "scored" for route in routes):
        return {
            "state": "insufficient_evidence",
            "reason": "At least one route has insufficient geometry coverage.",
            "best_route_id": None,
        }
    coverages = [route["summary"]["coverage"] for route in routes]
    if max(coverages) - min(coverages) > MAX_COMPARABLE_COVERAGE_SPREAD:
        return {
            "state": "insufficient_evidence",
            "reason": "Route coverage differs too much for a like-for-like comparison.",
            "best_route_id": None,
        }
    ordered = sorted(routes, key=lambda route: route["summary"]["score"])
    best = ordered[0]
    worst = ordered[-1]
    gap = worst["summary"]["score"] - best["summary"]["score"]
    return {
        "state": "comparable" if gap < COMPARABLE_SCORE_GAP else "ranked",
        "best_route_id": best["id"] if gap >= COMPARABLE_SCORE_GAP else None,
        "lowest_geometry_challenge_route_id": best["id"],
        "score_gap": round(gap, 2),
        "coverage_spread": round(max(coverages) - min(coverages), 4),
        "ranking_basis": "weighted geometry-challenge estimate; not an accident-risk ranking",
    }

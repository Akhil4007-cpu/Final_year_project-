from __future__ import annotations

from typing import Any, Iterable

from app.baseline import score_band

ADVISORY_MIN_SCORE = 55.0
ADVISORY_LEAD_M = 150.0
ADVISORY_COOLDOWN_S = 30.0
ADVISORY_CLEAR_AFTER_M = 20.0


def build_advisories(sections: Iterable[Any]) -> list[dict[str, Any]]:
    advisories: list[dict[str, Any]] = []
    for section in sections:
        if section.kind != "curve" or section.evidence != "scored":
            continue
        score = section.display_score if section.display_score is not None else section.baseline_score
        if score is None or score < ADVISORY_MIN_SCORE:
            continue
        band = score_band(score)
        advisories.append(
            {
                "id": f"curve-{section.index}",
                "section_index": section.index,
                "start_distance_m": round(section.start_distance_m, 2),
                "end_distance_m": round(section.start_distance_m + section.length_m, 2),
                "lead_m": ADVISORY_LEAD_M,
                "clear_after_m": ADVISORY_CLEAR_AFTER_M,
                "cooldown_s": ADVISORY_COOLDOWN_S,
                "band": band,
                "score": round(score, 2),
                "uncertainty": (
                    {"low": section.uncertainty_low, "high": section.uncertainty_high}
                    if section.uncertainty_low is not None
                    and section.uncertainty_high is not None
                    else None
                ),
                "message": _message(band),
                "provenance": "model_estimate"
                if section.model_status == "model_estimate"
                else "computed_geometry",
            }
        )
    advisories.sort(key=lambda item: item["start_distance_m"])
    return advisories


def _message(band: str) -> str:
    if band == "high":
        return "Curve ahead: high geometry challenge. Advisory only."
    return "Curve ahead: moderate geometry challenge. Advisory only."

from __future__ import annotations

import math

from app.features import ROAD_CLASS_SPEED_KMH
from app.geo import Section

LABEL_VERSION = "label_v1"
BASELINE_VERSION = "physics_v2r_v1"
A_REF_MPS2 = 3.5
MAX_GRADE_PCT = 8.0

ASSUMPTIONS = [
    "Geometry challenge is a computed indicator, not an accident probability.",
    "Speed is an advisory band; it is not a legal speed limit or measured rider speed.",
    "The reference lateral acceleration a_lat = v^2 / R uses the minimum curve radius (peak curvature), a conservative geometric estimator.",
    "Length and transition adjustments are documented engineering assumptions in label_v1.",
    "Grade is included only when real elevation data is supplied; otherwise it is marked unavailable.",
]


def challenge_score(
    *,
    radius_m: float | None,
    speed_kmh: float,
    curve_length_m: float = 0.0,
    transition_abruptness: float = 1.0,
    grade_pct: float | None = None,
) -> float:
    """label_v1: clean reference score in [0, 100]. Not a crash-risk estimate."""
    if radius_m is None or not math.isfinite(radius_m) or radius_m <= 0:
        return 0.0
    speed_mps = max(5.0, min(200.0, float(speed_kmh))) / 3.6
    a_lat = speed_mps**2 / radius_m
    base = 100.0 * a_lat / (a_lat + A_REF_MPS2)
    length_term = 6.0 * _clip(
        math.log10(max(curve_length_m, 5.0) / 5.0) / math.log10(40.0), 0.0, 1.0
    )
    transition_term = 4.0 * _clip(transition_abruptness, 0.0, 1.0)
    grade_term = 0.0
    if grade_pct is not None and math.isfinite(grade_pct):
        grade_term = 0.75 * _clip(grade_pct, -MAX_GRADE_PCT, MAX_GRADE_PCT)
    return round(_clip(base + length_term + transition_term + grade_term, 0.0, 100.0), 3)


def baseline_for_section(
    section: Section,
    *,
    speed_kmh: float | None = None,
    road_class: str | None = None,
    grade_pct: float | None = None,
) -> float | None:
    if section.evidence != "scored":
        return None
    if section.kind == "straight":
        return 0.0
    if speed_kmh is None:
        speed_kmh = ROAD_CLASS_SPEED_KMH.get((road_class or "unknown").lower(), 50.0)
    return challenge_score(
        radius_m=section.min_radius_m or section.radius_m,
        speed_kmh=speed_kmh,
        curve_length_m=section.curve_length_m,
        transition_abruptness=section.transition_abruptness,
        grade_pct=grade_pct,
    )


def score_band(score: float | None) -> str:
    if score is None:
        return "unavailable"
    if score < 35.0:
        return "low"
    if score < 60.0:
        return "moderate"
    return "high"


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))

from __future__ import annotations

import math
from typing import Any

from app.geo import Section

ROAD_CLASS_CODES = {
    "unknown": 0,
    "motorway": 1,
    "trunk": 2,
    "primary": 3,
    "secondary": 4,
    "tertiary": 5,
    "residential": 6,
    "service": 7,
    "unclassified": 8,
    "living_street": 9,
}

# Advisory speed assumptions, not legal speed limits. Used only when the caller
# does not supply a speed band; every score carries this assumption explicitly.
ROAD_CLASS_SPEED_KMH = {
    "unknown": 50.0,
    "motorway": 100.0,
    "trunk": 80.0,
    "primary": 70.0,
    "secondary": 60.0,
    "tertiary": 50.0,
    "residential": 30.0,
    "service": 20.0,
    "unclassified": 40.0,
    "living_street": 20.0,
}

FEATURE_SPECS: list[dict[str, Any]] = [
    {"name": "is_curve", "default": 0.0, "description": "1 for a curve section"},
    {"name": "length_m", "default": 0.0, "description": "Section length in metres"},
    {"name": "curve_length_m", "default": 0.0, "description": "Curve length in metres"},
    {"name": "log_radius", "default": math.log1p(10000.0), "description": "log(1 + effective radius)"},
    {"name": "inverse_min_radius", "default": 0.0, "description": "1 / minimum radius, 0 for straights"},
    {"name": "heading_change_deg", "default": 0.0, "description": "Absolute heading change over the section"},
    {"name": "heading_change_per_m", "default": 0.0, "description": "Heading change per metre"},
    {"name": "curvature_std", "default": 0.0, "description": "Std-dev of curvature samples"},
    {"name": "max_turn_deg", "default": 0.0, "description": "Largest single-vertex turn"},
    {"name": "transition_abruptness", "default": 1.0, "description": "0 = gradual spiral-like, 1 = abrupt"},
    {"name": "spiral_like", "default": 0.0, "description": "1 when curvature changes monotonically"},
    {"name": "gap_before_m", "default": 500.0, "description": "Distance from the previous curve, capped at 500 m"},
    {"name": "sequence_index", "default": 0.0, "description": "Curve order on the route, capped at 10"},
    {"name": "speed_mps", "default": 50.0 / 3.6, "description": "Speed band in m/s"},
    {"name": "speed_missing", "default": 1.0, "description": "1 when speed was not supplied"},
    {"name": "road_class_code", "default": 0.0, "description": "Ordinal road-class code"},
    {"name": "road_class_missing", "default": 1.0, "description": "1 when road class was not supplied"},
    {"name": "grade_pct", "default": 0.0, "description": "Real elevation grade in percent, 0 when missing"},
    {"name": "grade_missing", "default": 1.0, "description": "1 when real elevation was not available"},
    {"name": "geometry_quality", "default": 1.0, "description": "Upstream geometry quality score 0..1"},
    {"name": "median_spacing_m", "default": 20.0, "description": "Median polyline spacing"},
    {
        "name": "physics_prior",
        "default": 0.0,
        "description": (
            "label_v1 challenge score computed from the SAME (possibly degraded) features; "
            "a transparent v^2/R prior the model corrects, never the clean reference label"
        ),
    },
]

FEATURE_NAMES = [spec["name"] for spec in FEATURE_SPECS]
FEATURE_DEFAULTS = {spec["name"]: float(spec["default"]) for spec in FEATURE_SPECS}

MONOTONIC_CONSTRAINTS = {
    "is_curve": 1,
    "log_radius": -1,
    "inverse_min_radius": 1,
    "speed_mps": 1,
    "physics_prior": 1,
}


def resolve_speed(
    speed_kmh: float | None, road_class: str | None
) -> tuple[float, bool, str]:
    if speed_kmh is not None:
        return max(5.0, min(200.0, float(speed_kmh))), False, "caller_supplied"
    key = (road_class or "unknown").strip().lower()
    if key in ROAD_CLASS_SPEED_KMH:
        return ROAD_CLASS_SPEED_KMH[key], True, f"assumed_{key}"
    return ROAD_CLASS_SPEED_KMH["unknown"], True, "assumed_unknown"


def build_features(
    section: Section,
    *,
    road_class: str | None = None,
    speed_kmh: float | None = None,
    grade_pct: float | None = None,
    geometry_quality_score: float = 1.0,
) -> dict[str, float]:
    from app.baseline import challenge_score

    speed, speed_missing, _ = resolve_speed(speed_kmh, road_class)
    class_key = (road_class or "unknown").strip().lower()
    class_code = float(ROAD_CLASS_CODES.get(class_key, 0))
    class_missing = 1.0 if road_class is None else 0.0
    is_curve = 1.0 if section.kind == "curve" else 0.0
    radius = section.radius_m if section.radius_m and section.radius_m > 0 else 10000.0
    min_radius = (
        section.min_radius_m if section.min_radius_m and section.min_radius_m > 0 else None
    )
    gap = section.gap_before_m if section.gap_before_m is not None else 500.0
    length = max(0.0, section.length_m)
    heading_per_m = section.heading_change_deg / max(length, 1.0)
    grade = 0.0 if grade_pct is None else max(-20.0, min(20.0, float(grade_pct)))
    if section.kind == "straight" or section.evidence != "scored":
        physics_prior = 0.0
    else:
        physics_prior = challenge_score(
            radius_m=section.min_radius_m or section.radius_m,
            speed_kmh=speed,
            curve_length_m=section.curve_length_m,
            transition_abruptness=section.transition_abruptness,
            grade_pct=grade_pct,
        )
    return {
        "is_curve": is_curve,
        "length_m": length,
        "curve_length_m": section.curve_length_m,
        "log_radius": math.log1p(max(radius, 1.0)),
        "inverse_min_radius": (1.0 / min_radius) if min_radius else 0.0,
        "heading_change_deg": section.heading_change_deg,
        "heading_change_per_m": heading_per_m,
        "curvature_std": section.curvature_std,
        "max_turn_deg": section.max_turn_deg,
        "transition_abruptness": section.transition_abruptness,
        "spiral_like": 1.0 if section.spiral_like else 0.0,
        "gap_before_m": min(max(gap, 0.0), 500.0),
        "sequence_index": float(min(max(section.sequence_index, 0), 10)),
        "speed_mps": speed / 3.6,
        "speed_missing": 1.0 if speed_missing else 0.0,
        "road_class_code": class_code,
        "road_class_missing": class_missing,
        "grade_pct": grade,
        "grade_missing": 1.0 if grade_pct is None else 0.0,
        "geometry_quality": max(0.0, min(1.0, float(geometry_quality_score))),
        "median_spacing_m": float(section.quality.get("median_spacing_m") or 20.0),
        "physics_prior": float(physics_prior),
    }


def feature_vector(features: dict[str, float]) -> list[float]:
    vector: list[float] = []
    for name in FEATURE_NAMES:
        value = float(features.get(name, FEATURE_DEFAULTS[name]))
        if not math.isfinite(value):
            value = FEATURE_DEFAULTS[name]
        vector.append(value)
    return vector

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from app.baseline import baseline_for_section
from app.features import build_features
from app.geo import extract_sections, haversine_m, Section

GENERATOR_VERSION = "generator_v1"
GEOMETRY_VERSION = "geo_v1"
R_EARTH_M = 6_371_008.8
ORIGIN_LAT = 12.9716
ORIGIN_LON = 77.5946
SCENARIO_TYPES = (
    "straight",
    "simple_arc",
    "spiral",
    "reverse_curve",
    "compound",
    "hairpin",
    "urban_turn",
)
OOD_SCENARIO_TYPE = "hairpin"
OOD_RADIUS_BAND_M = (300.0, 700.0)


@dataclass(frozen=True)
class SyntheticScenario:
    scenario_id: str
    scenario_type: str
    seed: int
    points: list[tuple[float, float]]
    speed_kmh: float
    road_class: str
    grade_pct: float | None
    speed_source: str
    tightest_radius_m: float
    params: dict[str, Any] = field(default_factory=dict)

    def split(self) -> str:
        if self.scenario_type == OOD_SCENARIO_TYPE:
            return "ood_type"
        if OOD_RADIUS_BAND_M[0] <= self.tightest_radius_m <= OOD_RADIUS_BAND_M[1]:
            return "ood_radius"
        digest = hashlib.sha256(f"{GENERATOR_VERSION}:{self.scenario_id}".encode()).digest()
        bucket = int.from_bytes(digest[:8], "big") / float(2**64)
        if bucket < 0.70:
            return "train"
        if bucket < 0.85:
            return "calibration"
        return "test"


@dataclass(frozen=True)
class Degradation:
    noise_sigma_m: float = 0.0
    dropout_fraction: float = 0.0
    keep_every: int = 1
    duplicate_fraction: float = 0.0

    def describe(self) -> dict[str, Any]:
        return asdict(self)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _to_latlon(x: np.ndarray, y: np.ndarray) -> list[tuple[float, float]]:
    lat = ORIGIN_LAT + np.degrees(y / R_EARTH_M)
    lon = ORIGIN_LON + np.degrees(x / (R_EARTH_M * math.cos(math.radians(ORIGIN_LAT))))
    return [(float(a), float(b)) for a, b in zip(lat, lon)]


def _integrate_path(kappa_fn, length_m: float, ds: float = 1.0) -> np.ndarray:
    steps = max(2, int(math.ceil(length_m / ds)))
    ds = length_m / steps
    x = y = theta = 0.0
    points = [(0.0, 0.0)]
    for step in range(steps):
        s_mid = (step + 0.5) * ds
        kappa = kappa_fn(s_mid)
        theta_mid = theta + kappa * ds / 2.0
        x += math.cos(theta_mid) * ds
        y += math.sin(theta_mid) * ds
        theta += kappa * ds
        points.append((x, y))
    return np.asarray(points, dtype=float)


def _sample_polyline(points: np.ndarray, spacing_m: float) -> list[tuple[float, float]]:
    distances = np.concatenate(
        ([0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1)))
    )
    total = float(distances[-1])
    if total <= 0:
        return _to_latlon(points[:, 0], points[:, 1])
    targets = list(np.arange(0.0, total, spacing_m)) + [total]
    sampled = []
    for target in targets:
        index = int(np.searchsorted(distances, target, side="right") - 1)
        index = min(index, len(points) - 2)
        segment = distances[index + 1] - distances[index]
        ratio = 0.0 if segment <= 1e-9 else (target - distances[index]) / segment
        point = points[index] + ratio * (points[index + 1] - points[index])
        sampled.append(tuple(float(value) for value in point))
    return _to_latlon(np.asarray([p[0] for p in sampled]), np.asarray([p[1] for p in sampled]))


def _lead_in_out(
    path: np.ndarray, lead_in_m: float, lead_out_m: float
) -> np.ndarray:
    start = path[0]
    end = path[-1]
    heading = math.atan2(path[-1][1] - path[-2][1], path[-1][0] - path[-2][0])
    lead_count = max(1, int(round(lead_in_m / 2.0)))
    lead_in = np.asarray(
        [
            (start[0] - lead_in_m + i * (lead_in_m / lead_count), start[1])
            for i in range(lead_count)
        ]
        + [tuple(start)]
    )
    lead_out = np.asarray(
        [
            tuple(end + (j * 2.0) * np.asarray([math.cos(heading), math.sin(heading)]))
            for j in range(1, int(lead_out_m / 2) + 1)
        ]
    )
    return np.vstack([lead_in, path, lead_out])


def _build_profile(
    rng: np.random.Generator, scenario_type: str
) -> tuple[Any, float, dict[str, Any], float]:
    if scenario_type == "straight":
        length = rng.uniform(100.0, 400.0)
        return (lambda s: 0.0), length, {"length_m": length}, 1e6

    if scenario_type in {"simple_arc", "hairpin", "urban_turn"}:
        if scenario_type == "hairpin":
            radius = rng.uniform(15.0, 45.0)
            angle = rng.uniform(150.0, 220.0)
        elif scenario_type == "urban_turn":
            radius = rng.uniform(15.0, 30.0)
            angle = rng.uniform(80.0, 100.0)
        else:
            radius = math.exp(rng.uniform(math.log(40.0), math.log(800.0)))
            angle = rng.uniform(25.0, 120.0)
        kappa = 1.0 / radius
        arc = math.radians(angle) * radius
        return (lambda s, k=kappa: k), arc, {"radius_m": radius, "angle_deg": angle}, radius

    if scenario_type == "spiral":
        radius = math.exp(rng.uniform(math.log(30.0), math.log(600.0)))
        angle = rng.uniform(40.0, 120.0)
        transition = rng.uniform(12.0, 40.0)
        kappa = 1.0 / radius
        arc = math.radians(angle) * radius

        def arc_profile(s: float, k=kappa, t=transition, a=arc) -> float:
            if s < t:
                return k * (s / t)
            if s < t + a:
                return k
            if s < 2 * t + a:
                return k * (1.0 - (s - t - a) / t)
            return 0.0

        return arc_profile, arc + 2 * transition, {"radius_m": radius, "angle_deg": angle, "transition_m": transition}, radius

    if scenario_type == "reverse_curve":
        r1 = math.exp(rng.uniform(math.log(40.0), math.log(500.0)))
        r2 = math.exp(rng.uniform(math.log(40.0), math.log(500.0)))
        a1 = math.radians(rng.uniform(30.0, 90.0)) * r1
        a2 = math.radians(rng.uniform(30.0, 90.0)) * r2
        gap = rng.uniform(0.0, 30.0)
        k1, k2 = 1.0 / r1, -1.0 / r2

        def reverse_profile(s: float, k1=k1, k2=k2, first=a1, gap=gap) -> float:
            if s < first:
                return k1
            if s < first + gap:
                return 0.0
            if s < first + gap + a2:
                return k2
            return 0.0

        return reverse_profile, a1 + gap + a2, {"radius_1_m": r1, "radius_2_m": r2, "gap_m": gap}, min(r1, r2)

    if scenario_type == "compound":
        r1 = math.exp(rng.uniform(math.log(80.0), math.log(700.0)))
        r2 = math.exp(rng.uniform(math.log(40.0), math.log(400.0)))
        a1 = math.radians(rng.uniform(25.0, 90.0)) * r1
        a2 = math.radians(rng.uniform(25.0, 90.0)) * r2
        gap = rng.uniform(0.0, 20.0)
        k1, k2 = 1.0 / r1, 1.0 / r2

        def compound_profile(s: float, k1=k1, k2=k2, first=a1, gap=gap) -> float:
            if s < first:
                return k1
            if s < first + gap:
                return 0.0
            if s < first + gap + a2:
                return k2
            return 0.0

        return compound_profile, a1 + gap + a2, {"radius_1_m": r1, "radius_2_m": r2, "gap_m": gap}, min(r1, r2)

    raise ValueError(f"unknown scenario type {scenario_type}")


def generate_scenario(scenario_type: str, index: int, seed: int) -> SyntheticScenario:
    rng = np.random.default_rng(seed + index * 7919)
    profile, length, params, tightest_radius = _build_profile(rng, scenario_type)
    path = _integrate_path(profile, length)
    if scenario_type == "straight":
        lead_in, lead_out = 10.0, 10.0
    else:
        lead_in = rng.uniform(20.0, 60.0)
        lead_out = rng.uniform(20.0, 60.0)
    path = _lead_in_out(path, lead_in, lead_out)
    points = _sample_polyline(path, spacing_m=rng.uniform(4.0, 9.0))

    if scenario_type in {"hairpin", "urban_turn"}:
        road_class = rng.choice(["residential", "tertiary"])
    elif scenario_type == "straight":
        road_class = rng.choice(["primary", "secondary", "tertiary", "residential"])
    else:
        road_class = rng.choice(["primary", "secondary", "tertiary", "residential"])
    class_speed = {
        "primary": 70.0,
        "secondary": 60.0,
        "tertiary": 50.0,
        "residential": 30.0,
    }[str(road_class)]
    speed = _clip(class_speed * rng.uniform(0.75, 1.15), 20.0, 110.0)
    grade = float(rng.uniform(-6.0, 6.0)) if rng.random() < 0.3 else None
    return SyntheticScenario(
        scenario_id=f"{scenario_type}-{index:04d}",
        scenario_type=scenario_type,
        seed=int(seed + index),
        points=points,
        speed_kmh=float(speed),
        road_class=str(road_class),
        grade_pct=grade,
        speed_source="synthetic_truth",
        tightest_radius_m=float(tightest_radius),
        params={
            **params,
            "lead_in_m": lead_in,
            "lead_out_m": lead_out,
            "length_m": float(sum(haversine_m(points[i], points[i + 1]) for i in range(len(points) - 1))),
        },
    )


def generate_scenarios(seed: int = 42, per_type: int = 140) -> list[SyntheticScenario]:
    scenarios: list[SyntheticScenario] = []
    for type_index, scenario_type in enumerate(SCENARIO_TYPES):
        for index in range(per_type):
            scenarios.append(
                generate_scenario(scenario_type, type_index * 10_000 + index, seed)
            )
    return scenarios


def sample_degradation(rng: np.random.Generator) -> Degradation:
    return Degradation(
        noise_sigma_m=float(rng.choice([0.0, 3.0, 6.0, 10.0, 15.0], p=[0.15, 0.25, 0.25, 0.2, 0.15])),
        dropout_fraction=float(rng.choice([0.0, 0.1, 0.2, 0.3], p=[0.25, 0.3, 0.25, 0.2])),
        keep_every=int(rng.choice([1, 1, 2, 3, 4], p=[0.35, 0.25, 0.2, 0.12, 0.08])),
        duplicate_fraction=float(rng.choice([0.0, 0.05, 0.1], p=[0.6, 0.25, 0.15])),
    )


def _degrade_points(
    points: list[tuple[float, float]], degradation: Degradation, rng: np.random.Generator
) -> list[tuple[float, float]]:
    working = list(points)
    if degradation.keep_every > 1:
        working = [point for index, point in enumerate(working) if index % degradation.keep_every == 0]
        if working[-1] != points[-1]:
            working.append(points[-1])
    if degradation.dropout_fraction > 0 and len(working) > 5:
        keep = [True] * len(working)
        for index in range(1, len(working) - 1):
            if rng.random() < degradation.dropout_fraction:
                keep[index] = False
        working = [point for point, kept in zip(working, keep) if kept]
        if len(working) < 5:
            step = max(1, len(points) // 5)
            working = points[::step]
            if working[-1] != points[-1]:
                working.append(points[-1])
    if degradation.noise_sigma_m > 0:
        noisy: list[tuple[float, float]] = []
        cos_lat = math.cos(math.radians(ORIGIN_LAT))
        for lat, lon in working:
            dy = rng.normal(0.0, degradation.noise_sigma_m)
            dx = rng.normal(0.0, degradation.noise_sigma_m)
            noisy.append(
                (
                    lat + math.degrees(dy / R_EARTH_M),
                    lon + math.degrees(dx / (R_EARTH_M * cos_lat)),
                )
            )
        working = noisy
    if degradation.duplicate_fraction > 0 and len(working) > 4:
        duplicates: list[tuple[float, float]] = []
        for point in working:
            duplicates.append(point)
            if rng.random() < degradation.duplicate_fraction:
                duplicates.append(point)
        working = duplicates
    return working


def _section_midpoint(points: list[tuple[float, float]], section: Section) -> tuple[float, float]:
    subset = points[section.start_index : section.end_index + 1]
    return (
        float(np.mean([p[0] for p in subset])),
        float(np.mean([p[1] for p in subset])),
    )


def _select_section(
    result_sections: list[Section],
    target_mid: tuple[float, float],
    points: list[tuple[float, float]],
    kind: str,
) -> Section | None:
    if not result_sections:
        return None
    if kind == "curve":
        candidates = [section for section in result_sections if section.kind == "curve"]
    else:
        straights = [section for section in result_sections if section.kind == "straight"]
        candidates = straights or list(result_sections)
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda section: haversine_m(target_mid, _section_midpoint(points, section)),
    )


def make_row(
    scenario: SyntheticScenario,
    clean_section: Section,
    degradation: Degradation,
    rng: np.random.Generator,
    *,
    missing_context: bool = True,
) -> dict[str, Any] | None:
    crop_start = max(0, clean_section.start_index - 1)
    crop_end = min(len(scenario.points) - 1, clean_section.end_index + 1)
    crop = scenario.points[crop_start : crop_end + 1]
    target_mid = _section_midpoint(scenario.points, clean_section)
    degraded = _degrade_points(crop, degradation, rng)
    try:
        degraded_result = extract_sections(degraded)
    except ValueError:
        return None
    target = _select_section(degraded_result.sections, target_mid, degraded, clean_section.kind)
    if target is None or target.evidence != "scored":
        return None

    speed_kmh: float | None = scenario.speed_kmh
    road_class: str | None = scenario.road_class
    grade_pct: float | None = scenario.grade_pct
    if missing_context:
        if rng.random() < 0.20:
            speed_kmh = None
        if rng.random() < 0.20:
            road_class = None
        if grade_pct is not None and rng.random() < 0.50:
            grade_pct = None

    features = build_features(
        target,
        road_class=road_class,
        speed_kmh=speed_kmh,
        grade_pct=grade_pct,
        geometry_quality_score=degraded_result.quality.score,
    )
    features["gap_before_m"] = float(
        min(500.0, clean_section.gap_before_m if clean_section.gap_before_m is not None else 500.0)
    )
    features["sequence_index"] = float(min(10, clean_section.sequence_index))

    label = baseline_for_section(
        clean_section,
        speed_kmh=scenario.speed_kmh,
        road_class=scenario.road_class,
        grade_pct=scenario.grade_pct,
    )
    if label is None:
        return None
    baseline_degraded = baseline_for_section(
        target,
        speed_kmh=speed_kmh,
        road_class=road_class,
        grade_pct=grade_pct,
    )
    if baseline_degraded is None:
        return None
    return {
        "scenario_id": scenario.scenario_id,
        "scenario_type": scenario.scenario_type,
        "split": scenario.split(),
        "section_kind": clean_section.kind,
        "features": {name: float(value) for name, value in features.items()},
        "label": float(label),
        "baseline_degraded": float(baseline_degraded),
        "degradation": degradation.describe(),
        "clean_radius_m": clean_section.radius_m,
        "true_speed_kmh": scenario.speed_kmh,
        "road_class": scenario.road_class,
        "grade_pct": scenario.grade_pct,
    }


def build_rows(
    scenarios: list[SyntheticScenario],
    *,
    seed: int = 42,
    missing_context: bool = True,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for scenario_index, scenario in enumerate(scenarios):
        try:
            clean_result = extract_sections(scenario.points)
        except ValueError:
            continue
        curve_sections = [section for section in clean_result.sections if section.kind == "curve"]
        straight_sections = [
            section
            for section in clean_result.sections
            if section.kind == "straight" and section.length_m >= 25.0
        ]
        targets = curve_sections if curve_sections else straight_sections[:1]
        for target_index, section in enumerate(targets):
            rng = np.random.default_rng(seed + scenario_index * 104_729 + target_index * 997)
            degradation = sample_degradation(rng)
            row = make_row(scenario, section, degradation, rng, missing_context=missing_context)
            if row is not None:
                rows.append(row)
    return rows


def controlled_rows(
    scenarios: list[SyntheticScenario],
    *,
    split: str,
    degradation: Degradation,
    seed: int = 42,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected = [scenario for scenario in scenarios if scenario.split() == split]
    for scenario_index, scenario in enumerate(selected):
        try:
            clean_result = extract_sections(scenario.points)
        except ValueError:
            continue
        sections = [section for section in clean_result.sections if section.kind == "curve"]
        if not sections:
            sections = [
                section
                for section in clean_result.sections
                if section.kind == "straight" and section.length_m >= 25.0
            ][:1]
        for section_index, section in enumerate(sections):
            rng = np.random.default_rng(seed + 50_000 + scenario_index * 313 + section_index)
            row = make_row(scenario, section, degradation, rng, missing_context=False)
            if row is not None:
                rows.append(row)
    return rows


def dataset_manifest(rows: list[dict[str, Any]], seed: int) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["split"]] = counts.get(row["split"], 0) + 1
    payload = [
        {
            "scenario_id": row["scenario_id"],
            "split": row["split"],
            "label": row["label"],
            "features": row["features"],
        }
        for row in sorted(rows, key=lambda item: (item["scenario_id"], item["label"]))
    ]
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return {
        "generator_version": GENERATOR_VERSION,
        "geometry_version": GEOMETRY_VERSION,
        "label_version": "label_v1",
        "seed": seed,
        "scenario_types": list(SCENARIO_TYPES),
        "row_count": len(rows),
        "split_counts": counts,
        "dataset_sha256": digest,
        "ood_scenario_type": OOD_SCENARIO_TYPE,
        "ood_radius_band_m": list(OOD_RADIUS_BAND_M),
    }

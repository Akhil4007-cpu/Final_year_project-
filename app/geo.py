from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence

EARTH_RADIUS_M = 6_371_008.8
DUPLICATE_EPSILON_M = 0.5
MAX_USABLE_GAP_M = 2_000.0
COARSE_SPACING_M = 60.0
CURVE_RADIUS_THRESHOLD_M = 1_500.0
MIN_VERTEX_TURN_DEG = 0.2
MIN_CURVE_SECTION_LENGTH_M = 15.0

Point = tuple[float, float]


class GeometryError(ValueError):
    def __init__(self, message: str, issues: list[str] | None = None) -> None:
        super().__init__(message)
        self.issues = issues or [message]


@dataclass
class GeometryQuality:
    status: str
    point_count: int
    duplicate_points_removed: int
    median_spacing_m: float | None
    max_gap_m: float | None
    coarse: bool
    long_gap_count: int
    score: float
    issues: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "point_count": self.point_count,
            "duplicate_points_removed": self.duplicate_points_removed,
            "median_spacing_m": _round(self.median_spacing_m, 2),
            "max_gap_m": _round(self.max_gap_m, 2),
            "coarse": self.coarse,
            "long_gap_count": self.long_gap_count,
            "score": _round(self.score, 3),
            "issues": list(self.issues),
        }


@dataclass
class Section:
    index: int
    kind: str
    start_index: int
    end_index: int
    length_m: float
    start_distance_m: float
    radius_m: float | None
    min_radius_m: float | None
    p10_radius_m: float | None
    heading_change_deg: float
    curve_length_m: float
    curvature_std: float
    max_turn_deg: float
    transition_abruptness: float
    spiral_like: bool
    gap_before_m: float | None
    sequence_index: int
    evidence: str
    quality: dict[str, Any]
    baseline_score: float | None = None
    model_score: float | None = None
    display_score: float | None = None
    uncertainty_low: float | None = None
    uncertainty_high: float | None = None
    disagreement: bool = False
    model_status: str = "not_scored"
    ood: bool = False

    def geometry_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "start_index": self.start_index,
            "end_index": self.end_index,
            "length_m": _round(self.length_m, 2),
            "start_distance_m": _round(self.start_distance_m, 2),
            "radius_m": _round(self.radius_m, 2),
            "min_radius_m": _round(self.min_radius_m, 2),
            "p10_radius_m": _round(self.p10_radius_m, 2),
            "heading_change_deg": _round(self.heading_change_deg, 2),
            "curve_length_m": _round(self.curve_length_m, 2),
            "curvature_std": _round(self.curvature_std, 5),
            "max_turn_deg": _round(self.max_turn_deg, 2),
            "transition_abruptness": _round(self.transition_abruptness, 3),
            "spiral_like": self.spiral_like,
            "gap_before_m": _round(self.gap_before_m, 2),
            "sequence_index": self.sequence_index,
        }


@dataclass
class GeometryResult:
    cleaned_points: list[Point]
    quality: GeometryQuality
    sections: list[Section]
    total_length_m: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "quality": self.quality.as_dict(),
            "total_length_m": _round(self.total_length_m, 2),
            "sections": [section.geometry_dict() for section in self.sections],
        }


def _round(value: float | None, digits: int) -> float | None:
    if value is None:
        return None
    if math.isinf(value) or math.isnan(value):
        return None
    return round(value, digits)


def haversine_m(a: Point, b: Point) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def _validate_raw(points: Sequence[Point]) -> None:
    if not isinstance(points, (list, tuple)):
        raise GeometryError("geometry must be a list of [lat, lon] points")
    if len(points) < 2:
        raise GeometryError("at least two geometry points are required")
    issues: list[str] = []
    for index, point in enumerate(points):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise GeometryError(f"point {index} must be [lat, lon]")
        lat, lon = point
        if isinstance(lat, bool) or isinstance(lon, bool):
            raise GeometryError(f"point {index} has a boolean coordinate")
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            raise GeometryError(f"point {index} has a non-numeric coordinate")
        if not math.isfinite(float(lat)) or not math.isfinite(float(lon)):
            raise GeometryError(f"point {index} has a non-finite coordinate")
        if not -90.0 <= float(lat) <= 90.0:
            issues.append(f"point {index} latitude outside [-90, 90]")
        if not -180.0 <= float(lon) <= 180.0:
            issues.append(f"point {index} longitude outside [-180, 180]")
    if issues:
        raise GeometryError("geometry coordinates are invalid", issues)


def _deduplicate(points: Sequence[Point]) -> tuple[list[Point], int]:
    cleaned: list[Point] = [(float(points[0][0]), float(points[0][1]))]
    removed = 0
    for raw in points[1:]:
        point = (float(raw[0]), float(raw[1]))
        if haversine_m(cleaned[-1], point) < DUPLICATE_EPSILON_M:
            removed += 1
            continue
        cleaned.append(point)
    return cleaned, removed


def validate_geometry(points: Sequence[Point]) -> tuple[list[Point], GeometryQuality]:
    _validate_raw(points)
    cleaned, removed = _deduplicate(points)
    if len(cleaned) < 2:
        raise GeometryError("geometry collapses to fewer than two distinct points")
    spacings = [haversine_m(cleaned[i], cleaned[i + 1]) for i in range(len(cleaned) - 1)]
    median_spacing = statistics.median(spacings)
    max_gap = max(spacings)
    long_gaps = sum(1 for value in spacings if value > MAX_USABLE_GAP_M)
    coarse = median_spacing > COARSE_SPACING_M
    issues: list[str] = []
    score = 1.0
    if removed:
        issues.append(f"removed {removed} duplicate point(s)")
    if coarse:
        issues.append("coarse polyline sampling")
        score -= 0.15
    if long_gaps:
        issues.append(f"{long_gaps} segment gap(s) over {int(MAX_USABLE_GAP_M)} m")
        score -= min(0.45, 0.15 * long_gaps)
    if len(cleaned) < 5:
        issues.append("very few geometry points")
        score -= 0.1
    if max_gap > 0 and min(spacings) / max_gap < 0.05:
        issues.append("highly uneven point spacing")
        score -= 0.05
    score = max(0.0, min(1.0, score))
    quality = GeometryQuality(
        status="degraded" if issues else "valid",
        point_count=len(cleaned),
        duplicate_points_removed=removed,
        median_spacing_m=median_spacing,
        max_gap_m=max_gap,
        coarse=coarse,
        long_gap_count=long_gaps,
        score=score,
        issues=issues,
    )
    return cleaned, quality


def project_to_local(points: Sequence[Point]) -> tuple[list[tuple[float, float]], float, float]:
    """Equirectangular local projection in metres, with antimeridian unwrapping."""
    lat0 = sum(point[0] for point in points) / len(points)
    lon0 = points[0][1]
    cos_lat0 = math.cos(math.radians(lat0))
    projected: list[tuple[float, float]] = []
    previous_unwrapped = lon0
    for lat, lon in points:
        unwrapped = lon
        if projected:
            while unwrapped - previous_unwrapped > 180.0:
                unwrapped -= 360.0
            while unwrapped - previous_unwrapped < -180.0:
                unwrapped += 360.0
        previous_unwrapped = unwrapped
        x = math.radians(unwrapped - lon0) * EARTH_RADIUS_M * cos_lat0
        y = math.radians(lat - lat0) * EARTH_RADIUS_M
        projected.append((x, y))
    return projected, lat0, lon0


def _circumradius(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    ab = math.dist(a, b)
    bc = math.dist(b, c)
    ac = math.dist(a, c)
    area2 = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
    if area2 < 1e-6 or ab < 1e-6 or bc < 1e-6 or ac < 1e-6:
        return math.inf
    return (ab * bc * ac) / (2.0 * area2)


def _signed_turn_deg(
    a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]
) -> float:
    v1 = (b[0] - a[0], b[1] - a[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1)
    n2 = math.hypot(*v2)
    if n1 < 1e-9 or n2 < 1e-9:
        return 0.0
    cross = v1[0] * v2[1] - v1[1] * v2[0]
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    return math.degrees(math.atan2(cross, dot))


def _turn_deg(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float]) -> float:
    return abs(_signed_turn_deg(a, b, c))


def _polyline_length(points: Sequence[Point]) -> float:
    return sum(haversine_m(points[i], points[i + 1]) for i in range(len(points) - 1))


def _section_geometry(
    latlon: Sequence[Point],
    projected: Sequence[tuple[float, float]],
    segment_start: int,
    segment_end: int,
    kind: str,
    start_distance_m: float,
    index: int,
    sequence_index: int,
    gap_before_m: float | None,
) -> Section:
    start_point = segment_start
    end_point = segment_end + 1
    points = latlon[start_point : end_point + 1]
    local = projected[start_point : end_point + 1]
    length_m = sum(math.dist(local[i], local[i + 1]) for i in range(len(local) - 1))
    radii: list[float] = []
    turns: list[float] = []
    weights: list[float] = []
    for i in range(1, len(local) - 1):
        radius = _circumradius(local[i - 1], local[i], local[i + 1])
        if math.isfinite(radius):
            radii.append(radius)
            turns.append(_turn_deg(local[i - 1], local[i], local[i + 1]))
            weights.append(
                (math.dist(local[i - 1], local[i]) + math.dist(local[i], local[i + 1])) / 2.0
            )
    if kind == "curve" and not radii:
        mid = len(local) // 2
        if mid >= 1 and mid < len(local) - 1:
            radius = _circumradius(local[mid - 1], local[mid], local[mid + 1])
            if math.isfinite(radius):
                radii = [radius]
                turns = [_turn_deg(local[mid - 1], local[mid], local[mid + 1])]
                weights = [length_m]

    radius_m: float | None = None
    min_radius: float | None = None
    p10_radius: float | None = None
    curvature_std = 0.0
    heading_change = sum(turns)
    max_turn = max(turns) if turns else 0.0
    transition_abruptness = 1.0
    spiral_like = False

    if radii:
        curvatures = [1.0 / max(radius, 0.1) for radius in radii]
        total_weight = sum(weights) or float(len(radii))
        effective_curvature = sum(k * w for k, w in zip(curvatures, weights)) / total_weight
        radius_m = 1.0 / max(effective_curvature, 1e-9)
        min_radius = min(radii)
        ordered = sorted(radii)
        p10_radius = ordered[max(0, int(round(0.1 * (len(ordered) - 1))))]
        mean_curvature = sum(curvatures) / len(curvatures)
        curvature_std = (
            statistics.pstdev(curvatures) if len(curvatures) > 1 else 0.0
        )
        if len(curvatures) >= 4 and mean_curvature > 1e-9:
            peak_index = max(
                range(len(curvatures)), key=lambda index: curvatures[index]
            )
            peak = curvatures[peak_index]
            diffs = [
                curvatures[i + 1] - curvatures[i] for i in range(len(curvatures) - 1)
            ]
            tolerance = max(peak * 0.02, 1e-9)
            rise_diffs = [diff for diff in diffs[:peak_index] if abs(diff) > tolerance]
            fall_diffs = [diff for diff in diffs[peak_index:] if abs(diff) > tolerance]
            rise_mono = (
                sum(1 for diff in rise_diffs if diff > 0) / len(rise_diffs)
                if rise_diffs
                else 1.0
            )
            fall_mono = (
                sum(1 for diff in fall_diffs if diff < 0) / len(fall_diffs)
                if fall_diffs
                else 1.0
            )
            rise_span = max(0.0, peak - curvatures[0])
            fall_span = max(0.0, peak - curvatures[-1])
            coverage = min(1.0, (rise_span + fall_span) / max(2.0 * peak, 1e-9))
            spiral_score = ((rise_mono + fall_mono) / 2.0) * coverage
            spiral_like = spiral_score >= 0.5
            transition_abruptness = max(0.0, min(1.0, 1.0 - spiral_score))
        else:
            transition_abruptness = 1.0

    quality = {
        "median_spacing_m": None,
        "max_gap_m": 0.0,
        "coarse": False,
        "long_gap": False,
    }
    spacings = [haversine_m(points[i], points[i + 1]) for i in range(len(points) - 1)]
    if spacings:
        quality["median_spacing_m"] = round(statistics.median(spacings), 2)
        quality["max_gap_m"] = round(max(spacings), 2)
        quality["coarse"] = statistics.median(spacings) > COARSE_SPACING_M
        quality["long_gap"] = max(spacings) > MAX_USABLE_GAP_M

    evidence = "scored"
    if quality["long_gap"]:
        evidence = "insufficient_evidence"
    if kind == "curve" and radius_m is None:
        evidence = "insufficient_evidence"

    return Section(
        index=index,
        kind=kind,
        start_index=start_point,
        end_index=end_point,
        length_m=length_m,
        start_distance_m=start_distance_m,
        radius_m=radius_m,
        min_radius_m=min_radius,
        p10_radius_m=p10_radius,
        heading_change_deg=heading_change,
        curve_length_m=length_m if kind == "curve" else 0.0,
        curvature_std=curvature_std,
        max_turn_deg=max_turn,
        transition_abruptness=transition_abruptness,
        spiral_like=spiral_like,
        gap_before_m=gap_before_m,
        sequence_index=sequence_index,
        evidence=evidence,
        quality=quality,
    )


def extract_sections(
    points: Sequence[Point],
    *,
    curve_radius_threshold_m: float = CURVE_RADIUS_THRESHOLD_M,
    min_turn_deg: float = MIN_VERTEX_TURN_DEG,
) -> GeometryResult:
    cleaned, quality = validate_geometry(points)
    projected, _, _ = project_to_local(cleaned)
    segment_count = len(cleaned) - 1
    vertex_turn: list[float | None] = [None] * len(cleaned)
    vertex_signed_turn: list[float | None] = [None] * len(cleaned)
    vertex_radius: list[float | None] = [None] * len(cleaned)
    for i in range(1, len(cleaned) - 1):
        radius = _circumradius(projected[i - 1], projected[i], projected[i + 1])
        signed_turn = _signed_turn_deg(projected[i - 1], projected[i], projected[i + 1])
        vertex_signed_turn[i] = signed_turn
        vertex_turn[i] = abs(signed_turn)
        vertex_radius[i] = radius

    def is_curving(vertex_index: int) -> bool:
        radius = vertex_radius[vertex_index]
        turn = vertex_turn[vertex_index]
        return (
            radius is not None
            and math.isfinite(radius)
            and radius <= curve_radius_threshold_m
            and turn is not None
            and turn >= min_turn_deg
        )

    segment_kind: list[str] = []
    for i in range(segment_count):
        curving = is_curving(i) or is_curving(i + 1)
        segment_kind.append("curve" if curving else "straight")

    groups: list[tuple[str, int, int]] = []
    start = 0
    for i in range(1, segment_count):
        if segment_kind[i] != segment_kind[start]:
            groups.append((segment_kind[start], start, i - 1))
            start = i
    groups.append((segment_kind[start], start, segment_count - 1))

    split_groups: list[tuple[str, int, int]] = []
    for kind, group_start, group_end in groups:
        if kind != "curve" or group_start == group_end:
            split_groups.append((kind, group_start, group_end))
            continue
        bounds = [group_start]
        last_sign = 0
        last_radius: float | None = None
        for vertex in range(group_start + 1, group_end + 1):
            v_signed_turn = vertex_signed_turn[vertex]
            v_radius = vertex_radius[vertex]
            if v_signed_turn is not None and abs(v_signed_turn) >= 0.5:
                sign = 1 if v_signed_turn > 0 else -1
                if last_sign and sign != last_sign and vertex > bounds[-1] + 1:
                    bounds.append(vertex)
                last_sign = sign
            if (
                v_radius is not None
                and math.isfinite(v_radius)
                and last_radius is not None
                and math.isfinite(last_radius)
                and v_radius < 2000.0
                and last_radius < 2000.0
                and max(v_radius, last_radius) / max(1e-9, min(v_radius, last_radius)) > 3.0
                and vertex > bounds[-1] + 1
            ):
                bounds.append(vertex)
            if v_radius is not None and math.isfinite(v_radius):
                last_radius = v_radius
        bounds.append(group_end + 1)
        for left, right in zip(bounds[:-1], bounds[1:]):
            if right > left:
                split_groups.append(("curve", left, right - 1))
    groups = split_groups

    sections: list[Section] = []
    distance = 0.0
    sequence = 0
    previous_curve_end: float | None = None
    for kind, seg_start, seg_end in groups:
        gap_before = None
        if kind == "curve" and previous_curve_end is not None:
            gap_before = max(0.0, distance - previous_curve_end)
        section = _section_geometry(
            cleaned,
            projected,
            seg_start,
            seg_end,
            kind,
            distance,
            len(sections),
            sequence,
            gap_before,
        )
        if (
            kind == "curve"
            and section.length_m < 25.0
            and section.heading_change_deg < 10.0
        ):
            section.kind = "straight"
            section.curve_length_m = 0.0
            section.radius_m = None
            section.min_radius_m = None
            section.p10_radius_m = None
            section.sequence_index = 0
            section.gap_before_m = None
        if section.kind == "curve":
            sequence += 1
            previous_curve_end = distance + section.length_m
        sections.append(section)
        distance += section.length_m

    total_length = distance
    return GeometryResult(
        cleaned_points=cleaned,
        quality=quality,
        sections=sections,
        total_length_m=total_length,
    )


def point_to_polyline_distance_m(point: Point, polyline: Sequence[Point]) -> float:
    if len(polyline) < 2:
        raise GeometryError("polyline must contain at least two points")
    projected, _, _ = project_to_local([point, *polyline])
    px, py = projected[0]
    line = projected[1:]
    best = math.inf
    for i in range(len(line) - 1):
        ax, ay = line[i]
        bx, by = line[i + 1]
        dx, dy = bx - ax, by - ay
        denominator = dx * dx + dy * dy
        if denominator < 1e-12:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denominator))
        cx, cy = ax + t * dx, ay + t * dy
        best = min(best, math.hypot(px - cx, py - cy))
    return best

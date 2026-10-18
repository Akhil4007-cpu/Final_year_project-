from __future__ import annotations

import math

import pytest

from app.geo import (
    GeometryError,
    extract_sections,
    haversine_m,
    point_to_polyline_distance_m,
    project_to_local,
    validate_geometry,
)

# A real Hyderabad polyline used across geometry tests.
HYDERABAD_ROUTE: list[tuple[float, float]] = [
    (17.384885, 78.486691),
    (17.383500, 78.485000),
    (17.382000, 78.483200),
    (17.380100, 78.481500),
    (17.378000, 78.480900),
    (17.376000, 78.481500),
    (17.374200, 78.482800),
    (17.372800, 78.484600),
    (17.371900, 78.486800),
    (17.371600, 78.489200),
    (17.372000, 78.491600),
    (17.373100, 78.493800),
]


def test_haversine_known_distance():
    # ~111 km per degree of latitude.
    distance = haversine_m((0.0, 0.0), (1.0, 0.0))
    assert 110_000 < distance < 112_000


def test_haversine_zero_for_identical():
    assert haversine_m((17.38, 78.48), (17.38, 78.48)) == pytest.approx(0.0, abs=1e-6)


def test_validate_geometry_rejects_single_point():
    with pytest.raises(GeometryError):
        validate_geometry([(17.0, 78.0)])


def test_validate_geometry_rejects_non_numeric():
    with pytest.raises(GeometryError):
        validate_geometry([(17.0, 78.0), ("x", 78.0)])


def test_validate_geometry_rejects_boolean_coordinate():
    with pytest.raises(GeometryError):
        validate_geometry([(17.0, 78.0), (True, 78.0)])


def test_validate_geometry_rejects_out_of_range():
    with pytest.raises(GeometryError):
        validate_geometry([(95.0, 78.0), (17.0, 78.0)])


def test_validate_geometry_deduplicates():
    points = [(17.384885, 78.486691), (17.384885, 78.486691), (17.382000, 78.483200)]
    cleaned, quality = validate_geometry(points)
    assert len(cleaned) == 2
    assert quality.duplicate_points_removed == 1


def test_validate_geometry_flags_coarse_sampling():
    points = [(17.0 + i * 0.05, 78.0) for i in range(4)]
    _, quality = validate_geometry(points)
    assert quality.coarse is True
    assert quality.status == "degraded"


def test_extract_sections_finds_curves():
    result = extract_sections(HYDERABAD_ROUTE)
    assert result.sections
    kinds = {section.kind for section in result.sections}
    assert "curve" in kinds
    assert result.total_length_m > 0


def test_curve_section_has_radius():
    result = extract_sections(HYDERABAD_ROUTE)
    curves = [s for s in result.sections if s.kind == "curve"]
    assert curves
    tight = min(curves, key=lambda s: s.radius_m or math.inf)
    assert tight.radius_m is not None
    assert tight.radius_m > 0


def test_straight_line_has_no_curves():
    line = [(17.38 + i * 0.0006, 78.48) for i in range(12)]
    result = extract_sections(line)
    assert all(s.kind == "straight" for s in result.sections)


def test_project_to_local_uses_first_longitude_and_centroid_latitude():
    projected, lat0, lon0 = project_to_local(HYDERABAD_ROUTE)
    # Longitude origin is the first point, so its easting is zero.
    assert projected[0][0] == pytest.approx(0.0, abs=1e-6)
    # Latitude origin is the centroid, so the centroid latitude maps to y = 0.
    centroid_y = (HYDERABAD_ROUTE[0][0] - lat0) * (math.pi / 180) * 6_371_008.8
    assert projected[0][1] == pytest.approx(centroid_y, abs=1e-3)
    assert lon0 == pytest.approx(HYDERABAD_ROUTE[0][1])


def test_point_to_polyline_distance_on_line():
    polyline = [(17.38, 78.48), (17.39, 78.48)]
    on_line = point_to_polyline_distance_m((17.385, 78.48), polyline)
    assert on_line < 1.0


def test_point_to_polyline_distance_off_line():
    polyline = [(17.38, 78.48), (17.39, 78.48)]
    off = point_to_polyline_distance_m((17.385, 78.50), polyline)
    assert off > 100.0


def test_point_to_polyline_rejects_short_polyline():
    with pytest.raises(GeometryError):
        point_to_polyline_distance_m((17.38, 78.48), [(17.38, 78.48)])

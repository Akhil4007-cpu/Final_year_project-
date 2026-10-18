from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.advisory import build_advisories
from app.aggregation import aggregate_sections, compare_routes
from app.baseline import ASSUMPTIONS, score_band
from app.features import resolve_speed
from app.geo import GeometryError, Section, extract_sections
from app.model import ModelService
from app.providers import ProviderService

MODEL_ASSUMPTIONS = [
    "The geometry estimator is trained only on synthetic scenarios (generator_v1); "
    "it has not been validated on measured rides or historical crash outcomes.",
    "When the model and physics baseline disagree by more than 20 points, the "
    "baseline is displayed and the section is marked baseline_fallback.",
    "Route scores require at least 60% of route length to have scored geometry; "
    "unscored length is reported, never treated as zero challenge.",
    "Geometry challenge is a computed indicator, not an accident probability.",
    "Route comparison ranks only weighted geometry challenge; it is not a safety ranking.",
]

DISCLAIMER = (
    "Geometry challenge indicator — not an accident probability. "
    "Advisory based on mapped road shape; real conditions may differ."
)
SCORING_DISTANCE_BASIS = "mapped route geometry length"


class RouteAnalysisService:
    def __init__(self, provider: ProviderService, model: ModelService) -> None:
        self.provider = provider
        self.model = model

    async def analyze(
        self,
        *,
        origin: tuple[float, float],
        destination: tuple[float, float],
        alternatives: bool = True,
        speed_kmh: float | None = None,
    ) -> dict[str, Any]:
        provider_data = await self.provider.route(
            origin, destination, alternatives=alternatives
        )
        speed_used, speed_missing, speed_source = resolve_speed(speed_kmh, None)
        model_status = self.model.status()
        model_available = self.model.available
        routes: list[dict[str, Any]] = []
        for route in provider_data["routes"]:
            routes.append(self._analyze_route(route, speed_kmh=speed_kmh, model_available=model_available))

        comparison = None
        if len(routes) >= 2:
            comparison = compare_routes(routes)
        scored_any = any(route["state"] == "scored" for route in routes)
        return {
            "state": "scored" if scored_any else "insufficient_evidence",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "provider": provider_data["provider"],
            "model": model_status,
            "inputs": {
                "speed_kmh": round(speed_used, 2),
                "speed_source": speed_source,
                "speed_is_advisory": speed_missing,
                "road_class_supplied": False,
                "grade_supplied": False,
                "scoring_distance_basis": SCORING_DISTANCE_BASIS,
            },
            "routes": routes,
            "comparison": comparison,
            "assumptions": [*ASSUMPTIONS, *MODEL_ASSUMPTIONS],
            "disclaimer": DISCLAIMER,
        }

    def _analyze_route(
        self,
        route: dict[str, Any],
        *,
        speed_kmh: float | None,
        model_available: bool,
    ) -> dict[str, Any]:
        try:
            geometry = extract_sections(route["geometry"])
        except GeometryError as exc:
            return {
                "id": route["id"],
                "state": "unavailable",
                "distance_m": route["distance_m"],
                "duration_s": route["duration_s"],
                "geometry_length_m": 0.0,
                "geometry_quality": {
                    "status": "invalid",
                    "point_count": len(route["geometry"]),
                    "duplicate_points_removed": 0,
                    "median_spacing_m": None,
                    "max_gap_m": None,
                    "coarse": False,
                    "long_gap_count": 0,
                    "score": 0.0,
                    "issues": list(exc.issues),
                },
                "geometry": route["geometry"],
                "summary": _unavailable_summary(
                    reason="Mapped route geometry could not be validated.",
                    total_length_m=route["distance_m"],
                ),
                "sections": [],
                "advisories": [],
                "provider_route_index": route["provider_route_index"],
                "error": {
                    "code": "insufficient_evidence",
                    "message": str(exc),
                    "issues": list(exc.issues),
                },
            }

        self.model.score_sections(
            geometry.sections,
            road_class=None,
            speed_kmh=speed_kmh,
            grade_pct=None,
            geometry_quality_score=geometry.quality.score,
        )
        summary = aggregate_sections(
            geometry.sections,
            total_length_m=geometry.total_length_m,
            model_available=model_available,
        )
        advisories = build_advisories(geometry.sections)
        return {
            "id": route["id"],
            "state": summary["state"],
            "distance_m": round(route["distance_m"], 2),
            "duration_s": round(route["duration_s"], 2),
            "geometry_length_m": round(geometry.total_length_m, 2),
            "geometry_quality": geometry.quality.as_dict(),
            "geometry": geometry.cleaned_points,
            "summary": summary,
            "sections": [_section_payload(section) for section in geometry.sections],
            "advisories": advisories,
            "provider_route_index": route["provider_route_index"],
            "error": None,
        }


def _section_payload(section: Section) -> dict[str, Any]:
    payload = section.geometry_dict()
    scored = section.evidence == "scored" and section.baseline_score is not None
    uncertainty = None
    if section.uncertainty_low is not None and section.uncertainty_high is not None:
        uncertainty = {"low": section.uncertainty_low, "high": section.uncertainty_high}
    if not scored:
        provenance = ["unavailable"]
    elif section.model_status == "model_estimate":
        provenance = ["computed_geometry", "model_estimate"]
    else:
        provenance = ["computed_geometry"]
    payload.update(
        {
            "evidence": section.evidence,
            "provenance": provenance,
            "baseline_score": section.baseline_score,
            "model_score": section.model_score,
            "display_score": section.display_score,
            "band": score_band(section.display_score),
            "uncertainty": uncertainty,
            "disagreement": section.disagreement,
            "ood": section.ood,
            "model_status": section.model_status,
            "geometry_quality": dict(section.quality),
        }
    )
    return payload


def _unavailable_summary(*, reason: str, total_length_m: float) -> dict[str, Any]:
    return {
        "state": "insufficient_evidence",
        "coverage": 0.0,
        "scored_length_m": 0.0,
        "total_length_m": round(float(total_length_m), 2),
        "missing_length_m": round(float(total_length_m), 2),
        "score": None,
        "band": "unavailable",
        "baseline_score": None,
        "uncertainty": None,
        "uncertainty_coverage": 0.0,
        "model_available": False,
        "model_used_sections": 0,
        "fallback_sections": 0,
        "ood_sections": 0,
        "provenance": ["unavailable"],
        "reason": reason,
    }

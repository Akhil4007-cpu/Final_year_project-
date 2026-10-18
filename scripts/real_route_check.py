"""LIVE real-route plausibility check (OPT-IN, network-dependent, NOT part of CI).

Runs five real Hyderabad origin/destination pairs through the actual production path —
Nominatim geocoding, OSRM routing, geometry validation, section extraction, the physics
baseline and the GACE model — and records what comes out.

This is a PLAUSIBILITY CHECK ONLY. It has no ground-truth labels, so it makes **no
accuracy claim of any kind**: it answers "does the pipeline behave sensibly on real map
data, and what does real OSM geometry do to our coverage / radius / fallback numbers?",
and nothing more. The synthetic §7.5 suite remains the only place error is measured.

Run explicitly with:  python scripts/real_route_check.py --confirm
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.analysis import RouteAnalysisService  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.model import ModelService  # noqa: E402
from app.providers import ProviderService  # noqa: E402

OUT = PROJECT_ROOT / "docs" / "real_route_check.json"

# Real places in Hyderabad, Telangana. Resolved live through Nominatim, not assumed.
PAIRS = [
    ("Charminar, Hyderabad", "Secunderabad Railway Station, Hyderabad"),
    ("Golconda Fort, Hyderabad", "HITEC City, Madhapur, Hyderabad"),
    ("Hussain Sagar Lake, Hyderabad", "Gachibowli, Hyderabad"),
    ("Kukatpally, Hyderabad", "Banjara Hills, Hyderabad"),
    ("Mehdipatnam, Hyderabad", "Uppal Cross Road, Hyderabad"),
]

NOTE = (
    "PLAUSIBILITY CHECK ONLY — no ground truth exists for these routes, so no accuracy, "
    "error or safety claim is made or implied. Scores are the geometry-challenge indicator "
    "computed from OpenStreetMap way geometry via OSRM; agreement with real riding "
    "conditions is untested. Speed is the assumed advisory band, not measured. Providers "
    "are the public OSRM demo and Nominatim instances, paced at >=1.1 s per request."
)


def _radii(sections: list[dict[str, Any]]) -> list[float]:
    values = [
        float(section["min_radius_m"])
        for section in sections
        if section.get("min_radius_m") is not None
    ]
    return sorted(values)[:3]


def _radius_census(sections: list[dict[str, Any]]) -> dict[str, Any]:
    """Real OSM polylines produce implausibly small radii where vertices are bunched;
    count them so the plausibility write-up quantifies rather than eyeballs it."""
    values = sorted(
        float(section["min_radius_m"])
        for section in sections
        if section.get("min_radius_m") is not None
    )
    if not values:
        return {"radius_sections": 0, "radius_under_10m": 0, "radius_under_25m": 0,
                "radius_median_m": None, "radius_min_m": None}
    return {
        "radius_sections": len(values),
        "radius_under_10m": sum(1 for value in values if value < 10.0),
        "radius_under_25m": sum(1 for value in values if value < 25.0),
        "radius_median_m": round(values[len(values) // 2], 2),
        "radius_min_m": round(values[0], 2),
    }


def _route_record(route: dict[str, Any]) -> dict[str, Any]:
    sections = route["sections"]
    summary = route["summary"]
    bands: dict[str, int] = {}
    for section in sections:
        bands[section["band"]] = bands.get(section["band"], 0) + 1
    statuses: dict[str, int] = {}
    for section in sections:
        statuses[section["model_status"]] = statuses.get(section["model_status"], 0) + 1
    return {
        "provider_route_index": route["provider_route_index"],
        "state": route["state"],
        "distance_m": route["distance_m"],
        "geometry_length_m": route["geometry_length_m"],
        "coverage": summary["coverage"],
        "scored_length_m": summary["scored_length_m"],
        "missing_length_m": summary["missing_length_m"],
        "sections_total": len(sections),
        "sections_curve": sum(1 for section in sections if section["kind"] == "curve"),
        "sections_scored": sum(1 for section in sections if section["evidence"] == "scored"),
        "smallest_radius_estimates_m": _radii(sections),
        "radius_census": _radius_census(sections),
        "high_band_sections": bands.get("high", 0),
        "high_band_and_radius_under_25m": sum(
            1
            for section in sections
            if section["band"] == "high"
            and section.get("min_radius_m") is not None
            and float(section["min_radius_m"]) < 25.0
        ),
        "median_vertex_spacing_m": route["geometry_quality"]["median_spacing_m"],
        "max_vertex_gap_m": route["geometry_quality"]["max_gap_m"],
        "band_distribution": bands,
        "advisories": len(route["advisories"]),
        "model_status_distribution": statuses,
        "disagreement_sections": sum(1 for section in sections if section["disagreement"]),
        "ood_sections": summary["ood_sections"],
        "route_score": summary["score"],
        "route_band": summary["band"],
        "geometry_quality_issues": route["geometry_quality"]["issues"],
        "error": route["error"],
    }


async def _one_pair(provider: ProviderService, analysis: RouteAnalysisService, origin_q: str, dest_q: str) -> dict[str, Any]:
    record: dict[str, Any] = {"origin_query": origin_q, "destination_query": dest_q}
    try:
        origin_hits = (await provider.geocode(origin_q, limit=1))["results"]
        destination_hits = (await provider.geocode(dest_q, limit=1))["results"]
    except Exception as exc:  # noqa: BLE001 - a live probe must record any provider failure
        record["geocode_error"] = f"{type(exc).__name__}: {exc}"
        return record
    if not origin_hits or not destination_hits:
        record["geocode_error"] = "one or both places did not resolve"
        record["origin_resolved"] = bool(origin_hits)
        record["destination_resolved"] = bool(destination_hits)
        return record
    origin = (origin_hits[0]["lat"], origin_hits[0]["lon"])
    destination = (destination_hits[0]["lat"], destination_hits[0]["lon"])
    record["origin"] = {"display_name": origin_hits[0]["display_name"], "lat": origin[0], "lon": origin[1]}
    record["destination"] = {
        "display_name": destination_hits[0]["display_name"],
        "lat": destination[0],
        "lon": destination[1],
    }
    try:
        payload = await analysis.analyze(origin=origin, destination=destination, alternatives=True)
    except Exception as exc:  # noqa: BLE001 - a live probe must record any provider failure
        record["analysis_error"] = f"{type(exc).__name__}: {exc}"
        return record
    record["provider"] = payload["provider"]
    record["model_available"] = payload["model"]["available"]
    record["inputs"] = payload["inputs"]
    record["routes"] = [_route_record(route) for route in payload["routes"]]
    record["comparison"] = payload["comparison"]
    return record


def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    routes = [route for record in records for route in record.get("routes", [])]
    sections = sum(route["sections_total"] for route in routes)
    scored = sum(route["sections_scored"] for route in routes)
    fallback = sum(
        route["model_status_distribution"].get("baseline_fallback", 0) for route in routes
    )
    censuses = [route["radius_census"] for route in routes]
    radius_sections = sum(c["radius_sections"] for c in censuses)
    return {
        "route_records": len(routes),
        "pairs_with_a_route": sum(1 for record in records if record.get("routes")),
        "sections_total": sections,
        "sections_scored": scored,
        "scored_share": round(scored / sections, 4) if sections else None,
        "baseline_fallback_sections": fallback,
        "fallback_rate_over_scored": round(fallback / scored, 4) if scored else None,
        "ood_sections": sum(route["ood_sections"] for route in routes),
        "advisories": sum(route["advisories"] for route in routes),
        "coverage_min": min((route["coverage"] for route in routes), default=None),
        "coverage_max": max((route["coverage"] for route in routes), default=None),
        "radius_sections": radius_sections,
        "radius_under_10m": sum(c["radius_under_10m"] for c in censuses),
        "radius_under_25m": sum(c["radius_under_25m"] for c in censuses),
        "smallest_radius_m": min(
            (c["radius_min_m"] for c in censuses if c["radius_min_m"] is not None),
            default=None,
        ),
        "high_band_sections": sum(route["high_band_sections"] for route in routes),
        "high_band_and_radius_under_25m": sum(
            route["high_band_and_radius_under_25m"] for route in routes
        ),
        "states": {
            state: sum(1 for route in routes if route["state"] == state)
            for state in sorted({route["state"] for route in routes})
        },
    }


async def _run() -> dict[str, Any]:
    settings = get_settings()
    provider = ProviderService(settings)
    model = ModelService(settings.model_artifact, settings.require_model)
    analysis = RouteAnalysisService(provider, model)
    results = []
    for origin_query, destination_query in PAIRS:
        results.append(await _one_pair(provider, analysis, origin_query, destination_query))
        await asyncio.sleep(1.1)
    await provider.aclose()
    return {
        "label": "live",
        "kind": "plausibility check only — NOT an accuracy test",
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "providers": {
            "nominatim": settings.nominatim_base_url,
            "osrm": settings.osrm_base_url,
            "user_agent": settings.provider_user_agent,
        },
        "model_artifact": str(settings.model_artifact),
        "pair_count": len(PAIRS),
        "aggregate": _aggregate(results),
        "note": NOTE,
        "results": results,
    }


def _place(record: dict[str, Any], which: str) -> str:
    place = record.get(which)
    if isinstance(place, dict):
        return str(place.get("display_name", ""))
    key = "origin_query" if which == "origin" else "destination_query"
    return str(record.get(key, ""))


def _emit(text: str) -> None:
    """Windows consoles default to cp1252, which cannot encode map data such as
    non-Latin place names; fall back to a lossy ASCII rendering rather than losing
    the table after the live calls have already been paid for."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def _table(data: dict[str, Any]) -> list[str]:
    lines = [
        "| # | route (live geocode) | state | sections (curve/scored) | coverage | smallest radii (m) | radii <10 m / <25 m | median radius (m) | advisories | fallback sections | band |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for index, record in enumerate(data["results"], start=1):
        label = (
            f"{_place(record, 'origin')[:28]} -> {_place(record, 'destination')[:28]}"
        )
        routes = record.get("routes") or []
        if not routes:
            lines.append(
                f"| {index} | {label} | no route | — | — | — | — | — | — | — | "
                f"{record.get('geocode_error') or record.get('analysis_error') or 'provider failure'} |"
            )
            continue
        first = routes[0]
        census = first["radius_census"]
        lines.append(
            f"| {index} | {label} | {first['state']} | "
            f"{first['sections_total']} ({first['sections_curve']}/{first['sections_scored']}) | "
            f"{first['coverage'] * 100:.0f}% | "
            f"{', '.join(f'{r:.0f}' for r in first['smallest_radius_estimates_m']) or '—'} | "
            f"{census['radius_under_10m']} / {census['radius_under_25m']} of {census['radius_sections']} | "
            f"{census['radius_median_m']} | "
            f"{first['advisories']} | "
            f"{first['model_status_distribution'].get('baseline_fallback', 0)} | {first['route_band']} |"
        )
    return lines


def main() -> int:
    if "--confirm" not in sys.argv:
        print(
            "LIVE check: hits public Nominatim + OSRM. Re-run with --confirm to proceed. "
            "Plausibility only, no accuracy claim.",
            file=sys.stderr,
        )
        return 2
    data = asyncio.run(_run())
    OUT.write_text(json.dumps(data, indent=2), encoding="utf-8")
    _emit("\n".join(_table(data)))
    _emit("\naggregate:\n" + json.dumps(data["aggregate"], indent=2))
    _emit(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

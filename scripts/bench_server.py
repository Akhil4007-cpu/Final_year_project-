"""Server-side route-analysis benchmark (offline, reproducible).

Measures the controllable FastAPI request path for POST /routes/analyze with the
provider stubbed by an in-process httpx MockTransport, so no network is touched and
the result is stable enough to compare before/after an optimisation. It loads the real
committed GACE artifact (``ml/artifacts/model.joblib``) so scoring is genuinely on the
hot path. The public-provider rate-limit throttle is disabled (enforce_public_limits=
False) and the API rate limit is raised so the measurement reflects compute cost, not
test scaffolding.

Run:  python scripts/bench_server.py
Writes: docs/perf_server_bench.json
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import httpx
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.services import build_services  # noqa: E402

ARTIFACT = PROJECT_ROOT / "ml" / "artifacts" / "model.joblib"
OUT = PROJECT_ROOT / "docs" / "perf_server_bench.json"
CONCURRENCY_LEVELS = (1, 5, 20)
REQUESTS_PER_LEVEL = 60


def serpentine_polyline(n_points: int = 120) -> list[tuple[float, float]]:
    """A winding polyline (alternating curves) around Hyderabad -> ~20 scored sections."""
    lat0, lon0 = 17.3849, 78.4867
    pts: list[tuple[float, float]] = []
    for i in range(n_points):
        t = i / (n_points - 1)
        lon = lon0 + 0.020 * t
        lat = lat0 + 0.004 * (t * 6.0) + 0.0016 * np.sin(t * 6 * np.pi)
        pts.append((round(lat, 6), round(lon, 6)))
    return pts


def _osrm_payload(alternatives: bool) -> dict[str, Any]:
    routes = []
    for idx in range(2 if alternatives else 1):
        geometry = serpentine_polyline(120 if idx == 0 else 96)
        distance_m = 1800.0 + 400.0 * idx
        routes.append(
            {
                "distance": distance_m,
                "duration": distance_m / 12.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lat, lon in geometry],
                },
            }
        )
    return {"code": "Ok", "routes": routes, "waypoints": []}


def _mock_handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.startswith("/route/v1/driving/"):
        alternatives = "true" in str(request.url.params.get("alternatives", "")).lower()
        return httpx.Response(200, json=_osrm_payload(alternatives))
    return httpx.Response(500, json={"code": "Unsupported"})


def _stats(samples: list[float]) -> dict[str, float]:
    arr = np.percentile(samples, [50, 95, 99])
    return {
        "n": len(samples),
        "p50_ms": round(float(arr[0]), 3),
        "p95_ms": round(float(arr[1]), 3),
        "p99_ms": round(float(arr[2]), 3),
        "mean_ms": round(float(np.mean(samples)), 3),
        "max_ms": round(float(max(samples)), 3),
    }


def _make_settings(tmp_dir: Path) -> Settings:
    return Settings(
        env="test",
        db_path=tmp_dir / "bench.sqlite3",
        model_artifact=ARTIFACT,
        require_model=True,
        osrm_base_url="http://osrm.mock",
        nominatim_base_url="http://nominatim.mock",
        provider_user_agent="RoadGuardBench/0.1",
        provider_timeout_seconds=5.0,
        allowed_origins=("http://127.0.0.1:8000",),
        cookie_secure=False,
        session_ttl_seconds=3600,
        hazard_ttl_hours=24,
        route_rate_per_minute=1_000_000,
        hazard_rate_per_hour=1_000_000,
        login_rate_per_minute=1_000_000,
    )


async def _measure_analyze(services) -> dict[str, Any]:
    origin = (17.3849, 78.4867)
    destination = (17.3889, 78.5067)

    # single-call latency distribution (warm)
    for _ in range(10):
        await services.analysis.analyze(
            origin=origin, destination=destination, alternatives=True, speed_kmh=45.0
        )
    single: list[float] = []
    for _ in range(REQUESTS_PER_LEVEL):
        start = time.perf_counter()
        await services.analysis.analyze(
            origin=origin, destination=destination, alternatives=True, speed_kmh=45.0
        )
        single.append((time.perf_counter() - start) * 1000.0)

    concurrency: dict[str, dict[str, Any]] = {}
    for level in CONCURRENCY_LEVELS:
        async def one() -> float:
            start = time.perf_counter()
            await services.analysis.analyze(
                origin=origin, destination=destination, alternatives=True, speed_kmh=45.0
            )
            return (time.perf_counter() - start) * 1000.0

        sem = asyncio.Semaphore(level)

        async def capped() -> float:
            async with sem:
                return await one()

        wall_start = time.perf_counter()
        latencies = await asyncio.gather(*(capped() for _ in range(REQUESTS_PER_LEVEL)))
        wall = time.perf_counter() - wall_start
        concurrency[f"c{level}"] = {
            **_stats(list(latencies)),
            "throughput_rps": round(len(latencies) / wall, 2) if wall > 0 else None,
        }

    return {
        "endpoint": "POST /routes/analyze (provider mocked, alternatives=2 routes)",
        "single_call_latency": _stats(single),
        "concurrency": concurrency,
    }


async def _measure_model_scoring(services) -> dict[str, Any]:
    """Before/after for the scoring hot path on a fresh serpentine route.

    ``loop`` = score each section with its own model.predict call (the pre-change
    behaviour, still what ``score_section`` does for one section). ``batched`` =
    one vectorized ``score_sections`` call for the whole route (the optimised path
    the API now uses). Same sections, same service, same run, alternating order to
    cancel warm-up drift.
    """
    from app.geo import extract_sections

    geometry = extract_sections(serpentine_polyline(120))
    sections = geometry.sections
    quality = geometry.quality.score

    def loop_once() -> None:
        for section in sections:
            services.model.score_section(
                section, road_class=None, speed_kmh=45.0, grade_pct=None,
                geometry_quality_score=quality,
            )

    def batch_once() -> None:
        services.model.score_sections(
            sections, road_class=None, speed_kmh=45.0, grade_pct=None,
            geometry_quality_score=quality,
        )

    for _ in range(5):
        loop_once()
        batch_once()

    loop_reps: list[float] = []
    batch_reps: list[float] = []
    for _ in range(30):
        start = time.perf_counter()
        loop_once()
        loop_reps.append((time.perf_counter() - start) * 1000.0)

        start = time.perf_counter()
        batch_once()
        batch_reps.append((time.perf_counter() - start) * 1000.0)

    loop_stats = _stats(loop_reps)
    batch_stats = _stats(batch_reps)
    return {
        "sections": len(sections),
        "per_section_loop_before": {**loop_stats, "per_section_mean_ms": round(loop_stats["mean_ms"] / len(sections), 4)},
        "single_batch_after": {**batch_stats, "per_section_mean_ms": round(batch_stats["mean_ms"] / len(sections), 4)},
        "p50_speedup_x": round(loop_stats["p50_ms"] / batch_stats["p50_ms"], 2) if batch_stats["p50_ms"] else None,
    }


async def _measure_cache_effectiveness(services) -> dict[str, Any]:
    """Bounded provider cache: repeat identical route must hit cache, not re-fetch."""
    # Distinct coordinates unused by earlier phases so the first call is a genuine cold fetch.
    origin = (17.4100, 78.4500)
    destination = (17.4200, 78.4600)
    r1 = await services.provider.route(origin, destination, alternatives=True)
    r2 = await services.provider.route(origin, destination, alternatives=True)
    # force cache eviction behaviour with many distinct keys
    before_entries = services.provider.cache_entries
    for i in range(1, 301):
        d = (origin[0] + 0.0001 * i, origin[1] + 0.0001 * i)
        await services.provider.route(origin, d, alternatives=False)
    return {
        "cold_call_cached": r1["provider"]["cached"],
        "warm_identical_call_cached": r2["provider"]["cached"],
        "cache_entries_before_flood": before_entries,
        "cache_entries_after_300_distinct": services.provider.cache_entries,
        "cache_limit": 256,
        "cache_bounded": services.provider.cache_entries <= 256,
    }


async def _run(tmp_dir: Path) -> dict[str, Any]:
    settings = _make_settings(tmp_dir)
    init_db(settings.db_path)
    services = build_services(settings)
    assert services.model.available, f"model unavailable: {services.model.reason}"

    # Swap in a mock-transport provider so no network is used.
    await services.provider.aclose()
    mock_client = httpx.AsyncClient(transport=httpx.MockTransport(_mock_handler))
    from app.providers import ProviderService

    services.provider = ProviderService(settings, client=mock_client, enforce_public_limits=False)
    services.analysis.provider = services.provider

    result = {
        "python": sys.version.split()[0],
        "model": {
            "artifact": str(ARTIFACT),
            "model_name": services.model.model_name,
        },
        "analyze": await _measure_analyze(services),
        "model_scoring": await _measure_model_scoring(services),
        "provider_cache": await _measure_cache_effectiveness(services),
    }
    await services.aclose()
    await mock_client.aclose()
    return result


def main() -> int:
    tmp_dir = PROJECT_ROOT / "data" / "_bench_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    try:
        result = asyncio.run(_run(tmp_dir))
    finally:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    print(f"\nWrote {OUT}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""LIVE provider latency probe (OPT-IN, network-dependent, NOT part of CI).

Actually calls the public Nominatim + OSRM endpoints through the real
ProviderService and reports round-trip p50/p95. The provider enforces its
>=1.1s-per-request throttle and sends the configured User-Agent, so this is a
courteous, small sample rather than a load test. Public endpoints are shared and
variable, so treat these numbers as a real-world range, not a stable contract.

Run explicitly with:  python scripts/bench_provider_live.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.providers import ProviderService  # noqa: E402

OUT = PROJECT_ROOT / "docs" / "perf_provider_live.json"
GEOCODE_QUERIES = [
    "Charminar, Hyderabad",
    "Hussain Sagar Lake, Hyderabad",
    "Gandipet Lake, Hyderabad",
    "Kukatpally, Hyderabad",
    "Secunderabad Junction",
]
# (origin, destination) coordinate pairs near Hyderabad, in (lat, lon).
ROUTE_PAIRS = [
    ((17.3616, 78.4747), (17.3850, 78.4867)),
    ((17.4239, 78.4479), (17.3616, 78.4747)),
    ((17.3849, 78.4867), (17.4713, 78.4803)),
    ((17.4088, 78.4352), (17.3616, 78.4747)),
    ((17.3689, 78.4943), (17.4239, 78.4479)),
]


def _stats(samples: list[float]) -> dict[str, Any]:
    arr = np.percentile(samples, [50, 95])
    return {
        "n": len(samples),
        "p50_ms": round(float(arr[0]), 1),
        "p95_ms": round(float(arr[1]), 1),
        "max_ms": round(float(max(samples)), 1),
    }


async def _run() -> dict[str, Any]:
    settings = get_settings()
    # Own the courtesy pacing (>=1.1s between calls, sent with the configured UA) so the
    # internal throttle does not fold its sleep into the measured round-trip time.
    provider = ProviderService(settings, enforce_public_limits=False)
    geocode_ms: list[float] = []
    geocode_errors = 0
    for query in GEOCODE_QUERIES:
        await asyncio.sleep(1.1)
        start = time.perf_counter()
        try:
            await provider.geocode(query, limit=3)
            geocode_ms.append((time.perf_counter() - start) * 1000.0)
        except Exception as exc:  # noqa: BLE001 - live probe must record any provider failure
            geocode_errors += 1
            print(f"geocode failed for {query!r}: {type(exc).__name__}: {exc}", file=sys.stderr)

    route_ms: list[float] = []
    route_errors = 0
    for origin, destination in ROUTE_PAIRS:
        await asyncio.sleep(1.1)
        start = time.perf_counter()
        try:
            await provider.route(origin, destination, alternatives=True)
            route_ms.append((time.perf_counter() - start) * 1000.0)
        except Exception as exc:  # noqa: BLE001 - live probe must record any provider failure
            route_errors += 1
            print(f"route failed {origin}->{destination}: {type(exc).__name__}: {exc}", file=sys.stderr)

    await provider.aclose()
    result = {
        "label": "live",
        "measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "environment": f"osrm={settings.osrm_base_url} nominatim={settings.nominatim_base_url}",
        "note": (
            "Public shared endpoints; paced at >=1.1s between calls (external sleep) to "
            "respect usage policy, sent with the configured User-Agent; figures are the pure "
            "HTTP round-trip (network + TLS + provider compute), excluding the courtesy wait. "
            "A 'no matching place' geocode is a valid provider result, not a code failure. "
            "Variable by design."
        ),
        "geocode": {**_stats(geocode_ms), "errors": geocode_errors} if geocode_ms else {"errors": geocode_errors, "ok": 0},
        "route": {**_stats(route_ms), "errors": route_errors} if route_ms else {"errors": route_errors, "ok": 0},
    }
    return result


def main() -> int:
    if "--confirm" not in sys.argv:
        print("Live network probe. Re-run with --confirm to hit public Nominatim/OSRM.", file=sys.stderr)
        return 2
    result = asyncio.run(_run())
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

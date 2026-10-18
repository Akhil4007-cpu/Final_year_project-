"""POST /routes/analyze tests with a MOCKED provider (offline, deterministic).

The OSRM round-trip is replaced by an in-process httpx MockTransport so these run in CI
without network and exercise the full server path: provider parse -> extract_sections ->
batched score_sections -> aggregate -> build_advisories -> response serialisation. Labelled
`mock`: the route is synthetic, not a real Hyderabad drive. Graceful-failure cases assert the
app surfaces provider errors honestly and never invents a route (R4/insufficient-evidence).
"""

from __future__ import annotations

import json
import math
from contextlib import contextmanager
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.providers import ProviderService
from app.security import CLIENT_HEADER

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_ARTIFACT = PROJECT_ROOT / "ml" / "artifacts" / "model.joblib"
ORIGIN = (17.3849, 78.4867)
DEST = (17.3616, 78.4747)

HDRS = {CLIENT_HEADER: "web"}
BODY = {
    "origin": {"lat": ORIGIN[0], "lon": ORIGIN[1]},
    "destination": {"lat": DEST[0], "lon": DEST[1]},
    "alternatives": True,
    "speed_kmh": 45.0,
}


def _serpentine(n: int) -> list[tuple[float, float]]:
    lat0, lon0 = 17.3849, 78.4867
    pts = []
    for i in range(n):
        t = i / (n - 1)
        lon = lon0 + 0.020 * t
        lat = lat0 + 0.004 * (t * 6.0) + 0.0016 * math.sin(t * 6 * math.pi)
        pts.append((round(lat, 6), round(lon, 6)))
    return pts


def _ok_handler(request: httpx.Request) -> httpx.Response:
    alternatives = "true" in str(request.url.params.get("alternatives", "")).lower()
    routes = []
    for idx in range(2 if alternatives else 1):
        geometry = _serpentine(120 if idx == 0 else 96)
        distance = 1800.0 + 400.0 * idx
        routes.append(
            {
                "distance": distance,
                "duration": distance / 12.0,
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[lon, lat] for lat, lon in geometry],
                },
            }
        )
    return httpx.Response(200, json={"code": "Ok", "routes": routes, "waypoints": []})


def _down_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(503, json={"code": "E", "msg": "routing down"})


def _noroute_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"code": "NoRoute", "routes": []})


@contextmanager
def routed_client(tmp_path: Path, handler):
    settings = Settings(
        env="test",
        db_path=tmp_path / "routes.sqlite3",
        model_artifact=MODEL_ARTIFACT,
        require_model=False,
        osrm_base_url="http://osrm.mock",
        nominatim_base_url="http://nominatim.mock",
        provider_user_agent="RoadGuardTests/0.1",
        provider_timeout_seconds=5.0,
        allowed_origins=("http://testserver",),
        cookie_secure=False,
        session_ttl_seconds=3600,
        hazard_ttl_hours=24,
        route_rate_per_minute=1000,
        hazard_rate_per_hour=1000,
        login_rate_per_minute=1000,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        mock_http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        provider = ProviderService(
            settings, client=mock_http, enforce_public_limits=False
        )
        services = client.app.state.services
        services.provider = provider
        services.analysis.provider = provider
        yield client


def test_analyze_scores_route_with_advisories(tmp_path):
    with routed_client(tmp_path, _ok_handler) as client:
        r = client.post("/api/v1/routes/analyze", json=BODY, headers=HDRS)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state"] == "scored"
    assert len(body["routes"]) == 2
    route = body["routes"][0]
    assert route["state"] == "scored"
    assert route["sections"] and route["geometry"]
    assert isinstance(route["advisories"], list)
    # provider + model provenance tags are attached, not invented
    assert body["provider"]["name"] == "osrm"
    assert body["model"]["model_name"] == "hist_gradient_boosting"
    assert body["model"]["synthetic_training"] is True


def test_analyze_disclaimer_and_ban_accident_wording(tmp_path):
    with routed_client(tmp_path, _ok_handler) as client:
        r = client.post("/api/v1/routes/analyze", json=BODY, headers=HDRS)
    body = r.json()
    assert "geometry" in body["disclaimer"].lower()
    # R4: the whole response must never claim a route is "safe".
    flat = json.dumps(body).lower()
    assert "safe route" not in flat
    assert "prevents accidents" not in flat


def test_analyze_surfaces_provider_failure(tmp_path):
    with routed_client(tmp_path, _down_handler) as client:
        r = client.post("/api/v1/routes/analyze", json=BODY, headers=HDRS)
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "provider_unavailable"


def test_analyze_no_route_is_insufficient_evidence(tmp_path):
    with routed_client(tmp_path, _noroute_handler) as client:
        r = client.post("/api/v1/routes/analyze", json=BODY, headers=HDRS)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "insufficient_evidence"


def test_analyze_requires_client_header(tmp_path):
    with routed_client(tmp_path, _ok_handler) as client:
        r = client.post("/api/v1/routes/analyze", json=BODY)
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "authz_failure"


def test_analyze_rejects_bad_coordinates(tmp_path):
    bad = {
        "origin": {"lat": 200.0, "lon": 78.0},
        "destination": {"lat": 17.36, "lon": 78.47},
        "alternatives": True,
        "speed_kmh": 45.0,
    }
    with routed_client(tmp_path, _ok_handler) as client:
        r = client.post("/api/v1/routes/analyze", json=bad, headers=HDRS)
    assert r.status_code in (400, 422)

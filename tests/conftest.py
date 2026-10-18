from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.security import CLIENT_HEADER  # noqa: E402
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


def make_settings(tmp_path: Path, **overrides) -> Settings:
    base = dict(
        env="test",
        db_path=tmp_path / "test.sqlite3",
        model_artifact=tmp_path / "missing-model.joblib",
        require_model=False,
        osrm_base_url="http://osrm.test",
        nominatim_base_url="http://nominatim.test",
        provider_user_agent="RoadGuardTests/0.1",
        provider_timeout_seconds=2.0,
        allowed_origins=("http://testserver",),
        cookie_secure=False,
        session_ttl_seconds=3600,
        hazard_ttl_hours=24,
        route_rate_per_minute=1000,
        hazard_rate_per_hour=1000,
        login_rate_per_minute=1000,
    )
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return make_settings(tmp_path)


@pytest.fixture
def app(settings: Settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client


def mutate_headers() -> dict[str, str]:
    return {CLIENT_HEADER: "web"}


@pytest.fixture
def register(client):
    def _register(email: str, password: str = "StrongPass#2026"):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
            headers=mutate_headers(),
        )
        assert response.status_code == 201, response.text
        return response.json()["user"]

    return _register


@pytest.fixture
def login(client):
    def _login(email: str, password: str = "StrongPass#2026"):
        response = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
            headers=mutate_headers(),
        )
        assert response.status_code == 200, response.text
        return response.json()["user"]

    return _login


@pytest.fixture
def admin_user(client, settings):
    from app.auth import AuthService

    service = AuthService(settings.db_path, settings.session_ttl_seconds)
    user = service.register("admin@roadguard.test", "AdminPass#2026", role="admin")
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@roadguard.test", "password": "AdminPass#2026"},
        headers=mutate_headers(),
    )
    assert response.status_code == 200, response.text
    return user

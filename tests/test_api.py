from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.security import CLIENT_HEADER, SESSION_COOKIE


def _hdr():
    return {CLIENT_HEADER: "web"}


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_api_health(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"


def test_meta_carries_disclaimers(client):
    meta = client.get("/api/v1/meta").json()
    assert "not an accident probability" in meta["disclaimer"]
    assert "unverified" in meta["community_label"]
    assert "pothole" in meta["hazard_categories"]


def test_register_requires_client_header(client):
    r = client.post("/api/v1/auth/register", json={"email": "a@b.co", "password": "StrongPass#1"})
    assert r.status_code == 403
    assert r.json()["error"]["code"] == "authz_failure"


def test_register_login_and_me(client, register, login):
    user = register("rider@example.com")
    assert user["role"] == "rider"
    login("rider@example.com")
    me = client.get("/api/v1/auth/me").json()["user"]
    assert me["email"] == "rider@example.com"


def test_register_rejects_duplicate(client, register):
    register("dup@example.com")
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "StrongPass#1"},
        headers=_hdr(),
    )
    assert r.status_code == 400


def test_register_rejects_weak_password(client):
    r = client.post(
        "/api/v1/auth/register",
        json={"email": "weak@example.com", "password": "short"},
        headers=_hdr(),
    )
    assert r.status_code == 400


def test_login_wrong_password(client, register):
    register("who@example.com", "RightPass#2026")
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "who@example.com", "password": "WrongPass#2026"},
        headers=_hdr(),
    )
    assert r.status_code == 401


def test_session_cookie_is_httponly(client, register):
    register("ck@example.com")
    client.cookies.clear()
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "ck@example.com", "password": "StrongPass#2026"},
        headers=_hdr(),
    )
    cookie = r.headers.get("set-cookie", "")
    assert SESSION_COOKIE in cookie
    assert "httponly" in cookie.lower()
    assert "samesite=lax" in cookie.lower()


def test_hazard_requires_auth(client):
    r = client.post(
        "/api/v1/hazards",
        json={"category": "pothole", "lat": 17.38, "lon": 78.48, "source": "map_pin"},
        headers=_hdr(),
    )
    assert r.status_code == 401


def test_hazard_created_is_unverified(client, register):
    register("rep@example.com")
    r = client.post(
        "/api/v1/hazards",
        json={"category": "pothole", "description": "deep", "lat": 17.38, "lon": 78.48, "source": "map_pin"},
        headers=_hdr(),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "unverified"


def test_hazard_rejects_bad_category(client, register):
    register("bad@example.com")
    r = client.post(
        "/api/v1/hazards",
        json={"category": "glitch", "lat": 17.38, "lon": 78.48, "source": "map_pin"},
        headers=_hdr(),
    )
    assert r.status_code == 400


def test_admin_requires_admin_role(client, register):
    register("plain@example.com")
    r = client.get("/api/v1/admin/overview")
    assert r.status_code == 403


def test_admin_endpoints_forbidden_anonymous(client):
    assert client.get("/api/v1/admin/users").status_code == 401


def test_admin_moderate_and_list(client, admin_user, register):
    register("citizen@example.com")
    created = client.post(
        "/api/v1/hazards",
        json={"category": "debris", "lat": 17.4, "lon": 78.5, "source": "map_pin"},
        headers=_hdr(),
    ).json()
    # Log back in as admin (cookie currently belongs to citizen).
    client.cookies.clear()
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@roadguard.test", "password": "AdminPass#2026"},
        headers=_hdr(),
    )
    mod = client.post(
        f"/api/v1/admin/hazards/{created['id']}/moderate",
        json={"action": "verify", "note": "reviewed"},
        headers=_hdr(),
    )
    assert mod.status_code == 200
    assert mod.json()["status"] == "verified"
    audit = client.get("/api/v1/admin/audit").json()["events"]
    assert any(e["action"] == "hazard_verified" for e in audit)


def test_admin_cannot_self_deactivate(client, admin_user):
    client.post(
        "/api/v1/auth/login",
        json={"email": "admin@roadguard.test", "password": "AdminPass#2026"},
        headers=_hdr(),
    )
    me = client.get("/api/v1/auth/me").json()["user"]
    r = client.post(
        f"/api/v1/admin/users/{me['id']}/active",
        json={"active": False},
        headers=_hdr(),
    )
    assert r.status_code == 400


def test_logout_clears_session(client, register):
    register("bye@example.com")
    assert client.get("/api/v1/auth/me").status_code == 200
    client.post("/api/v1/auth/logout", headers=_hdr())
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_rate_limit_enforced(tmp_path):
    settings = Settings(
        env="test",
        db_path=tmp_path / "rate.sqlite3",
        model_artifact=tmp_path / "missing.joblib",
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
        login_rate_per_minute=2,
    )
    with TestClient(create_app(settings)) as rate_client:
        rate_client.post(
            "/api/v1/auth/register",
            json={"email": "rate@example.com", "password": "StrongPass#2026"},
            headers=_hdr(),
        )
        rate_client.cookies.clear()
        statuses = []
        for _ in range(4):
            r = rate_client.post(
                "/api/v1/auth/login",
                json={"email": "rate@example.com", "password": "WrongPass#2026"},
                headers=_hdr(),
            )
            statuses.append(r.status_code)
        assert 429 in statuses
        limited = rate_client.post(
            "/api/v1/auth/login",
            json={"email": "rate@example.com", "password": "WrongPass#2026"},
            headers=_hdr(),
        )
        assert limited.status_code == 429
        assert "retry-after" in {k.lower() for k in limited.headers}


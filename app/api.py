from __future__ import annotations

import os
import platform
import sys
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response

from app import audit
from app.db import database_health
from app.errors import (
    auth_failure,
    authz_failure,
    invalid_input,
    not_found,
    rate_limited,
)
from app.schemas import (
    ActiveUpdateRequest,
    ActiveUpdateResponse,
    AdminOverviewOut,
    AdminUserOut,
    AuditListOut,
    AuthResponse,
    DeleteAccountResponse,
    DiagnosticsOut,
    GeocodeResponse,
    HazardCreateRequest,
    HazardListOut,
    HazardModerateRequest,
    HazardOut,
    HazardVoteRequest,
    HealthOut,
    LoginRequest,
    LogoutResponse,
    MeResponse,
    MetaOut,
    ModelStatusOut,
    RegisterRequest,
    RouteAnalysisOut,
    RouteAnalyzeRequest,
)
from app.security import CLIENT_HEADER, SESSION_COOKIE
from app.services import Services
from app.version import APP_NAME, APP_VERSION

router = APIRouter(prefix="/api/v1")


def get_services(request: Request) -> Services:
    return request.app.state.services


ServicesDep = Annotated[Services, Depends(get_services)]


def require_client_header(request: Request) -> None:
    value = request.headers.get(CLIENT_HEADER, "").strip()
    if not value or len(value) > 64:
        raise authz_failure("Missing or invalid client request header.")


ClientHeader = Annotated[Any, Depends(require_client_header)]


def optional_user(request: Request, services: ServicesDep) -> dict[str, Any] | None:
    return services.auth.user_for_token(request.cookies.get(SESSION_COOKIE))


OptionalUser = Annotated[dict[str, Any] | None, Depends(optional_user)]


def require_user(user: OptionalUser) -> dict[str, Any]:
    if user is None:
        raise auth_failure()
    return user


CurrentUser = Annotated[dict[str, Any], Depends(require_user)]


def require_admin(user: CurrentUser) -> dict[str, Any]:
    if user["role"] != "admin":
        raise authz_failure("Administrator access is required.")
    return user


AdminUser = Annotated[dict[str, Any], Depends(require_admin)]


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _enforce_rate(
    request: Request,
    services: Services,
    bucket: str,
    limit: int,
    window_seconds: int,
    *,
    subject: str | None = None,
) -> None:
    key = f"{bucket}:{subject or _client_key(request)}"
    retry_after = services.rate_limiter.check(key, limit, window_seconds)
    if retry_after is not None:
        raise rate_limited("Too many requests; retry shortly.", retry_after)


def _set_session_cookie(response: Response, token: str, services: Services) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=services.settings.session_ttl_seconds,
        httponly=True,
        secure=services.settings.cookie_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response, services: Services) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=services.settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )


# ---------------------------------------------------------------- auth


@router.post(
    "/auth/register",
    response_model=AuthResponse,
    status_code=201,
    tags=["auth"],
)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, Any]:
    _enforce_rate(
        request,
        services,
        "register",
        services.settings.login_rate_per_minute,
        60,
    )
    user = services.auth.register(payload.email, payload.password)
    token = services.auth.create_session(user["id"])
    _set_session_cookie(response, token, services)
    return {"user": user, "session_expires_in_s": services.settings.session_ttl_seconds}


@router.post("/auth/login", response_model=AuthResponse, tags=["auth"])
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, Any]:
    normalized_email = payload.email.strip().lower()
    _enforce_rate(
        request,
        services,
        "login-ip",
        services.settings.login_rate_per_minute * 3,
        60,
    )
    _enforce_rate(
        request,
        services,
        "login-account",
        services.settings.login_rate_per_minute,
        60,
        subject=normalized_email or "unknown",
    )
    user = services.auth.authenticate(payload.email, payload.password)
    token = services.auth.create_session(user["id"])
    _set_session_cookie(response, token, services)
    return {"user": user, "session_expires_in_s": services.settings.session_ttl_seconds}


@router.post("/auth/logout", response_model=LogoutResponse, tags=["auth"])
def logout(
    request: Request,
    response: Response,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, bool]:
    services.auth.revoke_session(request.cookies.get(SESSION_COOKIE))
    _clear_session_cookie(response, services)
    return {"ok": True}


@router.get("/auth/me", response_model=MeResponse, tags=["auth"])
def me(user: CurrentUser) -> dict[str, Any]:
    return {"user": user}


@router.delete("/auth/account", response_model=DeleteAccountResponse, tags=["auth"])
def delete_account(
    response: Response,
    user: CurrentUser,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, bool]:
    services.auth.delete_account(user["id"])
    _clear_session_cookie(response, services)
    return {"deleted": True}


# ---------------------------------------------------------------- providers and analysis


@router.get("/geocode", response_model=GeocodeResponse, tags=["navigation"])
async def geocode(
    request: Request,
    services: ServicesDep,
    q: str = Query(min_length=2, max_length=200),
    limit: int = Query(default=5, ge=1, le=5),
) -> dict[str, Any]:
    _enforce_rate(
        request,
        services,
        "geocode",
        services.settings.route_rate_per_minute,
        60,
    )
    return await services.provider.geocode(q, limit)


@router.post("/routes/analyze", response_model=RouteAnalysisOut, tags=["navigation"])
async def analyze_routes(
    payload: RouteAnalyzeRequest,
    request: Request,
    services: ServicesDep,
    user: OptionalUser,
    _client: ClientHeader,
) -> dict[str, Any]:
    _enforce_rate(
        request,
        services,
        "route",
        services.settings.route_rate_per_minute,
        60,
        subject=str(user["id"]) if user else None,
    )
    return await services.analysis.analyze(
        origin=(payload.origin.lat, payload.origin.lon),
        destination=(payload.destination.lat, payload.destination.lon),
        alternatives=payload.alternatives,
        speed_kmh=payload.speed_kmh,
    )


@router.get("/model/status", response_model=ModelStatusOut, tags=["meta"])
def model_status(services: ServicesDep) -> dict[str, Any]:
    return services.model.status()


@router.get("/meta", response_model=MetaOut, tags=["meta"])
def meta() -> dict[str, Any]:
    from app.hazards import CATEGORIES

    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "disclaimer": (
            "Geometry challenge indicator — not an accident probability. "
            "Advisory based on mapped road shape; real conditions may differ."
        ),
        "geometry_label": "Geometry challenge indicator — not an accident probability.",
        "community_label": "Community reports are unverified until an administrator reviews them.",
        "hazard_categories": sorted(CATEGORIES),
    }


# ---------------------------------------------------------------- hazards


@router.get("/hazards", response_model=HazardListOut, tags=["hazards"])
def list_hazards(
    services: ServicesDep,
    user: OptionalUser,
    min_lat: float | None = Query(default=None, ge=-90, le=90),
    min_lon: float | None = Query(default=None, ge=-180, le=180),
    max_lat: float | None = Query(default=None, ge=-90, le=90),
    max_lon: float | None = Query(default=None, ge=-180, le=180),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    hazards = services.hazards.list_in_bbox(
        min_lat=min_lat,
        min_lon=min_lon,
        max_lat=max_lat,
        max_lon=max_lon,
        limit=limit,
        viewer_id=user["id"] if user else None,
    )
    return {"hazards": hazards, "count": len(hazards)}


@router.post("/hazards", response_model=HazardOut, status_code=201, tags=["hazards"])
def create_hazard(
    payload: HazardCreateRequest,
    request: Request,
    user: CurrentUser,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, Any]:
    _enforce_rate(
        request,
        services,
        "hazard",
        services.settings.hazard_rate_per_hour,
        3600,
        subject=str(user["id"]),
    )
    return services.hazards.create(
        user_id=user["id"],
        category=payload.category,
        description=payload.description,
        lat=payload.lat,
        lon=payload.lon,
        source=payload.source,
    )


@router.get("/hazards/{hazard_id}", response_model=HazardOut, tags=["hazards"])
def get_hazard(hazard_id: int, services: ServicesDep) -> dict[str, Any]:
    hazard = services.hazards.get(hazard_id)
    if hazard["status"] not in {"unverified", "verified"}:
        raise not_found("Hazard not found.")
    return hazard


@router.post("/hazards/{hazard_id}/votes", response_model=HazardOut, tags=["hazards"])
def vote_hazard(
    hazard_id: int,
    payload: HazardVoteRequest,
    user: CurrentUser,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, Any]:
    return services.hazards.vote(
        hazard_id=hazard_id, user_id=user["id"], action=payload.action
    )


# ---------------------------------------------------------------- admin


def _provider_overview(services: Services) -> dict[str, Any]:
    return {
        "mode": "public demo endpoints",
        "geocoding": {
            "name": "nominatim",
            "endpoint": services.provider.settings.nominatim_base_url,
            "attribution": "© OpenStreetMap contributors (ODbL)",
            "country_filter": "in",
        },
        "routing": {
            "name": "osrm",
            "endpoint": services.provider.settings.osrm_base_url,
            "attribution": "Routing by OSRM; map data © OpenStreetMap contributors (ODbL)",
        },
        "cache_entries": services.provider.cache_entries,
        "public_throttle_seconds": 1.1,
    }


def _uptime_seconds(services: Services) -> float:
    return round(
        (datetime.now(timezone.utc) - services.started_at).total_seconds(), 1
    )


@router.get("/admin/overview", response_model=AdminOverviewOut, tags=["admin"])
def admin_overview(admin: AdminUser, services: ServicesDep) -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "env": services.settings.env,
        "started_at": services.started_at.isoformat(timespec="seconds"),
        "uptime_s": _uptime_seconds(services),
        "database": database_health(services.settings.db_path),
        "hazards": services.hazards.stats(),
        "users": audit.user_count(services.settings.db_path),
        "model": services.model.status(),
        "providers": _provider_overview(services),
        "recent_audit": audit.list_audit_events(services.settings.db_path, limit=10),
    }


@router.get("/admin/hazards", response_model=HazardListOut, tags=["admin"])
def admin_list_hazards(
    admin: AdminUser,
    services: ServicesDep,
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
) -> dict[str, Any]:
    hazards = services.hazards.admin_list(status=status, limit=limit)
    return {"hazards": hazards, "count": len(hazards)}


@router.post(
    "/admin/hazards/{hazard_id}/moderate",
    response_model=HazardOut,
    tags=["admin"],
)
def moderate_hazard(
    hazard_id: int,
    payload: HazardModerateRequest,
    admin: AdminUser,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, Any]:
    return services.hazards.moderate(
        hazard_id=hazard_id,
        admin_id=admin["id"],
        action=payload.action,
        note=payload.note,
    )


@router.get("/admin/users", response_model=list[AdminUserOut], tags=["admin"])
def admin_list_users(admin: AdminUser, services: ServicesDep) -> list[dict[str, Any]]:
    return services.auth.list_users()


@router.post(
    "/admin/users/{user_id}/active",
    response_model=ActiveUpdateResponse,
    tags=["admin"],
)
def admin_set_user_active(
    user_id: int,
    payload: ActiveUpdateRequest,
    admin: AdminUser,
    services: ServicesDep,
    _client: ClientHeader,
) -> dict[str, Any]:
    if user_id == admin["id"] and not payload.active:
        raise invalid_input("You cannot deactivate your own administrator account.")
    services.auth.set_active(user_id, payload.active, actor_user_id=admin["id"])
    return {"user_id": user_id, "active": payload.active}


@router.get("/admin/audit", response_model=AuditListOut, tags=["admin"])
def admin_audit(
    admin: AdminUser,
    services: ServicesDep,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    events = audit.list_audit_events(services.settings.db_path, limit=limit)
    return {"events": events, "count": len(events)}


@router.get("/admin/model", response_model=ModelStatusOut, tags=["admin"])
def admin_model(admin: AdminUser, services: ServicesDep) -> dict[str, Any]:
    return services.model.status()


@router.get("/admin/diagnostics", response_model=DiagnosticsOut, tags=["admin"])
def admin_diagnostics(admin: AdminUser, services: ServicesDep) -> dict[str, Any]:
    return {
        "app": APP_NAME,
        "version": APP_VERSION,
        "env": services.settings.env,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "process_id": os.getpid(),
        "started_at": services.started_at.isoformat(timespec="seconds"),
        "uptime_s": _uptime_seconds(services),
        "database": database_health(services.settings.db_path),
        "model": services.model.status(),
        "provider_cache_entries": services.provider.cache_entries,
        "provider_endpoints": {
            "nominatim": services.settings.nominatim_base_url,
            "osrm": services.settings.osrm_base_url,
        },
        "rate_limits": {
            "route_per_minute": services.settings.route_rate_per_minute,
            "hazard_per_hour": services.settings.hazard_rate_per_hour,
            "login_per_minute": services.settings.login_rate_per_minute,
        },
        "synthetic_training_only": True,
    }


@router.get("/health", response_model=HealthOut, include_in_schema=False)
def api_health(services: ServicesDep) -> dict[str, str]:
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "env": services.settings.env,
    }

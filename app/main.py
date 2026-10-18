from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import router
from app.config import PROJECT_ROOT, Settings, get_settings
from app.db import database_health, init_db
from app.errors import AppError, ErrorCode
from app.security import CLIENT_HEADER
from app.services import build_services
from app.version import APP_NAME, APP_VERSION

logger = logging.getLogger("roadguard")
WEB_DIR = PROJECT_ROOT / "app" / "web"

CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https://*.tile.openstreetmap.org; "
    "connect-src 'self'; "
    "font-src 'self'; "
    "object-src 'none'; "
    "base-uri 'none'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "manifest-src 'self'; "
    "worker-src 'self'"
)
DOCS_PATHS = {"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}


def create_app(settings: Settings | None = None) -> FastAPI:
    effective = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(effective.db_path)
        services = build_services(effective)
        if effective.require_model and not services.model.available:
            await services.provider.aclose()
            raise RuntimeError(
                "ROADGUARD_REQUIRE_MODEL is enabled but the model is unavailable: "
                f"{services.model.reason}"
            )
        app.state.services = services
        app.state.settings = effective
        logger.info(
            "RoadGuard started env=%s db=%s model=%s",
            effective.env,
            effective.db_path,
            services.model.model_name,
        )
        try:
            yield
        finally:
            await services.aclose()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        description=(
            "Real-time road-geometry advisory API. Geometry challenge is a computed "
            "indicator, not an accident probability. Training data is synthetic only."
        ),
        lifespan=lifespan,
    )
    app.state.settings = effective

    app.add_middleware(GZipMiddleware, minimum_size=800)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(effective.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", CLIENT_HEADER],
    )

    app.include_router(router)
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next) -> Response:
        response = await call_next(request)
        path = request.url.path
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(self), camera=(), microphone=()"
        )
        response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.headers.setdefault("X-Permitted-Cross-Domain-Policies", "none")
        if effective.cookie_secure:
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        if path.startswith("/api/") or path in {"", "/", "/admin"}:
            response.headers.setdefault("Cache-Control", "no-store")
        if path not in DOCS_PATHS and not path.startswith("/docs/"):
            response.headers.setdefault("Content-Security-Policy", CSP)
        return response

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        headers = {}
        if exc.code == ErrorCode.rate_limited:
            retry_after = exc.details.get("retry_after_s")
            if retry_after:
                headers["Retry-After"] = str(retry_after)
        return JSONResponse(exc.as_body(), status_code=exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "loc": [str(part) for part in error.get("loc", ())],
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            for error in exc.errors()
        ]
        body = {
            "error": {
                "code": ErrorCode.invalid_input.value,
                "message": "Request validation failed.",
                "details": {"errors": errors},
            }
        }
        return JSONResponse(body, status_code=400)

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        mapping = {
            401: ErrorCode.auth_failure,
            403: ErrorCode.authz_failure,
            404: ErrorCode.not_found,
            405: ErrorCode.invalid_input,
            429: ErrorCode.rate_limited,
        }
        code = mapping.get(exc.status_code, ErrorCode.internal_error)
        message = str(exc.detail) if exc.detail else "Request failed."
        return JSONResponse(
            {"error": {"code": code.value, "message": message}},
            status_code=exc.status_code,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            {
                "error": {
                    "code": ErrorCode.internal_error.value,
                    "message": "An internal error occurred.",
                }
            },
            status_code=500,
        )

    @app.get("/health", tags=["meta"])
    def health() -> dict[str, str]:
        return {
            "status": "ok",
            "app": APP_NAME,
            "version": APP_VERSION,
            "env": effective.env,
        }

    @app.get("/ready", tags=["meta"])
    def ready(request: Request) -> JSONResponse:
        services = request.app.state.services
        db = database_health(effective.db_path)
        model = services.model.status()
        db_ok = bool(db.get("ok"))
        model_ok = model["available"] or not effective.require_model
        ok = db_ok and model_ok
        body = {
            "status": "ready" if ok else "not_ready",
            "checks": {
                "database": db,
                "model": {
                    "available": model["available"],
                    "model_name": model["model_name"],
                    "label_version": model["label_version"],
                    "synthetic_training": True,
                    "reason": model["reason"],
                    "required": effective.require_model,
                },
                "providers": {
                    "nominatim": services.settings.nominatim_base_url,
                    "osrm": services.settings.osrm_base_url,
                },
            },
        }
        return JSONResponse(body, status_code=200 if ok else 503)

    @app.get("/", include_in_schema=False)
    def rider_app() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/admin", include_in_schema=False)
    def admin_app() -> FileResponse:
        return FileResponse(WEB_DIR / "admin.html")

    return app


app = create_app()

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _as_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    lowered = raw.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def _as_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = os.environ.get(name)
    value = default if raw is None else int(raw)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _as_float(name: str, default: float, minimum: float | None = None) -> float:
    raw = os.environ.get(name)
    value = default if raw is None else float(raw)
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _resolve(path_value: str) -> Path:
    candidate = Path(path_value)
    return candidate if candidate.is_absolute() else PROJECT_ROOT / candidate


@dataclass(frozen=True)
class Settings:
    env: str
    db_path: Path
    model_artifact: Path
    require_model: bool
    osrm_base_url: str
    nominatim_base_url: str
    provider_user_agent: str
    provider_timeout_seconds: float
    allowed_origins: tuple[str, ...]
    cookie_secure: bool
    session_ttl_seconds: int
    hazard_ttl_hours: int
    route_rate_per_minute: int
    hazard_rate_per_hour: int
    login_rate_per_minute: int


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv(PROJECT_ROOT / ".env")
    return Settings(
        env=os.environ.get("ROADGUARD_ENV", "development"),
        db_path=_resolve(os.environ.get("ROADGUARD_DB_PATH", "data/roadguard.sqlite3")),
        model_artifact=_resolve(
            os.environ.get("ROADGUARD_MODEL_ARTIFACT", "ml/artifacts/model.joblib")
        ),
        require_model=_as_bool("ROADGUARD_REQUIRE_MODEL", False),
        osrm_base_url=os.environ.get(
            "ROADGUARD_OSRM_BASE_URL", "https://router.project-osrm.org"
        ).rstrip("/"),
        nominatim_base_url=os.environ.get(
            "ROADGUARD_NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"
        ).rstrip("/"),
        provider_user_agent=os.environ.get(
            "ROADGUARD_PROVIDER_USER_AGENT", "RoadGuardAI/0.1 (student project)"
        ),
        provider_timeout_seconds=_as_float("ROADGUARD_PROVIDER_TIMEOUT_SECONDS", 8.0, 1.0),
        allowed_origins=tuple(
            item.strip()
            for item in os.environ.get(
                "ROADGUARD_ALLOWED_ORIGINS",
                "http://127.0.0.1:8000,http://localhost:8000",
            ).split(",")
            if item.strip()
        ),
        cookie_secure=_as_bool("ROADGUARD_COOKIE_SECURE", False),
        session_ttl_seconds=_as_int("ROADGUARD_SESSION_TTL_SECONDS", 43_200, 300),
        hazard_ttl_hours=_as_int("ROADGUARD_HAZARD_TTL_HOURS", 24, 1),
        route_rate_per_minute=_as_int("ROADGUARD_ROUTE_RATE_PER_MINUTE", 20, 1),
        hazard_rate_per_hour=_as_int("ROADGUARD_HAZARD_RATE_PER_HOUR", 10, 1),
        login_rate_per_minute=_as_int("ROADGUARD_LOGIN_RATE_PER_MINUTE", 5, 1),
    )


def reset_settings_cache() -> None:
    """Test helper: re-read environment on next get_settings()."""
    get_settings.cache_clear()

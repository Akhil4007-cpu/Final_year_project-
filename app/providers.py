from __future__ import annotations

import asyncio
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.errors import insufficient_evidence, invalid_input, provider_unavailable

OSM_ATTRIBUTION = "© OpenStreetMap contributors (ODbL)"
OSRM_ATTRIBUTION = "Routing by OSRM; map data © OpenStreetMap contributors (ODbL)"
PUBLIC_LIMIT_INTERVAL_SECONDS = 1.1
CACHE_LIMIT = 256


@dataclass(frozen=True)
class ProviderMeta:
    name: str
    attribution: str
    fetched_at: str
    cached: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "attribution": self.attribution,
            "fetched_at": self.fetched_at,
            "cached": self.cached,
        }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProviderService:
    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.AsyncClient | None = None,
        enforce_public_limits: bool = True,
    ) -> None:
        self.settings = settings
        self._client = client or httpx.AsyncClient(
            timeout=settings.provider_timeout_seconds,
            headers={
                "User-Agent": settings.provider_user_agent,
                "Accept": "application/json",
            },
            follow_redirects=True,
        )
        self._owns_client = client is None
        self._cache: dict[str, tuple[float, Any]] = {}
        self._enforce_public_limits = enforce_public_limits
        self._locks = {
            "nominatim": asyncio.Lock(),
            "osrm": asyncio.Lock(),
        }
        self._last_request = {"nominatim": 0.0, "osrm": 0.0}

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    @property
    def cache_entries(self) -> int:
        return len(self._cache)

    def _cache_get(self, key: str, ttl: int) -> Any | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        created, value = entry
        if time.monotonic() - created > ttl:
            self._cache.pop(key, None)
            return None
        return value

    def _cache_set(self, key: str, value: Any) -> None:
        if len(self._cache) >= CACHE_LIMIT:
            oldest = next(iter(self._cache))
            self._cache.pop(oldest, None)
        self._cache[key] = (time.monotonic(), value)

    async def _throttle(self, provider: str) -> None:
        if not self._enforce_public_limits:
            return
        async with self._locks[provider]:
            elapsed = time.monotonic() - self._last_request[provider]
            if elapsed < PUBLIC_LIMIT_INTERVAL_SECONDS:
                await asyncio.sleep(PUBLIC_LIMIT_INTERVAL_SECONDS - elapsed)
            self._last_request[provider] = time.monotonic()

    async def _request_json(
        self,
        provider: str,
        base_url: str,
        path: str,
        params: dict[str, Any],
    ) -> Any:
        await self._throttle(provider)
        try:
            response = await self._client.get(f"{base_url}{path}", params=params)
        except (httpx.TimeoutException, httpx.RequestError):
            raise provider_unavailable(
                provider, f"{provider} did not respond in time."
            ) from None
        if response.status_code >= 500:
            raise provider_unavailable(
                provider,
                f"{provider} returned a server error.",
                status=response.status_code,
            )
        if response.status_code == 429:
            raise provider_unavailable(
                provider,
                f"{provider} rate limit reached; retry later.",
                status=429,
            )
        if response.status_code >= 400:
            raise provider_unavailable(
                provider,
                f"{provider} rejected the request.",
                status=response.status_code,
            )
        try:
            return response.json()
        except ValueError:
            raise provider_unavailable(
                provider, f"{provider} returned an unreadable response."
            ) from None

    async def geocode(self, query: str, limit: int = 5) -> dict[str, Any]:
        query = query.strip()
        if len(query) < 2:
            raise invalid_input("Search text must be at least two characters.")
        if len(query) > 200:
            raise invalid_input("Search text is too long.")
        limit = max(1, min(int(limit), 5))
        key = f"geocode:{query.lower()}:{limit}"
        cached = self._cache_get(key, ttl=600)
        if cached is not None:
            return {**cached, "provider": {**cached["provider"], "cached": True}}
        payload = await self._request_json(
            "nominatim",
            self.settings.nominatim_base_url,
            "/search",
            {
                "q": query,
                "format": "jsonv2",
                "limit": limit,
                "addressdetails": 0,
                "countrycodes": "in",
                "accept-language": "en",
            },
        )
        if not isinstance(payload, list):
            raise provider_unavailable("nominatim", "Nominatim returned an unexpected payload.")
        results: list[dict[str, Any]] = []
        for item in payload[:limit]:
            try:
                lat = float(item["lat"])
                lon = float(item["lon"])
            except (KeyError, TypeError, ValueError):
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue
            results.append(
                {
                    "display_name": str(item.get("display_name", "")),
                    "lat": lat,
                    "lon": lon,
                    "category": str(item.get("category", "")),
                    "type": str(item.get("type", "")),
                    "importance": float(item.get("importance", 0.0) or 0.0),
                }
            )
        if not results:
            raise insufficient_evidence("No matching place was found.")
        meta = ProviderMeta(
            name="nominatim",
            attribution=OSM_ATTRIBUTION,
            fetched_at=_now_iso(),
            cached=False,
        )
        response = {"results": results, "provider": meta.as_dict()}
        self._cache_set(key, response)
        return response

    async def route(
        self,
        origin: tuple[float, float],
        destination: tuple[float, float],
        *,
        alternatives: bool = True,
    ) -> dict[str, Any]:
        for label, point in (("origin", origin), ("destination", destination)):
            lat, lon = point
            if not (
                math.isfinite(lat)
                and math.isfinite(lon)
                and -90 <= lat <= 90
                and -180 <= lon <= 180
            ):
                raise invalid_input(f"{label} coordinates are invalid.")
        if abs(origin[0] - destination[0]) < 1e-7 and abs(origin[1] - destination[1]) < 1e-7:
            raise invalid_input("Origin and destination must differ.")
        coords = (
            f"{origin[1]:.6f},{origin[0]:.6f};"
            f"{destination[1]:.6f},{destination[0]:.6f}"
        )
        key = f"route:{coords}:{int(alternatives)}"
        cached = self._cache_get(key, ttl=120)
        if cached is not None:
            return {**cached, "provider": {**cached["provider"], "cached": True}}
        payload = await self._request_json(
            "osrm",
            self.settings.osrm_base_url,
            f"/route/v1/driving/{coords}",
            {
                "overview": "full",
                "geometries": "geojson",
                "steps": "false",
                "alternatives": "true" if alternatives else "false",
            },
        )
        if not isinstance(payload, dict) or payload.get("code") != "Ok":
            code = payload.get("code") if isinstance(payload, dict) else None
            if code in {"NoRoute", "NoSegment"}:
                raise insufficient_evidence(
                    "No drivable route was found between these points.",
                    provider_code=code,
                )
            raise provider_unavailable(
                "osrm", "OSRM could not compute a route.", provider_code=code
            )
        raw_routes = payload.get("routes") or []
        if not raw_routes:
            raise insufficient_evidence("OSRM returned no routes.")
        routes: list[dict[str, Any]] = []
        for index, raw in enumerate(raw_routes[:3]):
            geometry = raw.get("geometry", {}).get("coordinates") if isinstance(raw, dict) else None
            if not isinstance(geometry, list) or len(geometry) < 2:
                continue
            points: list[tuple[float, float]] = []
            for coordinate in geometry:
                if not isinstance(coordinate, (list, tuple)) or len(coordinate) < 2:
                    continue
                lon, lat = coordinate[0], coordinate[1]
                if not (
                    isinstance(lon, (int, float))
                    and isinstance(lat, (int, float))
                    and math.isfinite(float(lon))
                    and math.isfinite(float(lat))
                    and -90 <= float(lat) <= 90
                    and -180 <= float(lon) <= 180
                ):
                    continue
                points.append((float(lat), float(lon)))
            if len(points) < 2:
                continue
            distance = raw.get("distance")
            duration = raw.get("duration")
            if not isinstance(distance, (int, float)) or not isinstance(duration, (int, float)):
                continue
            routes.append(
                {
                    "id": f"route-{index}",
                    "distance_m": float(distance),
                    "duration_s": float(duration),
                    "geometry": points,
                    "provider_route_index": index,
                }
            )
        if not routes:
            raise provider_unavailable("osrm", "OSRM returned no usable geometry.")
        meta = ProviderMeta(
            name="osrm",
            attribution=OSRM_ATTRIBUTION,
            fetched_at=_now_iso(),
            cached=False,
        )
        response = {"routes": routes, "provider": meta.as_dict()}
        self._cache_set(key, response)
        return response


@lru_cache(maxsize=1)
def get_provider_service() -> ProviderService:
    return ProviderService(get_settings())


def reset_provider_service() -> None:
    get_provider_service.cache_clear()

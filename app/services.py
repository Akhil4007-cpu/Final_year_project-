from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.analysis import RouteAnalysisService
from app.auth import AuthService
from app.config import Settings
from app.hazards import HazardService
from app.model import ModelService
from app.providers import ProviderService
from app.security import RateLimiter


@dataclass
class Services:
    settings: Settings
    auth: AuthService
    hazards: HazardService
    provider: ProviderService
    model: ModelService
    analysis: RouteAnalysisService
    rate_limiter: RateLimiter
    started_at: datetime

    async def aclose(self) -> None:
        await self.provider.aclose()


def build_services(settings: Settings) -> Services:
    auth = AuthService(settings.db_path, settings.session_ttl_seconds)
    hazards = HazardService(settings.db_path, settings.hazard_ttl_hours)
    provider = ProviderService(settings)
    model = ModelService(settings.model_artifact, settings.require_model)
    analysis = RouteAnalysisService(provider, model)
    return Services(
        settings=settings,
        auth=auth,
        hazards=hazards,
        provider=provider,
        model=model,
        analysis=analysis,
        rate_limiter=RateLimiter(),
        started_at=datetime.now(timezone.utc),
    )

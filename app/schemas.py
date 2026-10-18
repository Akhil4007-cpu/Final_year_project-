from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Latitude = Annotated[float, Field(ge=-90.0, le=90.0)]
Longitude = Annotated[float, Field(ge=-180.0, le=180.0)]
Score = Annotated[float, Field(ge=0.0, le=100.0)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ApiErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: ApiErrorDetail


class Coordinate(StrictModel):
    lat: Latitude
    lon: Longitude


class RegisterRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=10, max_length=200)


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    email: str
    role: Literal["rider", "admin"]
    created_at: str


class AuthResponse(BaseModel):
    user: UserOut
    session_expires_in_s: int


class MeResponse(BaseModel):
    user: UserOut


class LogoutResponse(BaseModel):
    ok: bool


class DeleteAccountResponse(BaseModel):
    deleted: bool


class ProviderOut(BaseModel):
    name: str
    attribution: str
    fetched_at: str
    cached: bool


class GeocodeResult(BaseModel):
    display_name: str
    lat: float
    lon: float
    category: str
    type: str
    importance: float


class GeocodeResponse(BaseModel):
    results: list[GeocodeResult]
    provider: ProviderOut


class RouteAnalyzeRequest(StrictModel):
    origin: Coordinate
    destination: Coordinate
    alternatives: bool = True
    speed_kmh: float | None = Field(default=None, ge=5.0, le=200.0)


class GeometryQualityOut(BaseModel):
    median_spacing_m: float | None
    max_gap_m: float | None
    coarse: bool
    long_gap: bool


class SectionQualityOut(BaseModel):
    status: str
    point_count: int
    duplicate_points_removed: int
    median_spacing_m: float | None
    max_gap_m: float | None
    coarse: bool
    long_gap_count: int
    score: float
    issues: list[str]


class UncertaintyOut(BaseModel):
    low: float | None
    high: float | None


class SectionOut(BaseModel):
    index: int
    kind: Literal["curve", "straight"]
    start_index: int
    end_index: int
    length_m: float
    start_distance_m: float
    radius_m: float | None
    min_radius_m: float | None
    p10_radius_m: float | None
    heading_change_deg: float
    curve_length_m: float
    curvature_std: float
    max_turn_deg: float
    transition_abruptness: float
    spiral_like: bool
    gap_before_m: float | None
    sequence_index: int
    evidence: str
    provenance: list[str]
    baseline_score: float | None
    model_score: float | None
    display_score: float | None
    band: str
    uncertainty: UncertaintyOut | None
    disagreement: bool
    ood: bool
    model_status: str
    geometry_quality: GeometryQualityOut


class RouteSummaryOut(BaseModel):
    state: str
    coverage: float
    scored_length_m: float
    total_length_m: float
    missing_length_m: float
    score: Score | None
    band: str
    baseline_score: Score | None
    uncertainty: UncertaintyOut | None
    uncertainty_coverage: float
    model_available: bool
    model_used_sections: int
    fallback_sections: int
    ood_sections: int
    provenance: list[str]
    reason: str | None


class AdvisoryOut(BaseModel):
    id: str
    section_index: int
    start_distance_m: float
    end_distance_m: float
    lead_m: float
    clear_after_m: float
    cooldown_s: float
    band: str
    score: float
    uncertainty: UncertaintyOut | None
    message: str
    provenance: Literal["model_estimate", "computed_geometry"]


class RouteErrorOut(BaseModel):
    code: str
    message: str
    issues: list[str] = Field(default_factory=list)


class RouteOut(BaseModel):
    id: str
    state: str
    distance_m: float
    duration_s: float
    geometry_length_m: float
    geometry_quality: SectionQualityOut
    geometry: list[tuple[float, float]]
    summary: RouteSummaryOut
    sections: list[SectionOut]
    advisories: list[AdvisoryOut]
    provider_route_index: int
    error: RouteErrorOut | None = None


class ComparisonOut(BaseModel):
    state: str
    reason: str | None = None
    best_route_id: str | None = None
    lowest_geometry_challenge_route_id: str | None = None
    score_gap: float | None = None
    coverage_spread: float | None = None
    ranking_basis: str | None = None


class UncertaintyCoverageOut(BaseModel):
    nominal_coverage: float
    empirical_coverage: float
    mean_width: float


class ModelMetricsOut(BaseModel):
    clean: dict[str, Any] | None = None
    degraded: dict[str, Any] | None = None
    uncertainty_coverage: UncertaintyCoverageOut | None = None
    ood_radius: dict[str, Any] | None = None


class ModelStatusOut(BaseModel):
    available: bool
    reason: str | None
    model_name: str
    label_version: str
    baseline_version: str | None
    generator_version: str | None
    artifact_version: int | None
    synthetic_training: bool
    uncertainty_method: str | None
    nominal_coverage: float | None
    metrics: ModelMetricsOut | None
    feature_count: int
    monotonic_constraints: dict[str, int]
    require_model: bool


class AnalysisInputsOut(BaseModel):
    speed_kmh: float
    speed_source: str
    speed_is_advisory: bool
    road_class_supplied: bool
    grade_supplied: bool
    scoring_distance_basis: str


class RouteAnalysisOut(BaseModel):
    state: str
    generated_at: str
    provider: ProviderOut
    model: ModelStatusOut
    inputs: AnalysisInputsOut
    routes: list[RouteOut]
    comparison: ComparisonOut | None
    assumptions: list[str]
    disclaimer: str


class HazardCreateRequest(StrictModel):
    category: Literal[
        "pothole",
        "debris",
        "waterlogging",
        "poor_visibility",
        "sharp_curve",
        "road_work",
        "other",
    ]
    description: str = Field(default="", max_length=500)
    lat: Latitude
    lon: Longitude
    source: Literal["current_location", "map_pin"]


class HazardVoteRequest(StrictModel):
    action: Literal["confirm", "withdraw"]


class HazardModerateRequest(StrictModel):
    action: Literal["verify", "reject"]
    note: str = Field(default="", max_length=500)


class HazardOut(BaseModel):
    id: int
    category: str
    description: str
    lat: float
    lon: float
    source: str
    status: str
    created_at: str
    expires_at: str
    confirmations: int
    provenance: Literal["user_submitted"]
    label: str
    is_mine: bool


class HazardListOut(BaseModel):
    hazards: list[HazardOut]
    count: int


class AdminUserOut(BaseModel):
    id: int
    email: str
    role: str
    is_active: bool
    created_at: str


class ActiveUpdateRequest(StrictModel):
    active: bool


class ActiveUpdateResponse(BaseModel):
    user_id: int
    active: bool


class AuditEventOut(BaseModel):
    id: int
    actor_user_id: int | None
    action: str
    target_type: str
    target_id: str | None
    details: dict[str, Any]
    created_at: str


class AuditListOut(BaseModel):
    events: list[AuditEventOut]
    count: int


class AdminOverviewOut(BaseModel):
    app: str
    version: str
    env: str
    started_at: str
    uptime_s: float
    database: dict[str, Any]
    hazards: dict[str, int]
    users: dict[str, int]
    model: ModelStatusOut
    providers: dict[str, Any]
    recent_audit: list[AuditEventOut]


class DiagnosticsOut(BaseModel):
    app: str
    version: str
    env: str
    python: str
    platform: str
    process_id: int
    started_at: str
    uptime_s: float
    database: dict[str, Any]
    model: ModelStatusOut
    provider_cache_entries: int
    provider_endpoints: dict[str, str]
    rate_limits: dict[str, int]
    synthetic_training_only: bool


class MetaOut(BaseModel):
    app: str
    version: str
    disclaimer: str
    geometry_label: str
    community_label: str
    hazard_categories: list[str]


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    env: str


class ReadyOut(BaseModel):
    status: str
    checks: dict[str, Any]

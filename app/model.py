from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from app.baseline import baseline_for_section
from app.config import get_settings
from app.features import (
    FEATURE_DEFAULTS,
    FEATURE_NAMES,
    MONOTONIC_CONSTRAINTS,
    build_features,
    feature_vector,
)
from app.geo import Section

logger = logging.getLogger("roadguard.model")

DISAGREEMENT_THRESHOLD = 20.0
REQUIRED_ARTIFACT_KEYS = {
    "artifact_version",
    "feature_names",
    "model",
    "model_name",
    "label_version",
    "conformal_offset",
    "ood_radius_band_m",
}


@dataclass(frozen=True)
class Prediction:
    score: float
    low: float
    high: float
    ood: bool
    model_name: str
    label_version: str


class ModelService:
    def __init__(self, artifact_path: Path, require_model: bool) -> None:
        self.artifact_path = artifact_path
        self.require_model = require_model
        self.available = False
        self.reason: str | None = None
        self.artifact: dict[str, Any] | None = None
        self._load()

    def _load(self) -> None:
        if not self.artifact_path.is_file():
            self.reason = f"model artifact not found at {self.artifact_path}"
            logger.warning("Model unavailable: %s", self.reason)
            return
        try:
            artifact = joblib.load(self.artifact_path)
        except Exception as exc:  # noqa: BLE001 - artifact parsing must not crash startup
            self.reason = f"model artifact could not be loaded: {type(exc).__name__}"
            logger.error("Model unavailable: %s", self.reason)
            return
        if not isinstance(artifact, dict):
            self.reason = "model artifact is not a dictionary"
            return
        missing = REQUIRED_ARTIFACT_KEYS - set(artifact)
        if missing:
            self.reason = f"model artifact missing keys: {sorted(missing)}"
            return
        if list(artifact["feature_names"]) != FEATURE_NAMES:
            self.reason = "model feature schema does not match runtime feature schema"
            return
        if not callable(getattr(artifact["model"], "predict", None)):
            self.reason = "model object has no predict method"
            return
        self.artifact = artifact
        self.available = True
        self.reason = None
        logger.info(
            "Loaded model %s (%s) from %s",
            artifact.get("model_name"),
            artifact.get("label_version"),
            self.artifact_path,
        )

    @property
    def model_name(self) -> str:
        return str(self.artifact.get("model_name")) if self.artifact else "unavailable"

    @property
    def label_version(self) -> str:
        return str(self.artifact.get("label_version")) if self.artifact else "unavailable"

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "reason": self.reason,
            "model_name": self.model_name,
            "label_version": self.label_version,
            "baseline_version": str(self.artifact.get("baseline_version"))
            if self.artifact
            else None,
            "generator_version": str(self.artifact.get("generator_version"))
            if self.artifact
            else None,
            "artifact_version": self.artifact.get("artifact_version")
            if self.artifact
            else None,
            "synthetic_training": True,
            "uncertainty_method": self.artifact.get("uncertainty_method")
            if self.artifact
            else None,
            "nominal_coverage": self.artifact.get("nominal_coverage")
            if self.artifact
            else None,
            "metrics": {
                key: self.artifact.get("metrics", {}).get(key)
                for key in ("clean", "degraded", "uncertainty_coverage", "ood_radius")
            }
            if self.artifact
            else None,
            "feature_count": len(FEATURE_NAMES),
            "monotonic_constraints": MONOTONIC_CONSTRAINTS,
            "require_model": self.require_model,
        }

    def predict(self, features: dict[str, float]) -> Prediction:
        if not self.available or self.artifact is None:
            raise RuntimeError("model is unavailable")
        vector = np.asarray([feature_vector(features)], dtype=float)
        raw = float(self.artifact["model"].predict(vector)[0])
        return self._finalize(features, raw)

    def _finalize(self, features: dict[str, float], raw: float) -> Prediction:
        """Turn one raw model output into a calibrated Prediction.

        Shared by the single-row path and the batched route path so the numeric
        result never depends on how many sections were scored at once.
        """
        assert self.artifact is not None
        if self.artifact.get("prediction_mode") == "physics_prior_plus_boosted_residual":
            prior_name = str(self.artifact.get("prior_feature", "physics_prior"))
            prior = float(features.get(prior_name, FEATURE_DEFAULTS.get(prior_name, 0.0)))
            point = float(np.clip(prior + raw, 0.0, 100.0))
        else:
            point = float(np.clip(raw, 0.0, 100.0))
        offset = float(self.artifact["conformal_offset"])
        radius = max(1.0, math.exp(features["log_radius"]) - 1.0)
        band_low, band_high = self.artifact["ood_radius_band_m"]
        speed = features["speed_mps"]
        ranges = self.artifact.get("training_ranges", {})
        speed_range = ranges.get("speed_mps", [speed, speed])
        ood = (
            band_low <= radius <= band_high
            or speed < float(speed_range[0])
            or speed > float(speed_range[1])
        )
        width = offset * (
            float(self.artifact.get("ood_interval_widen_factor", 1.0)) if ood else 1.0
        )
        return Prediction(
            score=round(point, 2),
            low=round(max(0.0, point - width), 2),
            high=round(min(100.0, point + width), 2),
            ood=ood,
            model_name=self.model_name,
            label_version=self.label_version,
        )

    def score_section(
        self,
        section: Section,
        *,
        road_class: str | None,
        speed_kmh: float | None,
        grade_pct: float | None,
        geometry_quality_score: float,
    ) -> None:
        self.score_sections(
            [section],
            road_class=road_class,
            speed_kmh=speed_kmh,
            grade_pct=grade_pct,
            geometry_quality_score=geometry_quality_score,
        )

    def score_sections(
        self,
        sections,
        *,
        road_class: str | None,
        speed_kmh: float | None,
        grade_pct: float | None,
        geometry_quality_score: float,
    ) -> None:
        """Score every section on a route with a single vectorized model call.

        The per-section baseline and feature math is unchanged; only the model
        inference is batched, which dominates cost for multi-section routes.
        """
        prepared: list[tuple[Section, dict[str, float]]] = []
        for section in sections:
            section.baseline_score = baseline_for_section(
                section,
                speed_kmh=speed_kmh,
                road_class=road_class,
                grade_pct=grade_pct,
            )
            section.display_score = section.baseline_score
            if section.baseline_score is None or section.evidence != "scored":
                section.model_status = "unavailable"
                continue
            if not self.available or self.artifact is None:
                section.model_status = "unavailable"
                continue
            prepared.append(
                (
                    section,
                    build_features(
                        section,
                        road_class=road_class,
                        speed_kmh=speed_kmh,
                        grade_pct=grade_pct,
                        geometry_quality_score=geometry_quality_score,
                    ),
                )
            )
        if not prepared:
            return
        assert self.artifact is not None
        matrix = np.asarray(
            [feature_vector(features) for _, features in prepared], dtype=float
        )
        raws = self.artifact["model"].predict(matrix)
        for (section, features), raw in zip(prepared, raws):
            prediction = self._finalize(features, float(raw))
            section.model_score = prediction.score
            section.uncertainty_low = prediction.low
            section.uncertainty_high = prediction.high
            section.ood = prediction.ood
            section.disagreement = (
                abs(prediction.score - section.baseline_score) > DISAGREEMENT_THRESHOLD
            )
            if section.disagreement:
                section.model_status = "baseline_fallback"
                section.display_score = section.baseline_score
            else:
                section.model_status = "model_estimate"
                section.display_score = prediction.score


@lru_cache(maxsize=1)
def get_model_service() -> ModelService:
    settings = get_settings()
    return ModelService(settings.model_artifact, settings.require_model)


def reset_model_service() -> None:
    get_model_service.cache_clear()

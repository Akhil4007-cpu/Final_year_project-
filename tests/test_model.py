from __future__ import annotations

import math

import joblib
import numpy as np
import pytest

from app.features import FEATURE_NAMES
from app.geo import extract_sections
from app.model import DISAGREEMENT_THRESHOLD, ModelService

TIGHT_CURVE: list[tuple[float, float]] = [
    (17.3800, 78.4800),
    (17.3799, 78.4802),
    (17.3797, 78.4803),
    (17.3795, 78.4802),
    (17.3794, 78.4800),
    (17.3795, 78.4798),
    (17.3797, 78.4797),
    (17.3799, 78.4798),
    (17.3800, 78.4800),
    (17.3801, 78.4802),
]


class FakeModel:
    def __init__(self, value: float) -> None:
        self.value = value

    def predict(self, X):  # noqa: N803 - mirrors sklearn signature
        return np.full(X.shape[0], self.value, dtype=float)


def make_artifact(value: float = 40.0, *, offset: float = 8.0, band=(50.0, 2000.0), widen=2.0):
    return {
        "artifact_version": "v1",
        "feature_names": list(FEATURE_NAMES),
        "model": FakeModel(value),
        "model_name": "fake_gbm",
        "label_version": "label_v1",
        "baseline_version": "physics_v2r_v1",
        "generator_version": "generator_v1",
        "conformal_offset": offset,
        "ood_radius_band_m": list(band),
        "ood_interval_widen_factor": widen,
        "uncertainty_method": "split_conformal_absolute_residual",
        "nominal_coverage": 0.8,
        "training_ranges": {"speed_mps": [2.0, 30.0]},
        "metrics": {"clean": 4.77, "degraded": 14.47},
    }


def write_artifact(tmp_path, artifact):
    path = tmp_path / "model.joblib"
    joblib.dump(artifact, path)
    return path


def curve_section():
    result = extract_sections(TIGHT_CURVE)
    curves = [s for s in result.sections if s.kind == "curve"]
    assert curves, "fixture must contain a curve"
    return curves[0], result.quality.score


def test_missing_artifact_marks_unavailable(tmp_path):
    service = ModelService(tmp_path / "nope.joblib", require_model=False)
    assert service.available is False
    assert "not found" in service.reason


def test_corrupt_artifact_is_handled(tmp_path):
    path = tmp_path / "bad.joblib"
    path.write_bytes(b"not a joblib file")
    service = ModelService(path, require_model=False)
    assert service.available is False
    assert "could not be loaded" in service.reason


def test_feature_schema_mismatch_rejected(tmp_path):
    artifact = make_artifact()
    artifact["feature_names"] = ["wrong", "schema"]
    path = write_artifact(tmp_path, artifact)
    service = ModelService(path, require_model=False)
    assert service.available is False
    assert "schema" in service.reason


def test_status_reports_synthetic_only(tmp_path):
    path = write_artifact(tmp_path, make_artifact())
    service = ModelService(path, require_model=True)
    assert service.available is True
    status = service.status()
    assert status["synthetic_training"] is True
    assert status["model_name"] == "fake_gbm"
    assert status["feature_count"] == len(FEATURE_NAMES)
    assert status["require_model"] is True


def test_score_section_model_estimate_when_close(tmp_path):
    section, quality = curve_section()
    service = ModelService(write_artifact(tmp_path, make_artifact(value=100.0)), require_model=False)
    service.score_section(
        section, road_class=None, speed_kmh=50.0, grade_pct=None, geometry_quality_score=quality
    )
    baseline = section.baseline_score
    close = ModelService(write_artifact(tmp_path, make_artifact(value=baseline)), require_model=False)
    section2, _ = curve_section()
    close.score_section(
        section2, road_class=None, speed_kmh=50.0, grade_pct=None, geometry_quality_score=quality
    )
    assert section2.model_status == "model_estimate"
    assert section2.display_score == pytest.approx(baseline, abs=0.5)
    assert section2.disagreement is False


def test_score_section_falls_back_on_disagreement(tmp_path):
    section, quality = curve_section()
    service = ModelService(write_artifact(tmp_path, make_artifact(value=100.0)), require_model=False)
    service.score_section(
        section, road_class=None, speed_kmh=50.0, grade_pct=None, geometry_quality_score=quality
    )
    assert section.baseline_score is not None
    assert abs(section.model_score - section.baseline_score) > DISAGREEMENT_THRESHOLD
    assert section.model_status == "baseline_fallback"
    assert section.display_score == section.baseline_score
    assert section.disagreement is True


def test_predict_flags_ood_and_widens_interval(tmp_path):
    service = ModelService(write_artifact(tmp_path, make_artifact(band=(50.0, 5000.0), widen=2.0, offset=8.0)), require_model=False)
    features = {"log_radius": math.log1p(200.0), "speed_mps": 50.0 / 3.6}
    prediction = service.predict(features)
    assert prediction.ood is True
    assert prediction.high - prediction.low == pytest.approx(32.0, abs=0.05)


def test_predict_not_ood_inside_normal_band(tmp_path):
    service = ModelService(write_artifact(tmp_path, make_artifact(band=(2000.0, 5000.0), widen=2.0, offset=8.0)), require_model=False)
    features = {"log_radius": math.log1p(200.0), "speed_mps": 50.0 / 3.6}
    prediction = service.predict(features)
    assert prediction.ood is False
    assert prediction.high - prediction.low == pytest.approx(16.0, abs=0.05)


def test_predict_raises_when_unavailable(tmp_path):
    service = ModelService(tmp_path / "none.joblib", require_model=False)
    with pytest.raises(RuntimeError):
        service.predict({"log_radius": 5.0, "speed_mps": 10.0})


def test_residual_artifact_adds_prior_correction(tmp_path):
    # A residual-mode artifact: the stored model returns a constant correction that
    # must be added back to the physics_prior feature to form the final score.
    artifact = make_artifact(value=5.0)
    artifact["prediction_mode"] = "physics_prior_plus_boosted_residual"
    artifact["prior_feature"] = "physics_prior"
    service = ModelService(write_artifact(tmp_path, artifact), require_model=False)
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["physics_prior"] = 40.0
    prediction = service.predict(features)
    assert prediction.score == pytest.approx(45.0, abs=0.05)


def test_residual_score_section_uses_correction(tmp_path):
    section, quality = curve_section()
    # correction of +5 over the degraded prior -> display = baseline + 5
    artifact = make_artifact(value=5.0)
    artifact["prediction_mode"] = "physics_prior_plus_boosted_residual"
    artifact["prior_feature"] = "physics_prior"
    service = ModelService(write_artifact(tmp_path, artifact), require_model=False)
    service.score_section(
        section, road_class=None, speed_kmh=50.0, grade_pct=None, geometry_quality_score=quality
    )
    # physics_prior feature equals the degraded baseline the section already carries
    assert section.baseline_score is not None
    assert section.display_score == pytest.approx(section.baseline_score + 5.0, abs=0.05)
    assert section.model_status == "model_estimate"


def test_legacy_artifact_scores_directly(tmp_path):
    # An artifact without prediction_mode (e.g. the test FakeModel) is used as a direct score.
    service = ModelService(write_artifact(tmp_path, make_artifact(value=30.0)), require_model=False)
    features = {name: 0.0 for name in FEATURE_NAMES}
    features["physics_prior"] = 40.0
    prediction = service.predict(features)
    assert prediction.score == pytest.approx(30.0, abs=0.05)


class PriorEchoModel:
    """Residual output that echoes each row's own physics_prior feature.

    Because the raw value varies per section, a batched predict that misordered rows
    would produce different per-section scores than the per-section path — so this
    catches index misalignment, not just the happy path.
    """

    def predict(self, X):  # noqa: N803 - mirrors sklearn signature
        return X[:, -1].astype(float)


def test_score_sections_batch_matches_per_section(tmp_path):
    route = [
        (17.3849, 78.4867), (17.3838, 78.4852), (17.3826, 78.4838),
        (17.3814, 78.4830), (17.3802, 78.4838), (17.3796, 78.4854),
        (17.3799, 78.4871), (17.3810, 78.4883), (17.3824, 78.4886),
        (17.3837, 78.4879), (17.3846, 78.4866), (17.3849, 78.4850),
    ]
    artifact = make_artifact()
    artifact["model"] = PriorEchoModel()
    artifact["prediction_mode"] = "physics_prior_plus_boosted_residual"
    artifact["prior_feature"] = "physics_prior"
    path = write_artifact(tmp_path, artifact)

    single_service = ModelService(path, require_model=False)
    batch_service = ModelService(path, require_model=False)

    single = extract_sections(route)
    batch = extract_sections(route)
    assert len(single.sections) >= 3

    for section in single.sections:
        single_service.score_section(
            section, road_class=None, speed_kmh=45.0, grade_pct=None,
            geometry_quality_score=single.quality.score,
        )
    batch_service.score_sections(
        batch.sections, road_class=None, speed_kmh=45.0, grade_pct=None,
        geometry_quality_score=batch.quality.score,
    )

    for a, b in zip(single.sections, batch.sections):
        assert a.baseline_score == b.baseline_score
        assert a.model_status == b.model_status
        assert a.model_score == b.model_score
        assert a.uncertainty_low == b.uncertainty_low
        assert a.uncertainty_high == b.uncertainty_high
        assert a.ood == b.ood
        assert a.disagreement == b.disagreement
        assert a.display_score == b.display_score

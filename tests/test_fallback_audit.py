"""Guard the disagreement-fallback audit (docs/GEOMETRY_ML_LIMITATIONS.md).

`ml/fallback_audit.py` measures how often the runtime guard replaces the model with the
baseline and what that costs in error. These tests keep that published table honest:
the artifact must agree with the committed evaluation numbers, and it must have been
produced with the threshold the runtime actually ships. If someone changes
DISAGREEMENT_THRESHOLD or retrains without re-running the audit, this fails loudly
rather than letting a stale measurement stay in the docs.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.model import DISAGREEMENT_THRESHOLD

ARTIFACTS = Path(__file__).resolve().parents[1] / "ml" / "artifacts"


def _load(name: str) -> dict:
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


def test_fallback_audit_exists_and_covers_the_required_slices():
    audit = _load("fallback_audit.json")
    slices = audit["slices"]
    # the brief asks for degraded, the noise sweep and the OOD radius band
    for required in ["degraded", "ood_radius", "noise_3m", "noise_20m"]:
        assert required in slices, f"audit is missing slice {required}"
        assert slices[required]["count"] > 0
        for key in ["fallback_rate", "served_mae", "model_only_mae", "baseline_mae"]:
            assert isinstance(slices[required][key], (int, float))


def test_fallback_audit_model_only_mae_matches_committed_evaluation():
    """The audit must describe the shipped artifact, not a different regeneration."""
    audit = _load("fallback_audit.json")
    evaluation = _load("eval_results.json")
    for key in ["clean", "degraded", "ood_radius", "ood_type"]:
        served_model_mae = audit["slices"][key]["model_only_mae"]
        committed_mae = evaluation[key]["mae"]
        assert abs(served_model_mae - committed_mae) < 0.0015, (
            f"{key}: audit model_only_mae {served_model_mae} != committed eval mae "
            f"{committed_mae}; re-run `python -m ml.fallback_audit`"
        )


def test_fallback_audit_used_the_shipped_threshold_and_retuned_nothing():
    audit = _load("fallback_audit.json")
    assert audit["threshold_retuned"] is False
    assert str(DISAGREEMENT_THRESHOLD) in audit["rule"], (
        f"audit rule string does not mention the shipped threshold {DISAGREEMENT_THRESHOLD}; "
        "the threshold changed after the audit was run — re-run it and re-check the docs"
    )


def test_fallback_is_a_majority_of_sections_on_degraded_input():
    """The published finding: the guard fires often where the model is actually right."""
    slices = _load("fallback_audit.json")["slices"]
    assert slices["degraded"]["fallback_rate"] > 0.5
    assert slices["degraded"]["served_mae"] > slices["degraded"]["model_only_mae"]
    assert slices["ood_type"]["served_mae"] < slices["ood_type"]["model_only_mae"]

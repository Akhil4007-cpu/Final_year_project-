"""Measure how often the runtime's disagreement guard replaces the model with the
physics baseline, and what that substitution costs (or saves) in error.

The shipped rule (app/model.py) is: if |model_score - baseline_score| >
DISAGREEMENT_THRESHOLD, serve the baseline and tag the section `baseline_fallback`.
The §7.5 evaluation suite reports MAE for the *model* on each slice, but never for what
the rider actually sees after that guard fires. This script closes that gap on the
slices the plan asks for — mixed-degradation, the noise sweep and the OOD radius band —
plus clean and OOD-type for contrast.

Method: regenerate the dataset from the committed artifact's own seed and size, load the
COMMITTED model (nothing is retrained or re-tuned here; the threshold is used exactly as
shipped), score every row, then apply the runtime rule verbatim. Per slice we report the
fallback rate, the MAE of what is actually served, the MAE the model alone would have
produced, the baseline MAE, and how many fired guard decisions were correct (the baseline
was genuinely closer to the label than the model).

Consistency guard: the model-only MAE per slice is checked against the numbers in the
committed ml/artifacts/eval_results.json. A mismatch means this regeneration is not the
shipped dataset, so the script refuses to report instead of quoting foreign numbers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error

from app.model import DISAGREEMENT_THRESHOLD
from ml.generator import Degradation, build_rows, controlled_rows, generate_scenarios
from ml.train import final_predictions, rows_to_arrays

PER_TYPE = 140
# the same sigma ladder ml/train.py sweeps in the §7.5 noise test
NOISE_SIGMAS_M = [0.0, 3.0, 6.0, 10.0, 15.0, 20.0]
ARTIFACT = Path("ml/artifacts/model.joblib")
EVAL_RESULTS = Path("ml/artifacts/eval_results.json")
MANIFEST = Path("ml/artifacts/dataset_manifest.json")
OUTPUT = Path("ml/artifacts/fallback_audit.json")


def _slices(scenarios: list[Any], seed: int) -> dict[str, list[dict[str, Any]]]:
    rows = build_rows(scenarios, seed=seed, missing_context=True)
    slices: dict[str, list[dict[str, Any]]] = {
        "clean": controlled_rows(scenarios, split="test", degradation=Degradation(), seed=seed),
        "degraded": [row for row in rows if row["split"] == "test"],
        "ood_radius": [row for row in rows if row["split"] == "ood_radius"],
        "ood_type": [row for row in rows if row["split"] == "ood_type"],
    }
    for sigma in NOISE_SIGMAS_M:
        sweep = controlled_rows(
            scenarios,
            split="test",
            degradation=Degradation(noise_sigma_m=sigma),
            seed=seed + int(sigma),
        )
        if sweep:
            slices[f"noise_{sigma:g}m"] = sweep
    return slices


def _audit_slice(rows: list[dict[str, Any]], model: Any) -> dict[str, Any]:
    if not rows:
        return {"count": 0}
    matrix, y, baseline = rows_to_arrays(rows)
    predictions = final_predictions(model, matrix)
    fired = np.abs(predictions - baseline) > DISAGREEMENT_THRESHOLD
    served = np.where(fired, baseline, predictions)
    closer = (np.abs(baseline - y) < np.abs(predictions - y)) & fired
    return {
        "count": int(len(y)),
        "fallback_sections": int(np.sum(fired)),
        "fallback_rate": round(float(np.mean(fired)), 4),
        "served_mae": round(float(mean_absolute_error(y, served)), 3),
        "model_only_mae": round(float(mean_absolute_error(y, predictions)), 3),
        "baseline_mae": round(float(mean_absolute_error(y, baseline)), 3),
        # positive means the guard made the served answer worse than the model alone
        "served_minus_model_mae": round(
            float(mean_absolute_error(y, served) - mean_absolute_error(y, predictions)), 3
        ),
        "mean_abs_model_minus_baseline": round(float(np.mean(np.abs(predictions - baseline))), 3),
        "fallbacks_where_baseline_was_closer": int(np.sum(closer)),
        "fallback_precision": round(float(np.mean(closer[fired])), 4) if np.any(fired) else None,
    }


def _sweep(rows: list[dict[str, Any]], model: Any) -> list[dict[str, Any]]:
    """Threshold sweep evaluated on a given split.

    Used ONLY on the calibration split (the selection split). Nothing here changes the
    shipped DISAGREEMENT_THRESHOLD; it quantifies what the shipped guard costs.
    """
    matrix, y, baseline = rows_to_arrays(rows)
    predictions = final_predictions(model, matrix)
    gap = np.abs(predictions - baseline)
    out = []
    for threshold in [0.0, 5.0, 10.0, 20.0, 30.0, 40.0, 50.0, float("inf")]:
        fired = gap > threshold
        served = np.where(fired, baseline, predictions)
        out.append(
            {
                "threshold": None if threshold == float("inf") else threshold,
                "fallback_rate": round(float(np.mean(fired)), 4),
                "served_mae": round(float(mean_absolute_error(y, served)), 3),
            }
        )
    return out


def main() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    seed = int(manifest["seed"])
    artifact = joblib.load(ARTIFACT)
    model = artifact["model"]
    scenarios = generate_scenarios(seed=seed, per_type=PER_TYPE)
    results = {
        name: _audit_slice(rows, model) for name, rows in _slices(scenarios, seed).items()
    }
    calibration_rows = [
        row
        for row in build_rows(scenarios, seed=seed, missing_context=True)
        if row["split"] == "calibration"
    ]

    committed = json.loads(EVAL_RESULTS.read_text(encoding="utf-8"))
    expected = {
        "clean": committed["clean"]["mae"],
        "degraded": committed["degraded"]["mae"],
        "ood_radius": committed["ood_radius"]["mae"],
        "ood_type": committed["ood_type"]["mae"],
    }
    mismatches = {
        key: {"audit_model_only_mae": results[key]["model_only_mae"], "committed_eval_mae": want}
        for key, want in expected.items()
        if abs(float(results[key]["model_only_mae"]) - float(want)) > 0.0015
    }
    if mismatches:
        raise SystemExit(
            "regeneration does not match the committed artifact, refusing to report: "
            + json.dumps(mismatches, indent=2)
        )

    payload = {
        "artifact": str(ARTIFACT),
        "dataset_seed": seed,
        "dataset_sha256": manifest["dataset_sha256"],
        "per_type": PER_TYPE,
        "rule": (
            "serve baseline when |model_score - baseline_score| > "
            f"{DISAGREEMENT_THRESHOLD} (app/model.py DISAGREEMENT_THRESHOLD)"
        ),
        "threshold_retuned": False,
        "calibration_only_threshold_sweep": _sweep(calibration_rows, model),
        "consistency_check": "model_only_mae matches ml/artifacts/eval_results.json within 0.0015",
        "slices": results,
    }
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    header = f"{'slice':12s} {'n':>4s} {'fall%':>6s} {'served':>7s} {'model':>7s} {'baseline':>8s} {'delta':>7s} {'prec%':>6s}"
    print(header)
    print("-" * len(header))
    for name, row in results.items():
        precision = row["fallback_precision"]
        print(
            f"{name:12s} {row['count']:>4d} {row['fallback_rate'] * 100:>6.1f} "
            f"{row['served_mae']:>7.3f} {row['model_only_mae']:>7.3f} "
            f"{row['baseline_mae']:>8.3f} {row['served_minus_model_mae']:>+7.3f} "
            f"{('n/a' if precision is None else f'{precision * 100:.0f}'):>6s}"
        )
    print(f"\nwrote {OUTPUT}")


if __name__ == "__main__":
    main()

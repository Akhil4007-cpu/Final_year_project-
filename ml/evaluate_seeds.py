"""Multi-seed robustness report for GACE.

Runs the FULL production pipeline (ml.train.run) once per data/generation seed, so
each seed regenerates scenarios, re-selects the model by train-only grouped CV, and
re-calibrates the conformal band. Headline metrics are then reported as mean +/- 95%
CI across seeds. Nothing here consults the test split to pick anything; it only
MEASURES the shipped procedure repeatedly.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

from ml.train import run

SEEDS = [42, 43, 44, 45, 46]
PER_TYPE = 140
# per-seed full pipeline runs write throwaway artifacts here; only the aggregate is committed
SCRATCH = Path("ml/artifacts_ml2")
COMMITTED = Path("ml/artifacts")

HEADLINES = {
    "clean_r2": ("clean", "r2"),
    "clean_mae": ("clean", "mae"),
    "degraded_mae": ("degraded", "mae"),
    "degraded_baseline_mae": ("degraded", "baseline_mae"),
    "ood_radius_mae": ("ood_radius", "mae"),
    "ood_radius_baseline_mae": ("ood_radius", "baseline_mae"),
    "ood_type_mae": ("ood_type", "mae"),
    "ood_type_baseline_mae": ("ood_type", "baseline_mae"),
    "empirical_coverage": ("uncertainty_coverage", "empirical_coverage"),
    "latency_p50_ms": ("latency", "p50_ms"),
    "latency_p95_ms": ("latency", "p95_ms"),
}


def _ci95(values: list[float]) -> tuple[float, float]:
    mean = statistics.mean(values)
    if len(values) < 2:
        return mean, mean
    std = statistics.stdev(values)  # sample sd
    half = 1.96 * std / math.sqrt(len(values))
    return mean - half, mean + half


def main() -> None:
    per_seed: list[dict[str, Any]] = []
    for seed in SEEDS:
        artifact = run(seed=seed, per_type=PER_TYPE, output_dir=SCRATCH / f"_seed_{seed}")
        metrics = artifact["metrics"]
        row: dict[str, Any] = {"seed": seed, "production_model": metrics["production_model"]}
        for name, (grp, key) in HEADLINES.items():
            row[name] = metrics[grp].get(key)
        row["monotonic_pass"] = metrics["monotonic_checks"][metrics["production_model"]]["passed"]
        row["leakage_overlap"] = metrics["leakage_audit"]["train_test_scenario_overlap"]
        per_seed.append(row)
        print(
            f"seed={seed} cleanR2={row['clean_r2']} degrMAE={row['degraded_mae']} "
            f"cov={row['empirical_coverage']} prod={row['production_model']}"
        )

    summary: dict[str, Any] = {"seeds": SEEDS, "per_seed": per_seed}
    for name in HEADLINES:
        vals = [r[name] for r in per_seed if isinstance(r[name], (int, float))]
        if vals:
            lo, hi = _ci95(vals)
            summary[name] = {
                "mean": round(statistics.mean(vals), 4),
                "std": round(statistics.stdev(vals), 4) if len(vals) > 1 else 0.0,
                "ci95_low": round(lo, 4),
                "ci95_high": round(hi, 4),
                "n": len(vals),
            }
    summary["all_monotonic_pass"] = all(r["monotonic_pass"] for r in per_seed)
    summary["max_leakage_overlap"] = max(r["leakage_overlap"] for r in per_seed)
    (COMMITTED / "multi_seed_metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== MEAN +/- 95% CI over", len(SEEDS), "data seeds ===")
    for name in HEADLINES:
        s = summary.get(name)
        if s:
            print(f"{name:26s} {s['mean']:.4f}  [{s['ci95_low']:.4f}, {s['ci95_high']:.4f}]")
    print("all_monotonic_pass", summary["all_monotonic_pass"], "max_leakage", summary["max_leakage_overlap"])


if __name__ == "__main__":
    main()

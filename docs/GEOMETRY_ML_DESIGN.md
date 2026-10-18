# GEOMETRY_ML_DESIGN

The **Geometry-Aware Challenge Estimator (GACE)** maps a degraded road polyline to a
0–100 *geometry challenge score*. It is documented here as WHAT / WHY / HOW /
EVALUATION. It is **not** an accident model and is never presented as one (R4).

## WHAT

GACE is a **physics-anchored residual estimator**. It takes the measurable curve
geometry (radius statistics, heading change, curvature variation, transition abruptness,
polyline quality) plus contextual bands (speed, road class, grade) and produces a
0–100 challenge score as **the transparent `physics_v2r_v1` prior plus a learned
correction**. The prior is recomputed from the *same (possibly degraded)* features the
model is given, so the learned component can only widen or narrow the explainable
baseline — it can never reach the clean reference label. It ships with split-conformal
uncertainty and a hard fallback to the physics baseline whenever the two disagree.

## WHY

- The physics `v²/R` prior is a good but brittle floor: on clean geometry it is near
  exact, but on **degraded OSM polylines** sparse or noisy vertices make radius
  estimates explode, so the raw baseline MAE *rises* to 27.8 on mixed-degradation input
  while the corrected model drops to ~14 (measured, `eval_results.json`).
- Anchoring on the prior (rather than predicting the score from scratch) is what makes
  the in-distribution **clean** score reproduce the documented reference (R² ≥ 0.99):
  the residual is ~0 on clean input, so no learned error is introduced there. The
  model's genuine contribution is the **correction** on degraded and out-of-radius-band
  geometry, and it is only ever claimed there.
- The learned model earns its place **only** because it beats the transparent baseline
  on degraded data; the baseline remains the explainable floor and the arbiter (R7).
- Uncertainty is mandatory because a single point score over-claims precision the input
  cannot support (R3).

## HOW

### Baseline label — `physics_v2r_v1` / `label_v1`
`app/baseline.py` computes the reference score from lateral demand (`v²/R`) with
documented length and transition adjustments, clipped to [0, 100]; grade is capped at
`MAX_GRADE_PCT = 8.0`. `ASSUMPTIONS` are emitted in every response so the score's basis
is always visible. Missing radius or invalid geometry yields no score (`None`), never a
fabricated low score (R5).

### Features — 22 numeric, `feature_schema.json`
Curve flags and radius statistics (`is_curve`, `log_radius`, `inverse_min_radius`,
`curve_length_m`, `max_turn_deg`, `curvature_std`, `heading_change_deg`/`_per_m`,
`transition_abruptness`, `spiral_like`, `gap_before_m`, `sequence_index`, `length_m`,
`median_spacing_m`), context bands (`speed_mps`, `road_class_code`, `grade_pct`,
`geometry_quality`), **explicit missing flags** (`speed_missing`, `road_class_missing`,
`grade_missing`), and the **`physics_prior`** feature — the `label_v1` challenge score
recomputed from the same (possibly degraded) features. `physics_prior` is the only
physics quantity in the feature set and it is derived purely from the input geometry and
context, never from the clean reference label. When a value is absent it is imputed with
a documented default **and flagged** — never silently treated as measured
(`build_features`, `resolve_speed`).

### Monotonic constraints (physics-informed guardrails)
`MONOTONIC_CONSTRAINTS` require the correction to score: curves ≥ straights
(`is_curve +1`), lower challenge as radius grows (`log_radius -1`), higher as tightness
grows (`inverse_min_radius +1`), higher with speed (`speed_mps +1`), and non-decreasing
in the prior (`physics_prior +1`). Hist-gradient boosting enforces these natively
(`monotonic_cst`) and passes a 40-point radius × 20-point speed probe grid. Candidates
that violate the grid are rejected regardless of accuracy.

### Model selection & production model
`ml/train.py` trains candidate estimators (decision tree, random forest, and three
HistGradientBoosting capacities) and selects the production model by **grouped 5-fold
CV MAE computed on the TRAIN split only** — the test split is never consulted for
selection (R1). Two hard gates precede the ranking, both evaluated on a train-fit model:
a **monotonicity guard** and a **deployment latency budget** (`LATENCY_BUDGET_P95_MS =
12.0`, a mobile real-time requirement; random forest's train-measured p95 ≈ 48 ms exceeds
it, so a fast 0.4-MAE edge is not bought at a ~10× latency cost). Among candidates that
clear both gates, the lowest CV MAE ships: `hist_gradient_boosting`
(learning_rate 0.06, max_iter 400, monotonic). Clean-manifold training rows are
duplicated `CLEAN_EMPHASIS = 3×` — a ratio chosen by the same train-only grouped CV on
the clean manifold (peak clean CV R²), **not** by any test result. The model is fit on
the residual `label − physics_prior`; the artifact stores the residual predictor and
`prediction_mode = physics_prior_plus_boosted_residual`, and `app/model.py` adds the
prior back at inference. The artifact is loaded **once** at startup and the runtime
never imports `ml/` (R10).

### Uncertainty — split-conformal absolute residual
The conformal offset is the empirical `NOMINAL_COVERAGE = 0.80` quantile of the absolute
calibration residuals (linear interpolation). The band is ±offset around the corrected
score, widened by `ood_interval_widen_factor = 1.25` for OOD-radius scenarios. Split
conformal gives a marginal coverage guarantee only up to finite-sample scatter; on a
144-row held-out slice the standard error of a 0.80 coverage estimate is ≈3.3 points, so
the headline is reported as **mean ± 95% CI across ≥5 data seeds** (see
`ml/artifacts/multi_seed_metrics.json`), and over-coverage (a conservatively wide
band) is the safe direction. Out-of-distribution never yields fake confidence.

### Disagreement fallback
`DISAGREEMENT_THRESHOLD = 20.0`. If |model − baseline| > 20, `model_status` becomes
`baseline_fallback` and the baseline number is served; the model number is retained only
when it and the physics agree. Because the model is `baseline + residual` and the runtime
prior equals `baseline_for_section`, this threshold is exactly `|residual| > 20` — i.e.
"the learned correction departs from the transparent physics by more than 20 points, so
distrust it and fall back." Every ML output is tagged `model_estimate` and synthetic
origin is disclosed (R7).

## EVALUATION

See [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) and
[GEOMETRY_ML_LIMITATIONS.md](GEOMETRY_ML_LIMITATIONS.md). Headline measured numbers for
the default seed (42), all reproducible via `python -m ml.train --seed 42 --per-type 140`:

| Slice | count | model MAE | baseline MAE | reading |
|---|---|---|---|---|
| Clean (in-distribution) | 156 | 0.573 | 0.089 | **R² = 0.9948 ≥ 0.99** — correction reproduces the reference |
| Mixed-degradation | 144 | 14.142 | 27.826 | **model clearly wins where it matters** |
| OOD radius [300,700] | 102 | 14.994 | 43.287 | model far more robust than raw physics |
| OOD type (hairpin) | 140 | 20.307 | 12.647 | **model loses → baseline fallback justified** |
| Uncertainty coverage | 144 | empirical 0.8403 | nominal 0.80 | conservatively wide band (over-covers) |
| Inference latency | — | p50 5.02 ms / p95 6.62 ms (500 reps) | — | within the 12 ms mobile budget |

Seed stability: the HistGradientBoosting estimator is deterministic given fixed data, so
model-`random_state` variation across 5 seeds gives an identical degraded MAE — that is a
~0 CI by construction, **not** data robustness. True robustness is measured by re-running
the **whole** pipeline across 5 data-generation seeds (each regenerates scenarios,
re-selects by train CV, re-calibrates) via `python -m ml.evaluate_seeds`. Those
mean ± 95% CI figures (committed in `ml/artifacts/multi_seed_metrics.json`):

| Metric (5 data seeds 42–46) | mean | 95% CI | reading |
|---|---|---|---|
| Clean R² | **0.9975** | [0.9960, 0.9990] | clears ≥0.99 on the CI **lower** bound |
| Clean MAE | 0.475 | [0.408, 0.543] | reference reproduced on every seed |
| Degraded MAE | **13.999** | [13.044, 14.954] | vs baseline 28.273 [27.338, 29.208] — model wins on every seed |
| OOD radius MAE | 15.896 | [14.808, 16.984] | vs baseline 44.928 [43.335, 46.521] — error reduced |
| OOD type (hairpin) MAE | 19.456 | [17.959, 20.953] | vs baseline 12.556 [11.951, 13.160] — **model loses → baseline fallback justified** |
| Empirical coverage | 0.8173 | [0.787, 0.848] | nominal 0.80 ±3pt band 0.77–0.83; **mean inside band**, per-seed scatter (0.76–0.848) is finite-sample noise (≈3.3 pt SE on n≈144) |
| Latency p95 (ms) | 8.85 | [7.15, 10.56] | within the 12 ms real-time budget on every seed |

Monotonic grid check PASS and leakage overlap 0 on all 5 seeds. Splits train 643 / calib
151 / test 144 / ood_radius 102 / ood_type 140 (per seed).

# RoadGuard Model Card — GACE hist_gradient_boosting

## Intended use
Estimate a **geometry-challenge score (0–100)** for a mapped road section from a
degraded polyline. Advisory only. This model is **not** an accident-risk model and
must never be presented as one.

## Prediction design
GACE = `physics_v2r_v1` **physics prior** + a monotonicity-constrained
gradient-boosted **residual correction**. The `physics_prior` feature is the transparent
v^2/R score recomputed from the *same (possibly degraded)* features that the model sees,
so the correction can only widen or narrow that prior — never reach the clean reference
label. On clean, in-distribution input the residual is near zero, so GACE reproduces the
documented reference; the model's measured value is in **correcting degraded geometry**
toward the clean reference.

## Training data
Synthetic scenarios produced by `generator_v1` (1180 training/evaluation rows,
seed 42). No real crash labels, GPS traces, or Indian road observations were used.
Labels are the clean `label_v1` reference score: lateral-demand physics plus documented
length/transition adjustments. Scenario types: straight, simple_arc, spiral, reverse_curve, compound, hairpin, urban_turn.

## Features
22 numeric features including curve radius statistics, heading change,
curvature variation, transition abruptness, speed band (or an explicit missing flag),
road class (or missing), real grade (or missing), geometry quality, and the `physics_prior`
score the model corrects. Missing context is imputed with documented assumptions and flagged;
it is never silently treated as measured.

## Evaluation (measured)
Single committed artifact (data seed 42):
- Test rows: 156 clean, 144 mixed-degradation.
- Clean (in-distribution) holdout: R² 0.9948, MAE 0.573 (baseline 0.089), RMSE 1.827.
- Mixed-degradation MAE: 14.142 (baseline 27.826); R² 0.3804.
- Noise sweep MAE (ML / baseline): {0.0: 0.573, 3.0: 13.247, 6.0: 16.435, 10.0: 19.365, 15.0: 18.299, 20.0: 23.589} / {0.0: 0.089, 3.0: 33.723, 6.0: 40.936, 10.0: 39.588, 15.0: 36.784, 20.0: 34.607}.
- Uncertainty: nominal 0.8, empirical 0.8403, mean width 49.467 points.
- OOD scenario type (hairpin) MAE: 20.307 (baseline 12.647).
- OOD radius band [300.0, 700.0] MAE: 14.994 (baseline 43.287).
- Monotonic grid check: PASS.
- Top permutation features: max_turn_deg, heading_change_per_m, geometry_quality, road_class_code, length_m.

Cross-seed stability (`python -m ml.evaluate_seeds`, 5 data seeds 42–46, retrain + re-eval
each; mean ± 95% CI, scenario-level splits):
- Clean R²: **0.9975 [0.9960, 0.9990]** — clears the ≥0.99 target on the CI lower bound.
- Clean MAE: 0.475 [0.408, 0.543].
- Degraded MAE: **13.999 [13.044, 14.954]** vs baseline 28.273 [27.338, 29.208] — model beats baseline on every seed.
- OOD radius MAE: 15.896 [14.808, 16.984] vs baseline 44.928 [43.335, 46.521] — error reduced.
- OOD type (hairpin) MAE: 19.456 [17.959, 20.953] vs baseline 12.556 [11.951, 13.160] — model is worse than baseline on this slice, which is the intended trigger for the disagreement fallback to `physics_v2r_v1`.
- Empirical coverage: 0.8173 [0.787, 0.848] vs nominal 0.80 (±3pt band 0.77–0.83). Mean is inside the band; per-seed values scatter 0.76–0.848 because a single held-out slice (n≈144) carries ~3pt standard error — finite-sample noise, not a coverage failure.
- Latency p95: 8.85 ms [7.15, 10.56], within the 12 ms real-time budget on every seed.
- Monotonic grid check: PASS on all 5 seeds. Leakage overlap: 0 on all 5 seeds.

## Limitations
- Synthetic-only training; no real-world accuracy claim is possible.
- Speed is an advisory band, not a measured or legal speed.
- OSM/OSRM geometry quality varies; long gaps and very coarse polylines can make a section unscorable.
- Indian road geometry, mixed traffic, and surface conditions are not represented by the generator.
- The score does not encode banking, friction, pavement, traffic, weather, or rider behaviour.
- Out-of-distribution inputs widen intervals but cannot guarantee coverage.
- This model must remain in shadow/baseline mode if its noise robustness test fails in a future retrain.

## Reproduce
`python -m ml.train --seed 42 --per-type 140`
See `REPRODUCE.md` and `eval_results.json` for exact commands and outputs.

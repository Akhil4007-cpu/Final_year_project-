# GEOMETRY_ML_LIMITATIONS

Every limitation here is a real, measured property of the current pipeline. None are
spun as strengths; the point of this document is that no over-claim is made (R1, R4).

## Training-data limitations

- **Synthetic only.** Labels come from `generator_v1` scenarios scored by the `label_v1`
  physics formula. There are **no real crash records, no real GPS traces, no observed
  Indian road data**. "Accuracy" means agreement with the synthetic reference, not
  agreement with reality. The dataset SHA-256 and split counts are in
  `ml/artifacts/dataset_manifest.json`.
- **Coverage of scenario space.** Only seven types are generated: straight, simple_arc,
  spiral, reverse_curve, compound, hairpin, urban_turn. Real intersections, roundabouts,
  ramp merges, surface defects, and mixed traffic are absent.
- **No real-world generalisation claim** is possible. Indian road geometry, riding
  behaviour, weather, and traffic are not represented.

## Measured model weaknesses

- **The raw physics prior is still marginally more exact on clean input** (baseline MAE
  0.089 vs model 0.573, though the corrected model reproduces the reference at **R² 0.9948**).
  GACE's value is specifically on **degraded** polylines, where it cuts MAE from 27.826 to
  ~14; it is not universally superior and never claims to be.
- **The model loses on out-of-distribution type (hairpin)**: MAE 20.307 vs baseline
  12.647, and conformal coverage there falls to 0.6786 (nominal 0.8) even with the widened
  band. This is exactly the case where the disagreement fallback should route to the
  baseline — and where any retrained model must be re-checked before it is trusted.
- **Robustness degrades with noise:** model MAE rises 0.573 → 23.589 as noise grows 0→20
  m, but stays well under the raw-prior MAE at every noise level ≥3 m (0.089→34.607).
  At very high noise the model is materially less certain; intervals widen but **cannot
  guarantee coverage** OOD.

## Runtime-served accuracy: what the disagreement fallback costs

The §7.5 suite reports the **model's** error. At runtime the shipped guard
([app/model.py](../app/model.py) `DISAGREEMENT_THRESHOLD = 20.0`) replaces the model with the
physics baseline whenever `|model − baseline| > 20` and tags the section `baseline_fallback`.
That substitution changes what the rider actually sees, so it was measured directly
(`python -m ml.fallback_audit`, seed 42, committed artifact, **threshold unchanged** —
`ml/artifacts/fallback_audit.json`). The audit refuses to report unless its regenerated
model-only MAE matches `eval_results.json` to ±0.0015, which it does on all four headline
slices.

| slice | n | fallback fires | **served** MAE | model-only MAE | baseline MAE | served − model | guard was right |
|---|---|---|---|---|---|---|---|
| clean | 156 | 0.6 % | 0.445 | 0.573 | 0.089 | −0.128 | 100 % |
| degraded (mixed) | 144 | **61.1 %** | **27.252** | 14.142 | 27.826 | **+13.110** | 20 % |
| noise σ=3 m | 156 | 72.4 % | 32.960 | 13.247 | 33.723 | +19.713 | 15 % |
| noise σ=6 m | 149 | 89.3 % | 40.599 | 16.435 | 40.936 | +24.164 | 17 % |
| noise σ=10 m | 148 | 85.8 % | 39.144 | 19.365 | 39.588 | +19.779 | 21 % |
| noise σ=15 m | 153 | 85.6 % | 36.198 | 18.299 | 36.784 | +17.898 | 24 % |
| noise σ=20 m | 151 | 80.8 % | 34.733 | 23.589 | 34.607 | +11.144 | 38 % |
| OOD radius 300–700 m | 102 | **67.7 %** | **42.394** | 14.994 | 43.287 | **+27.400** | 3 % |
| OOD type (hairpin) | 140 | 66.4 % | 12.593 | 20.307 | 12.647 | **−7.714** | 72 % |

**Read this plainly.** The guard is worth it on exactly one slice — the unseen *curve type*
(hairpin), where the model is genuinely worse than the baseline and the guard recovers 7.7
MAE and is right 72 % of the time. On degraded, noise and OOD-*radius* input it is close to
counterproductive: it fires on 61–89 % of sections, and because a large model−baseline gap on
those slices is usually the model *correcting* degraded geometry rather than erring, the guard
is right only 3–38 % of the time. The consequence: **the score a rider is served on degraded
input (27.252) is barely better than the pure baseline (27.826), nowhere near the model's own
14.142.** So "GACE cuts degraded MAE from 27.826 to ~14" is a statement about the model, not
about the guarded pipeline's served output; both numbers are reported here to avoid the
ambiguity.

A calibration-split-only sweep of the same rule (in `fallback_audit.json`,
`calibration_only_threshold_sweep`) shows served MAE falling monotonically as the threshold
rises — 29.95 at 20, 27.10 at 30, 22.86 at 40, 19.80 at 50, 14.76 with the guard off — i.e.
**no finite threshold beats "don't guard" on degraded input**; the guard's only measured value
is OOD-*type* protection. **The threshold was not retuned.** Changing it would trade a
documented safety behaviour for accuracy on synthetic labels, which is a design decision for
the supervisor, not a post-hoc reaction to test numbers (plan R-rule: no loosening thresholds
after seeing results). What *is* recommended: keep the guard, keep surfacing the `disagreement`
flag and `baseline_fallback` provenance, and quote served MAE (not model MAE) whenever the
runtime path is described.

## Feature/context limitations

- **Speed is an advisory band, not measured or legal speed.** When the caller omits it,
  it is assumed from road class and flagged `speed_missing` — the number reflects an
  assumption, and the response says so. Since TASK 2 the rider UI additionally reads the
  device's `coords.speed` during navigation and shows how the lateral demand at that speed
  compares, in g, with the demand implied by the band the score used
  (`app/web/alerts.js` `speedAwareness`). This is a **note, not a re-score**: the model and
  baseline both still see the banded speed, so no published metric changes, and devices that
  report no speed (most desktops) see an explicit disclosure rather than a silent 0 km/h.
- **Grade and geometry quality can be missing**; they are imputed with documented
  defaults and flagged, never silently treated as observed (R3).
- The score encodes **only mapped road shape plus assumed context**. It deliberately
  ignores banking, friction, pavement condition, traffic, weather, and rider behaviour —
  so it must never be read as a safety guarantee (R4, R7).

## Data-quality limitations

- OSM/OSRM geometry varies by region. Long gaps and very coarse polylines can make a
  section **unscorable**; unscorable length is reported as missing evidence, not as
  zero risk (R5). Route-level results below 60% coverage return `insufficient_evidence`
  rather than a misleading average.

## Operational limitations

- Model confidence is bounded by the conformal calibration set's representativeness. If
  a future retrain fails the noise/degradation bar, the correct action per the plan is to
  keep ML in **shadow mode** and serve the baseline — this is a requirement, not an
  option.
- No accident-prediction capability exists or is claimed anywhere in the system.

## What would change these conclusions

Real Indian road geometry data with surveyed curve radii, measured speed distributions,
and validated labels — none of which is in scope for this build, and whose absence is
disclosed rather than papered over (R11).

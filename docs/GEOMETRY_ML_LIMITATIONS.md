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

## Feature/context limitations

- **Speed is an advisory band, not measured or legal speed.** When the caller omits it,
  it is assumed from road class and flagged `speed_missing` — the number reflects an
  assumption, and the response says so.
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

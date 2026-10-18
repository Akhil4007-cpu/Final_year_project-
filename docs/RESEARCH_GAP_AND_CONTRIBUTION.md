# RESEARCH_GAP_AND_CONTRIBUTION

## Refined problem statement

Riders on unfamiliar roads have no low-cost, privacy-preserving cue about *geometrically
demanding* curves ahead of them. The strongest prior art (Ma et al. 2023; Hossain & Lee
2026; Nadimi et al. 2025) predicts curve risk from **connected-vehicle telemetry, live
speed, or observed surrogate events** — data streams that a lightweight, map-only mobile
app cannot assume and should not secretly collect.

## The gap

There is no widely available method that:

1. scores road **geometry challenge** from an **open-map polyline alone** (no onboard
   sensors, no crash history),
2. is **honest about uncertainty** — surfacing when input is too sparse/noisy to score
   rather than inventing a number,
3. keeps a **transparent physics floor** the rider and examiner can interrogate, and
4. **refuses to pose as an accident predictor** while still being useful.

Prior work establishes *that* geometry matters (FHWA-HRT-13-077) and *that* sensors improve
curve-risk estimation (Ma 2023). It does **not** establish that a sensor-free, map-only,
India-restricted advisory can be delivered with defensible uncertainty — that is this
project's territory.

## Contribution

**GACE — a Geometry-Aware Challenge Estimator** that turns OSM geometry into a bounded,
uncertainty-carrying advisory, built around four deliberate design commitments:

| # | Contribution | Mechanism in code | Why it closes the gap |
|---|---|---|---|
| C1 | Sensor-free geometry scoring | `geo.extract_sections` → 22 features incl. the `physics_prior` the model corrects (`features.py`) | works from an open polyline only |
| C2 | Physics-first, ML-gated baseline | `baseline.py` `v²/R` prior; GACE = prior + boosted residual, →`baseline_fallback` if correction disagrees by > 20 (`model.py`) | explainable floor; ML must earn weight, never over-claims |
| C3 | Conformal uncertainty + OOD widening | split-conformal in `model.py` (empirical 0.8403 @ nominal 0.8, seed 42; mean±CI across seeds in `multi_seed_metrics.json`) | states how little it knows; no false precision |
| C4 | Explicit evidence provenance + no-silent-failure contract | `provenance.py` 5 channels; `errors.py` `insufficient_evidence`/`unavailable` (R3/R5) | honest about missing data |

A secondary, engineering contribution: a **fully reproducible synthetic pipeline** (seed
42, dataset hash recorded, leakage-audited split) that trains the model **without any real
crash or telemetry data**, and a runtime that **never imports the ML training code**
(R10) — keeping the synthetic origin auditable and the advisory claims bounded.

## What this contribution is NOT

- **Not** an accident/crash predictor (R4). It scores *geometry challenge*, an indicator,
  and says so in every rider-facing string.
- **Not** validated on Indian roads. Training is synthetic; the accuracy it can claim is
  agreement with a physics label, not reality. Real-world validation is future work and is
  flagged `REQUIRES STUDENT INPUT`/planned rather than asserted.
- **Not** a replacement for the sensor-based systems it cites as prior art; it is a
  deliberately lower-bar, privacy-preserving alternative for the no-telemetry case.

## Objectives traceability

| Objective | Met by | Evidence |
|---|---|---|
| O1 geometry scoring from open map | C1 | `test_geo` (15), live browser route |
| O2 uncertainty surfaced | C3 | conformal tests (`test_model`), OOD coverage disclosed |
| O3 transparent baseline | C2 | `test_baseline` (10), disagreement fallback |
| O4 honest evidence contract | C4 | `test_compliance`, `insufficient_evidence` paths |
| O5 no accident claim anywhere | scope | R2/R4 grep + tests pass |
| O6 privacy-preserving (no telemetry store) | design | no movement-trail persistence; waypoints only |

Real-world accuracy (an objective a crash-risk paper would claim) is **deliberately
out of scope** and its absence is the honest boundary of this contribution.

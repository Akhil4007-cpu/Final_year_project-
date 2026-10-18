# REVIEW_2_PROJECT_SPECIFICATION

Slide-by-slide content for the college 21-slide Review 2 structure, filled **only** from
this repository's verified evidence. Rows the code cannot supply are marked
`REQUIRES STUDENT INPUT` and left blank rather than invented (R11). Every number below
traces to a doc or `eval_results.json` in this repo.

| # | Slide | Content (from repo) | Source | Status |
|---|---|---|---|---|
| 1 | Title (team, supervisor) | **REQUIRES STUDENT INPUT** — names, roll numbers, guide | — | ☐ student |
| 2 | Project overview | Mobile-first real-time road-geometry **advisory**; FastAPI + SQLite + Leaflet + OSM/OSRM; GACE ML. **Not** an accident predictor. | README, ARCHITECTURE | ☑ Tested |
| 3 | Review 1 feedback + actions | **REQUIRES STUDENT INPUT** — actual feedback + what was changed | — | ☐ student |
| 4 | Refined problem statement | Riders lack a low-cost, privacy-preserving cue for geometrically demanding curves; prior art needs telemetry/speed/crash data the app cannot assume. | RESEARCH_GAP | ☑ |
| 5 | Objectives | O1 geometry score from open map; O2 surfaced uncertainty; O3 transparent baseline; O4 honest evidence contract; O5 no accident claim; O6 no telemetry stored. | RESEARCH_GAP §Objectives | ☑ Tested |
| 6 | Updated literature review | FHWA-HRT-13-077; Nadimi 2025; Hossain & Lee 2026; Ma 2023; Lei 2018; Roberts 2017 + standards. | RESEARCH_LITERATURE_REVIEW | ☑ Verified 2026-10-17 |
| 7 | Comparative table | Paper·Year·Method·Data·Perf·Limitation + Proposed row "to be evaluated". | RESEARCH_LITERATURE_REVIEW table | ☑ |
| 8 | Research gap | No sensor-free, map-only, uncertainty-honest, non-crash geometry advisory. | RESEARCH_GAP | ☑ |
| 9 | Proposed contribution | GACE: C1 sensor-free scoring, C2 physics-first ML-gated, C3 conformal uncertainty, C4 provenance/no-silent-failure. | RESEARCH_GAP | ☑ Tested |
| 10 | Methodology | Physics `v²/R` **prior** → 22 features → candidate models (train-only grouped-CV + monotonicity + latency gate) → GACE = prior + boosted **residual** → split-conformal → disagreement fallback → startup load. | GEOMETRY_ML_DESIGN | ☑ |
| 11 | Architecture diagram | Browser GPS FSM ↔ FastAPI (api/services) → geo/baseline/model/aggregation/advisory; providers (Nominatim/OSRM); `ml/` offline, never imported. | ARCHITECTURE | ☑ |
| 12 | Dataset / synthetic method | generator_v1, label_v1, seed 42, 1180 rows, 7 scenario types, SHA-256 `5e92447a…d5db9d`, leakage audited. **No real crash/GPS data.** | DATA_AND_PROVENANCE, dataset_manifest | ☑ |
| 13 | Tools & technologies | FastAPI (API), Pydantic v2 (strict schemas), SQLite WAL (store), scikit-learn HGB (model, monotonic_cst), joblib (artifact), Leaflet 1.9.4 vendored (map), OSM/OSRM/Nominatim (providers), pytest (tests). | requirements.txt | ☑ |
| 14 | Baseline approach | `physics_v2r_v1`/`label_v1`; clean MAE 0.089; degraded MAE 27.826 — the bar ML must clear. | baseline.py, eval_results | ☑ Tested |
| 15 | Implementation progress | 99 backend + 23 frontend `node --test` cases green; rider UI (incl. staged capability-aware alerts + settings) and admin console browser-verified; ML reproducible + multi-seed verified; `ruff`/`mypy`/`pip-audit` run clean (CI-blocking); performance measured + optimised (server batch ~6× faster, client 0.024 ms/fix, live provider latency). Playwright E2E / Docker build still pending. | IMPLEMENTATION_STATUS, PERFORMANCE_REPORT | ☑ |
| 16 | Preliminary results (measured only) | Clean **R² 0.9948** (MAE 0.573) / degraded MAE 14.142 vs baseline 27.826; OOD-radius 14.994 vs baseline 43.287; **hairpin OOD model 20.307 vs baseline 12.647 → fallback**; conformal coverage 0.8403 (seed 42; mean±CI across 5 seeds in `multi_seed_metrics.json`); inference p50 5.02 ms. | GEOMETRY_ML_DESIGN, PERFORMANCE_REPORT | ☑ Measured |
| 17 | Evaluation strategy | Monotonic grid, noise sweep, missing sweep, OOD type+radius, seed stability, leakage, latency, uncertainty coverage. | §7.5 / GEOMETRY_ML_DESIGN | ☑ |
| 18 | Current status table | per-feature Completed/Tested/In-progress/Planned/Unverified. | IMPLEMENTATION_STATUS | ☑ |
| 19 | Remaining work + timeline | restore done; research done; live+E2E tests, lint, audit, client perf, Docker/CI, deck. | LOOP_STATE | ☑ |
| 20 | Expected outcome | Defensible geometry advisory with honest uncertainty; **real-world accuracy explicitly "to be evaluated"** — not claimed. | RESEARCH_GAP | ☑ |
| 21 | References | 11 verified sources + 4 tool families, all URL + access date. | REFERENCES_VERIFIED | ☑ Verified |

## Viva-readiness (per guideline 20 questions)

Be ready to defend, with repo evidence: why not accident prediction (R4); why synthetic
(labels are physics, not observations); how each number was generated and whether it is
reliable (conformal coverage < nominal is disclosed); why the model falls back on hairpins
(disagreement + OOD weakness); what "insufficient_evidence" prevents (false zero-risk); and
why no CSRF token is in the DOM (header-based CSRF + HttpOnly cookie).

## Presenting measured charts — the honest reading

Every graph shown must be explainable: **how generated** (a `python -m ml.train` run),
**what it means** (MAE against a synthetic physics label), **why it changed**
(degradation hurts the baseline more than the model — the model's whole value), and
**whether reliable** (yes within synthetic regime; **no** claim of real-road generalisation).

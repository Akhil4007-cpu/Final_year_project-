# REVIEW_2_SLIDE_OUTLINE

Slide-by-slide talking points for the college 21-slide Review 2 structure. **Every number is a
measured value from this repository** (an artifact JSON, a test run, or a benchmark output) and is
reproducible with the command named in §"Numbers → command" below. Where a check did not run, the
slide says so rather than implying otherwise. Rows that only the student can supply are marked
`REQUIRES STUDENT INPUT` and left blank — never invented (rule R11).

Companion detail lives in [REVIEW_2_PROJECT_SPECIFICATION.md](REVIEW_2_PROJECT_SPECIFICATION.md)
(the 21-row mapping to sources) and [FINAL_REPORT.md](FINAL_REPORT.md) (full evidence).

---

## Slide 1 — Title

- Project: **RoadGuard AI — a geometry-aware road-challenge advisory for riders**.
- `REQUIRES STUDENT INPUT` — team members and roll numbers.
- `REQUIRES STUDENT INPUT` — guide / supervisor, co-guide, department, institution, review date.
- `REQUIRES STUDENT INPUT` — internal report / submission number.
- Speaker note: keep the subtitle literal — *advisory*, not *safety system*, because the whole
  project is built around not over-claiming (slide 16 and the viva section).

## Slide 2 — Project overview

- Mobile-first, real-time **road-geometry challenge advisory**: a 0–100 band per curve section,
  delivered as staged advisories before the rider enters the curve.
- Backend FastAPI + Pydantic v2 + SQLite (WAL); frontend **no-build** vanilla ES modules +
  Leaflet 1.9.4 (vendored); providers Nominatim (geocode) + OSRM (routing).
- Core deliverable **GACE** (Geometry-Aware Challenge Estimator) = split-conformal residual over a
  transparent `v²/R` physics baseline (`physics_v2r_v1`), with a disagreement fallback to that
  baseline.
- **Explicitly not an accident predictor** (R4): the API response and the UI both carry the
  limitation, and `tests/test_compliance.py` (7 cases) greps the tree for banned affirmatives.
- Evidence status: 112 backend + 31 frontend JS + 17 Playwright E2E cases green.

## Slide 3 — Review 1 feedback and actions taken

- `REQUIRES STUDENT INPUT` — the actual Review 1 feedback, verbatim, per item.
- `REQUIRES STUDENT INPUT` — which items were accepted, deferred or rejected, and why.
- For each accepted item, this repo can supply the action evidence: the code path, the test that
  locks it in, and the doc section (use `docs/IMPLEMENTATION_STATUS.md` row for the mapping).
- Suggested per-row format: *feedback → change → file → test → measured effect*.

## Slide 4 — Refined problem statement

- Riders get no low-cost cue for **geometrically demanding curves** before they are in them; the
  first cue is often the curve itself.
- Prior art that estimates crash risk needs telematics, speed-history or crash data — none of which
  a map-only, privacy-preserving student app can assume.
- Bounding finding from the verified literature (11 sources): **no paper establishes
  accident-probability prediction from static mapped road geometry**, let alone for Indian roads.
- So the problem was **narrowed and made defensible**: score the geometry, publish an uncertainty
  band with it, and refuse to answer when the evidence is thin (`insufficient_evidence`).
- Constraints kept: map-only input, no persistent precise-movement trail server-side, works on a
  phone browser.

## Slide 5 — Objectives

| # | Objective | Locked by |
|---|---|---|
| O1 | Score curve geometry from open map data alone | `test_geo.py` (15) + `test_baseline.py` (10) |
| O2 | Surface the uncertainty with the score, never a bare number | `test_model.py` (13), conformal coverage measured (0.8403 seed-42) |
| O3 | Keep a transparent physics baseline that ML must beat | `test_baseline.py`, `eval_results.json` noise sweep |
| O4 | Honour an evidence contract: typed errors, provenance, no silent failure | `test_api.py` (18) + `test_api_routes.py` (6) |
| O5 | Make no accident claim anywhere | `test_compliance.py` (7), R4 |
| O6 | Store no persistent movement telemetry | `SECURITY_AND_PRIVACY.md`, deletion + rate-limit tests |

- All six are **Tested**, not merely designed.
- Speaker note: O3 and O5 are the two objectives reviewers can attack hardest; both have
  automated checks, so answer with the test name.

## Slide 6 — Updated literature review

- **11 numbered sources**, each with URL + access date 2026-10-17
  ([REFERENCES_VERIFIED.md](REFERENCES_VERIFIED.md)), plus 10 versioned tool entries.
- Two sources re-checked **at the publisher on 2026-10-18**: FHWA-HRT-13-077 at ROSA P
  (Bauer & Harwood, published 2014-01-01) and Nadimi 2025 via the Crossref DOI record.
- Honest caveat to read out, not hide: the Nature landing page **could not be machine-read**
  (HTTP 303 → 404 interstitial), so that citation rests on the Crossref record, not on a
  full-text read.
- Themes: crash **surrogate** measures from telematics, harsh-event detection, proactive
  curve/geometry assessment, uncertainty communication to non-expert users.
- Conclusion the review feeds: the field models *surrogates from streams* → that is the gap
  slide 8 claims.

## Slide 7 — Comparative table

- Columns: Paper · Year · Method · Data · Reported performance · Limitation · Relevance.
- Populate only from the table in
  [RESEARCH_LITERATURE_REVIEW.md](RESEARCH_LITERATURE_REVIEW.md) — do not add a paper that is not
  in `REFERENCES_VERIFIED.md`.
- Proposed-approach row: **Performance = "to be evaluated"** — the only defensible entry, because
  there is no real-road ground truth in this project.
- Differentiator column: sensor-free (map-only), uncertainty-calibrated, non-crash claim.
- Speaker note: if asked "so what is your number?", the answer is slide 16's synthetic results and
  the explicit statement that real-world accuracy is unmeasured.

## Slide 8 — Research gap

- Existing work predicts accident **surrogates** from telematics/GPS streams; this repo's object is
  **static mapped geometry** with honest uncertainty — a different input and a different claim.
- Three unmet conditions, stated together: sensor-free **+** calibrated uncertainty **+** no crash
  claim. Any one of them exists in the literature; the conjunction does not.
- A map-only score is only publishable if it can say "I don't know" — coverage-aware aggregation
  (`insufficient_evidence`) is part of the gap response, not a footnote.
- The gap statement is the project's claim ceiling: it is quoted in
  [RESEARCH_GAP_AND_CONTRIBUTION.md](RESEARCH_GAP_AND_CONTRIBUTION.md) and bounded by
  [LIMITATIONS.md](LIMITATIONS.md).

## Slide 9 — Proposed contribution

- **C1 — sensor-free geometry scoring**: section extraction + curvature geometry from the OSM
  polyline only (no IMU, no fleet telemetry).
- **C2 — physics-first, ML gated**: the `v²/R` prior is a *feature* (`physics_prior`, feature 22)
  and the model learns a monotonic residual, so the model only ever corrects physics — it cannot
  replace it. ML is kept only because it beats the baseline under noise: **13.247 vs 33.723 MAE at
  3 m label noise**.
- **C3 — calibrated band + disagreement fallback**: split-conformal band (nominal 0.80, offset
  26.3) and a runtime guard that serves the baseline when model and baseline differ by more than
  20.0 points.
- **C4 — provenance, no silent failure**: every score carries `model_estimate` or
  `baseline_fallback`; every failure is a typed error code.
- The honest cost, disclosed on the slide itself: the guard **fires on 61–72 %** of degraded/noise
  sections and pulls served error back to baseline level (degraded served **27.252** vs model-only
  **14.142**). It helps where the model genuinely loses (hairpin: 12.593 served vs 20.307
  model-only). Source: `ml/artifacts/fallback_audit.json`.

## Slide 10 — Methodology

- Synthetic generation: `generator_v1` / `label_v1`, seed 42, **1180 rows**, 7 scenario types,
  dataset SHA-256 `5e92447a370b2646c8929a434a577f9decf5694afb28e3c2d76ce93415d5db9d`.
- Splits by scenario group — train 643 / calibration 151 / test 144 / OOD-radius 102 / OOD-type
  140; **leakage overlap = 0**.
- Model selection on **train-only** grouped CV + a monotonicity gate + a p95 latency budget of
  12.0 ms: decision tree, random forest, hist-gradient-boosting were eligible; random forest was
  rejected on latency, `hist_gradient_boosting` selected.
- GACE = prior + monotonic boosted residual → split-conformal band → disagreement fallback at
  runtime → artifact loaded at startup, never at request time.
- Nothing was tuned on the test split, and the fallback threshold was **not** changed after
  measuring it (`threshold_retuned: false`).

## Slide 11 — Architecture diagram

- Draw three layers behind one ASGI app ([ARCHITECTURE.md](ARCHITECTURE.md)): **providers**
  (`httpx` + bounded LRU cache of 256 + 1.1 s courtesy throttle + typed errors) → **analysis core**
  (`geo` → `baseline` → `model` → `aggregation` → `advisory`) → **API/infra** (REST v1, sessions,
  rate limits, audit, hazards, admin).
- Show the **dependency seam** (`get_services(request)`): it is what lets 17 Playwright + 112
  backend cases run with mocked providers and zero network.
- Show the client GPS state machine → `POST /routes/analyze` → staged advisory cues
  (visual / vibration / audio with capability fallback).
- State on the slide: **`ml/` is never imported by `app/`** — enforced by the R10 import-graph test.
- Label the trust boundary: OSM/OSRM are third-party demo services; production needs self-hosting.

## Slide 12 — Dataset and synthetic methodology

- 1180 rows from `ml/`'s generator at `per_type = 140`; scenario types straight, simple arc,
  spiral, reverse curve, compound, hairpin, urban turn.
- Labels are the **documented physics reference** (`label_v1`) plus noise/degradation variants —
  they are not observations, and the deck must say "synthetic" every time a metric appears.
- **No real accident, crash or telematics data is used or claimed** anywhere in the project.
- Reproduce with `python -m ml.train --seed 42 --per-type 140`, then
  `python -m ml.evaluate_seeds` (5 data seeds, 42–46) → `ml/artifacts/multi_seed_metrics.json`;
  provenance in `dataset_manifest.json` and `ml/artifacts/REPRODUCE.md`.
- Robustness framing: the estimator is deterministic on fixed data, so the meaningful variance is
  across **data** seeds, not model seeds.

## Slide 13 — Tools and technologies

- Runtime: FastAPI, Pydantic v2 (strict schemas), SQLite WAL, `httpx`; Python 3.10.10.
- ML: scikit-learn `HistGradientBoostingRegressor` with monotonic constraints, joblib artifact,
  NumPy/pandas; no deep learning and no GPU.
- Frontend: Leaflet 1.9.4 vendored locally, vanilla ES modules, no bundler; OpenStreetMap + OSRM +
  Nominatim as providers (ODbL attribution).
- Quality: pytest 8.3.2, `node --test`, Playwright 1.64.1 (Chromium), ruff 0.6.2, mypy 1.11.2,
  pip-audit 2.10.1 (Node 24 for the JS tiers) — **all four static/audit gates run clean and are
  CI-blocking**.
- Speaker note: the no-build frontend is a deliberate choice — reviewers should hear "auditable on
  a phone", not "we skipped a framework".

## Slide 14 — Baseline approach

- `physics_v2r_v1`: lateral demand from `v²/R` on the extracted section radius, mapped to the
  0–100 band; fully transparent, one formula, no training.
- Seed-42 baseline MAE: clean **0.089**, degraded **27.826**, OOD-radius **43.287**, OOD-type
  (hairpin) **12.647**.
- Read the first number out loud: **on clean input the baseline is more accurate than the model**
  (0.089 vs 0.573) — the baseline is not a strawman.
- The hairpin row is the case where the baseline beats the model too, which is exactly why the
  disagreement fallback exists.
- The model's entire licence to exist is the degraded / noise / OOD-radius columns of that table.

## Slide 15 — Implementation progress

- Tests: `python -m pytest -q` → **112 passed** (1 warning, from `TestClient` itself);
  `node --test "tests/js/**/*.test.js"` → **31/31**; `npx playwright test` → **17 passed**
  (10 rider + 5 admin + 2 screenshot cases), all with `mock`-labelled providers.
- Static gates: `ruff` clean, `mypy` clean on **31 source files**, `pip-audit` **0 known
  vulnerabilities**; all blocking in the authored CI workflow.
- Performance (measured): `routes/analyze` p50 **15.81 ms** after batching the model call
  (**9.49×**, provably lossless — 0 mismatches against the committed artifact), ~65.6 rps
  single-worker; live provider latency geocode p50 **21 ms**, route p50 **204 ms**.
- Client (browser-measured): **0.024 ms per GPS fix**, map DOM held at **258 nodes**, flat heap and
  listener count over a 300-fix soak, **0 duplicate GPS subscriptions**, **0 leaks** over 50
  sheet cycles.
- UI: rider app + 5-tab admin console verified in headless Chromium, including route-deviation
  pause (F14), the speed-aware lateral-demand note and the no-speed fallback disclosure;
  390 px rider screenshots in `docs/screenshots/`.

## Slide 16 — Preliminary results (measured only)

| Scenario | Model MAE | Baseline MAE | Winner |
|---|---|---|---|
| Clean holdout | 0.573 | 0.089 | **Baseline** |
| Degraded | 14.142 | 27.826 | Model |
| Noise @3 m | 13.247 | 33.723 | Model |
| OOD radius | 14.994 | 43.287 | Model |
| OOD type (hairpin) | 20.307 | 12.647 | **Baseline → fallback** |

- Seed-42 clean **R² 0.9948**; 5-seed clean R² **0.9975 [0.9960, 0.9990]**.
- 5-seed degraded: MAE **13.9986 [13.0437, 14.9535]**, RMSE **19.4270 [18.5491, 20.3049]**,
  **R² 0.3090 [0.2432, 0.3747]** — about a third of the variance the raw prior cannot explain, and
  nowhere near the clean number.
- Conformal coverage: seed-42 **0.8403**, 5-seed mean **0.8173 [0.787, 0.8476]** against nominal
  0.80; **OOD-type coverage drops to 0.6786**, which is disclosed, not smoothed over.
- Latency: seed-42 p50 **5.02 ms** (re-run 5.27 ms), p95 **6.62 ms**; 5-seed p95 mean
  **7.39 ms [6.93, 7.86]** — inside the 12.0 ms budget.
- Claim boundary, verbatim on the slide: *"accuracy" here means agreement with the documented
  physics reference label on held-out synthetic scenarios — it is not accident-prediction
  accuracy.*

## Slide 17 — Evaluation strategy

- **Monotonicity gate**: score must not fall as radius shrinks or speed rises — passed on 5/5 seeds
  (40 radius points, 20 speed points per candidate).
- **Noise sweep** 0→20 m and **missing-feature sweep** 0→1.0: the model is checked where the
  baseline is known to break; ML wins from 3 m upward (13.247 vs 33.723).
- **OOD slices**: unseen scenario type (hairpin, 140 rows) and an unseen radius band
  (300–700 m, 102 rows) — the hairpin loss is a *reported result*, not a failure hidden by tuning.
- **5 data-seed re-training** with mean ± 95 % CI on every headline; per-seed values published in
  `multi_seed_metrics.json`.
- **Leakage audit** (0 overlap), **latency budget** (p95 ≤ 12.0 ms), **coverage** (empirical vs
  nominal), and — new this review — a **served-output audit** (`ml/fallback_audit.py`) that
  measures what the guarded runtime actually emits instead of only the raw model.

## Slide 18 — Current status table

| Area | Completed | Tested | In progress | Yet to start |
|---|---|---|---|---|
| Geometry / baseline / aggregation / advisory | ● | ● (15 + 10 + 10 + 6) | | |
| Security, auth, hazards, admin, privacy | ● | ● (`test_security` 15, `test_api` 18) | | |
| GACE training + evaluation | ● | ● (5-seed, leakage, monotonic, latency) | | |
| Runtime integration + fallback | ● | ● (`test_model` 13, `test_fallback_audit` 4) | | |
| Rider UI + staged alerts + settings | ● | ● (31 JS + 17 E2E) | responsive matrix beyond 390 px | |
| Route analysis + providers (live) | ● | ● (mock in CI; `live` opt-in scripts) | | in-suite `live` pytest |
| Performance | ● | ● (server + client + live provider) | multi-worker variant | |
| Docs / references / review pack | ● | ● (11 verified, 2 publisher re-checks) | | |
| Deployment | ● (Dockerfile, CI workflow, runbook authored) | | | `docker build` run (deferred by student), hosted CI run |
| Known-issue #12: sub-25 m radii from bunched OSM vertices | | | ● documented with numbers | fix (needs a labelled decision) |

- Say plainly: nothing in the "Yet to start" column is claimed as done anywhere in the repo, and
  `docker build` was deferred by request, not passed.

## Slide 19 — Remaining work and timeline

- **Deployment proof**: build the image on a live Docker engine and let the authored GitHub-Actions
  workflow run once on a hosted runner (locally unverifiable).
- **Fallback quality**: the guard's precision is low where the model wins (0.2045 degraded,
  0.029 OOD-radius) — the next research step is a *better* trigger (e.g. band-width or OOD
  features), not a retuned threshold, and it must be chosen on validation and re-tested on the
  held-out split.
- **KNOWN_ISSUES #12**: 84 of 987 real-route sections report radii under 25 m (smallest 3.96 m ≈
  5.0 g at 50 km/h) and **all 84 are banded `high`** (58.7 % of high-band sections) — a
  minimum-radius / vertex-spacing policy is a labelled decision, deliberately not made from a
  plausibility probe.
- **Coverage**: an in-suite `live`-labelled provider test, multi-worker throughput, responsive
  screenshots beyond 390 px, and a physical-device GPS run.
- Indicative order: labelled-radius decision → fallback trigger → hosted CI + image build → device
  and live-evidence coverage. No dates are claimed.

## Slide 20 — Expected outcome

- A **defensible** map-only geometry advisory: transparent baseline first, ML only where it earns
  its keep, uncertainty surfaced, and a refusal path when evidence is thin.
- Real-world accuracy is stated as **"to be evaluated"** — the project makes no claim it cannot
  support, and that restraint is presented as a research contribution in itself.
- New this cycle: a **live plausibility check** on 5 real Hyderabad/Odisha origin-destination pairs
  (8 route records, 1247 sections, 1176 scored = **94.31 %**, coverage **0.9568–0.9831**, 162
  advisories, fallback **15.48 %** of scored sections) — labelled `live`, opt-in, **not an accuracy
  test**.
- That same probe is what surfaced KNOWN_ISSUES #12, which is the honest way to present it: the
  check found a defect, and the defect is on the slide.
- Launch blocker named: public OSRM/Nominatim demo limits require self-hosting or a commercial
  routing service before any public use.

## Slide 21 — References

- **11 numbered verified sources**, each with URL and access date (2026-10-17), in
  [REFERENCES_VERIFIED.md](REFERENCES_VERIFIED.md).
- **10 versioned tool entries** (frameworks, libraries, services) with their own citations —
  total counts on this slide must match that file exactly.
- Two publisher re-checks dated **2026-10-18** (FHWA-HRT-13-077 at ROSA P; Nadimi 2025 via
  Crossref), with the Nature full-text caveat stated.
- Third-party data attribution: map data © OpenStreetMap contributors (ODbL); routing by OSRM;
  geocoding by Nominatim.
- One plan-named source could not be independently confirmed and is **flagged as unconfirmed** in
  `REFERENCES_VERIFIED.md` rather than cited as fact.

---

## Likely viva questions and honest answers

1. **"Where does your model lose to the baseline?"** Two places, both reported. Clean input:
   baseline 0.089 vs model 0.573 MAE — clean labels *are* the physics formula, so a residual model
   can only add error. Hairpin OOD-type: model 20.307 vs baseline 12.647, which is why the runtime
   detects the disagreement and serves the baseline (served MAE 12.593 there).
2. **"What does your accuracy number actually mean?"** Agreement with the documented physics
   reference label (`label_v1`) on held-out **synthetic** scenarios. It is not agreement with
   observed crashes, observed rider behaviour, or any real-world ground truth. R² 0.9948 (seed 42)
   on clean synthetic input, and only 0.3090 [0.2432, 0.3747] on degraded input across 5 seeds.
3. **"Why no accident-prediction claims?"** Rule R4, and the literature supports it: no verified
   source establishes accident-probability prediction from static mapped geometry. The word
   "probability" of an accident never appears as an output; `test_compliance.py` greps for banned
   affirmatives ("safe route", "prevents accidents", "validated risk") and asserts that "accident
   probability" only occurs in negations.
4. **"Your ML beats the baseline on degraded — so ship the ML?"** Not that simple. The
   disagreement guard fires on 61.1 % of degraded sections and the **served** MAE there is 27.252,
   close to the baseline's 27.826, versus 14.142 for the raw model (fallback precision 0.2045). So
   the improvement describes the model, not the guarded output. That is in `fallback_audit.json`,
   `GEOMETRY_ML_LIMITATIONS.md` and FINAL_REPORT §8.
5. **"Did you tune the threshold after seeing the results?"** No —
   `fallback_audit.json` records `threshold_retuned: false`. A calibration-split-only sweep
   (20 → served 29.950, 30 → 27.099, 50 → 19.798, no guard → 14.761) is reported for transparency,
   and changing the production threshold from it would require selection on validation plus a fresh
   held-out test — which was not done, so the threshold stayed at 20.0.
6. **"Why synthetic data? Is the result meaningful?"** No real crash/telemetry dataset was
   available at student scale, and claiming one would be fabrication. Synthetic data still gives a
   meaningful *mechanism* result: it shows exactly where physics-first + residual + conformal
   widening helps (noise, degraded, OOD radius) and where it does not (unseen curve type).
7. **"How do you know there's no leakage?"** Scenario-group splits, audited: train/test scenario
   overlap 0 on every seed (`max_leakage_overlap: 0`), row counts published in
   `dataset_manifest.json`, and model selection used train-only grouped CV.
8. **"Why is your coverage above nominal?"** Split-conformal on a residual band is conservative;
   seed-42 empirical 0.8403 against nominal 0.80 (5-seed mean 0.8173 [0.787, 0.8476]). The
   **failure** direction is the honest one to report: on the OOD-type slice coverage drops to
   0.6786, so the band under-covers exactly where the model is weakest.
9. **"What stops your app from telling a rider a bad road is fine?"** Coverage-aware aggregation:
   if too little of the route can be scored, the API returns `insufficient_evidence` instead of a
   number, and `test_aggregation.py` asserts that missing geometry is never treated as a zero
   score. Plus `insufficient_evidence` / `provider_unavailable` never invent a route (asserted in
   `test_api_routes.py` and in E2E).
10. **"You use GPS — what about privacy?"** No persistent precise-movement trail is stored
    server-side; position is used for the request; accounts can be deleted; no tokens are placed in
    the DOM or logs (CSRF is header-based with an HttpOnly SameSite cookie). See
    `SECURITY_AND_PRIVACY.md`.
11. **"Is your CI green?"** The workflow is authored (lint → types → audit → pytest → compliance →
    frontend → e2e → build) with those gates blocking, but it has **not run on a hosted runner**,
    and `docker build` was **deferred by request** — both are recorded as open in
    `LOOP_STATE.md`, not as passing.
12. **"What did the real-route check prove?"** Only plausibility: coverage 0.9568–0.9831 and
    median radii 227–623 m look believable, and the guard fires on 15.48 % of real scored sections
    versus 61–89 % on synthetic degraded slices. It also found the sub-25 m radius artefact
    (84 sections, all banded `high`, smallest 3.96 m ≈ 5.0 g at 50 km/h) — so it is reported as a
    defect discovery, with **no accuracy claim attached**.
13. **"Why vanilla JS instead of React?"** Auditability and zero build step on a phone-class
    device; the alert planner is kept as pure functions (`alerts.js`) so it is unit-testable with
    `node --test` without a browser, which is how the 31 JS cases run in CI.
14. **"What is the single biggest weakness?"** The claim ceiling: everything is synthetic, so
    generalisation to Indian road geometry is unproven, and OSM geometry quality bounds the score.
    Say it before the examiner finds it.

---

## Numbers → command

So any figure on any slide can be produced live in the viva:

| Number | Command | Artifact |
|---|---|---|
| 112 / 31 / 17 tests | `python -m pytest -q`, `node --test "tests/js/**/*.test.js"`, `npx playwright test` | terminal |
| All MAE / R² / coverage / latency | `python -m ml.train --seed 42 --per-type 140` | `ml/artifacts/eval_results.json` |
| 5-seed means + 95 % CIs (incl. degraded R² 0.3090) | `python -m ml.evaluate_seeds` | `ml/artifacts/multi_seed_metrics.json` |
| Fallback rates + served MAE | `python -m ml.fallback_audit` | `ml/artifacts/fallback_audit.json` |
| Server latency / throughput | `python scripts/bench_server.py` | `docs/perf_server_bench.json` |
| Live provider latency (labelled `live`) | `python scripts/bench_provider_live.py --confirm` | `docs/perf_provider_live.json` |
| Real-route plausibility (labelled `live`) | `python scripts/real_route_check.py --confirm` | `docs/real_route_check.json` |
| 390 px rider screenshots | `npx playwright test tests/e2e/screenshots.spec.js` | `docs/screenshots/` |
| Ruff / mypy / pip-audit | `python -m ruff check app ml scripts tests`, `python -m mypy app ml scripts --ignore-missing-imports`, `python -m pip_audit -r requirements.txt` | terminal |

## Presentation rules for this deck

- Never write "safety score", "risk of accident" or "safe route" on a slide — the same wording
  rules the code obeys.
- Every metric slide carries the word **synthetic** next to the accuracy figure.
- Label `mock` vs `live` on any screenshot or latency figure, exactly as the repo does. The three
  390 px rider screenshots are **`mock`** (mocked API + stubbed tiles); the route table is
  **`live`**.
- `REQUIRES STUDENT INPUT` rows (slides 1 and 3) must be filled by the student; nothing in this
  outline invents them.

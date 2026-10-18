# FINAL REPORT — RoadGuard AI

> Format follows [ROADGUARD_FINAL_MASTER_PLAN.md](ROADGUARD_FINAL_MASTER_PLAN.md) §15. Every
> number below is a **measured** value reproduced on the dev machine (Python 3.10.10,
> Node 24.13.1, Windows). Where a check did **not** run, it is stated as not-run — never
> asserted. Mocked vs live tests are labelled separately. **Accident prediction is out of
> scope by design (rule R4)**; "accuracy" here means agreement with the documented physics
> reference label on held-out synthetic scenarios, nothing else.

## 1. Executive summary
RoadGuard AI is a mobile-first, real-time **road-geometry challenge advisory** for riders. It
takes an OSRM route, extracts curve/straight sections from the mapped polyline, and scores each
with a transparent physics baseline (`v²/R`) plus a split-conformal **Geometry-Aware Challenge
Estimator (GACE)** that reports an uncertainty band and falls back to the baseline on
disagreement/out-of-calibration regions. The rider gets a 0–100 "geometry challenge" band and
staged (visual/vibration/audio) advisories before sharp curves. It is **advisory only** — it does
not, and never claims to, predict accidents. The repository is FastAPI + Pydantic v2 + SQLite
(WAL) on the backend, a no-build vanilla ES-module + Leaflet frontend, and a scikit-learn/joblib
ML pipeline trained on **synthetic data only**. All locally-verifiable exit gates are green;
`docker build` is deferred by student request and GitHub-Actions execution is not reproducible
locally (see §15–16).

## 2. Architecture
Three layers behind one ASGI app ([ARCHITECTURE.md](ARCHITECTURE.md)):
- **Providers** (`app/providers.py`): Nominatim geocoding + OSRM routing via `httpx`, bounded
  LRU cache (limit 256), courtesy throttle 1.1 s, typed errors. Injected via a dependency seam
  (`get_services(request) → request.app.state.services`) so tests swap in a mock client.
- **Analysis core** (`app/geo.py`, `app/baseline.py`, `app/model.py`, `app/analysis.py`,
  `app/aggregation.py`, `app/advisory.py`): geometry validation → section extraction → physics
  baseline → GACE (conformal) → route aggregation with coverage → advisory scheduling.
- **API/infra** (`app/api.py`, `app/main.py`, `app/security.py`, `app/hazards.py`,
  `app/db.py`, `app/schemas.py`): REST v1, auth/session, rate limits, audit, community hazards,
  admin. Security headers middleware, CSP, `X-RoadGuard-Client` CSRF-by-header on writes.

## 3. Research findings + verified references
11 numbered sources verified with URL + access date 2026-10-17
([REFERENCES_VERIFIED.md](REFERENCES_VERIFIED.md),
[RESEARCH_LITERATURE_REVIEW.md](RESEARCH_LITERATURE_REVIEW.md)): FHWA-HRT-13-077, Nadimi 2025,
telematics surrogate-measure / harsh-event papers, proactive curve-assessment papers, OSM/ODbL,
OSRM docs, MDN Geolocation, map-matching, synthetic-data limits, spatial CV/leakage, uncertainty
communication, interpretable tabular ML. Two of them were **re-checked at the publisher on
2026-10-18**: FHWA-HRT-13-077 against the ROSA P / National Transportation Library record
(title, report number, Bauer & Harwood et al., 2014-01-01) and Nadimi 2025 against the Crossref
DOI record (10.1038/s41598-025-97384-7, *Scientific Reports*, 2025-04-11, Nadimi/Fathipour/
Sheykhfard — the full title is "…surrogate safety measures and machine learning"); the nature.com
HTML page itself could not be machine-read here (bot interstitial), which is recorded in the file.
**No paper establishes accident-probability prediction
for mapped road geometry on Indian roads** — this bounds what RoadGuard may claim.

## 4. Gap + contribution
Gap: existing work models accident *surrogates* from telematics/GPS streams, not from **static
mapped geometry** with honest uncertainty. Contribution: a transparent, calibrated **geometry
challenge indicator** (`v²/R` physics prior + monotonic conformal residual) with disagreement
fallback, coverage-aware aggregation, and advisory-first UX that refuses to over-claim. Design
in [GEOMETRY_ML_DESIGN.md](GEOMETRY_ML_DESIGN.md); limits in
[GEOMETRY_ML_LIMITATIONS.md](GEOMETRY_ML_LIMITATIONS.md), [LIMITATIONS.md](LIMITATIONS.md).

## 5. Implemented modules
Geometry (`test_geo` 15), baseline (`test_baseline` 10), aggregation (`test_aggregation` 10),
advisory (`test_advisory` 6), security/auth (`test_security` 15), model/GACE runtime
(`test_model` 13 incl. batch-vs-per-section equivalence), API (`test_api` 18, `test_api_routes`
6), staged-alert + speed-advisory + deviation wiring (`test_web_alerts` 7), disagreement-fallback
audit (`test_fallback_audit` 4), compliance (`test_compliance` 7), DB backup/restore
(`test_db_backup` 1). Frontend: rider app (`app/web/app.js`) + admin console
(`admin.js`) + pure alert planner and speed layer (`alerts.js`, `settings.js`).

## 6. Removed modules + reasons
No accident-probability or "safety-score" module was ever built (R4). Raw internal scores are not
shown to riders (only bands + advisory text). Dead/duplicate code from the prior-project audit
(`PROJECT_AUDIT.md`) was **not reused** — RoadGuard was built fresh in `D:\FP_ROADGUARD`.

## 7. Dataset + synthetic methodology
Synthetic scenarios generated by `ml/` (generator → degradation pipeline), `per_type = 140`,
seed 42 production; labels = the documented physics reference (`label_v1`) with noise/degradation
variants. **No real accident or telematics data is used or claimed.** Reproduced via
`python -m ml.train --seed 42 --per-type 140` then `python -m ml.evaluate_seeds` (5 seeds 42–46,
writes `multi_seed_metrics.json`) — see `ml/artifacts/REPRODUCE.md`; manifest `dataset_manifest.json`.

## 8. Baseline vs model evaluation (the honest headline)
`eval_results.json` + `multi_seed_metrics.json` (5 seeds: 42–46, seed 42 = production):

| Scenario | Model MAE | Baseline MAE | ML − baseline | Who wins |
|---|---|---|---|---|
| Clean holdout | 0.573 | 0.089 | **+0.484** | **Baseline** (clean labels are near-exact physics) |
| Degraded | 14.142 | 27.826 | −13.684 | Model |
| Noise sweep @3.0 | 13.247 | 33.723 | −20.476 | Model |
| OOD radius | 14.994 | 43.287 | −28.293 | Model |
| OOD type (hairpin) | 20.307 | 12.647 | **+7.660** | **Baseline → disagreement fallback** |

Seed-42 clean **R² 0.9948** = agreement with the physics reference label on held-out synthetic
scenarios — **not** accident-prediction accuracy. 5-seed clean R² **mean 0.9975 (CI 0.996–0.999)**.
Across all 5 seeds the model beats the baseline on degraded / noise / OOD-radius and loses on the
hairpin OOD-type case — so the runtime **detects that disagreement (threshold 20.0) and serves the
baseline** there. The "ML must beat baseline on the noise test" justification gate passes (ML<baseline
for noise ≥ 3.0). Monotonic grid invariants pass on every seed (`all_monotonic_pass = true`);
leakage overlap = 0 on every seed (`max_leakage_overlap = 0`).

**What the guard actually serves** (`ml/artifacts/fallback_audit.json`, seed-42 production
artifact, `threshold_retuned: false` — the threshold was **not** changed after seeing these
results; the sweep below ran on the calibration split only):

| Slice | n | fallback rate | served MAE | model-only MAE | baseline MAE |
|---|---|---|---|---|---|
| Clean | 156 | 0.64 % | 0.445 | 0.573 | 0.089 |
| Degraded | 144 | 61.11 % | **27.252** | 14.142 | 27.826 |
| OOD radius | 102 | 67.65 % | **42.394** | 14.994 | 43.287 |
| OOD type (hairpin) | 140 | 66.43 % | **12.593** | 20.307 | 12.647 |
| Noise @3 m | 156 | 72.44 % | **32.960** | 13.247 | 33.723 |

Read honestly: the guard **helps only where the model is known to lose** (OOD type: served
12.593 vs model-only 20.307, and 67/93 fallbacks were genuinely closer to the label), but on
degraded / noise / OOD-radius it fires on 61–72 % of sections and pulls served error back to
*baseline* level (degraded 27.252 vs model 14.142), because a large model-vs-baseline gap is a
poor proxy for "the model is wrong there" (fallback precision 0.2045 degraded, 0.029 OOD-radius).
So the "27.826 → 14.142" degraded improvement describes the **model**, not the **guarded
output** a rider receives. Full write-up: [GEOMETRY_ML_LIMITATIONS.md](GEOMETRY_ML_LIMITATIONS.md).

**Degraded-slice generalisation over 5 seeds** (`multi_seed_metrics.json`): MAE **13.9986
(CI 13.0437–14.9535)**, RMSE **19.4270 (CI 18.5491–20.3049)**, **R² 0.3090 (CI 0.2432–0.3747)**
against baseline MAE 28.2730 (CI 27.3380–29.2080). An R² of ≈0.31 on degraded input is the
honest statement of the situation: the corrected model explains about a third of the variance
the raw physics prior cannot, and it is nowhere near the clean-input R² of 0.9975.

## 9. Actual metrics + interpretation
- Split-conformal coverage: nominal **0.80**; empirical seed-42 **0.8403**; 5-seed mean **0.8173
  (CI 0.787–0.8476)** — slightly above nominal, as expected for a conservative residual conformal
  band.
- Inference latency (model scoring, wall-clock on the dev machine): **re-measured 2026-10-18**
  when the 5-seed run was re-executed for the degraded R²/CI figures — seed-42 p50 **5.27 ms**,
  p95 **8.29 ms**; 5-seed p50 mean **5.2124 ms (CI 5.1723–5.2524)**, p95 mean **7.3937 ms
  (CI 6.9307–7.8566)** — within the 12.0 ms budget (`LATENCY_BUDGET_P95_MS`). The previously
  committed run read p50 6.2159 ms / p95 8.8547 ms; the shift is machine load, not a code change
  (every deterministic metric in that re-run reproduced exactly).
- Constants: `BASELINE_VERSION=physics_v2r_v1`, `LABEL_VERSION=label_v1`, `NOMINAL_COVERAGE=0.80`,
  `DISAGREEMENT_THRESHOLD=20.0`, `CACHE_LIMIT=256`.
Model card: `ml/artifacts/MODEL_CARD.md`.

## 10. API + DB summary
REST v1 under `/api/v1` (`openapi.json` via FastAPI): geocode, `routes/analyze`, hazards
(submit/list/vote), auth (register/login/me/logout/delete), admin (overview/hazards/users/audit/
diagnostics/moderate). Typed error envelope `{"error":{code,message,details}}` with codes in
`app/errors.py` (`invalid_input`, `insufficient_evidence`, `provider_unavailable`,
`model_unavailable`, `auth_failure`, `authz_failure`, `rate_limited`, `not_found`). SQLite WAL;
backup→restore tested to lose 0 rows + `PRAGMA integrity_check ok`. Full spec in
[API_SPECIFICATION.md](API_SPECIFICATION.md), [DATABASE_DESIGN.md](DATABASE_DESIGN.md).

## 11. UI summary
Rider: map-first, mobile-first, GPS chip state machine, destination search, route card (distance/
provider-ETA/band/coverage), staged advisories with visual+vibration+audio fallback, reduced-motion
support, settings persisted to `localStorage`, assertive live-region escalation on high-band
"in-curve". The advisory card is **speed-aware**: when the device reports a ground speed it states
the `v²/R` lateral demand in g and how many times that is of the band the score was computed at
("At ~90 km/h (GPS) this 38 m curve needs 1.68 g lateral — 4.00× the 0.42 g scored band. Geometry
indicator, not an accident probability."); when it does not, the card **discloses that the assumed
band was kept** rather than inventing a number. It never outputs a target/allowed speed. Leaving the
analysed polyline pauses advisories with an off-route note (accuracy-scaled threshold, two-fix
latch). Admin: 5-tab console (overview/hazards/users/audit/system) with moderation dialog and
role gating. Both are **no-build ES modules**. Standard wording enforced (see §12). Three 390 px
rider captures (mock-labelled) are in [docs/screenshots/](screenshots/).

## 12. Security / privacy checks
PBKDF2 password hashing, HttpOnly+SameSite cookies, server-side authz (role gates), input
validation + coordinate bounds, `X-RoadGuard-Client` header on writes, rate limiting (429 +
Retry-After), safe error surfaces, secrets via env only. `pip-audit` → **0 known
vulnerabilities**. Static secret-scan + R2/R4/R8/R10 compliance grep run in `test_compliance` (7).
Privacy: no persistent precise movement trail server-side, account deletion, no tokens in DOM/logs
([SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)). Wording audit confirms "accident
probability" appears only in negations and never "safe route".

## 13. Test commands + results
```
python -m pytest -q                 → 112 passed, 1 warning (Starlette/TestClient deprecation)
node --test "tests/js/**/*.test.js" → tests 31, pass 31, fail 0
npx playwright test                 → 17 passed (10 rider + 5 admin + 2 screenshot) — all providers MOCKED (`mock`)
python -m ruff check app ml scripts tests                      → All checks passed!
python -m mypy app ml scripts --ignore-missing-imports         → Success: no issues found in 31 source files
python -m pip_audit -r requirements.txt                        → No known vulnerabilities found
python -m pytest tests/test_compliance.py -q                   → 7 passed
python scripts/bench_server.py                                 → docs/perf_server_bench.json (offline)
python scripts/bench_provider_live.py --confirm                → docs/perf_provider_live.json (LIVE, opt-in)
python scripts/real_route_check.py --confirm                   → docs/real_route_check.json (LIVE, opt-in, plausibility only)
python -m ml.fallback_audit                                    → ml/artifacts/fallback_audit.json (offline)
```
Which of these ran **in this session** (verbatim output in
[LOOP_STATE.md](LOOP_STATE.md) → Gate log): pytest, `node --test`, Playwright, ruff, mypy,
pip-audit, the compliance subset, `ml.fallback_audit`, and `real_route_check.py --confirm`
(three times, identical aggregates). The two `bench_*` scripts were **not** re-run here; their
figures are carried from the earlier recorded runs in `docs/perf_*.json`.
Playwright E2E (`tests/e2e`) boots the real ASGI app via the config `webServer`; every `/api/v1/*`
response is mocked and labelled `mock`; OSM tiles stubbed. Rider: startup (no JS errors),
search→route (+ client header `web` asserted on the POST), nav lifecycle → trip summary, live-GPS
→ staged advisory cue with assertive escalation, hazard submit (unverified toast),
insufficient-evidence (never invents a route), provider-failure (graceful unavailable), **route deviation
latch + recovery (F14)**, **speed-aware lateral-demand note when the device reports a speed**, and
**the disclosed fallback when it does not**. Admin:
login gate, role-denied gate, tab switch + hazards list, moderation posts `{action:"verify", note}`
+ `verified.` toast, system/diagnostics render. Detail: [TESTING_AND_EVALUATION.md](TESTING_AND_EVALUATION.md).

## 14. Performance (before → after, measured)
- `routes/analyze` endpoint (provider mocked, 2 routes): p50 **15.81 ms**, p95 **17.25 ms** (was
  ~90 ms before batching). Throughput single-worker **65.6 / 67.2 / 68.8 rps** at concurrency
  1 / 5 / 20 — flat/rising ⇒ CPU-bound; recommend `uvicorn --workers N`.
- Model scoring optimisation (Phase 10): per-section loop p50 **41.01 ms** → single batch p50
  **4.32 ms** = **9.49×**, **provably lossless** (verified field-for-field vs the committed
  `model.joblib`; guarded by a row-order-sensitive test).
- Provider cache bounded at 256 entries (cold call not cached, warm identical call cached).
- Live provider latency (labelled **live**, opt-in script): geocode p50 **21 ms**, route p50
  **204 ms**.
- Client (browser): boot heap 5.04 MB, DOMContentLoaded 241 ms / load 269 ms, Leaflet canvas keeps
  the map DOM at **258 nodes**, **0 duplicate GPS subscribers**, **0.024 ms/fix**, flat heap +
  listener count, 50-cycle soak → **0 leak**, exactly one expected signed-out 401 on `/auth/me`.
Full detail: [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md).

## 15. Known limitations
Synthetic-data-only training (no real road/accident labels); clean-input physics baseline is
**more accurate** than the model (it only earns its keep under degradation/noise/OOD-radius);
**and the runtime disagreement guard largely gives that advantage back on degraded input**
(served degraded MAE 27.252 vs model-only 14.142, §8);
hairpin OOD-type triggers baseline fallback; public OSRM/Nominatim demo limits mean **self-host or
commercial routing is required before any public launch**; OSM geometry quality bounds the score;
advisory is geometry-only (no surface condition, traffic, weather). See
[LIMITATIONS.md](LIMITATIONS.md), [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

**Live plausibility check on real routes (labelled `live`, opt-in, not CI).** Five real
Hyderabad pairs were pushed through the actual production path
([REAL_ROUTE_CHECK.md](REAL_ROUTE_CHECK.md), `docs/real_route_check.json`): 5/5 geocoded and
routed, **8 route records, 0 validation failures**, 1247 sections with 94.3 % scored, coverage
95.7–98.3 %, all eight route-level bands `low`, and the disagreement guard fired on
**182/1176 scored sections (15.5 %)** — far below the 61–72 % it reaches on the synthetic
degraded slices. It also exposed the pipeline's weakest point on real data: **84 sections with
radius < 25 m (15 under 10 m, minimum 3.96 m ≈ 5.0 g at the assumed 50 km/h band), and every
one of those 84 was banded `high`** — i.e. 58.7 % of high-band sections on real geometry sit in
an implausible tail produced by bunched OSRM vertices (all 8 records flagged `highly uneven
point spacing`). **This is a plausibility check only: no ground truth exists for these routes,
so no accuracy claim is made.** No minimum-radius floor was added, because that is a label
decision requiring a re-train/re-eval cycle; it is recorded as KNOWN_ISSUES #12.

## 16. Remaining work / exit-gate status
§14 gates, honestly:
- [x] Gates 0–12 green with evidence (this report + per-phase docs).
- [~] **Gate 13 Deployment partially NOT proven here:** `docker build` **deferred by student
  request** (Docker Desktop installed, engine not run); GitHub-Actions workflow authored
  (lint→types→audit→pytest→compliance→frontend→e2e→build) but **not executed on a runner**;
  clean-machine deploy from README reproduced only on the dev machine, not a fresh host.
- [x] Rules R1–R11: R2/R4/R8/R10 automated in `test_compliance` (7 green); rest documented, no
  accident-prediction claim anywhere.
- [x] ML pipeline present, reproducible, honestly evaluated; no accident claim.
- [x] Full test suite green (112 backend + 31 JS-unit + 17 Playwright), or documented: none failing.
- [~] "Clean-machine deploy works; CI green": commands verified locally except `docker build`
  (deferred) and runner execution (impossible here) — documented, not asserted.
- [x] Docs match code; references verified (11 numbered, dated; two publisher re-checks
  2026-10-18).
- [x] Version control: `main` with a first commit + small per-task commits; `.gitignore` covers
  env/DB/secrets/venv/node_modules/test-results/scratch artifacts. **No remote configured,
  nothing pushed** — that step is the student's own (README → Version control).
- [x] Review 2 checklist complete except `REQUIRES STUDENT INPUT` rows (kept blank by design).
- [~] Still open by choice/absence of environment: an in-suite `live`-labelled provider pytest
  (kept out of CI — network egress), `pyright` (mypy is authoritative and clean), multi-worker +
  CI-Playwright perf variants, admin-console responsive screenshot matrix at 6 widths.

## 17. Review 2 checklist
See [REVIEW_2_PROJECT_SPECIFICATION.md](REVIEW_2_PROJECT_SPECIFICATION.md) (the 21-row mapping of
each slide to its evidence source) and
[REVIEW_2_SLIDE_OUTLINE.md](REVIEW_2_SLIDE_OUTLINE.md) (the slide-by-slide talking points: 3–5
measured bullets per slide, a Completed/Tested/In-progress/Yet-to-start status table, a
**Numbers → command** table so any figure can be reproduced in the viva, and a 14-question honest
viva Q&A). Title / team / supervisor / Review-1-feedback slides are marked
`REQUIRES STUDENT INPUT` and left blank; the deck **file** itself is still the student's to build.

## 18. Exact local run commands
```
cp .env.example .env
pip install -r requirements.txt
uvicorn app.main:app --reload      # rider at /, admin at /admin, docs at /docs
npm ci && npx playwright install chromium
npx playwright test                # E2E (mock providers)
python scripts/create_admin.py     # bootstrap an admin (see MANUAL_RUNBOOK.md)
```
Docker (deferred here): `docker build -t roadguard:ci .` on a machine with a live daemon.
Full operations in [MANUAL_RUNBOOK.md](MANUAL_RUNBOOK.md).

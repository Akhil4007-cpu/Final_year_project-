# LOOP_STATE

Running state of the RoadGuard build loop. Updated as of this session. **All locally-verifiable
exit gates (master plan §14) are now green** and the §15 Final Report is written
([FINAL_REPORT.md](FINAL_REPORT.md)). The only §14 items not marked done require resources this
environment does not have or were **deferred by student request**: `docker build` verification
(student: "no docker needed as of now"), a real GitHub-Actions runner execution, and a fresh
clean-machine deploy. Version control is now in use: the tree was committed starting
2026-10-17 (one commit per task, nothing pushed — see the Gate log below and
FINAL_REPORT §16).

## Gate status

| Gate | State | Notes |
|---|---|---|
| 0 Audit | **Closed** | `PROJECT_AUDIT.md` written; R2/R8/R4 confirmed by tests. **Restore-verification now evidenced** by `tests/test_db_backup.py` (0 rows lost, integrity_check ok). |
| 1 Research | **Done (verified pass)** | 11 numbered sources verified with URL + access date 2026-10-17; RESEARCH_LITERATURE_REVIEW, RESEARCH_GAP_AND_CONTRIBUTION, REFERENCES_VERIFIED written. One plan-named source (a second "Nadimi 2025" telematics paper) **could not** be independently confirmed and is flagged, not fabricated. **2026-10-18 publisher re-checks:** FHWA-HRT-13-077 confirmed on ROSA P/NTL (title, report no., Bauer & Harwood, 2014-01-01); Nadimi 2025 confirmed via the Crossref DOI record (10.1038/s41598-025-97384-7, *Scientific Reports*, 2025-04-11, Nadimi/Fathipour/Sheykhfard) — the nature.com HTML page could not be machine-read here (bot interstitial), which is stated in the file rather than glossed over. |
| 2 Contracts | Done | ARCHITECTURE / API_SPECIFICATION (live OpenAPI) / DATABASE_DESIGN written. OpenAPI is app-generated. |
| 3 UI/Auth/Nav shell | Mostly done | Implemented; authz tested. **Staged, capability-aware alerts added** (`alerts.js` pure planner + `settings.js` localStorage prefs): visual/audio/vibrate with iOS (no `navigator.vibrate`) and reduced-motion fallbacks, sound gated behind a user gesture, `role="alert"` assertive region for high-band in-curve. **Browser-verified this session** (server on :8171): settings sheet opens, per-channel toggles persist across reload, capability note renders, assertive live region present, no JS errors (only the expected 401 on `/auth/me`). Alert logic unit-tested (31 `node --test` cases) + static wiring smoke tests (`tests/test_web_alerts.py`, 7). **The nav FSM, layout, cue playback and deviation/speed paths are now automated** by the 10 rider Playwright cases in `tests/e2e/rider.spec.js` (this row previously said they were not — stale). |
| 4 Geometry | Done | 15 geo tests, analytical cases pass. |
| 5 Route-level | Done | 10 aggregation tests. |
| 6 Baseline | Done | 10 baseline tests; measured clean+degraded table. |
| 7 ML mandatory | **Redesigned + retested (multi-seed verified)** | GACE = `physics_v2r_v1` **prior + monotonic boosted residual** (feature 22 = `physics_prior`); selection by **train-only grouped CV + monotonicity gate + latency budget** (random forest rejected for p95 > 12 ms); split-conformal band. Seed 42 committed artifact: clean **R² 0.9948** (MAE 0.573), degraded MAE 14.142 vs baseline 27.826, OOD-radius 14.994 vs 43.287, hairpin OOD 20.307 vs 12.647 → fallback; leakage 0; latency p50 5.02 / p95 6.62 ms. **5-data-seed run verified** (`evaluate_seeds` → `ml/artifacts/multi_seed_metrics.json`): clean R² **0.9975 [0.9960, 0.9990]** (≥0.99 met on CI lower bound), degraded MAE **13.999 [13.044, 14.954]** vs baseline 28.273 (< baseline every seed), OOD-radius reduced, hairpin → fallback every seed, coverage mean **0.8173 [0.787, 0.848]** (inside ±3pt band on the mean; per-seed 0.76–0.848 is finite-sample noise), latency p95 8.85 ms [7.15, 10.56] under budget, monotonic 5/5, leakage 0/5. **2026-10-18 re-run** of `evaluate_seeds` reproduced every deterministic per-seed metric exactly (only wall-clock latency moved: p50 mean 5.2124 [5.1723, 5.2524], p95 mean 7.3937 [6.9307, 7.8566]) and added the Review-2 request: **degraded RMSE 19.4270 [18.5491, 20.3049] and degraded R² 0.3090 [0.2432, 0.3747]** over the same 5 seeds — i.e. the corrected model explains ≈31 % of degraded variance vs 99.75 % clean. **Served-output audit** (`ml/fallback_audit.py` → `ml/artifacts/fallback_audit.json`, threshold NOT retuned, sweep on the calibration split only): fallback fires on 61.1 % degraded / 67.7 % OOD-radius / 66.4 % OOD-type / 72.4 % noise@3 m and pulls served MAE back to baseline level except on unseen curve type, where it genuinely helps (12.593 served vs 20.307 model-only). Pinned by `tests/test_fallback_audit.py` (4). |
| 8 ML integration | Done | startup load, uncertainty, disagreement fallback, admin status, provenance tags, import-graph test. `app/model.py` adds the prior back for `prediction_mode=…residual`; legacy artifacts still load. New residual runtime covered by `tests/test_model.py` (incl. a batch-vs-per-section equivalence guard); the scored route path is now also covered end-to-end by `tests/test_api_routes.py`. |
| 9 Hazards/admin/privacy/security | Mostly done | lifecycle/authz/secret-scan/deletion tested; **`pip-audit` now RUN clean** (0 known vulns, live DB). Graceful-failure provider mocks now in CI (`tests/test_api_routes.py`); remaining: in-suite `live`-labelled pytest (network-gated). |
| 10 Performance | **Measured + optimised** | server path batched (`score_sections`): analyze p50 ~90→16 ms, single-worker ~8→66 rps, **provably lossless** (0 mismatches on real model + `test_score_sections_batch_matches_per_section`); bounded provider cache (cold→warm skip re-fetch, ≤256 entries); **live** provider p50 geocode 21 ms / route 204 ms; **client** 0.024 ms/fix, flat heap + 0 listener growth over soak, 0 duplicate GPS subs (browser-verified). Open: multi-worker + CI-Playwright perf variants. Evidence: `PERFORMANCE_REPORT.md`, `docs/perf_server_bench.json`, `docs/perf_provider_live.json`. |
| 11 Regression | Mostly done | **112 backend + 31 `node --test` + 17 Playwright E2E cases green (rider + admin + screenshot; E2E covers nav-FSM, **route deviation (F14)**, **speed-aware advisory note + no-speed fallback**, cue playback, trip summary, login/role gating, tab switch, moderation, insufficient-evidence + provider-failure paths, and the 390 px captures with `mock`-labelled providers; backend `tests/test_api_routes.py` covers `/routes/analyze` offline). `ruff` clean; `mypy` clean on app+ml+scripts (31 files, findings fixed in source, not suppressed); `pip-audit` clean.** Open: `pyright` (mypy is authoritative; not run) + an in-suite `live`-labelled provider pytest (network egress out of CI). |
| 11b Live plausibility (real routes) | Done (opt-in, not CI) | `scripts/real_route_check.py --confirm` → `docs/real_route_check.json` + [REAL_ROUTE_CHECK.md](REAL_ROUTE_CHECK.md): 5/5 pairs geocoded+routed, 8 route records, **0 validation failures**, 1247 sections / 94.3 % scored, coverage 95.7–98.3 %, all route bands `low`, fallback on 15.5 % of scored sections; **but 84 sections with radius <25 m (min 3.96 m ≈ 5.0 g at the assumed band), all banded `high`** → KNOWN_ISSUES #12. Three runs, identical aggregates. **Plausibility only — no accuracy claim.** |
| 12 Docs + Review 2 | Mostly done | §11 docs written; REVIEW_2_PROJECT_SPECIFICATION filled with `REQUIRES STUDENT INPUT` rows kept blank. |
| 13 Deployment | Partial | `Dockerfile` + `.dockerignore` + CI workflow + runbook authored; CI **lint/mypy/pip-audit flipped to blocking, a `frontend-test` (node) job, and a `e2e` (Playwright, Chromium, mock-labelled) job added** (build now `needs: [test, e2e]`); **`docker build` verification deferred by student request** (Docker Desktop is installed but the engine isn't running here and the student asked to skip it — KNOWN_ISSUES #11) and no GH runner has executed the workflow yet. |

Exit gates R1–R11: compliance rules R2/R4/R8/R10/R7/R3/R5 pass via `test_compliance`; R11
student-inputs marked in docs.

## Immediate next actions (ordered)

1. ~~Restore verification~~ **DONE** — `tests/test_db_backup.py` proves backup→restore
   loses 0 rows (Gate 0 closed).
2. ~~Verified research docs~~ **DONE** — 11 sources verified 2026-10-17 (Gate 1). One
   plan-named source could not be confirmed and is flagged, not invented.
3. ~~`ruff`~~ / **`mypy` / `pip-audit`** **DONE — all RUN clean.** ruff (app ml scripts
   tests), mypy 1.11.2 (app+ml+scripts, 14 real findings fixed in source → clean), pip-audit
   2.10.1 (0 known vulns). CI steps flipped to **blocking**. Only `pyright` remains unrun
   (needs an `npm` download; `mypy` covers types). See TESTING_AND_EVALUATION.
4. **Verify `docker build`** on a machine with a live Docker engine — the image was authored
   but **never built** here (Gate 13, KNOWN_ISSUES #11).
5. **Live-labelled provider tests + graceful-failure mocks** (Gate 9/11) — a re-runnable
   **live** latency benchmark now exists (`scripts/bench_provider_live.py --confirm`, numbers
   in `PERFORMANCE_REPORT.md`); **deterministic graceful-failure mocks are now PRESENT and
   in CI** (`tests/test_api_routes.py`: provider 503 → `provider_unavailable`, OSRM NoRoute →
   `insufficient_evidence`, never invents a route). Only the in-suite `live`-labelled pytest
   remains open (network-gated, so kept out of CI by design).
6. **E2E harness** — ~~frontend alert/settings logic~~ **DONE** (31 `node --test` cases in
   `tests/js`, plus `tests/test_web_alerts.py` static wiring). **Playwright nav-FSM / layout /
   cue / admin E2E now DONE**: `tests/e2e/` boots the real ASGI app and runs **17 green
   headless-Chromium cases** — rider (10): startup, search→route + client header, nav lifecycle →
   trip summary, live-GPS→staged advisory cue with assertive escalation, hazard submit,
   insufficient evidence, provider failure, **route-deviation latch + recovery**, **speed-aware
   advisory note**, **no-speed disclosure**; admin (5): login gate, role-denied gate, tab switch +
   hazards list, moderation posts `{action,note}` + toast, system/diagnostics render; screenshots
   (2): the three 390 px rider captures — all with
   **`mock`-labelled providers + stubbed tiles on every `*.tile.openstreetmap.org` subdomain**,
   deterministic and wired into CI (`e2e` job in
   `.github/workflows/ci.yml`). Only the in-suite `live`-labelled provider pytest remains open
   (network egress kept out of CI by design).
7. ~~Client performance measurement~~ **DONE** — render cost (canvas, 258 DOM nodes),
   per-fix update latency (0.024 ms), memory soak + listener growth (flat, 0 leak over a
   300-fix soak and 50 sheet cycles), 0 duplicate GPS subscriptions — all measured
   browser-side this session (Gate 10). Server side batched + ~6× faster, provably lossless.
   Remaining perf variants: multi-process load + a CI Playwright harness.
8. ~~**Review 2 deck** generated from REVIEW_2_PROJECT_SPECIFICATION~~ **Outline DONE** —
   [REVIEW_2_SLIDE_OUTLINE.md](REVIEW_2_SLIDE_OUTLINE.md) gives all 21 slides with 3–5
   measured bullets each, a Completed/Tested/In-progress/Yet-to-start status table, the
   `REQUIRES STUDENT INPUT` rows (title, team, supervisor, Review-1 feedback) and a viva Q&A
   section. The slide **file** itself is still the student's to produce.
9. ~~**Commit** the tree once the student asks~~ **DONE** — student authorised commits on
   2026-10-17; one commit per task, nothing pushed (push is the student's step).

## Remaining-work timeline (indicative, not a promise)

| Order | Work | Depends on |
|---|---|---|
| Done | Restore verification, verified research docs, static analysis + audit, client perf, E2E + unit suites, fallback audit, live plausibility probe, Review 2 outline | — |
| Next | Student inputs: title/supervisor/Review-1 feedback rows, deck build from `REVIEW_2_SLIDE_OUTLINE.md`, `git remote add` + push | student |
| Then | KNOWN_ISSUES #12 decision (minimum-radius floor / spacing gate) → re-train + re-eval | a labelled modelling decision |
| Then | `docker build` on a live engine + a real GitHub-Actions runner execution | environment |
| Later | multi-worker perf, in-suite `live`-labelled pytest, admin-console 6-width screenshot matrix | infrastructure |

## What is deliberately NOT claimed

Generalised real-world accuracy, any accident-related capability, or a "safe route" verdict —
none of those exist anywhere in the product or the docs. Clean audit, clean types and passing
Playwright E2E are **no longer** in this list: they were re-run on 2026-10-18 and are green
(gate log below). What remains genuinely unevidenced: **real riding conditions** (the live
probe is a plausibility check with no ground truth), **responsive coverage beyond 390 px**
(the three new rider captures are `mock`-provider images at one width, not the 6-width matrix
originally planned), and **a physical device's GPS** (cue playback is driven by a scripted
`geolocation` feed in headless Chromium, not by a phone). The alert **settings, persistence,
capability fallback and assertive live region were browser-verified**. See
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Gate log (actual command output, most recent first)

Full gate re-run after every task in this session. Commands are exactly as listed in README.

### TASK 5 + TASK 6 — consistency sweep + Review 2 outline (2026-10-18)

| Command | Actual output |
|---|---|
| `python -m pytest -q` | `112 passed, 1 warning in 9.70s` (warning is the `TestClient`/Starlette deprecation) |
| `node --test "tests/js/**/*.test.js"` | `tests 31 / pass 31 / fail 0` (184.9 ms) |
| `npx playwright test` | `17 passed (26.3s)` — 10 rider + 5 admin + 2 screenshot cases |
| `python -m ruff check app ml scripts tests` | `All checks passed!` |
| `python -m mypy app ml scripts --ignore-missing-imports` | `Success: no issues found in 31 source files` |
| `python -m pip_audit -r requirements.txt` | `No known vulnerabilities found` |
| `python -m pytest tests/test_compliance.py -q` | `7 passed, 1 warning in 0.07s` |
| `python -m ml.fallback_audit` | table + `wrote ml\artifacts\fallback_audit.json` (regenerated, values unchanged) |

**TASK 5 (consistency) — what was stale and is now corrected.** The drift was found by sweeping
counts and status claims, not by re-reading prose: `grep -rn "sources verified|N sources|versioned
tool entries"` → every doc now says **11 numbered sources + 10 versioned tool entries**, which
matches `REFERENCES_VERIFIED.md` exactly (verified by a Python regex count over that file → 11
numbered entries, and the Tooling
line lists FastAPI · Pydantic · Uvicorn · httpx · NumPy · scikit-learn · joblib · PyYAML · Leaflet ·
SQLite = 10). `docs/ROADGUARD_FINAL_MASTER_PLAN.md:3` path corrected earlier and §16's quoted kickoff
prompt now carries a "historical text, this build is `D:\FP_ROADGUARD`" note. README's
`ml/artifacts/REPRODUCE.md` link fixed. Publisher re-checks dated 2026-10-18 for **FHWA-HRT-13-077**
(ROSA P/NTL: title, report number, Bauer & Harwood, 2014-01-01) and **Nadimi 2025** (Crossref DOI
`10.1038/s41598-025-97384-7`, *Scientific Reports*, 2025-04-11) — with the nature.com page reported
as **not machine-readable here** (303 → bot interstitial), not glossed over.

**Two contradictions fixed rather than harmonised silently.** (1) `docs/PROJECT_AUDIT.md` (Phase-0
snapshot) claimed the Rider UI had "e2e not automated" and geocode/route-analysis needed
"add live-labelled test"; it now carries a dated **Refresh — measured 2026-10-18** table (112/31/17
tests, 0→2 commits, 5,132→6,363 Python lines, 2,800→3,296 browser-JS lines, mypy 31 files) and the
three action cells updated in place, with the Phase-0 numbers left visible as history.
(2) `KNOWN_ISSUES.md` said the four `data/ui-*.png` manual captures "should not be committed" —
`git ls-files data` shows they **are** tracked (they went in with the initial commit). The file now
states the truth (sqlite3 + `ml/artifacts_debug/` ignored and untracked; the 4 PNGs tracked) and
labels them **manual, unlabelled, un-reproducible**, distinct from the `mock`-labelled
`docs/screenshots/` set. The PNGs were **not** deleted — they are the only pre-E2E verification
evidence.

**Banned-claims string audit re-run** (product surfaces `app/ scripts/ ml/`):
`grep -rniE "safe route|prevents acc|validated risk|accident probability|safety score|risk of acc|predicts acc"`
→ **10 hits, every one the negation** "… not an accident probability" (`wc -l` on the grep = 10, and
`grep -c "not an accident probability"` on the same set = 10) in `analysis.py`, `api.py`,
`baseline.py`, `main.py`, `alerts.js`, `index.html`; **0 hits** for "safe route", "prevents
accidents", "validated risk", "safety score", "risk of acc", "predicts acc". Docs sweep: the only non-negation-shaped hits are
audit rules quoting the banned strings (`ROADGUARD_FINAL_MASTER_PLAN.md:20`) and descriptions of
*prior art* ("existing work predicts accident surrogates from telematics") — no product claim.
Speed-instruction sweep → only negations ("not a legal speed limit", "never tells the rider what
speed to ride at"), so the deck's "no target speed" statement is true of the shipped code.

**TASK 6 — written:** [REVIEW_2_SLIDE_OUTLINE.md](REVIEW_2_SLIDE_OUTLINE.md) — 21 slides, 3–5
bullets each, a 14-question viva Q&A (where the model loses, what "accuracy" means, why no accident
claims, plus the new fallback-cost finding and the degraded R² CI), a
Completed/Tested/In-progress/Yet-to-start status table, a **Numbers → command** table, and a
`REQUIRES STUDENT INPUT` block on slides 1 and 3. Every figure was re-read from the artifacts
before writing (`eval_results.json`, `multi_seed_metrics.json`, `fallback_audit.json`,
`real_route_check.json`, `dataset_manifest.json`, `perf_server_bench.json`) and cross-checked
against disk: `radius_median_m` spans 227.29–623.34 m, `random_forest` p95 **48.516 ms** (hence
rejected against the 12.0 ms budget), OOD-type empirical coverage **0.6786**, 3 files in
`docs/screenshots/`.

### TASK 4 — live real-route plausibility check (2026-10-18)

| Command | Actual output |
|---|---|
| `python scripts/real_route_check.py` (no flag) | refuses to run: "LIVE check: hits public Nominatim + OSRM. Re-run with --confirm…" → exit 2 |
| `python scripts/real_route_check.py --confirm` | table for 5/5 pairs + `"wrote D:\FP_ROADGUARD\docs\real_route_check.json"`; aggregate: 8 route records, 1247 sections, 1176 scored (0.9431), fallback 182 (0.1548), ood 216, advisories 162, coverage 0.9568–0.9831, radius <10 m 15, <25 m 84 of 987, min 3.96 m, high-band 143 (84 of them <25 m), states `{"scored": 8}` |
| repeat `--confirm` ×2 | **identical aggregates** on all three runs (OSRM deterministic for fixed endpoints) |
| `python -m ruff check scripts/real_route_check.py` | `All checks passed!` |
| `python -m mypy scripts/real_route_check.py --ignore-missing-imports` | `Success: no issues found in 1 source file` |
| `npx playwright test tests/e2e/screenshots.spec.js` | `2 passed (17.6s)` → 3 PNGs in `docs/screenshots/` |
| `npx playwright test` | `17 passed (25.3s)` |

Two defects found while producing the screenshots, both fixed in source: the tile mock glob
missed Leaflet's `{a,b,c}.tile…` subdomains, so the "mock" E2E suite had been loading **live
OSM tiles** (visible street labels in the first capture); and the first capture was taken
mid-animation / under a lingering toast, so the spec now waits for `opacity: 1` and for the
toast to hide. The script also hit a real Windows-console bug: printing the table raised
`UnicodeEncodeError: 'charmap' codec can't encode character '\u2192'` under a piped cp1252
stdout, so output now goes through an ASCII-lossy fallback writer (the JSON had already been
written, so no live work was lost).

### TASK 3 — disagreement-fallback measurement + degraded R²/CI (2026-10-18)

| Command | Actual output |
|---|---|
| `python -m ml.fallback_audit` | wrote `ml/artifacts/fallback_audit.json`; consistency guard passed (`model_only_mae matches ml/artifacts/eval_results.json within 0.0015`); `threshold_retuned: false` |
| `python -m ml.evaluate_seeds` (5 seeds, ~11 min) | `clean_r2 0.9975 [0.9960, 0.9990]`, `clean_mae 0.4754 [0.4078, 0.5430]`, `degraded_mae 13.9986 [13.0437, 14.9535]`, **`degraded_rmse 19.4270 [18.5491, 20.3049]`**, **`degraded_r2 0.3090 [0.2432, 0.3747]`**, `degraded_baseline_mae 28.2730 [27.3380, 29.2080]`, `ood_radius_mae 15.8956 [14.8076, 16.9836]`, `ood_type_mae 19.4558 [17.9587, 20.9529]`, `empirical_coverage 0.8173 [0.7870, 0.8476]`, `latency_p50 5.2124 [5.1723, 5.2524]`, `all_monotonic_pass True max_leakage 0` |
| reproduction check vs committed `multi_seed_metrics.json` | **per-seed deterministic diffs (ex-latency): NONE**; every headline block MATCH (only p50/p95 latency moved: 6.2159→5.2124 / 8.8547→7.3937 ms) |
| `python -m pytest tests/test_fallback_audit.py -q` | 4 passed |
| `python -m pytest -q` | `112 passed, 1 warning in 9.32s` |
| `node --test "tests/js/**/*.test.js"` | `tests 31 / pass 31 / fail 0` (186.8 ms) |
| `npx playwright test` | `17 passed (25.3s)` |
| `python -m ruff check app ml scripts tests` | `All checks passed!` |
| `python -m mypy app ml scripts --ignore-missing-imports` | `Success: no issues found in 31 source files` |
| `python -m pip_audit -r requirements.txt` | `No known vulnerabilities found` |
| `python -m pytest tests/test_compliance.py -q` | `7 passed, 1 warning in 0.07s` |

**Finding published in** [GEOMETRY_ML_LIMITATIONS.md](GEOMETRY_ML_LIMITATIONS.md) **and
FINAL_REPORT §8:** the shipped guard (`DISAGREEMENT_THRESHOLD = 20.0`, unchanged) fires on
61.1 % of degraded, 67.7 % of OOD-radius, 66.4 % of OOD-type and 72.4 % of noise@3 m sections;
served MAE 27.252 (degraded) / 42.394 (OOD-radius) / 12.593 (OOD-type) vs model-only
14.142 / 14.994 / 20.307. Fallback precision (share of firings where the baseline really was
closer) is 0.2045 degraded, 0.029 OOD-radius, 0.7204 OOD-type. So the guard pays off only on
unseen curve **type**; elsewhere it discards the model's degraded advantage. Calibration-split
sweep (recorded, **not** applied): threshold 20 → 0.6358 rate / 29.950 MAE; 30 → 0.4570 /
27.099; 50 → 0.1722 / 19.798; ∞ → 0 / 14.761. Changing the threshold would need validation-split
tuning + a held-out re-test, which was not done.

### TASK 2 — speed-aware advisory + deviation coverage (2026-10-17)

| Command | Actual output |
|---|---|
| `python -m pytest -q` | `108 passed, 1 warning in 8.23s` (was 105; +3 wiring tests) |
| `node --test "tests/js/**/*.test.js"` | `tests 31 / pass 31 / fail 0` (was 23; +8 speed cases) |
| `npx playwright test` | `15 passed (12.2s)` — 10 rider + 5 admin (was 12; +3) |
| `python -m ruff check app ml scripts tests` | `All checks passed!` |
| `python -m mypy app ml scripts --ignore-missing-imports` | `Success: no issues found in 29 source files` |
| `python -m pip_audit -r requirements.txt` | `No known vulnerabilities found` |
| `python -m pytest tests/test_compliance.py -q` | `7 passed, 1 warning in 0.07s` |

**Gap report that drove this task.** (a) F14 route-deviation was already implemented in
`app/web/app.js` (accuracy-scaled cross-track threshold, 2-fix latch, `route_deviation` chip
state, advisory pause, recovery) but had **zero** automated coverage — `grep -rn deviat tests/`
returned nothing. (b) The advisory did **not** use the rider's real GPS speed: `speed_kmh` came
only from the manual `#speed-select`, falling back to a road-class assumption server-side, and
`coords.speed` was never read anywhere in the client.

**Implemented.** `speedAwareness()` / `lateralDemandG()` / `normaliseSpeedKmh()` in
`app/web/alerts.js` (pure, node-tested) re-evaluate `v²/R` in g at the device's reported speed
and compare it against the band the advisory was actually scored at (`inputs.speed_kmh` from the
payload), on the section's mapped radius. `onFix` now stores `speed_kmh`; `updateAdvisory`
renders the note into `#advisory-speed` with `data-status` ∈ above/below/matching/
speed_unavailable/radius_unavailable; the technical detail view reports the live-speed source.
Invalid or missing speed **falls back to the assumed band and says so** — it never renders as
0 km/h. No instruction about what speed to ride at is produced anywhere (asserted by
`test_speed_note_is_a_disclosure_not_an_instruction`). Scores/MAE are unchanged: the note is a
display layer, so all §7.5 evaluation numbers still refer to the same banded scoring.

**Real bug the new tests caught:** `Number(coords.speed)` coerces `null` → `0`, so an
unreported speed would have displayed "0 km/h (GPS)" and a 0.00 g demand. Fixed in source
(`app/web/app.js` `onFix`) by testing for absent speed first, not by weakening the test.

### TASK 1 — version control (2026-10-17)

| Command | Actual output |
|---|---|
| `python -m pytest -q` | `105 passed, 1 warning in 13.53s` |
| `node --test "tests/js/**/*.test.js"` | `tests 23 / pass 23 / fail 0` (260.55 ms) |
| `npx playwright test` | `12 passed (15.1s)` (headless Chromium, 390×844) |
| `python -m ruff check app ml scripts tests` | `All checks passed!` |
| `python -m mypy app ml scripts --ignore-missing-imports` | `Success: no issues found in 29 source files` |
| `python -m pip_audit -r requirements.txt` | `No known vulnerabilities found` |
| `python -m pytest tests/test_compliance.py -q` | `7 passed, 1 warning in 0.07s` |

`.gitignore` now also excludes `*.db`/`*.db-wal`/`*.db-shm`, `*.sqlite`, `.env.*` (with
`!.env.example` kept tracked), `*.pem`/`*.key`, and `ml/artifacts_debug/` (the duplicate
scratch model dir documented as local-only in PROJECT_AUDIT and KNOWN_ISSUES — untracked,
not deleted). No `.env` file exists in the tree; a staged-diff secret scan
(api key / password / token / bearer literals) returned **zero** findings. Nothing pushed.

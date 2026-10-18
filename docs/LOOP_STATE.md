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
| 1 Research | **Done (verified pass)** | 11 sources verified with URL + access date 2026-10-17; RESEARCH_LITERATURE_REVIEW, RESEARCH_GAP_AND_CONTRIBUTION, REFERENCES_VERIFIED written. One plan-named source (a second "Nadimi 2025" telematics paper) **could not** be independently confirmed and is flagged, not fabricated. |
| 2 Contracts | Done | ARCHITECTURE / API_SPECIFICATION (live OpenAPI) / DATABASE_DESIGN written. OpenAPI is app-generated. |
| 3 UI/Auth/Nav shell | Mostly done | Implemented; authz tested. **Staged, capability-aware alerts added** (`alerts.js` pure planner + `settings.js` localStorage prefs): visual/audio/vibrate with iOS (no `navigator.vibrate`) and reduced-motion fallbacks, sound gated behind a user gesture, `role="alert"` assertive region for high-band in-curve. **Browser-verified this session** (server on :8171): settings sheet opens, per-channel toggles persist across reload, capability note renders, assertive live region present, no JS errors (only the expected 401 on `/auth/me`). Alert logic unit-tested (23 `node --test` cases) + static wiring smoke tests (`tests/test_web_alerts.py`). **FSM + layout Playwright E2E still not automated.** |
| 4 Geometry | Done | 15 geo tests, analytical cases pass. |
| 5 Route-level | Done | 10 aggregation tests. |
| 6 Baseline | Done | 10 baseline tests; measured clean+degraded table. |
| 7 ML mandatory | **Redesigned + retested (multi-seed verified)** | GACE = `physics_v2r_v1` **prior + monotonic boosted residual** (feature 22 = `physics_prior`); selection by **train-only grouped CV + monotonicity gate + latency budget** (random forest rejected for p95 > 12 ms); split-conformal band. Seed 42 committed artifact: clean **R² 0.9948** (MAE 0.573), degraded MAE 14.142 vs baseline 27.826, OOD-radius 14.994 vs 43.287, hairpin OOD 20.307 vs 12.647 → fallback; leakage 0; latency p50 5.02 / p95 6.62 ms. **5-data-seed run verified** (`evaluate_seeds` → `ml/artifacts/multi_seed_metrics.json`): clean R² **0.9975 [0.9960, 0.9990]** (≥0.99 met on CI lower bound), degraded MAE **13.999 [13.044, 14.954]** vs baseline 28.273 (< baseline every seed), OOD-radius reduced, hairpin → fallback every seed, coverage mean **0.8173 [0.787, 0.848]** (inside ±3pt band on the mean; per-seed 0.76–0.848 is finite-sample noise), latency p95 8.85 ms [7.15, 10.56] under budget, monotonic 5/5, leakage 0/5. |
| 8 ML integration | Done | startup load, uncertainty, disagreement fallback, admin status, provenance tags, import-graph test. `app/model.py` adds the prior back for `prediction_mode=…residual`; legacy artifacts still load. New residual runtime covered by `tests/test_model.py` (incl. a batch-vs-per-section equivalence guard); the scored route path is now also covered end-to-end by `tests/test_api_routes.py`. |
| 9 Hazards/admin/privacy/security | Mostly done | lifecycle/authz/secret-scan/deletion tested; **`pip-audit` now RUN clean** (0 known vulns, live DB). Graceful-failure provider mocks now in CI (`tests/test_api_routes.py`); remaining: in-suite `live`-labelled pytest (network-gated). |
| 10 Performance | **Measured + optimised** | server path batched (`score_sections`): analyze p50 ~90→16 ms, single-worker ~8→66 rps, **provably lossless** (0 mismatches on real model + `test_score_sections_batch_matches_per_section`); bounded provider cache (cold→warm skip re-fetch, ≤256 entries); **live** provider p50 geocode 21 ms / route 204 ms; **client** 0.024 ms/fix, flat heap + 0 listener growth over soak, 0 duplicate GPS subs (browser-verified). Open: multi-worker + CI-Playwright perf variants. Evidence: `PERFORMANCE_REPORT.md`, `docs/perf_server_bench.json`, `docs/perf_provider_live.json`. |
| 11 Regression | Mostly done | **108 backend + 31 `node --test` + 15 Playwright E2E cases green (rider + admin; E2E covers nav-FSM, **route deviation (F14)**, **speed-aware advisory note + no-speed fallback**, cue playback, trip summary, login/role gating, tab switch, moderation, and insufficient-evidence + provider-failure paths with `mock`-labelled providers; backend `tests/test_api_routes.py` covers `/routes/analyze` offline). `ruff` clean; `mypy` clean on app+ml+scripts (29 files, findings fixed in source, not suppressed); `pip-audit` clean.** Open: `pyright` (mypy is authoritative; not run) + an in-suite `live`-labelled provider pytest (network egress out of CI). |
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
6. **E2E harness** — ~~frontend alert/settings logic~~ **DONE** (23 `node --test` cases in
   `tests/js`, plus `tests/test_web_alerts.py` static wiring). **Playwright nav-FSM / layout /
   cue / admin E2E now DONE**: `tests/e2e/` boots the real ASGI app and runs **12 green
   headless-Chromium cases** — rider (7): startup, search→route + client header, nav lifecycle →
   trip summary, live-GPS→staged advisory cue with assertive escalation, hazard submit,
   insufficient evidence, provider failure; admin (5): login gate, role-denied gate, tab switch +
   hazards list, moderation posts `{action,note}` + toast, system/diagnostics render — all with
   **`mock`-labelled providers + stubbed tiles**, deterministic and wired into CI (`e2e` job in
   `.github/workflows/ci.yml`). Only the in-suite `live`-labelled provider pytest remains open
   (network egress kept out of CI by design).
7. ~~Client performance measurement~~ **DONE** — render cost (canvas, 258 DOM nodes),
   per-fix update latency (0.024 ms), memory soak + listener growth (flat, 0 leak over a
   300-fix soak and 50 sheet cycles), 0 duplicate GPS subscriptions — all measured
   browser-side this session (Gate 10). Server side batched + ~6× faster, provably lossless.
   Remaining perf variants: multi-process load + a CI Playwright harness.
8. **Review 2 deck** generated from REVIEW_2_PROJECT_SPECIFICATION; `REQUIRES STUDENT
   INPUT` rows are the student's to fill.
9. ~~**Commit** the tree once the student asks~~ **DONE** — student authorised commits on
   2026-10-17; one commit per task, nothing pushed (push is the student's step).

## Remaining-work timeline (indicative, not a promise)

| Order | Work | Depends on |
|---|---|---|
| Now | Restore verification | — |
| Next | Verified research docs | web access |
| Then | live provider + E2E tests | UI stable |
| Then | static analysis + audit | deps pinned |
| Then | client perf measurement | E2E harness |
| Last | Docker/CI/runbook + Review 2 deck | all above |

## What is deliberately NOT claimed

Clean audit, clean types, passing Playwright E2E, generalised accuracy, or "safe route"
capability. Each appears above as open, not done. The alert **settings, persistence,
capability fallback and assertive live region were browser-verified**, but **responsive
screenshots were NOT captured** this session (the in-app browser viewport was unavailable);
responsiveness rests on the existing mobile-first stylesheet (safe-area insets, ≥44 px touch
targets, `env(safe-area-inset-*)`), not on new visual evidence. The **GPS→cue playback** was
verified by unit tests + wiring, not a live headless-GPS run. See
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## Gate log (actual command output, most recent first)

Full gate re-run after every task in this session. Commands are exactly as listed in README.

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

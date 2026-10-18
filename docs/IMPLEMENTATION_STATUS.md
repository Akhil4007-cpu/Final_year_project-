# IMPLEMENTATION_STATUS

Status vocabulary (per plan): **Completed** · **Tested** · **In progress** · **Planned** ·
**Unverified**. "Tested" means an automated test asserts it; "Unverified" means present in
code but not covered by an executed check here. No cell claims more than the evidence in
[TESTING_AND_EVALUATION.md](TESTING_AND_EVALUATION.md).

## Feature status

| Area | Status | Evidence |
|---|---|---|
| App scaffold, config, env | Completed | `app/config.py`, `.env.example`, 91-test run |
| SQLite schema + migrations + indexes | Tested | `test_api` runs against migrated DB; EXPLAIN in PERFORMANCE_REPORT |
| Auth (register/login/logout/me) | Tested | `test_api` (cookie HttpOnly/SameSite, 401/400/403 paths) |
| Password hashing / token / CSRF header | Tested | `test_security`, `test_api::register requires header` |
| Rate limiting (single worker) | Tested | `test_login_rate_limit_enforced` (429 + Retry-After) |
| Account deletion + anonymisation | Tested | `test_api`; SQL in `auth.delete_account` |
| Geocoding (Nominatim, India) | Tested (mock) + live probe | wired in `providers.py`; mocked in `test_api_routes` + Playwright (`mock`); live path exercised only by the opt-in `scripts/real_route_check.py --confirm` (5/5 places resolved) and `bench_provider_live.py` — no live test in CI |
| Routing (OSRM) | In progress / Unverified | wired; manual browser only |
| Geometry extraction | Tested | `test_geo` (15) analytical cases |
| Physics baseline `v²/R` | Tested | `test_baseline` (10) |
| Route aggregation + coverage | Tested | `test_aggregation` (10) |
| Comparison / insufficient-evidence | Tested | `test_aggregation` comparable/ranked |
| Advisory engine | Tested | `test_advisory` (6) |
| Synthetic data generator | Tested (reproducible) | seed 42, manifest hash, `ml.train` |
| GACE model + selection | Tested | `test_model` (9); `eval_results.json` |
| Conformal uncertainty + OOD widening | Tested | `test_model` predict widening; eval coverage |
| Disagreement → baseline fallback | Tested | `test_model` model_estimate vs fallback |
| Startup artifact load, never import ml | Tested | `test_runtime_never_imports_ml_training` |
| Model card / limitations docs | Completed | `ml/artifacts/MODEL_CARD.md`, this docs set |
| Hazard lifecycle + votes | Tested | `test_api` (unverified default, votes auth) |
| Admin moderation + audit | Tested | `test_admin_moderate_and_audit` |
| Admin users/overview/diagnostics | Tested | `test_api` role-gate 403/401 |
| Rider UI (map, nav FSM, advisory) | Tested (E2E) + browser-verified | **10 Playwright cases** (`tests/e2e/rider.spec.js`, mock-labelled providers): startup, search→route, nav lifecycle→trip summary, live-GPS advisory cue, hazard submit, insufficient-evidence, provider-failure, **route-deviation latch + recovery (F14)**, **speed-aware advisory note (measured speed above the scored band)**, **no-speed fallback disclosure** |
| Route deviation (F14) | Tested | Cross-track distance vs an accuracy-scaled threshold (`max(55, min(120, ±m × 1.6))`) in `app/web/app.js::updateNavigation` (line 802 as of
2026-10-18); latches after 2 fixes, pauses advisories, chip → `route_deviation`, clears on return. Was previously implemented but **untested**; now covered by a Playwright case + wiring test |
| Speed-aware advisory note | Tested | `speedAwareness()` in `app/web/alerts.js` compares the device's `coords.speed` (m/s → km/h) with the band the score was computed at, re-evaluating `v²/R` in g on the section's mapped radius. Invalid/missing speed → explicit disclosure, never a silent 0 km/h. **No instruction on what speed to ride at** (R4) |
| Staged alerts + capability fallback + settings | Tested (logic) + browser-verified (UI) | `tests/js` (31 node cases), `tests/test_web_alerts.py` (7); settings/persistence/live-region browser-checked on `:8171`; cue playback now also covered by the Playwright cue E2E |
| Admin console UI (tabbed SPA) | Tested (E2E) + browser-verified | **5 Playwright cases** (`tests/e2e/admin.spec.js`, mock-labelled): login gate, role-denied gate, tab switch + hazards list, moderation posts `{action,note}` + toast, system/diagnostics render |
| Rider UI screenshots at 390 px | Generated (mock-labelled) | `tests/e2e/screenshots.spec.js` (2 cases) regenerates `docs/screenshots/rider-{1,2,3}-*-390.png`; route panel, moderate advisory (matching speed), high advisory (above speed). Mock providers + mocked tiles — visual evidence of the shipped frontend only |
| Compliance rules R2/R4/R8/R10 | Tested | `test_compliance` (7) |
| Disagreement-fallback audit | Tested (regression-pinned) | `python -m ml.fallback_audit` → `ml/artifacts/fallback_audit.json`; `test_fallback_audit` (4) pins the published table, asserts `threshold_retuned: false` and that the recorded rule string still names the shipped `DISAGREEMENT_THRESHOLD`. Findings in `GEOMETRY_ML_LIMITATIONS.md` |
| JS unit tests (`node --test`) | Tested | 31 cases (alert planner + speed layer + settings), no npm/build needed |
| Playwright E2E | Tested | **PRESENT** — 17 headless-Chromium cases (`tests/e2e`: 10 rider + 5 admin + 2 screenshot), `npx playwright test` → `17 passed`; boots the real ASGI app, all providers mocked; wired into CI (`e2e` job). `@playwright/test` 1.64.1, Node 24 |
| Lint (`ruff`) | Tested | `ruff check` → `All checks passed!` (9 findings fixed in source) |
| `mypy` static type check | Tested | `mypy 1.11.2` → clean on `app`+`ml`+`scripts` (31 files); findings fixed in source (no `# type: ignore`); CI-blocking |
| `pyright` | Not run | not installed here (needs `npm install`); `mypy` is the authoritative type checker and passes |
| `pip-audit` dependency audit | Tested | `pip-audit 2.10.1` → 0 known vulnerabilities in the resolved env; CI-blocking |
| Performance: server throughput + client render/soak | Tested (measured) | `scripts/bench_server.py` → `docs/perf_server_bench.json`; batched scoring cut analyze p50 ~90→16 ms (~9.5× scoring, provably lossless), single-worker ~8→66 rps; client 0.024 ms/fix, flat heap/listeners, 0 duplicate GPS subs (browser-verified) |
| Live provider latency (Nominatim/OSRM) | Measured (live, manual run) | `scripts/bench_provider_live.py --confirm` → `docs/perf_provider_live.json`; geocode p50 21 ms, route p50 204 ms; not in CI (network) |
| Real-route plausibility (live, opt-in) | Measured (live, **plausibility only — no accuracy claim**) | `scripts/real_route_check.py --confirm` → `docs/real_route_check.json` + [REAL_ROUTE_CHECK.md](REAL_ROUTE_CHECK.md); 5/5 pairs routed, 8 route records, 0 validation failures, 1247 sections / 94.3 % scored, coverage 95.7–98.3 %, fallback fired on 15.5 % of scored sections, but 84 sections with radius <25 m (min 3.96 m) all banded `high` → KNOWN_ISSUES #12. Run three times, identical aggregates |
| Multi-worker / CI-automated Playwright perf | Not run | single-worker ceiling measured; multi-process + Playwright-harness variants open |
| Dockerfile + `.dockerignore` | In progress | authored; `node_modules`/playwright now gitignored + dockerignored; **`docker build` NOT verified** (engine absent) |
| GitHub Actions CI | In progress | `.github/workflows/ci.yml` authored with test / frontend-test / e2e / build jobs; not executed on a runner |
| Runbook / deploy docs | Completed | `MANUAL_RUNBOOK.md` |
| Version control | Completed (local only) | `main`, first commit + small per-task commits; `.gitignore` excludes env/DB/secrets/venv/node_modules/test-results/scratch. **No remote, nothing pushed** — student runs `git remote add origin <URL> && git push -u origin main` |
| Verified research docs | Completed | 11 numbered sources w/ URL + 2026-10-17 access date; FHWA-HRT-13-077 re-checked at ROSA P and Nadimi 2025 at Crossref on 2026-10-18 |
| Review 2 outline | Completed | `REVIEW_2_SLIDE_OUTLINE.md`: 21 slides × 3–5 measured bullets, 14-question viva Q&A, Completed/Tested/In-progress/Yet-to-start status table, Numbers→command table. Slides 1 and 3 (title, team, supervisor, Review-1 feedback) are `REQUIRES STUDENT INPUT` |
| Review 2 deck (the slide file) | Not started | Building the actual deck from the outline is the student's step — college template, title and Review-1 feedback are student-only inputs |

## Exit-gate reflection

Phases 0, 3–9 core logic are Implemented & Tested; the ML baseline is retrained,
multi-seed verified, and documented (Gate 7/8). Phase 10 performance is now **measured and
optimised** (server before/after + client render/soak + live provider + bounded cache, all
in `PERFORMANCE_REPORT.md`); `ruff`, `mypy` (app+ml+scripts, 31 files) and `pip-audit` are
green — re-run 2026-10-18 with the actual output logged in
[LOOP_STATE.md](LOOP_STATE.md) → Gate log. The **Playwright E2E gate is met** (17
headless-Chromium cases — 10 rider + 5 admin + 2 screenshot, mock-labelled providers, in CI)
alongside **112 backend tests** and **31 `node --test` cases**. The Review-2 follow-up round
closed the two plan gaps it found (untested F14 route deviation, speed-blind advisory),
quantified what the runtime disagreement guard costs in served accuracy, and added a live
real-route plausibility probe. The loop is **not** at exit — remaining open: a live `docker
build` verification on a running engine (deferred by student request — no Docker needed as of
now), an in-suite `live`-labelled provider pytest (network egress kept out of CI), a real
GitHub-Actions runner execution of the workflow, KNOWN_ISSUES #12 (implausibly small radii on
real OSM polylines), and the deck build itself; `pyright` is not run (mypy is authoritative).
See [LOOP_STATE.md](LOOP_STATE.md).

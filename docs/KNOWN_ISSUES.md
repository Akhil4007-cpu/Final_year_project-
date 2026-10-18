# KNOWN_ISSUES

Real, currently-open issues. Each has severity, evidence, and status — none is hidden or
spun as fixed.

## Open

| # | Issue | Severity | Evidence / why | Status |
|---|---|---|---|---|
| 1 | Rate limiter is in-process only | Medium | `app/security.py::RateLimiter` keeps buckets in memory; a second uvicorn worker or host has its own counters. | Open — needs a shared store (Redis/SQLite) before multi-worker. |
| 2 | CSP allows `style-src 'unsafe-inline'` | Low–Med | `app/main.py:30`. Needed for vendored Leaflet inline styles. `script-src` is strict, no `unsafe-eval`. | Open — acceptable for student scope; documented in SECURITY_AND_PRIVACY. |
| 3 | ~~No automated E2E / frontend tests~~ | Medium | **RESOLVED.** `tests/e2e/` runs **17 Playwright headless-Chromium cases** (10 rider + 5 admin + 2 screenshot) against the real ASGI app with **`mock`-labelled providers + stubbed tiles** — nav FSM, cue playback, trip summary, **route deviation (F14)**, **speed-aware advisory note + its no-speed fallback**, login/role gating, tab switch, moderation, insufficient-evidence and provider-failure paths, and the three 390 px rider captures. 31 `node --test` JS-unit cases cover the pure alert planner, the speed comparison and settings persistence. Wired into the CI `e2e` job. | Closed. |
| 4 | Live provider paths are not asserted by CI | Medium | `/geocode` and `/routes/analyze` are covered offline by mocked tests; the live paths are covered only by **opt-in, non-CI** probes: `scripts/bench_provider_live.py --confirm` (round-trip p50/p95) and `scripts/real_route_check.py --confirm` (5 real pairs end-to-end, [REAL_ROUTE_CHECK.md](REAL_ROUTE_CHECK.md)). Neither can run in CI (network + public-endpoint courtesy limits). | Open — live-labelled CI job with graceful skip remains the right fix. |
| 5 | Static analysis | Low | **ruff 0.6.2 + mypy 1.11.2 RUN clean** (mypy on app+ml+scripts; findings fixed in source, not suppressed); CI-blocking. `pyright` still not run (needs npm; mypy is authoritative). | Closed for ruff/mypy; pyright optional. |
| 6 | ~~Dependency audit not run~~ | Low | **`pip-audit` 2.10.1 RUN clean** — 0 known vulnerabilities in the resolved env; CI-blocking. | Closed (re-run in CI as the advisory DB updates). |
| 7 | Public OSRM demo limits | Medium | `router.project-osrm.org` throttles/rejects bulk traffic. Fine for a demo, not for launch. (Live latency now measured: route p50 ~204 ms, geocode p50 ~21 ms.) | Open — self-host or commercial routing plan required pre-launch. |
| 8 | ~~Client render / memory / throughput NOT MEASURED~~ | Low | **Measured** (browser + `scripts/bench_server.py`): analyze p50 ~16 ms after batching (was ~90 ms, provably lossless), single-worker ~66 rps; client 0.024 ms/fix, flat heap/listeners, 0 duplicate GPS subs. | Closed — see PERFORMANCE_REPORT. Open variants: multi-process + CI Playwright perf. |
| 9 | Provider calls synchronous httpx, no circuit breaker | Low | `app/providers.py`; a slow provider consumes a worker for the timeout window. | Open — acceptable at student scale. |
| 10 | ~~Repo has 0 commits~~ | Info | **RESOLVED.** `git init` + first commit made on `main`; work is now committed in small per-task commits. `.gitignore` excludes `.env*`, `*.db`/`*.sqlite*` (+ WAL/SHM), `.venv`, `node_modules`, `test-results`, `*.pem`/`*.key`, `data/backups`, and the scratch artifact dirs. **Nothing has been pushed** — remote setup is the student's own step. | Closed (local only). |
| 11 | Docker image build not verified | Medium | `Dockerfile` + `.dockerignore` authored (node_modules/playwright now ignored). Docker Desktop is installed here, but `docker build` was **deferred by student request** ("no docker needed as of now"), so the image has **never been built** in this environment. | Deferred — run `docker build -t roadguard:ci .` on a machine with a live daemon when needed. |
| 12 | Real OSM polylines yield physically impossible curve radii | Medium | Live probe over 8 real route records: 987 radius-bearing sections, median 227–623 m, but **84 under 25 m and 15 under 10 m (min 3.96 m)** — 3.96 m at the assumed 50 km/h band is ≈5.0 g lateral. **All 84 sub-25 m sections were banded `high`**, i.e. 58.7 % of high-band sections on real geometry. Cause: bunched/uneven OSRM vertices (all 8 records flagged `highly uneven point spacing`). Route-level aggregation damped it (every route still read `low`). Numbers: [REAL_ROUTE_CHECK.md](REAL_ROUTE_CHECK.md). | Open — needs a labelled decision (minimum-radius floor or a spacing gate on `v²/R`), which would change the training label and require re-train + re-eval; deliberately NOT retuned from a plausibility probe. |

## Fixed this session (regression-tested)

| # | Was | Severity | Fix | Now asserted by |
|---|---|---|---|---|
| A | Trip summary sheet rendered empty | High | `detailBlock` expects an array; wrapped node in `app/web/app.js::renderTripSummary`. | `rider.spec.js` navigation-lifecycle E2E case (asserts the summary sheet content) — no longer manual-only |
| B | Audit action `hazard_verifyd`/`hazard_rejectd` | Medium | Emit `hazard_verified`/`hazard_rejected` in `app/hazards.py`. | `test_api::test_admin_moderate_and_audit` |
| C | The "mock" E2E suite was silently loading **live** OSM map tiles: the harness glob `**/tile.openstreetmap.org/**` does not match Leaflet's `{a,b,c}.tile…` subdomains | Medium (test honesty) | Subdomain-agnostic pattern in `tests/e2e/_harness.js`, plus a solid placeholder tile so captures are visibly synthetic. | `npx playwright test` (17 cases) now runs with no tile traffic; `tests/e2e/screenshots.spec.js` asserts the captures exist |
| D | Rider UI rendered `~0 km/h` / `data-status="below"` when the device reported no speed, because `Number(null) === 0` | High (product honesty) | Absence checked before coercion in `app/web/app.js::onFix`; fixed in source, not by relaxing the test. | `rider.spec.js` "device reports no speed" + `tests/js/alerts.test.js` |
| E | The 390 px rider captures were **not reproducible** between runs — infinite CSS keyframes (`pulse`, `alert-pulse`) froze at different phases, and Leaflet's JS map pan kept moving after the assertions | Medium (evidence quality) | `animations: "disabled"` + `settleMap()` (polls the `.leaflet-map-pane` transform) in `tests/e2e/screenshots.spec.js`. Diagnosed by decoding the PNGs and diffing pixel arrays, **not** by comparing bytes — Chromium emits different PNG streams for identical pixels, so byte hashes are not a determinism test. | Three consecutive `npx playwright test tests/e2e/screenshots.spec.js` runs → identical decoded-pixel hashes for all three files (measured 2026-10-18) |

## Scratch / artifacts to exclude from packaging

`data/*.sqlite3` (smoke, roadguard, ui_review) and `ml/artifacts_debug/` are local
manual-verification scratch: they are matched by `.gitignore` (`*.sqlite3`,
`ml/artifacts_debug/`), are **not** tracked by git, are **not** imported by any test, and are
excluded from the image by `.dockerignore`. Removal from disk is deferred until the student
confirms.

The four Phase-0 manual browser captures `data/ui-review-rider-home.png`,
`data/ui-review-rider-route.png`, `data/ui-verify-advisory.png`, `data/ui-verify-trip-summary.png`
**are tracked** (they went in with the initial commit). They are left in place — they are the only
evidence of the pre-E2E manual verification pass — but they must be read as **manual, unlabelled,
un-reproducible** captures: nothing regenerates them, and they predate the automated
`mock`-labelled set in `docs/screenshots/` produced by `tests/e2e/screenshots.spec.js`. Do not
present them as automated evidence.

# KNOWN_ISSUES

Real, currently-open issues. Each has severity, evidence, and status — none is hidden or
spun as fixed.

## Open

| # | Issue | Severity | Evidence / why | Status |
|---|---|---|---|---|
| 1 | Rate limiter is in-process only | Medium | `app/security.py::RateLimiter` keeps buckets in memory; a second uvicorn worker or host has its own counters. | Open — needs a shared store (Redis/SQLite) before multi-worker. |
| 2 | CSP allows `style-src 'unsafe-inline'` | Low–Med | `app/main.py:30`. Needed for vendored Leaflet inline styles. `script-src` is strict, no `unsafe-eval`. | Open — acceptable for student scope; documented in SECURITY_AND_PRIVACY. |
| 3 | ~~No automated E2E / frontend tests~~ | Medium | **RESOLVED.** `tests/e2e/` runs **15 Playwright headless-Chromium cases** (10 rider + 5 admin) against the real ASGI app with **`mock`-labelled providers + stubbed tiles** — nav FSM, cue playback, trip summary, **route deviation (F14)**, **speed-aware advisory note + its no-speed fallback**, login/role gating, tab switch, moderation, insufficient-evidence and provider-failure paths. 31 `node --test` JS-unit cases cover the pure alert planner, the speed comparison and settings persistence. Wired into the CI `e2e` job. | Closed. |
| 4 | Live provider paths not unit-tested | Medium | `/geocode` and `/routes/analyze` hit real Nominatim/OSRM; only manual browser runs. | Open — needs `live`-labelled tests with graceful-failure mocks. |
| 5 | Static analysis | Low | **ruff 0.6.2 + mypy 1.11.2 RUN clean** (mypy on app+ml+scripts, 29 files; findings fixed in source, not suppressed); CI-blocking. `pyright` still not run (needs npm; mypy is authoritative). | Closed for ruff/mypy; pyright optional. |
| 6 | ~~Dependency audit not run~~ | Low | **`pip-audit` 2.10.1 RUN clean** — 0 known vulnerabilities in the resolved env; CI-blocking. | Closed (re-run in CI as the advisory DB updates). |
| 7 | Public OSRM demo limits | Medium | `router.project-osrm.org` throttles/rejects bulk traffic. Fine for a demo, not for launch. (Live latency now measured: route p50 ~204 ms, geocode p50 ~21 ms.) | Open — self-host or commercial routing plan required pre-launch. |
| 8 | ~~Client render / memory / throughput NOT MEASURED~~ | Low | **Measured** (browser + `scripts/bench_server.py`): analyze p50 ~16 ms after batching (was ~90 ms, provably lossless), single-worker ~66 rps; client 0.024 ms/fix, flat heap/listeners, 0 duplicate GPS subs. | Closed — see PERFORMANCE_REPORT. Open variants: multi-process + CI Playwright perf. |
| 9 | Provider calls synchronous httpx, no circuit breaker | Low | `app/providers.py`; a slow provider consumes a worker for the timeout window. | Open — acceptable at student scale. |
| 10 | Repo has 0 commits | Info | Working tree fully untracked (audit §Phase 0). | Intentional — commit deferred until the student asks. |
| 11 | Docker image build not verified | Medium | `Dockerfile` + `.dockerignore` authored (node_modules/playwright now ignored). Docker Desktop is installed here, but `docker build` was **deferred by student request** ("no docker needed as of now"), so the image has **never been built** in this environment. | Deferred — run `docker build -t roadguard:ci .` on a machine with a live daemon when needed. |

## Fixed this session (regression-tested)

| # | Was | Severity | Fix | Now asserted by |
|---|---|---|---|---|
| A | Trip summary sheet rendered empty | High | `detailBlock` expects an array; wrapped node at `app/web/app.js:925`. | Manual browser (still no e2e) |
| B | Audit action `hazard_verifyd`/`hazard_rejectd` | Medium | Emit `hazard_verified`/`hazard_rejected` in `app/hazards.py`. | `test_api::test_admin_moderate_and_audit` |

## Scratch / artifacts to exclude from packaging

`data/*.sqlite3` (smoke, roadguard, ui_review) and `data/ui-*-*.png` / `data/ui-verify-*.png`
screenshots, plus `ml/artifacts_debug/`, are local manual-verification scratch. They are
**not** imported by tests and should not be committed or packaged. `.gitignore` and the
README cleanup note cover this; removal from disk is deferred until the student confirms.

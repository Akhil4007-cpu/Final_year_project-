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
| Geocoding (Nominatim, India) | In progress / Unverified | wired in `providers.py`; manual browser only, no live test |
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
| Rider UI (map, nav FSM, advisory) | Tested (E2E) + browser-verified | **7 Playwright cases** (`tests/e2e/rider.spec.js`, mock-labelled providers): startup, search→route, nav lifecycle→trip summary, live-GPS advisory cue, hazard submit, insufficient-evidence, provider-failure |
| Staged alerts + capability fallback + settings | Tested (logic) + browser-verified (UI) | `tests/js` (23 node cases), `tests/test_web_alerts.py`; settings/persistence/live-region browser-checked on `:8171`; cue playback now also covered by the Playwright cue E2E |
| Admin console UI (tabbed SPA) | Tested (E2E) + browser-verified | **5 Playwright cases** (`tests/e2e/admin.spec.js`, mock-labelled): login gate, role-denied gate, tab switch + hazards list, moderation posts `{action,note}` + toast, system/diagnostics render |
| Compliance rules R2/R4/R8/R10 | Tested | `test_compliance` (7) |
| JS unit tests (`node --test`) | Tested | 23 cases (alert planner + settings), no npm/build needed |
| Playwright E2E | Tested | **PRESENT** — 12 headless-Chromium cases (`tests/e2e`: 7 rider + 5 admin), `npx playwright test` → `12 passed`; boots the real ASGI app, all providers mocked; wired into CI (`e2e` job). `@playwright/test` 1.64.1, Node 24 |
| Lint (`ruff`) | Tested | `ruff check` → `All checks passed!` (9 findings fixed in source) |
| `mypy` static type check | Tested | `mypy 1.11.2` → clean on `app`+`ml`+`scripts` (29 files); findings fixed in source (no `# type: ignore`); CI-blocking |
| `pyright` | Not run | not installed here (needs `npm install`); `mypy` is the authoritative type checker and passes |
| `pip-audit` dependency audit | Tested | `pip-audit 2.10.1` → 0 known vulnerabilities in the resolved env; CI-blocking |
| Performance: server throughput + client render/soak | Tested (measured) | `scripts/bench_server.py` → `docs/perf_server_bench.json`; batched scoring cut analyze p50 ~90→16 ms (~9.5× scoring, provably lossless), single-worker ~8→66 rps; client 0.024 ms/fix, flat heap/listeners, 0 duplicate GPS subs (browser-verified) |
| Live provider latency (Nominatim/OSRM) | Measured (live, manual run) | `scripts/bench_provider_live.py --confirm` → `docs/perf_provider_live.json`; geocode p50 21 ms, route p50 204 ms; not in CI (network) |
| Multi-worker / CI-automated Playwright perf | Not run | single-worker ceiling measured; multi-process + Playwright-harness variants open |
| Dockerfile + `.dockerignore` | In progress | authored; `node_modules`/playwright now gitignored + dockerignored; **`docker build` NOT verified** (engine absent) |
| GitHub Actions CI | In progress | `.github/workflows/ci.yml` authored with test / frontend-test / e2e / build jobs; not executed on a runner |
| Runbook / deploy docs | Completed | `MANUAL_RUNBOOK.md` |
| Verified research docs | Completed | 11 sources w/ URL + 2026-10-17 access date |
| Review 2 deck | Planned | content in REVIEW_2_PROJECT_SPECIFICATION; REQUIRES STUDENT INPUT |

## Exit-gate reflection

Phases 0, 3–9 core logic are Implemented & Tested; the ML baseline is retrained,
multi-seed verified, and documented (Gate 7/8). Phase 10 performance is now **measured and
optimised** (server before/after + client render/soak + live provider + bounded cache, all
in `PERFORMANCE_REPORT.md`); `ruff`, `mypy` (app+ml+scripts, 29 files) and `pip-audit` are
green. The **Playwright E2E gate is now met** (12 headless-Chromium cases — 7 rider + 5 admin,
mock-labelled providers, in CI). The loop is **not** at exit — remaining open: a live `docker
build` verification on a running engine (deferred by student request — no Docker needed as of
now), an in-suite `live`-labelled provider pytest (network egress kept out of CI), and a real
GitHub-Actions runner execution of the workflow; `pyright` is not run (mypy is authoritative).
See [LOOP_STATE.md](LOOP_STATE.md).

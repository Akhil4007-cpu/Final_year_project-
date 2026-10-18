# PERFORMANCE_REPORT

All figures below were produced by running the stated command on this machine
(Python 3.10.10, Windows dev box; Chromium browser) at the time of writing. This is a
noisy laptop, so treat single-run figures as indicative; ranges are shown where I
measured more than once. Numbers I could not measure here are labelled **NOT MEASURED**
rather than estimated — per project rule, a check is never reported as passed unless it
actually ran.

Re-runnable benchmarks (committed):

- `python scripts/bench_server.py` → `docs/perf_server_bench.json` (offline: provider
  mocked, real committed model loaded, API rate limit + public throttle raised so the
  figure is compute cost, not scaffolding).
- `python scripts/bench_provider_live.py --confirm` → `docs/perf_provider_live.json`
  (OPT-IN live network probe; paced >=1.1s/call with the configured User-Agent; not in CI).

## Model inference (from training pipeline, `eval_results.json`)

Workload: score each holdout section with the loaded `hist_gradient_boosting` model,
500 repeats. This is the raw **per-row** predict cost; the server batches it (below).

| Metric | Value |
|---|---|
| p50 | 5.0204 ms |
| p95 | 6.623 ms |
| max | 9.2199 ms |

The residual-corrected `hist_gradient_boosting` stays inside the 12 ms `LATENCY_BUDGET_P95_MS`
used for train-only selection; random forest (train-measured p95 ≈ 48 ms) was rejected.

## Artifact cold load

Workload: `joblib.load(ml/artifacts/model.joblib)`, 7 repeats.

| Metric | Value |
|---|---|
| p50 | 154.3 ms |
| min | 118.2 ms |
| max | 2969.6 ms |

The first read pays the disk-cache miss; steady-state is ~120–155 ms for the residual
model (larger artifact than the earlier direct-score model). The app loads **once at
startup**, so this is boot cost, not per-request cost.

## Scoring hot path — before / after batching (Phase-10 optimisation)

The original route path called `model.predict` **once per section**. Hist gradient
boosting predicts each row independently, so the whole route's scored sections were
collapsed into a single vectorized `predict((N, 22))` call (`ModelService.score_sections`,
[app/model.py:220](file:///d/FP_ROADGUARD/app/model.py#L220)); the per-section baseline
and feature math is unchanged. Workload: the committed serpentine route → 10 scored
sections, 30 alternating reps, same run/service (`bench_server.py`).

| Path | p50 | p95 | per-section mean |
|---|---|---|---|
| BEFORE — one predict per section (`score_section` loop) | 41.01 ms | — | 4.15 ms |
| AFTER — one batched predict for the route (`score_sections`) | 4.32 ms | — | 0.43 ms |

**≈ 9.5× faster on the scoring path**, with the p50 measured for both in the same run to
cancel warm-up drift.

**Lossless:** batched output was verified byte-for-byte identical to the per-section path
across `baseline_score / model_score / uncertainty_low / uncertainty_high / display_score
/ model_status / ood / disagreement` on the real committed GACE model (0 mismatches over
10 sections). Guarded by `tests/test_model.py::test_score_sections_batch_matches_per_section`,
which uses a row-ordering-sensitive fake so a mis-batch would fail.

## Route-analysis endpoint (`POST /routes/analyze`) — before / after

Workload: mocked provider, alternatives=2 routes, speed 45 km/h, real model loaded,
60 warm requests for the single-call distribution plus concurrency waves of 60.

| Metric | Before (per-section predict) | After (batched predict) |
|---|---|---|
| single-call p50 | ~91–97 ms (two runs) | 15.81 ms |
| single-call p95 | ~100–147 ms | 17.25 ms |
| single-call p99 | ~104–172 ms | 18.21 ms |
| throughput, concurrency 1 / 5 / 20 (single worker) | ~8–11 rps | 65.6 / 67.2 / 68.8 rps |

Reading: the endpoint is CPU-bound (throughput barely moves 1→20 on one worker — added
concurrency just queues behind the event loop). Batching removes the dominant per-row
predict overhead, cutting p50 ~6× and lifting single-worker throughput ~6–8×. For real
multi-client concurrency, run **multiple uvicorn workers** (`--workers N`) so each process
has its own CPU and one already-loaded artifact — documented in `MANUAL_RUNBOOK.md`.

## Geometry extraction (in-process, unchanged by the scoring optimisation)

Workload: serpentine polyline → `extract_sections` (validate + geometry).

| Stage | p50 |
|---|---|
| `extract_sections` (validate + geometry) | ~1.5 ms |

Geometry math stays cheap relative to the (now-batched) model scoring.

## Provider cache / debounce effectiveness (bounded)

Workload (`bench_server.py`): fetch an identical route twice, then flood 300 distinct
route keys.

| Check | Result |
|---|---|
| cold (first) call `cached` flag | `false` |
| warm identical call `cached` flag | `true` (served from cache, no re-fetch / re-score) |
| cache entries after 300 distinct keys | **256** (hard `CACHE_LIMIT`) |
| bounded? | yes (`<= 256`) |

So repeated requests for the same origin/destination within the 120 s TTL skip the OSRM
round-trip and the scoring pass entirely; the cache cannot grow without bound.

## Live provider latency (`LIVE`, `perf_provider_live.json`)

Public shared endpoints (OSRM demo + Nominatim), paced >=1.1s/call with the project
User-Agent. Small samples (n=4 geocode, n=5 route), warm keep-alive connection. **These
include the network round-trip and are variable by design** — not a stable contract.

| Call | p50 | p95 | max | notes |
|---|---|---|---|---|
| Nominatim geocode | 21.0 ms | 53.5 ms | 59.2 ms | 1 query legitimately returned "no match" (valid result, not a code error) |
| OSRM route (full geometry, alternatives) | 203.8 ms | 515.5 ms | 592.5 ms | first call pays TLS handshake |

The earlier server-side numbers (~15 ms p50 analyze) exclude this; total user-visible
route latency is dominated by this network leg, not our compute.

## Client (rider app, Chromium, browser-driven this session)

Driven with a mocked `navigator.geolocation` (the standard Playwright-style harness:
stub `watchPosition`, capture the app's real `onFix`, feed synthetic fixes) against the
live server. A real Charminar search → select → analyze → "Start advisories" flow was
run, then a fix burst + UI soak were measured.

| Metric | Value | How |
|---|---|---|
| Boot: DOMContentLoaded / load | 241 ms / 269 ms | Navigation Timing |
| Boot: JS heap used | 5.04 MB | `performance.memory` |
| Route render model | **Canvas** (Leaflet), 258 DOM nodes total | DOM census — few nodes, not one marker per section |
| Duplicate GPS subscriptions | **0** — 5 GPS-chip clicks → exactly 1 `watchPosition` | guard `if (state.gps.watchId !== null) return` at [app/web/app.js:278](file:///d/FP_ROADGUARD/app/web/app.js#L278) |
| Per-GPS-fix update latency | **0.024 ms** (300 fixes in 7 ms) | timed `onFix`→`updateNavigation`→`updateAdvisory` loop |
| Memory under 300-fix soak | flat, 3.17 MB before = after | `performance.memory` |
| Listener leak under 300 fixes | none (166 → 166) | counted `addEventListener` calls |
| Listener leak under 50 settings open/close cycles | **0** delta; heap 3.43 MB flat | `addEventListener` census |
| Console errors during session | one routine `401` on `/api/v1/auth/me` (anonymous bootstrap → signed-out), no CSP/JS errors | console log |

Reading: the per-fix client path (project + advisory match + DOM text update) costs
~24 µs, orders of magnitude below a GPS cadence (≈1 Hz); heap and listener counts are
flat across both a fix soak and repeated sheet open/close. The canvas renderer keeps the
DOM tiny regardless of section count.

## NOT MEASURED (honest remaining open items)

- **Multi-worker / cross-process load test** — the single-worker CPU-bound ceiling and
  the batching win are measured; running N uvicorn workers under sustained concurrent
  clients was not (needs a load generator against a multi-process server).
- **Playwright E2E + client render timing inside a CI harness** — the client numbers
  above are from a manual browser session this run, not an automated, re-runnable
  Playwright suite (npm/network gated). Labelled `manual`, not `automated`.
- **Long memory soak (hours)** — flat memory shown over 300 fixes / 50 cycles, not a
  multi-hour drift test.

## Conclusion

The controllable server path is now measured end-to-end and **optimised**: batching the
route scoring cut analyze p50 from ~90 ms to ~16 ms and lifted single-worker throughput
~6–8× (provably lossless), with an index-backed DB, a bounded provider cache that skips
re-fetch+re-score on repeats, and a startup-once artifact load. Live provider latency and
the client path (24 µs/fix, flat heap, zero duplicate listeners/subscriptions) are now
quantified rather than asserted. The remaining open items are multi-process and
CI-automated variants of measurements already done manually.

# LIMITATIONS

Project-wide, plain-spoken limits of RoadGuard AI. ML-specific limits are in
[GEOMETRY_ML_LIMITATIONS.md](GEOMETRY_ML_LIMITATIONS.md); this is the umbrella.

## What RoadGuard is, and is emphatically not

- It **is** a real-time *geometry-challenge* advisory: "this mapped curve is tight, at
  your assumed speed band it scores high — ease off." 
- It **is not** an accident predictor, safety score, or insurance input. The word "safe"
  is never shown to a rider; ranking is "lowest_geometry_challenge", and the disclaimer
  "Geometry challenge indicator — not an accident probability" ships with the score
  (R4, enforced by `test_no_affirmative_risk_marketing_phrases`).

## Data & evidence

- **Synthetic-only training.** No real crash data, GPS traces, or Indian road
  observations exist anywhere in the system (R2, R10). Accuracy = agreement with a
  physics label, not with reality.
- **No accident CSV / blackspot tables / invented weather or traffic.** These are out of
  scope by rule; their absence is stated, not disguised with placeholders (R1).
- **OSM/OSRM geometry quality governs everything downstream.** Sparse or coarse
  polylines can make sections unscorable; that returns `insufficient_evidence`, never a
  zero ("no data" ≠ "safe", R5).
- **Speed/grade/road-class are advisory bands or missing-flagged assumptions**, not
  measured or legal values.

## Scope of what is covered

- Only 7 synthetic curve scenario types; real intersections, roundabouts, merges, surface
  defects, mixed traffic, weather, banking, friction, and rider behaviour are **not**
  modelled (R7 — every advisory is labelled advisory-only).
- India-restricted geocoding only; the system makes no claim outside that region.

## Engineering limits

- **Rate limiting is in-process** (`RateLimiter`): correct for one worker only; not a
  distributed guarantee. Multi-worker/production needs a shared store.
- **Client GPS trust boundary is the browser.** The server sees discrete waypoints on
  request, not a continuous trace — good for privacy, but means deviation/advisory
  timing depends on the device's GPS quality and the single `watchPosition` feed.
- **Public OSRM demo** is used for routing; it has usage limits unsuitable for public
  launch. Self-host/commercial routing plan is a pre-launch requirement, not yet done.
- **CSP allows `style-src 'unsafe-inline'`** (vendored Leaflet inline styles); script-src
  stays strict. Documented in [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md).

## Verification limits (honesty)

- The 91-test automated suite covers geometry, baseline, aggregation, advisory, security,
  model, API, and compliance. **Frontend/E2E behaviour was verified manually in the
  browser this session, not by an automated harness.** No Playwright/JS-unit tests exist
  yet.
- `ruff`, `mypy` (app+ml+scripts, 29 files) and `pip-audit` have been **run clean** here
  and are CI-blocking; `pyright` has **not** been run (needs npm; mypy is the authoritative
  type checker). See [LOOP_STATE.md](LOOP_STATE.md).
- Client render cost, per-fix update latency, memory soak and server throughput are now
  **measured** (`PERFORMANCE_REPORT.md`), including a provably-lossless scoring batch.
  Remaining perf limits: multi-process (uvicorn `--workers`) load and an automated CI
  Playwright harness were not run — the client figures are from a manual browser session.

## Student-only inputs still required (R11)

Team & supervisor names, Review 1 feedback, guide confirmation of the synthetic-only
scope, and the Review 2 date/slide logistics are marked `REQUIRES STUDENT INPUT` in
[../README.md](../README.md) and the Review 2 package; they cannot be filled by the code.

# REAL_ROUTE_CHECK — live pipeline run on five real Hyderabad pairs

**Label: `live`.** Produced by `scripts/real_route_check.py --confirm`, an **opt-in,
network-dependent probe that is NOT part of CI** (see README → Test). It hits the public
Nominatim and OSRM instances, paced at ≥1.1 s per request with the configured
User-Agent, and runs the **real production path**: geocode → OSRM route → geometry
validation → section extraction → physics baseline `physics_v2r_v1` → GACE.

**This is a PLAUSIBILITY CHECK ONLY — it makes no accuracy claim of any kind.**
No ground truth exists for these routes, so nothing here measures error. The synthetic
held-out suite in `docs/TESTING_AND_EVALUATION.md` §7.5 remains the only place error is
measured. Raw output: [`real_route_check.json`](real_route_check.json)
(`"kind": "plausibility check only — NOT an accuracy test"`).

Run date: 2026-10-18 (UTC `measured_at_utc` in the JSON). The probe was executed three
times in this session; **all three runs produced byte-identical aggregate figures**
(1247 sections, 1176 scored, 182 fallback, 162 advisories, coverage 0.9568–0.9831),
because OSRM is deterministic for a fixed origin/destination pair.

## Command

```bash
python scripts/real_route_check.py            # refuses to run without --confirm
python scripts/real_route_check.py --confirm  # live; writes docs/real_route_check.json
```

## The five pairs (first alternative shown)

| # | route (live geocode) | state | sections (curve/scored) | coverage | smallest radii (m) | radii <10 m / <25 m | median radius (m) | advisories | fallback sections | band |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Charminar → Secunderabad Junction | scored | 170 (126/159) | 96% | 8, 8, 9 | 3 / 15 of 135 | 312.8 | 33 | 33 | low |
| 2 | Golconda Fort → HITEC City | scored | 146 (115/139) | 96% | 7, 9, 10 | 3 / 14 of 117 | 227.29 | 26 | 25 | low |
| 3 | Hussain Sagar → Gachibowli | scored | 182 (136/172) | 97% | 9, 13, 14 | 1 / 9 of 143 | 504.14 | 13 | 15 | low |
| 4 | Kukatpally → Banjara Hills | scored | 134 (85/126) | 98% | 7, 10, 11 | 2 / 6 of 100 | 623.34 | 12 | 14 | low |
| 5 | Mehdipatnam → Uppal (Vaishnavi Olympiad School) | scored | 147 (112/138) | 96% | 7, 8, 12 | 2 / 11 of 117 | 306.26 | 18 | 23 | low |

Place names above are truncated forms of the live Nominatim `display_name` values stored
in the JSON; nothing is hard-coded — both endpoints of every pair were resolved at run
time.

## Aggregate (from `real_route_check.json → aggregate`)

- **5/5 pairs geocoded and routed; 8 route records** (three pairs returned a second
  OSRM alternative). **Validation failures: 0** — no `insufficient_evidence`, no
  `unavailable`, no provider error; `states` is `{"scored": 8}`.
- **1247 sections, 1176 scored (94.3%)**; route coverage **95.7 %–98.3 %**; distances
  11.0–18.2 km.
- **Disagreement fallback fired on 182/1176 scored sections = 15.5 %**, and
  `ood_sections` totalled 216. Model status split: 994 `model_estimate`, 182
  `baseline_fallback`, 71 `unavailable`.
- **Band split: 873 low / 160 moderate / 143 high / 71 unavailable**; every route-level
  band came out `low`. Three pairs returned two alternatives: `comparison.state` was
  `comparable` twice and `ranked` once, with `score_gap` 1.32–5.60 and coverage spread
  0.0035–0.0133; the two single-alternative pairs returned `comparison: null` rather than
  inventing a ranking.
- **Geometry quality: all 8 route records were flagged `highly uneven point spacing`**
  (one also `removed 1 duplicate point(s)`). Real OSM polylines are far less regular than
  the synthetic evaluation set.
- **Radius census over real geometry: 987 radius-bearing sections, median per route
  227–623 m, but 84 sections under 25 m and 15 under 10 m, minimum 3.96 m.**

## What looks plausible

1. Coverage and section counts are in the same range as the synthetic suite, so real
   Hyderabad geometry is *scorable* by the extractor rather than rejected.
2. Median radii of 227–623 m and an all-`low` route band are what Indian urban arterials
   should look like: mostly gentle geometry, a small sharp tail.
3. The disagreement guard fires far less on real map data (15.5 %) than on the synthetic
   degraded slice (61–89 %, see
   [GEOMETRY_ML_LIMITATIONS.md](GEOMETRY_ML_LIMITATIONS.md)) — i.e. the degraded slice is
   a deliberately pessimistic stress case, not a picture of ordinary OSM quality.

## What does NOT look plausible (disclosed, not fixed)

- **Sub-10 m radii cannot be real road geometry.** A 3.96 m radius at the assumed 50 km/h
  band implies `v²/R` ≈ 48.7 m/s² ≈ **5.0 g** of lateral demand, several times what a
  two-wheeler can generate on asphalt. These come from bunched OSRM vertices on short, noisy urban polylines — exactly the condition the
  `highly uneven point spacing` flag describes — and **all 84 sections under 25 m radius
  landed in the `high` band**, i.e. 84 of 143 high-band sections (58.7 %) on real routes
  sit in that implausible tail.
- Consequence, stated plainly: on real data the **per-section** high band and the 162
  advisories are inflated by mapping artefacts. Route-level aggregation damped it (every
  route still read `low`), which is the coverage-weighted design working, but this is a
  genuine weakness of a polyline-only estimator, not a passing grade.
- **No minimum-radius floor was added**, because choosing one is a modelling decision that
  would change the label the model was trained against and require a re-train/re-eval
  cycle; a plausibility probe must not silently retune the estimator. It is recorded in
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md) as an open item with these numbers attached.
- Speed here is the **assumed 50 km/h advisory band** (`inputs.speed_source =
  "assumed_unknown"`, `speed_is_advisory = true`), not measured riding speed; the rider
  UI's speed-aware note is a separate, mock-tested path.

## Rider UI at 390 px (labelled `mock`, NOT live)

Generated by `npx playwright test tests/e2e/screenshots.spec.js` (viewport 390×844, the
same width the responsive tests assert). **Every `/api/v1/*` response and every map tile
in these three captures is mocked by `tests/e2e/_harness.js`** — the shapes, bands and
advisories are the harness's, not OSRM's. What is real is the shipped frontend.

| File | state captured |
|---|---|
| [rider-1-route-overview-390.png](screenshots/rider-1-route-overview-390.png) | analysed route panel: distance, provider ETA, challenge score 33.1 `moderate`, "99% of 1.6 km scored · 20 m without usable geometry", riding-speed assumption selector |
| [rider-2-advisory-moderate-390.png](screenshots/rider-2-advisory-moderate-390.png) | in-curve advisory, moderate band, speed note reads *matching* (45 km/h GPS vs the 45 km/h scored band, 0.42 g) |
| [rider-3-advisory-high-speed-above-390.png](screenshots/rider-3-advisory-high-speed-above-390.png) | in-curve advisory, high band, speed note reads *above*: "At ~90 km/h (GPS) this 38 m curve needs 1.68 g lateral — 4.00× the 0.42 g scored band. Geometry indicator, not an accident probability." |

Capturing these screenshots exposed a real harness defect: the tile mock used the glob
`**/tile.openstreetmap.org/**`, which does **not** match Leaflet's
`{a,b,c}.tile.openstreetmap.org` subdomains, so the "mock" E2E suite had been silently
loading **live OSM tiles**. Fixed in `_harness.js` with a subdomain-agnostic pattern; the
full Playwright suite passes (17 tests) with no external tile traffic.

## Non-claims

This file asserts none of the following: that the scores match real riding difficulty,
that the model is accurate on Indian roads, that any output predicts accidents, or that
the public OSRM demo will behave the same at another time. It shows only that the shipped
pipeline runs end-to-end on real map data and where its output stops looking believable.

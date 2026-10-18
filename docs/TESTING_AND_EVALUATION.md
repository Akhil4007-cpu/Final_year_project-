# TESTING_AND_EVALUATION

This records the **exact commands and actual output** for the automated suite. Mocked
tests and live-provider manual checks are labelled separately — a mocked test is never
described as a live one (rule of the plan §12).

## Automated suite — exact command and real output

```
$ python -m pytest -q
112 passed, 1 warning in 9.32s
```

(The single warning is a Starlette/httpx deprecation notice from `TestClient` itself, not
from project code. Earlier baselines were 91, then 105, then 108 (the 105→108 step added the
TASK-2 speed-aware advisory and route-deviation wiring tests); the current suite is 112 —
the +4 are `tests/test_fallback_audit.py`, which pins the published disagreement-fallback
table.)

Environment: Python 3.10.10, pytest 8.3.2, fastapi.testclient `TestClient` (used as a
context manager so the app lifespan — DB migration + artifact load — runs).

## Per-module breakdown (`--collect-only`, 112 backend total)

| File | Tests | Covers | Level |
|---|---|---|---|
| `tests/test_geo.py` | 15 | haversine, `validate_geometry` (rejects bool/non-numeric/out-of-range, dedup, coarse), `extract_sections` (known-radius arcs, straights, curves), `project_to_local`, point-to-polyline distance | Unit |
| `tests/test_baseline.py` | 10 | `challenge_score` bounds/None, `score_band` thresholds, `baseline_for_section`, version strings | Unit |
| `tests/test_aggregation.py` | 10 | low coverage → `insufficient_evidence`, weighted avg, missing never zero-scored, coverage boundary, uncertainty band, `compare_routes` (unscored/rejected, spread rejection, comparable → no recommendation, ranked when gap ≥5) | Unit |
| `tests/test_advisory.py` | 6 | only curves ≥55, boundary inclusive, distance sort, lead/clear/cooldown/band/message, provenance, uncertainty | Unit |
| `tests/test_security.py` | 15 | email/password validation, PBKDF2 hash/verify roundtrip + random salt, session tokens, `RateLimiter` isolation + block, audit JSON | Unit |
| `tests/test_model.py` | 13 | missing/corrupt artifact, feature-schema mismatch rejection, synthetic_training flag, model_estimate vs baseline_fallback (>20 disagreement), conformal OOD widening, predict raises when unavailable, residual prior correction, legacy direct score, **batch-vs-per-section `score_sections` equivalence (row-order sensitive)** | Unit/Integration |
| `tests/test_api.py` | 18 | health/meta, register requires CSRF header (403), register/login/me, duplicate 400, weak pw 400, wrong pw 401, cookie HttpOnly+SameSite=lax, hazard auth gate + unverified default, admin role gate (403)/anonymous (401), moderate+audit `hazard_verified`, self-deactivate blocked, logout, login rate limit → 429 + Retry-After | Integration |
| `tests/test_api_routes.py` | 6 | **`POST /routes/analyze` with a MOCKED provider (`mock`-labelled, offline):** scored 2-route response + advisories + provider/model provenance, R4 disclaimer / no "safe route", provider 503 → `provider_unavailable`, OSRM NoRoute → `insufficient_evidence` (never invents a route), missing client header → 403, out-of-range coords → validation reject | Integration |
| `tests/test_web_alerts.py` | 7 | static wiring of the staged-alert + settings feature in `app/web/` (vibration/WebAudio/webkit + cue de-dup key + reduced-motion + localStorage load + assertive live region + disclaimer copy), **speed-aware advisory wiring (`speedAwareness`/`lateralDemandG`/`coords.speed`/`#advisory-speed`)**, **the speed note's banned-wording audit (no speed instruction)**, **route-deviation wiring (deviation counter, `route_deviation` chip state, accuracy-scaled threshold, `#router-note`)** | Static |
| `tests/test_fallback_audit.py` | 4 | the published disagreement-fallback audit: required slices present, regenerated model-only MAE agrees with committed `eval_results.json` (±0.0015), `threshold_retuned` is false **and** the shipped `DISAGREEMENT_THRESHOLD` is the one recorded in the audit rule (so changing the threshold breaks CI until the audit is re-run), plus the finding itself (fallback rate >0.5 and served-worse-than-model on degraded; served-better-than-model on unseen curve type) | Unit/Regression |
| `tests/test_compliance.py` | 7 | R2 grep, R4 phrase audit, "accident probability" only negated, R10 import graph, R8 secret scan, R3/R5 error codes, R7 assumptions | Static/Compliance |
| `tests/test_db_backup.py` | 1 | populate→`backup_database`→restore loses 0 rows, `PRAGMA integrity_check` ok, restored DB still enforces role gate + returns verified hazard | Integration |

## Real bugs found and fixed (in source, not tests)

Per project rule, tests were **not** weakened; the source was corrected:

1. **Trip summary rendered empty** — `app/web/app.js` `renderTripSummary` passed a single
   `<dl>` node where `detailBlock` iterates an array. Fixed to wrap `[createKv(entries)]`
   at [app/web/app.js:1060](../app/web/app.js#L1060). Found via a `window.onerror` probe
   because nothing appeared in the console.
2. **Audit action misspelled** — `app/hazards.py` produced `hazard_verifyd`/`hazard_rejectd`.
   Corrected to emit `hazard_verified`/`hazard_rejected` in
   [app/hazards.py](../app/hazards.py). Now asserted by
   `test_admin_moderate_and_audit`.
3. **The advisory showed "0 km/h measured" when no speed was measured** — `Number(null)` is
   `0` in JS, so a device that does not report ground speed looked like a stationary rider
   and the note claimed the band was over-*under*-used. Fixed in
   `app/web/app.js::onFix` by testing for an absent/invalid speed before coercion, so the
   note now reads `speed_unavailable` and discloses the assumed band. Found by the
   no-speed Playwright case; **fixed in source, not by relaxing the test**.
4. **The "mock" E2E harness was loading live OSM tiles** — its tile stub used the glob
   `**/tile.openstreetmap.org/**`, which does not match Leaflet's
   `{a,b,c}.tile.openstreetmap.org` subdomains. Found while capturing the 390 px rider
   screenshots (real Hyderabad street labels appeared in the image). Fixed with a
   subdomain-agnostic pattern in [tests/e2e/_harness.js](../tests/e2e/_harness.js).

One test assertion was corrected because it encoded *my wrong assumption*, not a code bug:
`test_project_to_local_origin_is_zero` was rewritten to assert the actual (correct)
behaviour — first longitude maps to x=0, y is centroid-relative. The source was right;
the test was.

## Frontend / E2E — status (labelled honestly)

- **Manual browser verification (done this session, not automated):** rider home, live
  Nominatim search, live OSRM route (30.8/33.1 LOW, 99% coverage, comparable → no
  recommendation), advisory countdown, destination-reached, trip summary, login,
  auth-gated report submission with unverified labelling; admin console all 5 tabs,
  moderation persistence, role gate, sign-out, XSS-safe rendering. **Alert settings
  re-verified this session** (server on `:8171`): gear opens the sheet, Visual/Vibration/
  Sound toggles persist to `localStorage` across reload, the capability note renders, and the
  high-band assertive `role="alert"` live region is present — no JS errors beyond the
  expected signed-out 401 on `/api/v1/auth/me`.
- **Automated JS-unit tests: PRESENT for the pure alert logic** (no browser/npm needed —
  Node's built-in runner). `node --test "tests/js/**/*.test.js"` → **31 cases green**:
  `alerts.test.js` (capability detection incl. iOS no-vibration, intensity escalation,
  haptic→audio→visual fallback, reduced-motion suppression, assertive escalation, **the
  speed layer: `normaliseSpeedKmh` rejection of null/undefined/""/NaN/negative/implausible
  values while accepting 0, `lateralDemandG` in g, and the above/matching/below ratios with
  their 1.15 / 0.87 boundaries plus the no-instruction wording loop**) and
  `settings.test.js` (normalisation, corrupt/absent-storage and quota-error resilience,
  round-trip persistence). `tests/test_web_alerts.py` keeps the Python-only CI authoritative
  about the wiring's presence in the shipped frontend.
- **Automated Playwright E2E: PRESENT.** `tests/e2e/` (`rider.spec.js`, `admin.spec.js`,
  `screenshots.spec.js`, `_harness.js`) boots the **real ASGI app** via the `playwright.config.js` `webServer` and
  drives both SPAs in headless Chromium. **17 cases green** (`npx playwright test` →
  `17 passed`; 10 rider + 5 admin + 2 screenshot). **Rider (10):** startup (shell + GPS chip + search, no uncaught JS errors),
  search→route (scored panel, provider provenance, and the browser actually sending the
  `X-RoadGuard-Client: web` header on the analyze POST), navigation lifecycle (start →
  destination-reached → trip summary), live-GPS→staged advisory cue (banner `data-band=high` +
  the assertive `role=alert` region populated), hazard submit (unverified toast),
  insufficient-evidence (never invents a route), provider-failure (graceful unavailable state),
  **route deviation (F14): two off-polyline fixes → advisories pause + `route_deviation` chip +
  `#router-note`, and the on-route fix clears it**, **speed-aware note: a 90 km/h device speed
  against the 45 km/h scored band renders `data-status="above"` with the g figure**, and
  **the no-speed fallback: `speed: null` renders `data-status="speed_unavailable"` and says the
  band was assumed**. The last case is what caught a real bug — `Number(coords.speed)` coerces
  `null` to `0`, which would have displayed "0 km/h measured" instead of disclosing the absence.
  **Admin (5):** signed-out boot → login gate → admin login reveals console (login POST carries
  the client header), non-admin role is denied the console, tab switching shows only the selected
  panel and renders the hazards list, moderation posts `{action:"verify", note}` + shows the
  `verified.` toast + closes the dialog, and the system tab renders diagnostics. **Screenshots
  (2 cases):** regenerate the three 390 px rider captures in `docs/screenshots/` — analysed
  route panel, moderate in-curve advisory with a *matching* speed note, high in-curve advisory
  with an *above* speed note — asserting the DOM state (band, `data-status`, settled opacity)
  before each capture and that the files exist. **Every
  `/api/v1/*` response in these tests is MOCKED and labelled `mock`** (geocode, analyze, hazards,
  auth, all `/admin/*`) and OSM tiles are stubbed on every `*.tile.openstreetmap.org` subdomain
  (see bug 4 above) — no OSRM/Nominatim/model dependency, so it is
  deterministic and CI-safe. It verifies the **frontend state machine + layout + cue playback +
  admin gating**; the analyze/admin *contracts* are covered offline by `tests/test_api_routes.py`
  and `tests/test_api.py`. Requires a dev-only npm dependency (`@playwright/test` 1.64.1, Node 24)
  — `npm ci && npx playwright install chromium`.
- **In-suite `live`-labelled pytest: NOT PRESENT.** The live paths exist only as opt-in,
  network-dependent scripts that refuse to run without `--confirm`:
  `scripts/bench_provider_live.py --confirm` (Nominatim/OSRM round-trip p50/p95) and
  `scripts/real_route_check.py --confirm` (five real Hyderabad pairs end-to-end →
  [REAL_ROUTE_CHECK.md](REAL_ROUTE_CHECK.md) + `docs/real_route_check.json`, **plausibility
  only, no accuracy claim**). Neither is a CI test (network egress is intentionally kept out
  of CI). Tracked in [LOOP_STATE.md](LOOP_STATE.md).

## Static analysis / lint

- **`ruff` 0.6.2 — run, clean.** `python -m ruff check app ml scripts tests` →
  `All checks passed!` (exit 0). Initial run surfaced 9 findings (5 dead imports + 4
  intentional `sys.path`-bootstrap E402 in `create_admin.py`); the dead imports were
  removed in source and the bootstrap imports annotated `# noqa: E402`. Suite still green
  after the edits (91 at that time; the current baseline is 112 backend + 31 JS).
- **`mypy` 1.11.2 — RUN, clean.** `python -m mypy app ml scripts --ignore-missing-imports`
  → `Success: no issues found in 31 source files` (exit 0; 31 files now, up from 27 after
  the Phase-10 benchmark scripts and the live/audit scripts were added). The first run surfaced **14 real
  findings**, all fixed in source (no `# type: ignore` suppression): a `float | None` reused
  under a `float` binding in `geo.py` (renamed the second loop's locals); two
  `int(cursor.lastrowid)` where the DB-API type is `int | None` (narrowed with
  `typing.cast`); a `HazardService.list` method that shadowed the builtin `list` inside the
  class body (renamed to `list_in_bbox`, call site in `api.py` updated), plus bbox-guard
  narrowing; a `_build_profile` `profile` closure redefined per branch with differing
  signatures (each branch now returns a uniquely named `arc_profile` / `reverse_profile` /
  `compound_profile`); and a missing PyYAML stub (`types-PyYAML` pinned in
  `requirements-dev.txt`). **`pyright` was NOT run** — it needs an `npm` download; `mypy` is
  the authoritative type check here and is wired into CI as a **blocking** step. Renaming in
  `generator.py` was verified behaviour-neutral: dataset SHA-256 is still
  `5e92447a370b2646c8929a434a577f9decf5694afb28e3c2d76ce93415d5db9d` over 1180 rows.
- **`pip-audit` 2.10.1 — RUN, clean.** `python -m pip_audit -r requirements.txt` →
  `No known vulnerabilities found` (exit 0), querying the live PyPI advisory DB. CI runs it
  as a **blocking** step. The advisory wording in this project ("advisory", "advisor") is the
  product term, not a security notice.

## Reproducibility of ML evaluation

```
$ python -m ml.train --seed 42 --per-type 140
# regenerates ml/artifacts/{model.joblib, eval_results.json, ...}; dataset SHA-256
# 5e92447a370b2646c8929a434a577f9decf5694afb28e3c2d76ce93415d5db9d

$ python -m ml.evaluate_seeds
# re-runs the whole pipeline across 5 data-generation seeds and writes
# ml/artifacts/multi_seed_metrics.json (headline mean +/- 95% CI, incl. degraded RMSE and
# degraded R^2 added for Review 2)

$ python -m ml.fallback_audit
# re-measures how often the runtime disagreement guard serves the baseline instead of the
# model, and what that costs, on the degraded / noise-sweep / OOD-radius / OOD-type slices;
# writes ml/artifacts/fallback_audit.json. Hard consistency guard: if the regenerated
# model-only MAE differs from committed eval_results.json by >0.0015 the script aborts.
# The threshold sweep is run on the CALIBRATION split only; DISAGREEMENT_THRESHOLD was
# NOT retuned (fallback_audit.json records "threshold_retuned": false).
```

Verified on 2026-10-18: re-running `ml.evaluate_seeds` reproduced **every** committed
per-seed deterministic metric exactly (clean R²/MAE, degraded MAE, OOD-radius and OOD-type
MAE, empirical coverage, monotonicity, leakage) — only the wall-clock latency fields moved
(p50 mean 5.2124 ms vs 6.2159 ms committed; p95 7.3937 ms vs 8.8547 ms — machine-load noise
on a laptop, not a code change).
Model-seed stability: the HistGradientBoosting estimator is deterministic on fixed data,
so varying only `random_state` across 5 seeds gives an identical degraded MAE (± 0.0).
Genuine robustness is the 5 **data**-seed run (`evaluate_seeds`), which regenerates
scenarios, re-selects by train-only CV and re-calibrates the band; headline mean ± 95% CI
is written to `multi_seed_metrics.json`. Leakage audit shows zero train/test scenario
overlap. Numbers in [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) and
[GEOMETRY_ML_DESIGN.md](GEOMETRY_ML_DESIGN.md) come from `eval_results.json`, not from
estimates.

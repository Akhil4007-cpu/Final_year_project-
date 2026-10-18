# PROJECT_AUDIT — Phase 0

RoadGuard AI is a **new, from-scratch** build in this repository. It was not derived
from, copied from, or wired to any earlier project. This audit records the real,
measured state of the code as of this writing. Every count below was produced by
running the command shown, not estimated.

> **Read this as a Phase-0 snapshot.** The counts in the top blocks (commits, test total,
> source size) are what was true when the audit ran and are deliberately left un-edited so the
> history stays checkable. The current status of every row that has since changed is in
> [§ "Refresh — measured 2026-10-18"](#refresh--measured-2026-10-18) at the foot of this file.

## Repo state (measured)

- Branch: `main`. Commits: **0** (working tree fully untracked — nothing has been
  committed yet; committing is deferred until the student asks).
- Python: 3.10.10. FastAPI 0.141.1, Pydantic 2.13.5, scikit-learn 1.7.2,
  joblib 1.5.3, numpy 1.26.4, pytest 8.3.2 (see `requirements.txt` /
  `requirements-dev.txt`).
- Source size: 5,132 lines of Python under `app/`, `ml/`, `scripts/`; 2,800 lines of
  browser JS under `app/web/`.

## Non-negotiable rule checks (measured)

| Rule | Check run | Result |
|---|---|---|
| R2 — no accident CSV / fake blackspots | `grep -rniE "accident.*csv\|blackspot" app/` | **ZERO matches** |
| R10 — runtime never imports ML training | `tests/test_compliance.py::test_runtime_never_imports_ml_training` | PASS |
| R4 — geometry score ≠ accident probability | `tests/test_compliance.py::test_no_affirmative_risk_marketing_phrases`, `test_accident_probability_only_in_negated_disclaimers` | PASS |
| R3/R5 — missing data is typed, never zero-risk | `tests/test_compliance.py::test_error_codes_expose_unavailable_not_zero` | PASS |
| R8 — no hardcoded secrets | `tests/test_compliance.py::test_no_hardcoded_secrets_in_source` | PASS |
| R7 — advisory labelling present | `tests/test_compliance.py::test_baseline_assumptions_state_indicator_not_probability` | PASS |

All 91 automated tests pass (`python -m pytest -q` → `91 passed in 4.97s`) — a Phase-0 count,
superseded by the refresh section at the foot of this file. Full
per-module breakdown is in [TESTING_AND_EVALUATION.md](TESTING_AND_EVALUATION.md).

## Feature inventory

Statuses: Implemented&tested · Incomplete tests · Partial · Mocked · Unavailable ·
Dead · Not implemented.

| Feature | Files | Endpoints | DB | Providers | Tests | Status | Limits / notes | Action |
|---|---|---|---|---|---|---|---|---|
| Health / readiness | [app/main.py:176](../app/main.py#L176) | `/health`, `/ready` | — | — | `test_api` | Implemented&tested | — | none |
| Auth (register/login/me/logout) | [app/auth.py](../app/auth.py), [app/security.py](../app/security.py) | `/auth/*` | `users`,`sessions` | — | `test_api`,`test_security` | Implemented&tested | PBKDF2 260k, HttpOnly cookie | none |
| Account deletion | [app/auth.py](../app/auth.py) | `DELETE /auth/account` | cascade | — | `test_api` | Implemented&tested | anonymises verified hazards | none |
| Rate limiting | [app/security.py](../app/security.py) | login/route/hazard | — | — | `test_api`,`test_security` | Implemented&tested | in-process (single worker only) | see KNOWN_ISSUES |
| Geocode | [app/providers.py](../app/providers.py) | `/geocode` | — | Nominatim (live) | `mock` in CI + opt-in `live` probe | Implemented&tested (mock) · live path exercised by scripts, not a CI test | India-restricted | **2026-10-18:** offline mock tests added; `bench_provider_live.py --confirm` measures live latency; in-suite `live` pytest still open (network egress kept out of CI) |
| Route analysis | [app/analysis.py](../app/analysis.py) | `POST /routes/analyze` | — | OSRM (live) | `test_aggregation`, `test_api_routes` (6, mock), 17 Playwright E2E | Implemented&tested | up to 3 alternatives | **2026-10-18:** contract covered offline incl. provider-503 and NoRoute paths; live route analysis covered by `real_route_check.py --confirm` |
| Geometry / sections | [app/geo.py](../app/geo.py) | — | — | — | `test_geo` (15) | Implemented&tested | analytical arc/straight/S-curve cases | none |
| Physics baseline | [app/baseline.py](../app/baseline.py) | — | — | — | `test_baseline` (10) | Implemented&tested | `v²/R`, label_v1 | none |
| Route aggregation | [app/aggregation.py](../app/aggregation.py) | — | — | — | `test_aggregation` (10) | Implemented&tested | MIN coverage 0.60 | none |
| Advisory engine | [app/advisory.py](../app/advisory.py) | — | — | — | `test_advisory` (6) | Implemented&tested | score≥55, lead 150 m | none |
| ML model service | [app/model.py](../app/model.py) | `/model/status` | — | — | `test_model` (9) | Implemented&tested | loads artifact at startup | none |
| Synthetic pipeline | [ml/generator.py](../ml/generator.py), [ml/train.py](../ml/train.py) | — | — | — | reproduced offline | Implemented&tested | seed 42, 1180 rows | none |
| Hazards lifecycle | [app/hazards.py](../app/hazards.py) | `/hazards*` | `hazards`,`hazard_votes` | — | `test_api` | Implemented&tested | unverified by default, 24h TTL | none |
| Admin console | [app/api.py](../app/api.py), [app/web/admin.js](../app/web/admin.js) | `/admin/*` | all | — | `test_api` | Implemented&tested | role gate, DOM-only render | none |
| Rider UI + GPS FSM | [app/web/app.js](../app/web/app.js) | — | — | browser GPS (mocked in E2E) | 31 `node --test` + 17 Playwright E2E | Implemented&tested (E2E automated 2026-10-18) | single watchPosition | **2026-10-18:** Phase-0 action "add Playwright e2e" is **done** — `tests/e2e/` drives the real ASGI app with `mock`-labelled providers; physical-device GPS is still not evidenced |

## Dead / duplicate code

`app/provenance.py`, `app/features.py`, `app/version.py` are all referenced by runtime
or tests; no orphan modules found in the import graph exercised by the suite.
`app/audit.py` exposes read helpers used by admin endpoints. Nothing classified dead.

## Data / artifacts present (not code)

`data/*.sqlite3` and `ml/artifacts_debug/` are local scratch from manual browser
verification; they are excluded from packaging (see [KNOWN_ISSUES.md](KNOWN_ISSUES.md)
cleanup note) and are not imported by any test.

## Backup / restore

`app/db.py::backup_database` copies the DB via the SQLite backup API. **Restore
verification is now evidenced** by `tests/test_db_backup.py`: a populated DB (3 users,
2 hazards, votes, moderation, sessions) is backed up, the copy loses **zero rows**, passes
`PRAGMA integrity_check`, and the restored DB still enforces the role gate and returns the
verified hazard. Phase-0 restore gate: **closed**.

## Refresh — measured 2026-10-18

Re-run of the same quantities after the six-task brief, with the commands, so the Phase-0 blocks
above can be read as history rather than current status.

| Quantity | Phase 0 | Measured 2026-10-18 | Command |
|---|---|---|---|
| Git commits | 0 (all untracked) | 2 committed before this session's work; **nothing pushed** — the remote step is the student's | `git log --oneline` |
| Backend tests | 91 | **112 passed, 1 warning** (`TestClient` deprecation) | `python -m pytest -q` |
| Frontend JS unit tests | — (none) | **31 / 31 pass** | `node --test "tests/js/**/*.test.js"` |
| Browser E2E | 0 ("add Playwright e2e") | **17 passed** (10 rider + 5 admin + 2 screenshot), `mock`-labelled providers, stubbed tiles | `npx playwright test` |
| Per-file backend counts | — | geo 15, baseline 10, aggregation 10, advisory 6, security 15, model 13, api 18, api_routes 6, web_alerts 7, compliance 7, fallback_audit 4, db_backup 1 | `python -m pytest --collect-only -q` |
| Python source size | 5,132 lines | **6,363 lines** under `app/`, `ml/`, `scripts/` | `find … \| xargs wc -l` |
| Browser JS size | 2,800 lines | **3,296 lines** under `app/web/` excluding the vendored Leaflet; `app.js` 1869, `admin.js` 827, `alerts.js` 226, `settings.js` 55 | `wc -l` |
| Static gates | not run | `ruff` clean · `mypy` clean on **31 source files** · `pip-audit` **0 known vulnerabilities** — all CI-blocking | see [TESTING_AND_EVALUATION.md](TESTING_AND_EVALUATION.md) |
| ML headline | pre-redesign | seed-42 clean R² **0.9948**, degraded MAE **14.142** vs baseline 27.826; 5-seed clean R² 0.9975 [0.9960, 0.9990]; degraded R² **0.3090 [0.2432, 0.3747]** | `python -m ml.train`, `python -m ml.evaluate_seeds` |
| Scratch dirs | noted | `data/*.sqlite3` + `ml/artifacts_debug/` are **untracked and ignored**; the 4 `data/ui-*.png` manual captures **are tracked** — see [KNOWN_ISSUES.md](KNOWN_ISSUES.md) | `git check-ignore -v`, `git ls-files data` |

New since Phase 0, all evidenced: the disagreement-guard **served-output audit**
(`ml/fallback_audit.py` → `ml/artifacts/fallback_audit.json`), the **live** real-route plausibility
check (`scripts/real_route_check.py --confirm` → `docs/real_route_check.json`,
[REAL_ROUTE_CHECK.md](REAL_ROUTE_CHECK.md)), and 390 px rider captures
(`docs/screenshots/`). Still open from Phase 0 and honestly un-closed: an in-suite `live`-labelled
provider pytest, a hosted-CI run, a `docker build` on a live engine (deferred by student request),
and `pyright` (mypy is the authoritative type check here).

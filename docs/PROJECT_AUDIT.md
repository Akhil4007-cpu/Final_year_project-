# PROJECT_AUDIT — Phase 0

RoadGuard AI is a **new, from-scratch** build in this repository. It was not derived
from, copied from, or wired to any earlier project. This audit records the real,
measured state of the code as of this writing. Every count below was produced by
running the command shown, not estimated.

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

All 91 automated tests pass (`python -m pytest -q` → `91 passed in 4.97s`). Full
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
| Geocode | [app/providers.py](../app/providers.py) | `/geocode` | — | Nominatim (live) | manual browser | Implemented, live path not unit-tested | India-restricted | add live-labelled test |
| Route analysis | [app/analysis.py](../app/analysis.py) | `POST /routes/analyze` | — | OSRM (live) | `test_aggregation` | Implemented&tested (logic) | up to 3 alternatives | add live-labelled test |
| Geometry / sections | [app/geo.py](../app/geo.py) | — | — | — | `test_geo` (15) | Implemented&tested | analytical arc/straight/S-curve cases | none |
| Physics baseline | [app/baseline.py](../app/baseline.py) | — | — | — | `test_baseline` (10) | Implemented&tested | `v²/R`, label_v1 | none |
| Route aggregation | [app/aggregation.py](../app/aggregation.py) | — | — | — | `test_aggregation` (10) | Implemented&tested | MIN coverage 0.60 | none |
| Advisory engine | [app/advisory.py](../app/advisory.py) | — | — | — | `test_advisory` (6) | Implemented&tested | score≥55, lead 150 m | none |
| ML model service | [app/model.py](../app/model.py) | `/model/status` | — | — | `test_model` (9) | Implemented&tested | loads artifact at startup | none |
| Synthetic pipeline | [ml/generator.py](../ml/generator.py), [ml/train.py](../ml/train.py) | — | — | — | reproduced offline | Implemented&tested | seed 42, 1180 rows | none |
| Hazards lifecycle | [app/hazards.py](../app/hazards.py) | `/hazards*` | `hazards`,`hazard_votes` | — | `test_api` | Implemented&tested | unverified by default, 24h TTL | none |
| Admin console | [app/api.py](../app/api.py), [app/web/admin.js](../app/web/admin.js) | `/admin/*` | all | — | `test_api` | Implemented&tested | role gate, DOM-only render | none |
| Rider UI + GPS FSM | [app/web/app.js](../app/web/app.js) | — | — | browser GPS | browser (manual) | Implemented, e2e not automated | single watchPosition | add Playwright e2e |

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

# RUNBOOK — deployment, operations, recovery

Honest scope note: the Dockerfile and CI workflow are **authored and lint-plausible**, but
`docker build` was **not** executed to completion in this environment because the Docker
Desktop engine was not running (only the CLI is installed). Treat "image builds /
clean-machine deploy works" as **NOT YET VERIFIED** until the command below is run on a
machine with a live Docker daemon. This matches the rule that no check is reported green
unless it actually ran.

## 1. Local run (verified this session)

```bash
pip install -r requirements-dev.txt
cp .env.example .env          # edit values
uvicorn app.main:app --reload # rider app at /, admin at /admin, docs at /docs
python -m pytest -q           # 112 backend tests — verified passing 2026-10-18
node --test "tests/js/**/*.test.js"  # 31 frontend unit tests — verified passing

# Rider-app E2E (Playwright, headless Chromium; providers are MOCKED/labelled `mock`):
npm ci                        # installs the one dev-only dep (@playwright/test)
npx playwright install chromium   # first run only (downloads the browser)
npx playwright test           # 17 cases (10 rider + 5 admin + 2 screenshot) — boots the real
                              # ASGI app via the config's webServer; tiles are stubbed too

# Live real-route plausibility probe (OPT-IN, network, NOT an accuracy test, never in CI):
python scripts/real_route_check.py --confirm   # -> docs/real_route_check.json

# Performance benchmarks (see PERFORMANCE_REPORT.md):
python scripts/bench_server.py                 # offline analyze latency/throughput + scoring before/after
python scripts/bench_provider_live.py --confirm  # OPT-IN live Nominatim/OSRM round-trip (network)
```

**Scaling note.** The `/routes/analyze` path is CPU-bound (measured: single-worker
throughput is flat-to-rising across concurrency 1→20). For real multi-client load, run
`uvicorn app.main:app --workers N` so each process owns a core and its own loaded model
artifact. `--reload` is for development only; do not combine it with `--workers`.

**Alert channels (browser-verified this session).** Open the rider app, tap the header
**Alert settings** (gear). Toggle Visual / Vibration / Sound; each change persists to
`localStorage` and survives a reload. The note under the switches reflects the device's
real capabilities — e.g. iOS Safari (no `navigator.vibrate`) shows that haptics fall back
to visual/audible, and a browser without Web Audio shows alerts stay visual. **Sound is off
by default** and only unlocks after a user tap (autoplay policy). The high-band "in the
curve now" advisory uses a `role="alert"` assertive live region for screen readers.

## 2. Container build + run (run this to verify; NOT verified here)

```bash
docker build -t roadguard:ci .
docker run -d --name roadguard -p 8000:8000 \
  -e ROADGUARD_ENV=production -e ROADGUARD_COOKIE_SECURE=true \
  -e ROADGUARD_ALLOWED_ORIGINS=https://your.domain \
  -v roadguard-data:/app/data roadguard:ci
docker exec roadguard python scripts/create_admin.py --email you@example.com
```

The image runs as non-root (uid 10001), health-checks `/health`, and keeps the SQLite DB
in a mounted volume.

## 3. HTTPS reverse proxy (required before non-local use)

Terminate TLS in front of uvicorn and forward the original scheme/host so `Secure`
cookies and CORS behave correctly:

```
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

Set `ROADGUARD_COOKIE_SECURE=true` and the exact `ROADGUARD_ALLOWED_ORIGINS` when TLS is on.
The app already sends HSTS, CSP, `X-Frame-Options: DENY`, and nosniff (see
[SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)).

## 4. Environment profiles

| Var | dev | production |
|---|---|---|
| `ROADGUARD_ENV` | development | production |
| `ROADGUARD_COOKIE_SECURE` | false | **true** |
| `ROADGUARD_REQUIRE_MODEL` | false | true (fail closed if artifact missing) |
| `ROADGUARD_ALLOWED_ORIGINS` | localhost | your https origin |
| `ROADGUARD_PROVIDER_USER_AGENT` | `REQUIRES STUDENT INPUT` | real contact (Nominatim policy) |

## 5. Migrations

`app.main` lifespan calls `init_db`, applying pending versions in
`app/db.py::MIGRATIONS` and bumping `PRAGMA user_version`. Forward-only, idempotent.
To add a migration, append `(version, sql)` and test on a **copy** first (see §6).

## 6. Backup / restore (verified by test)

```bash
# automated proof:
python -m pytest tests/test_db_backup.py -q   # backup→restore loses 0 rows + integrity_check

# operational copy:
sqlite3 data/roadguard.sqlite3 ".backup 'data/backups/roadguard-$(date -u +%Y%m%dT%H%M%SZ).sqlite3'"
```
Restore = stop app, swap the DB file into `ROADGUARD_DB_PATH`, restart, hit `/ready`.
`backup_database` uses the SQLite online-backup API, so it is safe against a busy WAL DB.

## 7. Provider limits (pre-launch gate)

- **Nominatim**: single request thread, identifiable `ROADGUARD_PROVIDER_USER_AGENT` with
  a real contact (currently `REQUIRES STUDENT INPUT`), no distributed bulk — per the OSMF
  Nominatim Usage Policy.
- **OSRM**: the public `router.project-osrm.org` demo is for testing only. Before public
  launch, **self-host OSRM or use a commercial routing provider** (KNOWN_ISSUES #7).
- **Tiles**: OSM raster tiles © OpenStreetMap contributors (ODbL) — keep attribution.

## 8. Logging & PII

App errors are logged server-side as typed codes without secrets. Keep access logs free of
full query strings that could carry coordinates. `/health` and `/ready` are the JSON
liveness probes (no PII).

## 9. CI

`.github/workflows/ci.yml` has four jobs: **`test`** (Python 3.12) runs ruff → mypy →
pip-audit → pytest → compliance — all **blocking** (no `continue-on-error`; each is verified
clean locally); **`frontend-test`** (Node 24) runs the 31 `node --test` cases; **`e2e`**
(Node 24 + Python 3.12) runs `npm ci` + `npx playwright install --with-deps chromium` then
`npx playwright test` (17 cases — 10 rider + 5 admin + 2 screenshot — with mock-labelled
providers and stubbed tiles); **`build`**
(`needs: [test, e2e]`) runs `docker build`. **Caveat:** this workflow has not yet been executed
on a GitHub runner, and `docker build` is not verified here (no running engine — KNOWN_ISSUES
#11). The individual commands it chains are all reproduced green locally except `docker build`.

## 10. Rollback

Redeploy the previous image tag; restore the prior DB from `data/backups/`. Migrations are
additive, so an older image reads the newer schema's tables it knows about. There is no
down-migration script yet — a documented gap, not a claim.

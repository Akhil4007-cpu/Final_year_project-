# ARCHITECTURE

## WHAT

RoadGuard AI is a mobile-first, real-time **road-geometry advisory** web app. A rider
enters a destination, the app routes via OSRM, extracts curve geometry from the
polyline, scores each section's *geometry challenge*, and issues a lead-time advisory
before sharp sections. It is explicitly **not** an accident-prediction system.

Stack: FastAPI + Pydantic v2 backend, SQLite (WAL) persistence, vanilla ES-module JS +
Leaflet front-end, OSM/Nominatim/OSRM providers, and an offline-trained
scikit-learn/joblib model (GACE) loaded once at startup.

## WHY

- **Transparent physics first.** A documented `v²/R` baseline is the honest floor; the
  ML model must beat it on *degraded* input to earn runtime weight, otherwise the
  baseline serves and ML stays in shadow. This keeps every number explainable to a
  viva panel.
- **Uncertainty over false precision.** Split-conformal intervals and explicit
  `model_status` (`model_estimate` / `baseline_fallback` / `unavailable`) mean the UI
  never shows a confident number it cannot justify (R3).
- **Separation of training from runtime.** `ml/` is offline-only; the server never
  imports it (enforced by `test_runtime_never_imports_ml_training`, R10).

## HOW — module map

```
Browser (Leaflet + GPS FSM)          FastAPI backend
 app/web/app.js  rider UI              api.py ── request validation (schemas.py)
 app/web/admin.js admin console          │
 app/web/geo.js  client geometry         ├─ services.py  (composition root)
 app/web/api.js  fetch wrapper           │    ├─ auth.py      ── security.py (hash, tokens, RateLimiter)
 app/web/alerts.js pure alert planner    │    ├─ hazards.py   ── db.py (SQLite WAL, migrations)
 app/web/settings.js channel prefs       │    ├─ analysis.py ─┐
 app/web/ui.js DOM/toast/sheet helpers   │    │               ├─ geo.py ── baseline.py ── model.py
                                        │    │               └─ aggregation.py ─ advisory.py
   Nominatim  OSRM  ◄── providers.py ───┤    └─ analysis.py calls providers.py
   ml/ (OFFLINE, never imported at run) ┘    └─ model.py loads ml/artifacts/model.joblib
```

Request lifecycle: `api.py` validates with Pydantic `StrictModel` (`extra="forbid"`),
enforces the `X-RoadGuard-Client: web` header on mutations (CSRF-by-header, no token in
DOM), checks auth via HttpOnly session cookie + server-side role gate, applies the
in-process `RateLimiter`, and calls the services. Errors surface as typed `AppError`
codes, never as silent fallbacks.

Scoring path: `analysis.py` drives `geo.extract_sections` → per-section
`baseline.challenge_score` and `model.score_section`; the model's disagreement with the
baseline (>20 points, `DISAGREEMENT_THRESHOLD`) flips it to `baseline_fallback`.
`aggregation.aggregate_sections` rolls sections into a route score with coverage
(`MIN_ROUTE_COVERAGE = 0.60`); unscorable length is **never** counted as zero risk (R5).
`compare_routes` only ranks when the score gap ≥ 5.0 **and** coverage spread ≤ 0.15,
and labels the winner "lowest_geometry_challenge" — never "safest".
`advisory.build_advisories` turns curve sections ≥ 55 into lead-time cards (150 m lead,
20 m clear, 30 s cooldown).

Client alerting is staged and capability-aware. On each GPS fix `app.js` matches progress to
an advisory window and, on a stage crossing (approach → in-curve), calls the DOM-free
`alerts.planAlert({band, ahead, settings, capabilities, reducedMotion})`. That pure planner
picks the intensity and the channels to actually fire, applying graceful fallbacks: haptic →
audio → visual when the device lacks `navigator.vibrate` (iOS Safari), and no visual flash
under `prefers-reduced-motion`. `settings.js` persists the rider's per-channel choices in
`localStorage` (default: visual on, haptics on where supported, **sound off** — it unlocks
only after a user gesture to satisfy the Web Audio autoplay policy). The banner is a
`role="status"` polite live region; a high-band in-curve advisory additionally writes a
`role="alert"` assertive region so screen readers interrupt. The planner is unit-tested with
Node's built-in runner (`tests/js`); no alert wording ever claims accident prediction (R4).

## Boundaries and guarantees

- **Server-side authority.** Roles, ownership, and moderation gates are enforced in the
  backend; the UI is not the trust boundary.
- **XSS-safe rendering.** Admin and rider UI build DOM via `textContent`/nodes, never
  `innerHTML` of untrusted data.
- **Secrets.** All configuration comes from env (`.env.example`); no secret is embedded
  in source, DOM, or logs (R8, scanned by `test_no_hardcoded_secrets_in_source`).

## Known architectural limits

- The `RateLimiter` is in-process and correct only for a **single** worker; multi-worker
  or multi-host deployments need a shared store. Tracked in
  [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
- Provider calls are synchronous `httpx` with a fixed timeout and no circuit breaker.
- Client GPS trust boundary is the browser; server does not receive continuous traces
  (privacy, see [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)).

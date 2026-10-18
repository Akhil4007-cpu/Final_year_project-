# SECURITY_AND_PRIVACY

This document states what the code actually enforces and, just as importantly, what it
does **not** claim. Honesty rule R8 (no secrets in repo, DOM, or logs) and R3 (no silent
fallbacks) govern the whole design.

## Authentication

- **Passwords** are hashed with **PBKDF2-HMAC-SHA256, 260,000 iterations**, a fresh
  16-byte `secrets.token_bytes` salt per user, stored as
  `pbkdf2_sha256$iterations$salt_hex$digest_hex`. Verification re-derives with the
  stored iteration count and compares with a constant-time digest check. Plaintext is
  never stored or logged.
- **Password policy** (`validate_password`): length 10–200 plus complexity checks;
  rejected with `invalid_input` on the way in. **Email** validated against a bounded
  regex (≤254 chars).
- **Sessions** are opaque `secrets.token_urlsafe(32)` tokens. The **SHA-256 hash** of
  the token is what the `sessions` table stores — a DB leak does not yield usable
  cookies. TTL default 43,200 s; expired rows are swept on authentication.

## Authorization (server-side)

- The browser is never the trust boundary. Role (`rider` / `admin`) is read from the DB
  on every privileged call; `require_admin` returns `401` for anonymous and `403` for a
  non-admin. Rider-UI hiding of admin features is cosmetic only.
- Hazard ownership: only the author may withdraw their own vote; only admins may verify
  or reject; an admin cannot self-deactivate (blocked `400`).

## CSRF / DOM safety

- Mutations require a custom header `X-RoadGuard-Client: web`. Because a cross-origin
  form/script cannot set that custom header without a preflight the server controls, its
  absence is a `403`. **No CSRF token is placed in the DOM** (R8).
- The session cookie is `HttpOnly` + `SameSite=Lax` (`Secure` in production), so
  client JS and cross-site requests cannot read or attach it.

## Rate limiting

In-process token buckets (`RateLimiter`) isolated per key. Defaults from config:
login 5/min, route 20/min, hazard 10/hour. Exceeding the limit returns `429` with a
`Retry-After` header. **Limitation:** the store is per-process, so it is correct only
for a single worker — a documented open item, not a claim of distributed safety.

## Transport & headers

`create_app` sets on every response:
`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
`Referrer-Policy: strict-origin-when-cross-origin`,
`Strict-Transport-Security: max-age=31536000; includeSubDomains`, and a strict CSP:

```
default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline';
img-src 'self' data: https://*.tile.openstreetmap.org; connect-src 'self';
font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self';
frame-ancestors 'none'; manifest-src 'self'; worker-src 'self'
```

Docs paths (`/docs`, `/openapi.json`, `/redoc`) are the only carve-outs. CORS is
allow-listed from `ROADGUARD_ALLOWED_ORIGINS` with credentials on, methods GET/POST/
DELETE/OPTIONS, headers Content-Type + the client header only.

> `style-src 'unsafe-inline'` is a known, deliberate concession for the vendored Leaflet
> inline styles; `script-src` stays strict and there is no `unsafe-eval`. Tracked in
> [KNOWN_ISSUES.md](KNOWN_ISSUES.md).

## Error hygiene

`AppError` returns a typed `code` + safe `message` and never a stack trace or internal
detail to the client. `internal_error` (500) is the catch-all; unexpected exceptions are
logged server-side without secrets.

## Secrets management

All credentials/limits come from environment variables (see `.env.example`). The
provider User-Agent string carries a `REQUIRES STUDENT INPUT` contact placeholder, not a
real secret. `test_no_hardcoded_secrets_in_source` scans the tree and passes; `.env` is
git-ignored. **Before any commit, the student must confirm no personal API key or token
has been pasted into `.env` or logs.**

## Privacy

- **Data minimisation.** Only email + role + hashed password are stored per account. No
  name, phone, or payment data exists in the schema.
- **No movement trails.** The rider's GPS is processed in the browser; the server
  receives a discrete set of route waypoints on demand, never a continuous precise
  trace, and does not persist location history.
- **Account deletion** revokes sessions, deletes the user's unverified/rejected hazards,
  removes their votes, and anonymises their verified hazards (`user_id = NULL`). This is
  tested end-to-end.
- **Community reports** are geolocated but not attributed to a rider identity in the
  public feed; unverified reports are labelled `unverified`, never "confirmed" (R6).

## Dependency audit

`pip-audit` is the intended scanner (CI wiring planned — see
[LOOP_STATE.md](LOOP_STATE.md)); it has **not** been run in this environment yet, so no
clean-audit result is claimed here.

## Threat model — what is NOT protected against

Shared/multi-process rate limits, OS-level secret leakage, side-channel timing on
password comparison beyond the constant-time digest check, and DoS at the network layer
are out of scope for a student deployment. Stated plainly rather than implied safe.

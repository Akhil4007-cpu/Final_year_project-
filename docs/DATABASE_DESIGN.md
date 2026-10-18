# DATABASE_DESIGN

Engine: **SQLite** with `journal_mode = WAL`, `foreign_keys = ON`,
`busy_timeout = 5000`. Schema version is tracked in `schema_migrations` and mirrored to
`PRAGMA user_version`. Current `SCHEMA_VERSION = 1`. Path is configurable via
`ROADGUARD_DB_PATH` (dev default `data/roadguard.sqlite3`).

## Migration mechanism

`app/db.py` holds an ordered `MIGRATIONS: list[tuple[version, sql]]`. `init_db` creates
`schema_migrations`, skips already-applied versions, executes each new migration inside
the WAL transaction, records it with `applied_at`, and bumps `user_version`. This is
forward-only and idempotent; a fresh DB and an existing DB converge to the same schema.

## ER model

```
users (1) ──< sessions (N)         users (1) ──< hazard_votes (N) >── (1) hazards
   │                                        │                              │
   └──< hazards (N, SET NULL on delete)     └── actor refs in audit_log ───┘
   └──< audit_log (N, actor SET NULL)
```

## Tables (verbatim from the migration)

### users
| column | type | notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| email | TEXT NOT NULL UNIQUE COLLATE NOCASE | case-insensitive login |
| password_hash | TEXT NOT NULL | PBKDF2-HMAC-SHA256, never the plaintext |
| role | TEXT NOT NULL CHECK IN ('rider','admin') | |
| is_active | INTEGER NOT NULL DEFAULT 1 | soft-disable; login blocked when 0 |
| created_at | TEXT NOT NULL | ISO-8601 UTC |

### sessions
| column | type | notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| token_hash | TEXT NOT NULL UNIQUE | only the hash of the cookie token is stored |
| user_id | INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE | |
| created_at / expires_at | TEXT NOT NULL | TTL default 43200 s |

### hazards
| column | type | notes |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| user_id | INTEGER REFERENCES users(id) ON DELETE SET NULL | report author; kept on deletion |
| category | TEXT NOT NULL | one of the seven UI categories |
| description | TEXT NOT NULL DEFAULT '' | capped at 500 chars |
| lat / lon | REAL NOT NULL | validated server-side |
| source | TEXT NOT NULL DEFAULT 'map_pin' CHECK IN ('current_location','map_pin') | |
| status | TEXT NOT NULL CHECK IN ('unverified','verified','rejected','expired') | new reports are `unverified` (R6) |
| created_at / expires_at | TEXT NOT NULL | TTL default 24 h |
| verified_by / verified_at | INTEGER REFERENCES users(id) SET NULL / TEXT | |
| rejected_by / rejected_at | INTEGER REFERENCES users(id) SET NULL / TEXT | |

### hazard_votes
Composite PK `(hazard_id, user_id)`; `action CHECK IN ('confirm','withdraw')`. Cascade
delete with the hazard. One live vote per user per hazard.

### audit_log
Append-only record of security-relevant actions: `actor_user_id` (SET NULL on delete),
`action`, `target_type`, `target_id`, `details_json` (defaults `{}`), `created_at`.

## Indexes

`idx_hazards_status`, `idx_hazards_location(lat,lon)`, `idx_hazards_expires`,
`idx_sessions_expires`, `idx_votes_hazard`, `idx_audit_created`.

## Retention & privacy

- Sessions expire and are swept on read (`user_for_token` deletes expired rows).
- Hazards expire on TTL (`_expire` on each access); expired reports leave the rider feed.
- **Account deletion** (`app/auth.py::delete_account`): revokes sessions, removes the
  user's votes, deletes the user's `unverified`/`rejected` hazards, and **anonymises**
  their `verified` hazards by setting `user_id = NULL` (community value is preserved,
  personal link is removed). No precise movement trace is ever persisted server-side —
  geocoding/routing are stateless provider calls (see
  [SECURITY_AND_PRIVACY.md](SECURITY_AND_PRIVACY.md)).
- No PII beyond email + role is stored. There is no name, phone, or location history
  column.

## Backup / restore

`app/db.py::backup_database(source, destination)` copies the DB via the SQLite backup
API. Restore verification **is** evidenced: `tests/test_db_backup.py` populates a DB
(3 users, hazards, votes, moderation, sessions), backs it up, asserts the copy loses
**zero rows**, runs `PRAGMA integrity_check`, and confirms the restored DB still enforces
the role gate and returns the verified hazard.

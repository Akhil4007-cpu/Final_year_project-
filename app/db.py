from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

SCHEMA_VERSION = 1

MIGRATIONS: list[tuple[int, str]] = [
    (
        1,
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('rider', 'admin')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token_hash TEXT NOT NULL UNIQUE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS hazards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            lat REAL NOT NULL,
            lon REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'map_pin' CHECK (source IN ('current_location', 'map_pin')),
            status TEXT NOT NULL CHECK (status IN ('unverified', 'verified', 'rejected', 'expired')),
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            verified_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            verified_at TEXT,
            rejected_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
            rejected_at TEXT
        );

        CREATE TABLE IF NOT EXISTS hazard_votes (
            hazard_id INTEGER NOT NULL REFERENCES hazards(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            action TEXT NOT NULL CHECK (action IN ('confirm', 'withdraw')),
            created_at TEXT NOT NULL,
            PRIMARY KEY (hazard_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT,
            details_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_hazards_status ON hazards(status);
        CREATE INDEX IF NOT EXISTS idx_hazards_location ON hazards(lat, lon);
        CREATE INDEX IF NOT EXISTS idx_hazards_expires ON hazards(expires_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at);
        CREATE INDEX IF NOT EXISTS idx_votes_hazard ON hazard_votes(hazard_id);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at);
        """,
    )
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _configure(conn: sqlite3.Connection) -> None:
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")


@contextmanager
def connection(path: Path) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(path, timeout=10.0)
    _configure(conn)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with connection(path) as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            row["version"] for row in conn.execute("SELECT version FROM schema_migrations")
        }
        for version, sql in MIGRATIONS:
            if version in applied:
                continue
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, utc_now_iso()),
            )
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def backup_database(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(source)
    try:
        destination_conn = sqlite3.connect(destination)
        try:
            source_conn.backup(destination_conn)
        finally:
            destination_conn.close()
    finally:
        source_conn.close()


def database_health(path: Path) -> dict[str, object]:
    try:
        with connection(path) as conn:
            conn.execute("SELECT 1").fetchone()
            users = conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
            hazards = conn.execute("SELECT COUNT(*) AS n FROM hazards").fetchone()["n"]
            migration = conn.execute(
                "SELECT MAX(version) AS v FROM schema_migrations"
            ).fetchone()["v"]
        return {
            "ok": True,
            "path_exists": path.is_file(),
            "users": users,
            "hazards": hazards,
            "schema_version": migration,
        }
    except Exception as exc:  # noqa: BLE001 - ready endpoint must report, not crash
        return {"ok": False, "error": type(exc).__name__, "path_exists": path.is_file()}

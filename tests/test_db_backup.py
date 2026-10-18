from __future__ import annotations

import sqlite3
from pathlib import Path

from app.auth import AuthService
from app.db import backup_database, init_db
from app.hazards import HazardService


def _row_counts(path: Path) -> dict[str, int]:
    with sqlite3.connect(path) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("users", "sessions", "hazards", "hazard_votes", "audit_log")
        }


def test_backup_restore_preserves_all_rows(tmp_path: Path) -> None:
    source = tmp_path / "source.sqlite3"
    init_db(source)

    auth = AuthService(source)
    rider = auth.register("rider@example.test", "StrongPass#2026", role="rider")
    peer = auth.register("peer@example.test", "StrongPass#2026", role="rider")
    admin = auth.register("admin@example.test", "AdminPass#2026", role="admin")
    auth.create_session(rider["id"])

    hazards = HazardService(source)
    first = hazards.create(
        user_id=rider["id"],
        category="pothole",
        description="deep edge break",
        lat=17.385,
        lon=78.4867,
        source="current_location",
    )
    hazards.create(
        user_id=rider["id"],
        category="debris",
        description="",
        lat=17.4001,
        lon=78.4902,
        source="map_pin",
    )
    hazards.vote(hazard_id=first["id"], user_id=peer["id"], action="confirm")
    hazards.moderate(hazard_id=first["id"], admin_id=admin["id"], action="verify", note="ok")

    before = _row_counts(source)
    assert before["users"] == 3
    assert before["hazards"] == 2
    assert before["audit_log"] >= 3  # registrations, hazard create(s), moderation

    destination = tmp_path / "restore" / "backup.sqlite3"
    backup_database(source, destination)

    assert destination.is_file()
    after = _row_counts(destination)
    assert after == before, "backup/restore must lose zero rows"

    # The restored DB must be live: same role gate and moderation still resolve.
    restored_auth = AuthService(destination)
    token = restored_auth.create_session(admin["id"])
    user = restored_auth.user_for_token(token)
    assert user is not None and user["role"] == "admin"

    restored_hazards = HazardService(destination)
    verified = restored_hazards.get(first["id"])
    assert verified["status"] == "verified"

    # integrity_check confirms the copy is a structurally valid SQLite file.
    with sqlite3.connect(destination) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

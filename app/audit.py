from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.db import connection


def list_audit_events(db_path: Path, limit: int = 100) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 500))
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, actor_user_id, action, target_type, target_id, details_json, created_at "
            "FROM audit_log ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    events = []
    for row in rows:
        try:
            details = json.loads(row["details_json"])
        except (TypeError, ValueError):
            details = {}
        events.append(
            {
                "id": int(row["id"]),
                "actor_user_id": int(row["actor_user_id"])
                if row["actor_user_id"] is not None
                else None,
                "action": str(row["action"]),
                "target_type": str(row["target_type"]),
                "target_id": str(row["target_id"]) if row["target_id"] is not None else None,
                "details": details if isinstance(details, dict) else {},
                "created_at": str(row["created_at"]),
            }
        )
    return events


def user_count(db_path: Path) -> dict[str, int]:
    with connection(db_path) as conn:
        role_rows = conn.execute(
            "SELECT role, COUNT(*) AS n FROM users GROUP BY role"
        ).fetchall()
        active = conn.execute(
            "SELECT COUNT(*) AS n FROM users WHERE is_active = 1"
        ).fetchone()["n"]
    counts = {str(row["role"]): int(row["n"]) for row in role_rows}
    return {
        "total": sum(counts.values()),
        "admins": counts.get("admin", 0),
        "riders": counts.get("rider", 0),
        "active": int(active),
    }

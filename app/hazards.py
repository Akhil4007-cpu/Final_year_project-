from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from app.db import connection, utc_now_iso
from app.errors import invalid_input, not_found
from app.geo import haversine_m
from app.security import audit_event

CATEGORIES = {
    "pothole",
    "debris",
    "waterlogging",
    "poor_visibility",
    "sharp_curve",
    "road_work",
    "other",
}
SOURCES = {"current_location", "map_pin"}
DUPLICATE_RADIUS_M = 50.0
DUPLICATE_WINDOW_MINUTES = 10


def _validate_coordinates(lat: float, lon: float) -> None:
    if not (
        isinstance(lat, (int, float))
        and isinstance(lon, (int, float))
        and math.isfinite(float(lat))
        and math.isfinite(float(lon))
        and -90.0 <= float(lat) <= 90.0
        and -180.0 <= float(lon) <= 180.0
    ):
        raise invalid_input("Hazard coordinates are invalid.")


def _expire(conn: Any, now: str) -> None:
    conn.execute(
        "UPDATE hazards SET status = 'expired' "
        "WHERE status IN ('unverified', 'verified') AND expires_at <= ?",
        (now,),
    )


def _hazard_dict(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "category": str(row["category"]),
        "description": str(row["description"]),
        "lat": float(row["lat"]),
        "lon": float(row["lon"]),
        "source": str(row["source"]),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "expires_at": str(row["expires_at"]),
        "confirmations": int(row["confirmations"] or 0),
        "provenance": "user_submitted",
        "label": "Community report — unverified."
        if row["status"] == "unverified"
        else f"Community report — {row['status']}.",
        "is_mine": bool(row["is_mine"]) if "is_mine" in row.keys() else False,
    }


class HazardService:
    def __init__(self, db_path: Path, ttl_hours: int = 24) -> None:
        self.db_path = db_path
        self.ttl_hours = ttl_hours

    def create(
        self,
        *,
        user_id: int,
        category: str,
        description: str,
        lat: float,
        lon: float,
        source: str,
    ) -> dict[str, Any]:
        _validate_coordinates(lat, lon)
        if category not in CATEGORIES:
            raise invalid_input("Unknown hazard category.")
        if source not in SOURCES:
            raise invalid_input("Unknown hazard source.")
        description = (description or "").strip()
        if len(description) > 500:
            raise invalid_input("Description must be at most 500 characters.")
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat(timespec="seconds")
        expires = (now_dt + timedelta(hours=self.ttl_hours)).isoformat(timespec="seconds")
        with connection(self.db_path) as conn:
            _expire(conn, now)
            recent = conn.execute(
                "SELECT id, lat, lon FROM hazards WHERE user_id = ? AND category = ? "
                "AND status IN ('unverified', 'verified') AND created_at >= ?",
                (
                    user_id,
                    category,
                    (now_dt - timedelta(minutes=DUPLICATE_WINDOW_MINUTES)).isoformat(
                        timespec="seconds"
                    ),
                ),
            ).fetchall()
            for row in recent:
                if haversine_m((lat, lon), (float(row["lat"]), float(row["lon"]))) <= DUPLICATE_RADIUS_M:
                    raise invalid_input("A similar report already exists nearby.")
            cursor = conn.execute(
                "INSERT INTO hazards(user_id, category, description, lat, lon, source, status, created_at, expires_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'unverified', ?, ?)",
                (user_id, category, description, lat, lon, source, now, expires),
            )
            hazard_id = cast(int, cursor.lastrowid)
            audit_event(
                conn,
                actor_user_id=user_id,
                action="hazard_created",
                target_type="hazard",
                target_id=str(hazard_id),
                details={"category": category, "source": source},
                created_at=now,
            )
            row = conn.execute(
                "SELECT h.*, (SELECT COUNT(*) FROM hazard_votes v WHERE v.hazard_id = h.id AND v.action = 'confirm') "
                "AS confirmations FROM hazards h WHERE h.id = ?",
                (hazard_id,),
            ).fetchone()
        result = _hazard_dict(row)
        result["is_mine"] = True
        return result

    def list_in_bbox(
        self,
        *,
        min_lat: float | None = None,
        min_lon: float | None = None,
        max_lat: float | None = None,
        max_lon: float | None = None,
        statuses: tuple[str, ...] = ("unverified", "verified"),
        limit: int = 200,
        viewer_id: int | None = None,
    ) -> list[dict[str, Any]]:
        now = utc_now_iso()
        limit = max(1, min(int(limit), 500))
        clauses = ["h.status IN (" + ",".join("?" for _ in statuses) + ")"]
        params: list[Any] = list(statuses)
        box = [min_lat, min_lon, max_lat, max_lon]
        if any(value is not None for value in box):
            if any(value is None for value in box):
                raise invalid_input("All four bounding-box coordinates are required.")
            assert min_lat is not None and max_lat is not None
            assert min_lon is not None and max_lon is not None
            if not (-90 <= min_lat <= max_lat <= 90 and -180 <= min_lon <= max_lon <= 180):
                raise invalid_input("Bounding box is invalid.")
            clauses.append("h.lat BETWEEN ? AND ? AND h.lon BETWEEN ? AND ?")
            params.extend([min_lat, max_lat, min_lon, max_lon])
        with connection(self.db_path) as conn:
            _expire(conn, now)
            rows = conn.execute(
                "SELECT h.*, "
                "(SELECT COUNT(*) FROM hazard_votes v WHERE v.hazard_id = h.id AND v.action = 'confirm') AS confirmations "
                "FROM hazards h WHERE " + " AND ".join(clauses) + " ORDER BY h.created_at DESC LIMIT ?",
                (*params, limit),
            ).fetchall()
        results = []
        for row in rows:
            item = _hazard_dict(row)
            if viewer_id is not None:
                item["is_mine"] = int(row["user_id"] or -1) == viewer_id
            results.append(item)
        return results

    def get(self, hazard_id: int) -> dict[str, Any]:
        now = utc_now_iso()
        with connection(self.db_path) as conn:
            _expire(conn, now)
            row = conn.execute(
                "SELECT h.*, (SELECT COUNT(*) FROM hazard_votes v WHERE v.hazard_id = h.id AND v.action = 'confirm') "
                "AS confirmations FROM hazards h WHERE h.id = ?",
                (hazard_id,),
            ).fetchone()
        if row is None:
            raise not_found("Hazard not found.")
        return _hazard_dict(row)

    def vote(self, *, hazard_id: int, user_id: int, action: str) -> dict[str, Any]:
        if action not in {"confirm", "withdraw"}:
            raise invalid_input("Vote action must be confirm or withdraw.")
        now = utc_now_iso()
        with connection(self.db_path) as conn:
            _expire(conn, now)
            hazard = conn.execute(
                "SELECT id, user_id, status FROM hazards WHERE id = ?", (hazard_id,)
            ).fetchone()
            if hazard is None:
                raise not_found("Hazard not found.")
            if hazard["status"] not in {"unverified", "verified"}:
                raise invalid_input("This hazard is no longer open for confirmation.")
            if int(hazard["user_id"] or -1) == user_id:
                raise invalid_input("You cannot confirm your own report.")
            if action == "confirm":
                conn.execute(
                    "INSERT INTO hazard_votes(hazard_id, user_id, action, created_at) VALUES (?, ?, 'confirm', ?) "
                    "ON CONFLICT(hazard_id, user_id) DO UPDATE SET action = 'confirm', created_at = excluded.created_at",
                    (hazard_id, user_id, now),
                )
            else:
                conn.execute(
                    "DELETE FROM hazard_votes WHERE hazard_id = ? AND user_id = ?",
                    (hazard_id, user_id),
                )
            audit_event(
                conn,
                actor_user_id=user_id,
                action=f"hazard_{action}",
                target_type="hazard",
                target_id=str(hazard_id),
                created_at=now,
            )
        return self.get(hazard_id)

    def moderate(
        self,
        *,
        hazard_id: int,
        admin_id: int,
        action: str,
        note: str = "",
    ) -> dict[str, Any]:
        if action not in {"verify", "reject"}:
            raise invalid_input("Moderation action must be verify or reject.")
        note = (note or "").strip()[:500]
        now = utc_now_iso()
        with connection(self.db_path) as conn:
            _expire(conn, now)
            row = conn.execute("SELECT * FROM hazards WHERE id = ?", (hazard_id,)).fetchone()
            if row is None:
                raise not_found("Hazard not found.")
            if row["status"] not in {"unverified", "verified"}:
                raise invalid_input("Only open hazards can be moderated.")
            if action == "verify":
                conn.execute(
                    "UPDATE hazards SET status = 'verified', verified_by = ?, verified_at = ?, "
                    "rejected_by = NULL, rejected_at = NULL WHERE id = ?",
                    (admin_id, now, hazard_id),
                )
            else:
                conn.execute(
                    "UPDATE hazards SET status = 'rejected', rejected_by = ?, rejected_at = ?, "
                    "verified_by = NULL, verified_at = NULL WHERE id = ?",
                    (admin_id, now, hazard_id),
                )
            audit_event(
                conn,
                actor_user_id=admin_id,
                action="hazard_verified" if action == "verify" else "hazard_rejected",
                target_type="hazard",
                target_id=str(hazard_id),
                details={"note": note},
                created_at=now,
            )
        return self.get(hazard_id)

    def admin_list(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        now = utc_now_iso()
        limit = max(1, min(int(limit), 500))
        with connection(self.db_path) as conn:
            _expire(conn, now)
            if status:
                if status not in {"unverified", "verified", "rejected", "expired"}:
                    raise invalid_input("Unknown hazard status.")
                rows = conn.execute(
                    "SELECT h.*, (SELECT COUNT(*) FROM hazard_votes v WHERE v.hazard_id = h.id AND v.action = 'confirm') "
                    "AS confirmations FROM hazards h WHERE h.status = ? ORDER BY h.created_at DESC LIMIT ?",
                    (status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT h.*, (SELECT COUNT(*) FROM hazard_votes v WHERE v.hazard_id = h.id AND v.action = 'confirm') "
                    "AS confirmations FROM hazards h ORDER BY h.created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [_hazard_dict(row) for row in rows]

    def stats(self) -> dict[str, int]:
        now = utc_now_iso()
        with connection(self.db_path) as conn:
            _expire(conn, now)
            rows = conn.execute(
                "SELECT status, COUNT(*) AS n FROM hazards GROUP BY status"
            ).fetchall()
        result = {"unverified": 0, "verified": 0, "rejected": 0, "expired": 0}
        for row in rows:
            result[str(row["status"])] = int(row["n"])
        return result

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from app.db import connection, utc_now_iso
from app.errors import auth_failure, invalid_input
from app.security import (
    audit_event,
    hash_password,
    hash_token,
    new_session_token,
    validate_email,
    validate_password,
    verify_password,
)


def _row_to_user(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "email": str(row["email"]),
        "role": str(row["role"]),
        "created_at": str(row["created_at"]),
    }


class AuthService:
    def __init__(self, db_path: Path, session_ttl_seconds: int = 43_200) -> None:
        self.db_path = db_path
        self.session_ttl_seconds = session_ttl_seconds

    def register(self, email: str, password: str, role: str = "rider") -> dict[str, Any]:
        email = validate_email(email)
        password = validate_password(password)
        if role not in {"rider", "admin"}:
            raise invalid_input("Invalid role.")
        now = utc_now_iso()
        with connection(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM users WHERE email = ? COLLATE NOCASE", (email,)
            ).fetchone()
            if existing:
                raise invalid_input("An account with this email already exists.")
            try:
                cursor = conn.execute(
                    "INSERT INTO users(email, password_hash, role, is_active, created_at) "
                    "VALUES (?, ?, ?, 1, ?)",
                    (email, hash_password(password), role, now),
                )
            except sqlite3.IntegrityError:
                raise invalid_input("An account with this email already exists.") from None
            user_id = cast(int, cursor.lastrowid)
            audit_event(
                conn,
                actor_user_id=user_id,
                action="user_registered",
                target_type="user",
                target_id=str(user_id),
                details={"role": role},
                created_at=now,
            )
        return {"id": user_id, "email": email, "role": role, "created_at": now}

    def authenticate(self, email: str, password: str) -> dict[str, Any]:
        normalized = email.strip().lower()
        with connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (normalized,)
            ).fetchone()
        if row is None or not int(row["is_active"]):
            raise auth_failure("Invalid email or password.")
        if not verify_password(password, str(row["password_hash"])):
            raise auth_failure("Invalid email or password.")
        return _row_to_user(row)

    def create_session(self, user_id: int) -> str:
        token = new_session_token()
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.session_ttl_seconds)
        with connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                (
                    hash_token(token),
                    user_id,
                    now.isoformat(timespec="seconds"),
                    expires.isoformat(timespec="seconds"),
                ),
            )
        return token

    def user_for_token(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        now = utc_now_iso()
        with connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
                "WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1",
                (hash_token(token), now),
            ).fetchone()
            conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        return _row_to_user(row) if row else None

    def revoke_session(self, token: str | None) -> None:
        if not token:
            return
        with connection(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))

    def revoke_user_sessions(self, user_id: int) -> None:
        with connection(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))

    def list_users(self) -> list[dict[str, Any]]:
        with connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, email, role, is_active, created_at FROM users ORDER BY id"
            ).fetchall()
        return [
            {
                "id": int(row["id"]),
                "email": str(row["email"]),
                "role": str(row["role"]),
                "is_active": bool(row["is_active"]),
                "created_at": str(row["created_at"]),
            }
            for row in rows
        ]

    def set_active(
        self, user_id: int, active: bool, *, actor_user_id: int | None = None
    ) -> None:
        with connection(self.db_path) as conn:
            row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                raise invalid_input("User not found.")
            conn.execute(
                "UPDATE users SET is_active = ? WHERE id = ?", (1 if active else 0, user_id)
            )
            if not active:
                conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            audit_event(
                conn,
                actor_user_id=actor_user_id,
                action="user_activation_changed",
                target_type="user",
                target_id=str(user_id),
                details={"active": active},
                created_at=utc_now_iso(),
            )

    def delete_account(self, user_id: int) -> None:
        now = utc_now_iso()
        with connection(self.db_path) as conn:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM hazard_votes WHERE user_id = ?", (user_id,))
            conn.execute(
                "DELETE FROM hazards WHERE user_id = ? AND status IN ('unverified', 'rejected')",
                (user_id,),
            )
            conn.execute(
                "UPDATE hazards SET user_id = NULL WHERE user_id = ?", (user_id,)
            )
            audit_event(
                conn,
                actor_user_id=user_id,
                action="account_deleted",
                target_type="user",
                target_id=str(user_id),
                details={"hazards_anonymised": True},
                created_at=now,
            )
            conn.execute("DELETE FROM users WHERE id = ?", (user_id,))

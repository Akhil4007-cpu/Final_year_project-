"""Provision an administrator account from the server console.

Usage:
    python scripts/create_admin.py --email admin@example.com
    python scripts/create_admin.py --email existing@example.com --reset-password
    python scripts/create_admin.py --email rider@example.com --promote

The password is read with getpass and never passed on the command line.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.db import connection, init_db, utc_now_iso  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.security import audit_event, hash_password, validate_email, validate_password  # noqa: E402


def _read_password() -> str:
    password = getpass.getpass("Administrator password (min 10 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")
    return validate_password(password)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote a RoadGuard administrator.")
    parser.add_argument("--email", required=True, help="Administrator email address.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--reset-password",
        action="store_true",
        help="Reset the password of an existing administrator.",
    )
    group.add_argument(
        "--promote",
        action="store_true",
        help="Promote an existing rider and reset their password.",
    )
    args = parser.parse_args()

    try:
        email = validate_email(args.email)
    except AppError as exc:
        print(exc.message, file=sys.stderr)
        return 1

    settings = get_settings()
    init_db(settings.db_path)
    now = utc_now_iso()

    with connection(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, role, is_active FROM users WHERE email = ? COLLATE NOCASE",
            (email,),
        ).fetchone()
        if row is not None:
            if row["role"] == "rider" and not args.promote:
                print(
                    f"{email} belongs to a rider account. Re-run with --promote to "
                    "promote it and reset its password.",
                    file=sys.stderr,
                )
                return 1
            if row["role"] == "admin" and not args.reset_password:
                print(
                    f"{email} is already an administrator. Re-run with --reset-password "
                    "to set a new password.",
                    file=sys.stderr,
                )
                return 1

        password_hash = hash_password(_read_password())

        if row is None:
            cursor = conn.execute(
                "INSERT INTO users(email, password_hash, role, is_active, created_at) "
                "VALUES (?, ?, 'admin', 1, ?)",
                (email, password_hash, now),
            )
            user_id = cast(int, cursor.lastrowid)
            action = "admin_bootstrapped"
            details = {"method": "cli", "created": True}
        else:
            user_id = int(row["id"])
            conn.execute(
                "UPDATE users SET password_hash = ?, role = 'admin', is_active = 1 WHERE id = ?",
                (password_hash, user_id),
            )
            promoted = row["role"] == "rider"
            action = "admin_promoted" if promoted else "admin_password_reset"
            details = {"method": "cli", "promoted": promoted}
        audit_event(
            conn,
            actor_user_id=None,
            action=action,
            target_type="user",
            target_id=str(user_id),
            details=details,
            created_at=now,
        )

    print(f"Administrator ready: {email} (user id {user_id}).")
    print("Sign in at /admin. Do not store the password in the repository.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

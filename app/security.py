from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
import time
from collections import defaultdict, deque
from typing import Any

from app.errors import invalid_input

PBKDF2_ITERATIONS = 260_000
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_COOKIE = "roadguard_session"
CLIENT_HEADER = "X-RoadGuard-Client"


def validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or not EMAIL_RE.match(normalized):
        raise invalid_input("A valid email address is required.")
    return normalized


def validate_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < 10:
        raise invalid_input("Password must be at least 10 characters.")
    if len(password) > 200:
        raise invalid_input("Password must be at most 200 characters.")
    return password


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class RateLimiter:
    """Single-process sliding-window limiter; documented as such in the runbook."""

    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._last_cleanup = time.monotonic()

    def check(self, key: str, limit: int, window_seconds: int) -> int | None:
        now = time.monotonic()
        with self._lock:
            if now - self._last_cleanup > 300:
                self._cleanup(now)
            bucket = self._events[key]
            while bucket and now - bucket[0] >= window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])) + 1)
                return retry_after
            bucket.append(now)
            return None

    def _cleanup(self, now: float) -> None:
        stale = [
            key
            for key, bucket in self._events.items()
            if not bucket or now - bucket[-1] > 3600
        ]
        for key in stale:
            self._events.pop(key, None)
        self._last_cleanup = now


def audit_event(
    conn: Any,
    *,
    actor_user_id: int | None,
    action: str,
    target_type: str,
    target_id: str | None,
    details: dict[str, Any] | None = None,
    created_at: str,
) -> None:
    import json

    conn.execute(
        "INSERT INTO audit_log(actor_user_id, action, target_type, target_id, details_json, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (
            actor_user_id,
            action,
            target_type,
            target_id,
            json.dumps(details or {}, separators=(",", ":"), sort_keys=True),
            created_at,
        ),
    )

from __future__ import annotations

import pytest

from app.errors import AppError
from app.security import (
    PBKDF2_ITERATIONS,
    RateLimiter,
    audit_event,
    hash_password,
    hash_token,
    new_session_token,
    validate_email,
    validate_password,
    verify_password,
)


def test_validate_email_normalises_case():
    assert validate_email("  Rider@Example.COM ") == "rider@example.com"


@pytest.mark.parametrize("bad", ["no-at-sign", "a@b", "@nolocal.com", "spaces in@x.com", "a@b@c.com"])
def test_validate_email_rejects_bad(bad):
    with pytest.raises(AppError):
        validate_email(bad)


def test_validate_password_min_length():
    with pytest.raises(AppError):
        validate_password("short1!")
    assert validate_password("LongEnough#2026") == "LongEnough#2026"


def test_validate_password_max_length():
    with pytest.raises(AppError):
        validate_password("a" * 201)


def test_hash_and_verify_roundtrip():
    stored = hash_password("CorrectHorse#1")
    assert stored.startswith("pbkdf2_sha256$")
    assert str(PBKDF2_ITERATIONS) in stored
    assert verify_password("CorrectHorse#1", stored)
    assert not verify_password("WrongPassword#2", stored)


def test_hash_uses_random_salt():
    a = hash_password("SamePass#123")
    b = hash_password("SamePass#123")
    assert a != b
    assert verify_password("SamePass#123", a) and verify_password("SamePass#123", b)


def test_verify_password_rejects_garbage():
    assert not verify_password("x", "not-a-valid-hash")
    assert not verify_password("x", "md5$1$deadbeef$cafebabe")


def test_session_tokens_are_unique_and_hashed():
    t1, t2 = new_session_token(), new_session_token()
    assert t1 != t2
    assert hash_token(t1) != hash_token(t2)
    assert hash_token(t1) == hash_token(t1)


def test_rate_limiter_blocks_after_limit():
    limiter = RateLimiter()
    assert limiter.check("k", limit=3, window_seconds=60) is None
    assert limiter.check("k", limit=3, window_seconds=60) is None
    assert limiter.check("k", limit=3, window_seconds=60) is None
    retry = limiter.check("k", limit=3, window_seconds=60)
    assert retry is not None and retry >= 1


def test_rate_limiter_isolated_per_key():
    limiter = RateLimiter()
    for _ in range(3):
        limiter.check("a", limit=3, window_seconds=60)
    assert limiter.check("b", limit=3, window_seconds=60) is None


def test_audit_event_writes_json_details(tmp_path):
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE audit_log(id INTEGER PRIMARY KEY, actor_user_id INTEGER, action TEXT, "
        "target_type TEXT, target_id TEXT, details_json TEXT, created_at TEXT)"
    )
    audit_event(
        conn,
        actor_user_id=1,
        action="hazard_created",
        target_type="hazard",
        target_id="5",
        details={"category": "pothole"},
        created_at="2026-10-17T00:00:00+00:00",
    )
    row = conn.execute("SELECT details_json FROM audit_log").fetchone()
    assert '"category":"pothole"' in row[0]

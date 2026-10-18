from __future__ import annotations

from enum import Enum
from typing import Any


class ErrorCode(str, Enum):
    invalid_input = "invalid_input"
    insufficient_evidence = "insufficient_evidence"
    provider_unavailable = "provider_unavailable"
    auth_failure = "auth_failure"
    authz_failure = "authz_failure"
    model_unavailable = "model_unavailable"
    internal_error = "internal_error"
    rate_limited = "rate_limited"
    not_found = "not_found"


class AppError(Exception):
    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}

    def as_body(self) -> dict[str, Any]:
        body: dict[str, Any] = {"code": self.code.value, "message": self.message}
        if self.details:
            body["details"] = self.details
        return {"error": body}


def invalid_input(message: str, **details: Any) -> AppError:
    return AppError(ErrorCode.invalid_input, message, status_code=400, details=details or None)


def insufficient_evidence(message: str, **details: Any) -> AppError:
    return AppError(
        ErrorCode.insufficient_evidence, message, status_code=422, details=details or None
    )


def provider_unavailable(provider: str, message: str, **details: Any) -> AppError:
    payload = {"provider": provider, **details}
    return AppError(
        ErrorCode.provider_unavailable,
        message,
        status_code=503,
        details=payload,
    )


def model_unavailable(message: str, **details: Any) -> AppError:
    return AppError(
        ErrorCode.model_unavailable, message, status_code=503, details=details or None
    )


def auth_failure(message: str = "Authentication required") -> AppError:
    return AppError(ErrorCode.auth_failure, message, status_code=401)


def authz_failure(message: str = "Not permitted") -> AppError:
    return AppError(ErrorCode.authz_failure, message, status_code=403)


def not_found(message: str) -> AppError:
    return AppError(ErrorCode.not_found, message, status_code=404)


def rate_limited(message: str, retry_after_s: int) -> AppError:
    return AppError(
        ErrorCode.rate_limited,
        message,
        status_code=429,
        details={"retry_after_s": retry_after_s},
    )

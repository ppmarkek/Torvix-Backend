from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# NOTE: bcrypt backend has compatibility issues in this runtime.
# pbkdf2_sha256 is stable and supported directly by passlib.
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash plain password using passlib context.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string")
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify plain password against stored hash.
    """
    if not password or not password_hash:
        return False
    try:
        return pwd_context.verify(password, password_hash)
    except Exception:
        return False


def _create_token(
    *,
    user_id: str | int,
    token_type: str,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    exp = now + expires_delta

    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "type": token_type,
    }
    if extra_claims:
        for key in ("sub", "iat", "exp", "type"):
            if key in extra_claims:
                raise ValueError(f"extra_claims cannot override '{key}'")
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def create_access_token(
    user_id: str | int,
    *,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    Create JWT access token.
    """
    if expires_minutes is None:
        expires_minutes = settings.ACCESS_TOKEN_MINUTES

    return _create_token(
        user_id=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=int(expires_minutes)),
        extra_claims=extra_claims,
    )


def create_refresh_token(
    user_id: str | int,
    *,
    session_id: str | int,
    expires_days: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    if expires_days is None:
        expires_days = settings.REFRESH_TOKEN_DAYS

    claims = {"sid": str(session_id)}
    if extra_claims:
        claims.update(extra_claims)
    return _create_token(
        user_id=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=int(expires_days)),
        extra_claims=claims,
    )


def _decode_token(token: str, *, expected_type: str) -> dict[str, Any]:
    if not token:
        raise ValueError("Token is required")

    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except JWTError as e:
        raise ValueError("Invalid or expired token") from e

    if payload.get("type") != expected_type:
        raise ValueError("Invalid token type")

    sub = payload.get("sub")
    if not sub:
        raise ValueError("Token subject is missing")

    return payload


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and validate JWT access token.
    Returns token payload dict if valid.

    Raises ValueError on invalid/expired token.
    """
    return _decode_token(token, expected_type="access")


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(token, expected_type="refresh")


def hash_refresh_token(token: str) -> str:
    if not token:
        raise ValueError("Refresh token is required")
    digest = hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest


def verify_refresh_token(token: str, token_hash: str) -> bool:
    if not token or not token_hash:
        return False
    expected = hash_refresh_token(token)
    return hmac.compare_digest(expected, token_hash)

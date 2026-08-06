"""Password hashing, JWT issuance/validation, and refresh-token hashing."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from hmac import compare_digest
from typing import Literal
from uuid import UUID, uuid4

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import PwdlibError

from app.config import Settings, get_settings
from app.exceptions import AuthenticationError

TokenType = Literal["access", "refresh"]

password_hasher = PasswordHash.recommended()
_DUMMY_PASSWORD_HASH = password_hasher.hash(
    "not-a-user-password-dummy-verification-value"
)


@dataclass(frozen=True)
class IssuedToken:
    value: str
    jti: UUID
    expires_at: datetime


@dataclass(frozen=True)
class TokenClaims:
    user_id: UUID
    tenant_id: UUID
    token_type: TokenType
    jti: UUID
    issued_at: datetime
    expires_at: datetime


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Normalize timestamps returned without tzinfo by lightweight test databases."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def hash_password(password: str) -> str:
    """Hash a password with pwdlib's recommended Argon2id parameters."""
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password without surfacing malformed-hash details."""
    try:
        return password_hasher.verify(password, password_hash)
    except (PwdlibError, ValueError):
        return False


def verify_dummy_password(password: str) -> None:
    """Spend normal verification work when the requested identity does not exist."""
    verify_password(password, _DUMMY_PASSWORD_HASH)


def issue_token(
    *,
    user_id: UUID,
    tenant_id: UUID,
    token_type: TokenType,
    settings: Settings | None = None,
    now: datetime | None = None,
    lifetime: timedelta | None = None,
    jti: UUID | None = None,
) -> IssuedToken:
    """Create a signed access or refresh token with all mandatory claims."""
    settings = settings or get_settings()
    issued_at = ensure_utc(now or utc_now())
    if lifetime is None:
        lifetime = (
            timedelta(minutes=settings.jwt_access_token_minutes)
            if token_type == "access"
            else timedelta(days=settings.jwt_refresh_token_days)
        )
    expires_at = issued_at + lifetime
    token_jti = jti or uuid4()
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "token_type": token_type,
        "jti": str(token_jti),
        "iat": issued_at,
        "exp": expires_at,
    }
    encoded = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    return IssuedToken(value=encoded, jti=token_jti, expires_at=expires_at)


def decode_token(
    token: str,
    *,
    expected_type: TokenType,
    settings: Settings | None = None,
) -> TokenClaims:
    """Verify a JWT before returning typed, structurally validated claims."""
    settings = settings or get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["sub", "tenant_id", "token_type", "jti", "iat", "exp"],
                "verify_exp": True,
                "verify_iat": True,
                "verify_signature": True,
            },
        )
        token_type = payload["token_type"]
        if token_type != expected_type or token_type not in ("access", "refresh"):
            raise AuthenticationError
        return TokenClaims(
            user_id=UUID(payload["sub"]),
            tenant_id=UUID(payload["tenant_id"]),
            token_type=token_type,
            jti=UUID(payload["jti"]),
            issued_at=datetime.fromtimestamp(payload["iat"], tz=UTC),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (
        InvalidTokenError,
        KeyError,
        TypeError,
        ValueError,
        AuthenticationError,
    ) as exc:
        raise AuthenticationError from exc


def hash_refresh_token(token: str) -> str:
    """Return the irreversible digest persisted for a refresh token."""
    return sha256(token.encode("utf-8")).hexdigest()


def refresh_token_matches(token: str, stored_hash: str) -> bool:
    return compare_digest(hash_refresh_token(token), stored_hash)

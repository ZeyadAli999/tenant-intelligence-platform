"""Password and JWT primitive tests."""

from datetime import timedelta
from uuid import uuid4

import pytest

from app.exceptions import AuthenticationError
from core.security import (
    decode_token,
    hash_password,
    hash_refresh_token,
    issue_token,
    utc_now,
    verify_password,
)
from database.session import engine


def test_passwords_use_argon2id_and_verify_safely() -> None:
    password = "A-Sufficiently-Strong-Password-99"
    password_hash = hash_password(password)

    assert password_hash.startswith("$argon2id$")
    assert password not in password_hash
    assert verify_password(password, password_hash) is True
    assert verify_password("wrong-password", password_hash) is False
    assert verify_password(password, "not-a-valid-hash") is False


def test_jwt_contains_and_validates_required_claims() -> None:
    user_id = uuid4()
    tenant_id = uuid4()
    issued = issue_token(
        user_id=user_id,
        tenant_id=tenant_id,
        token_type="access",
    )

    claims = decode_token(issued.value, expected_type="access")

    assert claims.user_id == user_id
    assert claims.tenant_id == tenant_id
    assert claims.jti == issued.jti
    assert claims.token_type == "access"
    assert claims.expires_at > claims.issued_at


def test_expired_token_is_rejected() -> None:
    issued = issue_token(
        user_id=uuid4(),
        tenant_id=uuid4(),
        token_type="access",
        now=utc_now() - timedelta(minutes=2),
        lifetime=timedelta(minutes=1),
    )

    with pytest.raises(AuthenticationError):
        decode_token(issued.value, expected_type="access")


def test_modified_and_wrong_type_tokens_are_rejected() -> None:
    refresh = issue_token(
        user_id=uuid4(),
        tenant_id=uuid4(),
        token_type="refresh",
    )
    header, payload, signature = refresh.value.split(".")
    modified_signature = ("a" if signature[0] != "a" else "b") + signature[1:]
    modified = f"{header}.{payload}.{modified_signature}"

    with pytest.raises(AuthenticationError):
        decode_token(modified, expected_type="refresh")
    with pytest.raises(AuthenticationError):
        decode_token(refresh.value, expected_type="access")


def test_refresh_hash_is_deterministic_and_not_raw_token() -> None:
    token = "signed.refresh.token"
    digest = hash_refresh_token(token)

    assert digest == hash_refresh_token(token)
    assert token not in digest
    assert len(digest) == 64


def test_sqlalchemy_always_hides_parameter_values() -> None:
    assert engine.sync_engine.hide_parameters is True

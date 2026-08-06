"""AES-GCM credential encryption and configuration tests."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.config import Settings
from core.encryption import (
    CredentialCipher,
    CredentialDecryptionError,
    credential_context,
)

VALID_KEY = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8"


def test_credential_encryption_round_trip_is_randomized_and_bound() -> None:
    cipher = CredentialCipher.from_settings(
        Settings(connection_encryption_key=VALID_KEY)
    )
    context = credential_context(uuid4(), uuid4())

    first = cipher.encrypt("customer-password", associated_data=context)
    second = cipher.encrypt("customer-password", associated_data=context)

    assert first != second
    assert "customer-password" not in first
    assert cipher.decrypt(first, associated_data=context) == "customer-password"
    with pytest.raises(CredentialDecryptionError):
        cipher.decrypt(first, associated_data=credential_context(uuid4(), uuid4()))


def test_tampered_ciphertext_is_rejected() -> None:
    cipher = CredentialCipher.from_settings(
        Settings(connection_encryption_key=VALID_KEY)
    )
    context = credential_context(uuid4(), uuid4())
    payload = cipher.encrypt("customer-password", associated_data=context)
    version, nonce, ciphertext = payload.split(".")
    replacement = ("a" if ciphertext[0] != "a" else "b") + ciphertext[1:]

    with pytest.raises(CredentialDecryptionError):
        cipher.decrypt(f"{version}.{nonce}.{replacement}", associated_data=context)


@pytest.mark.parametrize(
    "invalid_key",
    [
        "short",
        "replace-with-a-base64url-encoded-32-byte-key",
        "not!base64url!material",
    ],
)
def test_invalid_connection_encryption_key_is_rejected_without_echo(
    invalid_key: str,
) -> None:
    with pytest.raises(ValidationError) as captured:
        Settings(connection_encryption_key=invalid_key)

    assert invalid_key not in str(captured.value)

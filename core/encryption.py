"""Versioned authenticated encryption for customer database credentials."""

import base64
import binascii
import os
from dataclasses import dataclass
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import Settings, get_settings

PAYLOAD_VERSION = "v1"
NONCE_BYTES = 12


class CredentialDecryptionError(Exception):
    """Raised without credential details when a payload cannot be authenticated."""


def _decode_base64url(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(value + padding, altchars=b"-_", validate=True)


def _encode_base64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def credential_context(tenant_id: UUID, connection_id: UUID) -> bytes:
    """Bind ciphertext to one tenant-owned connection record."""
    return f"database-credential:{tenant_id}:{connection_id}:{PAYLOAD_VERSION}".encode()


@dataclass(frozen=True)
class CredentialCipher:
    """AES-256-GCM cipher with a stable versioned storage envelope."""

    key: bytes

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "CredentialCipher":
        settings = settings or get_settings()
        encoded = settings.connection_encryption_key.get_secret_value()
        return cls(key=_decode_base64url(encoded))

    def encrypt(self, plaintext: str, *, associated_data: bytes) -> str:
        nonce = os.urandom(NONCE_BYTES)
        ciphertext = AESGCM(self.key).encrypt(
            nonce,
            plaintext.encode("utf-8"),
            associated_data,
        )
        return ".".join(
            (PAYLOAD_VERSION, _encode_base64url(nonce), _encode_base64url(ciphertext))
        )

    def decrypt(self, payload: str, *, associated_data: bytes) -> str:
        try:
            version, encoded_nonce, encoded_ciphertext = payload.split(".", maxsplit=2)
            if version != PAYLOAD_VERSION:
                raise CredentialDecryptionError
            nonce = _decode_base64url(encoded_nonce)
            ciphertext = _decode_base64url(encoded_ciphertext)
            if len(nonce) != NONCE_BYTES:
                raise CredentialDecryptionError
            plaintext = AESGCM(self.key).decrypt(
                nonce,
                ciphertext,
                associated_data,
            )
            return plaintext.decode("utf-8")
        except (
            InvalidTag,
            UnicodeDecodeError,
            ValueError,
            binascii.Error,
            CredentialDecryptionError,
        ) as exc:
            raise CredentialDecryptionError from exc

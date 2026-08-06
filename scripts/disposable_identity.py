"""Safe generated identities used only by disposable smoke and evaluation flows."""

from __future__ import annotations

import re

_LOCAL_PART = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?\Z")


def disposable_email(prefix: str, unique_value: str) -> str:
    """Return a unique, EmailStr-compatible documentation address."""
    local = f"{prefix.strip().casefold()}-{unique_value.strip().casefold()}"
    if _LOCAL_PART.fullmatch(local) is None:
        raise ValueError("INVALID_DISPOSABLE_EMAIL_COMPONENT")
    return f"{local}@example.com"

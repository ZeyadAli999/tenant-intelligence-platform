"""Configuration contract and security-hardening tests."""

import pytest
from pydantic import ValidationError

from app.config import Settings

TEST_DATABASE_URL = (
    "postgresql+asyncpg://test_user:test_password@localhost:5432/test_database"
)


def test_phase_1_public_contract_settings() -> None:
    settings = Settings(database_url=TEST_DATABASE_URL)

    assert settings.app_version == "1.0.0"
    assert settings.api_prefix == "/api"
    assert settings.debug is False
    assert TEST_DATABASE_URL not in repr(settings)


def test_false_debug_value_from_environment_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEBUG", "false")

    settings = Settings(database_url=TEST_DATABASE_URL, _env_file=None)

    assert settings.debug is False


@pytest.mark.parametrize(
    ("field", "value"),
    [("api_prefix", "/other"), ("debug", True)],
)
def test_public_prefix_and_debug_mode_cannot_be_overridden(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=TEST_DATABASE_URL, **{field: value})


@pytest.mark.parametrize(
    "weak_secret",
    ["short", "replace-with-at-least-32-random-bytes", "a" * 40],
)
def test_weak_jwt_secrets_fail_without_echoing_the_secret(weak_secret: str) -> None:
    with pytest.raises(ValidationError) as captured:
        Settings(database_url=TEST_DATABASE_URL, jwt_secret=weak_secret)

    assert weak_secret not in str(captured.value)


def test_missing_jwt_secret_is_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("JWT_SECRET")

    with pytest.raises(ValidationError) as captured:
        Settings(database_url=TEST_DATABASE_URL, _env_file=None)

    assert "jwt_secret" in str(captured.value)
    assert "Field required" in str(captured.value)


def test_groq_provider_requires_non_placeholder_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GROQ_API_KEY")
    with pytest.raises(ValidationError) as captured:
        Settings(
            database_url=TEST_DATABASE_URL,
            groq_api_key="replace-with-your-local-groq-key",
            _env_file=None,
        )
    assert "replace-with-your-local-groq-key" not in str(captured.value)

    with pytest.raises(ValidationError):
        Settings(database_url=TEST_DATABASE_URL, _env_file=None)


def test_valid_groq_configuration_protects_key_in_repr() -> None:
    key = "gsk_test_only_inert_value_12345678901234567890"
    settings = Settings(database_url=TEST_DATABASE_URL, groq_api_key=key)
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert key not in repr(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [("groq_model", "other/model"), ("groq_timeout_seconds", 0)],
)
def test_invalid_groq_runtime_settings_are_rejected(field: str, value: object) -> None:
    with pytest.raises(ValidationError):
        Settings(database_url=TEST_DATABASE_URL, **{field: value})

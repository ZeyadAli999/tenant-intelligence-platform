"""Dedicated PostgreSQL integration-test safeguards."""

import os

import pytest
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def postgres_test_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL is not configured")
    url = make_url(value)
    if url.drivername != "postgresql+asyncpg":
        pytest.fail("TEST_DATABASE_URL must use postgresql+asyncpg")
    if not url.database or "test" not in url.database.casefold():
        pytest.fail(
            "TEST_DATABASE_URL must name a dedicated database containing 'test'"
        )
    return value

"""Live PostgreSQL Alembic upgrade and downgrade verification."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark = pytest.mark.integration
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.asyncio
async def test_migration_upgrade_and_downgrade(postgres_test_url: str) -> None:
    run_alembic(postgres_test_url, "upgrade", "head")
    run_alembic(postgres_test_url, "downgrade", "20260803_0001")

    engine = create_async_engine(postgres_test_url)
    async with engine.connect() as connection:
        tables_after_downgrade = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    assert "tenants" not in tables_after_downgrade

    run_alembic(postgres_test_url, "upgrade", "head")
    async with engine.connect() as connection:
        tables_after_upgrade = await connection.run_sync(
            lambda sync_connection: inspect(sync_connection).get_table_names()
        )
    await engine.dispose()

    assert {
        "tenants",
        "users",
        "roles",
        "user_roles",
        "refresh_tokens",
        "database_connections",
        "database_schemas",
        "database_tables",
        "database_columns",
        "table_permissions",
        "column_permissions",
        "query_executions",
        "knowledge_bases",
        "files",
        "document_chunks",
        "message_citations",
    }.issubset(tables_after_upgrade)

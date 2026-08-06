"""Deterministic, permission-trimmed schema retrieval tests."""

import json

import pytest

from app.config import Settings
from services.database.permission_resolver import PermissionResolver
from services.database.schema_retriever import AllowedSchemaRetriever
from tests.unit.conftest import DatabaseHarness
from tests.unit.test_safe_query_service import setup_execution


@pytest.mark.asyncio
async def test_retriever_contains_only_effective_readable_schema_and_no_rows(
    test_database: DatabaseHarness,
) -> None:
    identity, catalog, context = await setup_execution(test_database, Settings())
    async with test_database.sessions() as session:
        allowed = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=tuple(role.id for role in context.roles),
            connection_id=catalog.connection.id,
        )
        result = AllowedSchemaRetriever(3, 20).retrieve("customers by country", allowed)
    assert result is not None
    payload = json.loads(result.serialized)
    assert result.table_names == ("business.customers",)
    assert {item["name"] for item in payload["tables"][0]["columns"]} == {
        "id",
        "country",
        "tax_identifier",
    }
    assert payload["metadata_is_untrusted"] is True
    assert "EG-SECRET-001" not in result.serialized
    assert "row_filter" not in result.serialized


@pytest.mark.asyncio
async def test_retriever_returns_none_when_question_matches_no_allowed_object(
    test_database: DatabaseHarness,
) -> None:
    identity, catalog, context = await setup_execution(test_database, Settings())
    async with test_database.sessions() as session:
        allowed = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=tuple(role.id for role in context.roles),
            connection_id=catalog.connection.id,
        )
        result = AllowedSchemaRetriever(3, 20).retrieve(
            "unrelated weather forecast", allowed
        )
    assert result is None

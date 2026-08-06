"""Regression coverage for tenant/connection-scoped sensitive-column setup."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from models import DatabaseColumn
from scripts import phase4_live_stages as live
from scripts import phase4_safe_inspect as inspect
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import seed_identity
from tests.unit.phase3b_helpers import seed_catalog


@pytest.mark.asyncio
async def test_mark_sensitive_scopes_through_owning_table_connection(
    test_database: DatabaseHarness, monkeypatch
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    tax = next(
        item
        for item in catalog.customer_columns
        if item.column_name == "tax_identifier"
    )
    country = next(
        item for item in catalog.customer_columns if item.column_name == "country"
    )
    async with test_database.sessions() as session:
        stored = await session.get(DatabaseColumn, tax.id)
        stored.is_sensitive = False
        await session.commit()
    monkeypatch.setattr(inspect, "AsyncSessionFactory", test_database.sessions)
    result = await inspect.mark_sensitive(
        SimpleNamespace(
            tenant_id=str(identity.tenant.id),
            connection_id=str(catalog.connection.id),
            column_id=str(tax.id),
        )
    )
    async with test_database.sessions() as session:
        values = dict(
            (
                await session.execute(
                    select(DatabaseColumn.id, DatabaseColumn.is_sensitive)
                )
            ).all()
        )
    assert result == {"updated": True}
    assert values[tax.id] is True
    assert values[country.id] is False


@pytest.mark.asyncio
async def test_mark_sensitive_rejects_wrong_connection_and_other_tenant(
    test_database: DatabaseHarness, monkeypatch
) -> None:
    first = await seed_identity(test_database)
    second = await seed_identity(
        test_database, tenant_code="sensitive-other", email="admin@sensitive.example"
    )
    first_catalog = await seed_catalog(test_database, first, name="first")
    second_catalog = await seed_catalog(test_database, second, name="second")
    column = first_catalog.customer_columns[0]
    monkeypatch.setattr(inspect, "AsyncSessionFactory", test_database.sessions)
    wrong_connection = await inspect.mark_sensitive(
        SimpleNamespace(
            tenant_id=str(first.tenant.id),
            connection_id=str(uuid4()),
            column_id=str(column.id),
        )
    )
    wrong_tenant = await inspect.mark_sensitive(
        SimpleNamespace(
            tenant_id=str(second.tenant.id),
            connection_id=str(second_catalog.connection.id),
            column_id=str(column.id),
        )
    )
    assert wrong_connection == {"updated": False}
    assert wrong_tenant == {"updated": False}


def table_payload() -> dict[str, object]:
    return {
        "table_name": "customers",
        "id": "table-id",
        "columns": [
            {"column_name": "country", "id": "country-id"},
            {"column_name": "tax_identifier", "id": "tax-id"},
        ],
    }


def smoke_state() -> dict[str, object]:
    return {
        "connection_id": "connection-id",
        "tenant_id": "tenant-id",
        "admin_access_token": "token",
        "normal_user_id": "user-id",
    }


def test_configure_permissions_continues_with_egypt_filter_and_redact(
    monkeypatch, tmp_path
) -> None:
    requests: list[tuple[str, str, dict[str, object]]] = []

    def request(state, method, path, **kwargs):
        requests.append((method, path, kwargs.get("json", {})))
        if method == "GET":
            return {"items": [table_payload()]}
        return {"id": "permission-id"}

    monkeypatch.setattr(live, "request", request)
    monkeypatch.setattr(live, "safe_inspect", lambda *args: {"updated": True})
    live.configure_permissions(tmp_path, smoke_state(), "hybrid")
    table_request = next(item for item in requests if item[0] == "POST")
    column_request = next(item for item in requests if item[0] == "PUT")
    assert table_request[1] == "/permissions/tables"
    assert column_request[1] == "/permissions/tables/permission-id/columns"
    condition = table_request[2]["row_filter"]["all"][0]
    assert condition["column_id"] == "country-id"
    assert condition["value"] == {"source": "literal", "value": "Egypt"}
    masks = {
        item["column_id"]: item["mask_type"] for item in column_request[2]["items"]
    }
    assert masks["tax-id"] == "redact"


def test_failed_sensitive_scope_stops_permission_configuration(
    monkeypatch, tmp_path
) -> None:
    methods: list[str] = []

    def request(state, method, path, **kwargs):
        methods.append(method)
        return {"items": [table_payload()]}

    monkeypatch.setattr(live, "request", request)
    monkeypatch.setattr(live, "safe_inspect", lambda *args: {"updated": False})
    with pytest.raises(AssertionError, match="SENSITIVE_COLUMN_SCOPE_FAILED"):
        live.configure_permissions(tmp_path, smoke_state(), "hybrid")
    assert methods == ["GET"]


def test_database_column_has_no_redundant_connection_id() -> None:
    assert "connection_id" not in DatabaseColumn.__table__.columns


def test_customer_compose_does_not_inherit_host_groq_gate(
    monkeypatch, tmp_path
) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setenv("GROQ_API_KEY", "host-gate-not-runtime-configuration")
    monkeypatch.setenv("RUN_REAL_GROQ_VERIFICATION", "1")
    monkeypatch.setenv("CUSTOMER_POSTGRES_READER_USER", "reader")

    def run(*args, **kwargs):
        captured.update(kwargs["env"])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(live.subprocess, "run", run)
    monkeypatch.setattr(
        live,
        "customer_source_facts",
        lambda: {"row_count": 2, "table_exists": True},
    )
    monkeypatch.setattr(
        live.httpx,
        "get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200),
    )
    live.create_customer_database(tmp_path, {}, "hybrid")
    assert "GROQ_API_KEY" not in captured
    assert "RUN_REAL_GROQ_VERIFICATION" not in captured
    assert captured["CUSTOMER_POSTGRES_READER_USER"] == "reader"


def test_hybrid_contract_failure_reports_only_safe_shape(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        live,
        "request",
        lambda *args, **kwargs: {
            "intent": "hybrid",
            "sources_used": ["documents"],
            "sql": None,
            "answer": "raw answer must not enter details",
            "citations": [],
            "message_id": "hidden-id",
            "usage": {"prompt_tokens": 1},
        },
    )
    state = {
        "normal_user_access_token": "token",
        "conversation_id": "conversation",
        "knowledge_base_id": "kb",
        "connection_id": "connection",
    }
    with pytest.raises(live.StageContractFailure) as raised:
        live.verify_hybrid_chat(tmp_path, state, "hybrid")
    assert raised.value.category == "HYBRID_SOURCES_MISMATCH"
    serialized = str(raised.value.details)
    assert "raw answer" not in serialized and "hidden-id" not in serialized

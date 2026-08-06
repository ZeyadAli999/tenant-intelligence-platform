"""Tenant-isolated permission API behavior."""

from uuid import uuid4

import pytest

from core.security import hash_password
from models import User
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import login, seed_identity
from tests.unit.phase3b_helpers import seed_catalog


@pytest.mark.asyncio
async def test_admin_permission_crud_and_columns(
    api_client: object, test_database: DatabaseHarness
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    tokens = await login(api_client, identity)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    created = await api_client.post(
        "/api/permissions/tables",
        headers=headers,
        json={
            "role_id": str(identity.roles[0].id),
            "connection_id": str(catalog.connection.id),
            "table_id": str(catalog.customers.id),
            "row_filter": {
                "version": 1,
                "all": [
                    {
                        "column_id": str(catalog.customer_columns[1].id),
                        "operator": "eq",
                        "value": {"source": "literal", "value": "Egypt"},
                    }
                ],
            },
        },
    )
    assert created.status_code == 201
    permission_id = created.json()["id"]
    assert (
        not {"tenant_id", "password", "token", "encrypted_password"}
        & created.json().keys()
    )
    replaced = await api_client.put(
        f"/api/permissions/tables/{permission_id}/columns",
        headers=headers,
        json={
            "items": [
                {
                    "column_id": str(catalog.customer_columns[0].id),
                    "can_read": True,
                    "can_filter": True,
                    "can_aggregate": True,
                },
                {
                    "column_id": str(catalog.customer_columns[1].id),
                    "can_read": True,
                    "can_filter": True,
                    "can_aggregate": True,
                },
                {
                    "column_id": str(catalog.customer_columns[2].id),
                    "can_read": True,
                    "can_filter": False,
                    "can_aggregate": False,
                    "mask_type": "redact",
                },
            ]
        },
    )
    assert replaced.status_code == 200 and len(replaced.json()["items"]) == 3
    assert (
        await api_client.get(
            f"/api/permissions/tables/{permission_id}", headers=headers
        )
    ).status_code == 200
    assert (
        await api_client.get(
            "/api/permissions/tables?page=1&page_size=10", headers=headers
        )
    ).json()["total"] == 1
    assert (
        await api_client.put(
            f"/api/permissions/tables/{permission_id}",
            headers=headers,
            json={"can_read": False},
        )
    ).json()["can_read"] is False
    assert (
        await api_client.get(
            f"/api/permissions/tables/{permission_id}/columns", headers=headers
        )
    ).status_code == 200
    assert (
        await api_client.delete(
            f"/api/permissions/tables/{permission_id}", headers=headers
        )
    ).status_code == 204


@pytest.mark.asyncio
async def test_normal_user_cannot_mutate_and_unknown_fields_are_rejected(
    api_client: object, test_database: DatabaseHarness
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    normal = User(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        email="normal@acme.example",
        password_hash=hash_password("Normal-User-Password-99"),
        is_tenant_admin=False,
    )
    async with test_database.sessions() as session:
        session.add(normal)
        await session.commit()
    normal_identity = type(identity)(
        identity.tenant, normal, "Normal-User-Password-99", ()
    )
    tokens = await login(api_client, normal_identity)
    response = await api_client.post(
        "/api/permissions/tables",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={
            "user_id": str(normal.id),
            "connection_id": str(catalog.connection.id),
            "table_id": str(catalog.customers.id),
        },
    )
    assert response.status_code == 403
    admin = await login(api_client, identity)
    invalid = await api_client.post(
        "/api/permissions/tables",
        headers={"Authorization": f"Bearer {admin['access_token']}"},
        json={
            "user_id": str(normal.id),
            "connection_id": str(catalog.connection.id),
            "table_id": str(catalog.customers.id),
            "tenant_id": str(identity.tenant.id),
        },
    )
    assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_cross_tenant_permission_resources_are_hidden(
    api_client: object, test_database: DatabaseHarness
) -> None:
    tenant_a = await seed_identity(
        test_database, tenant_code="perm-a", email="admin@perm-a.example"
    )
    tenant_b = await seed_identity(
        test_database, tenant_code="perm-b", email="admin@perm-b.example"
    )
    catalog_b = await seed_catalog(test_database, tenant_b, name="customer-b")
    tokens = await login(api_client, tenant_a)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = await api_client.post(
        "/api/permissions/tables",
        headers=headers,
        json={
            "user_id": str(tenant_a.user.id),
            "connection_id": str(catalog_b.connection.id),
            "table_id": str(catalog_b.customers.id),
        },
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_allowed_schema_is_current_user_only_and_inactive_membership_is_rejected(
    api_client: object, test_database: DatabaseHarness
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    normal = User(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        email="schema-user@acme.example",
        password_hash=hash_password("Schema-User-Password-99"),
        is_tenant_admin=False,
    )
    async with test_database.sessions() as session:
        session.add(normal)
        await session.commit()
    admin_tokens = await login(api_client, identity)
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    created = await api_client.post(
        "/api/permissions/tables",
        headers=admin_headers,
        json={
            "user_id": str(normal.id),
            "connection_id": str(catalog.connection.id),
            "table_id": str(catalog.customers.id),
        },
    )
    permission_id = created.json()["id"]
    await api_client.put(
        f"/api/permissions/tables/{permission_id}/columns",
        headers=admin_headers,
        json={
            "items": [
                {"column_id": str(catalog.customer_columns[0].id)},
                {"column_id": str(catalog.customer_columns[1].id)},
            ]
        },
    )
    normal_identity = type(identity)(
        identity.tenant, normal, "Schema-User-Password-99", ()
    )
    normal_tokens = await login(api_client, normal_identity)
    headers = {"Authorization": f"Bearer {normal_tokens['access_token']}"}
    allowed = await api_client.get(
        f"/api/database-connections/{catalog.connection.id}/allowed-schema",
        headers=headers,
    )
    assert allowed.status_code == 200
    assert {item["name"] for item in allowed.json()["tables"][0]["columns"]} == {
        "id",
        "country",
    }
    async with test_database.sessions() as session:
        stored = await session.get(User, normal.id)
        assert stored is not None
        stored.status = "inactive"
        await session.commit()
    assert (
        await api_client.get(
            f"/api/database-connections/{catalog.connection.id}/allowed-schema",
            headers=headers,
        )
    ).status_code == 401

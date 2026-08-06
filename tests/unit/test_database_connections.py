"""Connection CRUD, authorization, encryption-at-rest, and isolation tests."""

from uuid import UUID

import httpx
import pytest
from sqlalchemy import select

from models import DatabaseConnection, User
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import bearer, login, seed_identity


def connection_payload(
    *,
    name: str = "Customer Reporting",
    password: str = "customer-database-password",
) -> dict[str, object]:
    return {
        "name": name,
        "database_type": "PostgreSQL",
        "host": "8.8.8.8",
        "port": 5432,
        "database_name": "customer",
        "username": "customer_reader",
        "password": password,
        "ssl_enabled": False,
        "ssl_settings": {"mode": "verify-full"},
        "connection_options": {"application_name": "phase3a-tests"},
    }


@pytest.mark.asyncio
async def test_admin_crud_encrypts_password_and_never_returns_credentials(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)
    headers = bearer(tokens["access_token"])
    plaintext = "customer-database-password"

    created = await api_client.post(
        "/api/database-connections",
        json=connection_payload(password=plaintext),
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "customer reporting"
    assert body["database_type"] == "postgresql"
    assert not {"password", "encrypted_password", "connection_url"} & set(body)
    assert plaintext not in created.text

    async with test_database.sessions() as session:
        stored = (await session.scalars(select(DatabaseConnection))).one()
        original_ciphertext = stored.encrypted_password
        assert plaintext not in original_ciphertext
        assert original_ciphertext.startswith("v1.")

    fetched = await api_client.get(
        f"/api/database-connections/{body['id']}",
        headers=headers,
    )
    listed = await api_client.get("/api/database-connections", headers=headers)
    assert fetched.status_code == 200
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    renamed = await api_client.put(
        f"/api/database-connections/{body['id']}",
        json={"name": "Renamed Reporting"},
        headers=headers,
    )
    assert renamed.status_code == 200
    async with test_database.sessions() as session:
        stored = await session.get(DatabaseConnection, UUID(body["id"]))
        assert stored.encrypted_password == original_ciphertext

    replaced = await api_client.put(
        f"/api/database-connections/{body['id']}",
        json={"password": "replacement-customer-password"},
        headers=headers,
    )
    assert replaced.status_code == 200
    async with test_database.sessions() as session:
        stored = await session.get(DatabaseConnection, UUID(body["id"]))
        assert stored.encrypted_password != original_ciphertext
        assert "replacement-customer-password" not in stored.encrypted_password

    deleted = await api_client.delete(
        f"/api/database-connections/{body['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204
    for method, suffix in [
        ("GET", ""),
        ("POST", "/test"),
        ("POST", "/sync-schema"),
    ]:
        response = await api_client.request(
            method,
            f"/api/database-connections/{body['id']}{suffix}",
            headers=headers,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_tenant_scoped_connection_name_uniqueness(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(test_database)
    tenant_b = await seed_identity(
        test_database,
        tenant_code="globex",
        tenant_name="Globex",
        email="admin@globex.example",
    )
    headers_a = bearer((await login(api_client, tenant_a))["access_token"])
    headers_b = bearer((await login(api_client, tenant_b))["access_token"])

    first = await api_client.post(
        "/api/database-connections",
        json=connection_payload(),
        headers=headers_a,
    )
    duplicate = await api_client.post(
        "/api/database-connections",
        json=connection_payload(name=" customer reporting "),
        headers=headers_a,
    )
    other_tenant = await api_client.post(
        "/api/database-connections",
        json=connection_payload(),
        headers=headers_b,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert other_tenant.status_code == 201


@pytest.mark.asyncio
async def test_normal_user_cannot_mutate_test_or_sync_connections(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database, is_tenant_admin=True)
    admin_headers = bearer((await login(api_client, identity))["access_token"])
    created = await api_client.post(
        "/api/database-connections",
        json=connection_payload(),
        headers=admin_headers,
    )
    async with test_database.sessions() as session:
        member = User(
            tenant_id=identity.tenant.id,
            email="member@acme.example",
            password_hash=identity.user.password_hash,
            is_tenant_admin=False,
        )
        session.add(member)
        await session.commit()
    member_login = await api_client.post(
        "/api/auth/login",
        json={
            "tenant_code": identity.tenant.code,
            "email": member.email,
            "password": identity.password,
        },
    )
    member_headers = bearer(member_login.json()["access_token"])
    connection_id = created.json()["id"]

    readable = await api_client.get(
        f"/api/database-connections/{connection_id}",
        headers=member_headers,
    )
    assert readable.status_code == 200
    for method, path, payload in [
        ("POST", "/api/database-connections", connection_payload(name="blocked")),
        ("PUT", f"/api/database-connections/{connection_id}", {"name": "blocked"}),
        ("DELETE", f"/api/database-connections/{connection_id}", None),
        ("POST", f"/api/database-connections/{connection_id}/test", None),
        ("POST", f"/api/database-connections/{connection_id}/sync-schema", None),
    ]:
        response = await api_client.request(
            method,
            path,
            json=payload,
            headers=member_headers,
        )
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_cross_tenant_connection_and_metadata_are_always_not_found(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(test_database)
    tenant_b = await seed_identity(
        test_database,
        tenant_code="globex",
        tenant_name="Globex",
        email="admin@globex.example",
    )
    headers_a = bearer((await login(api_client, tenant_a))["access_token"])
    headers_b = bearer((await login(api_client, tenant_b))["access_token"])
    connection = await api_client.post(
        "/api/database-connections",
        json=connection_payload(),
        headers=headers_b,
    )
    connection_id = connection.json()["id"]

    for method, suffix, payload in [
        ("GET", "", None),
        ("PUT", "", {"name": "intrusion"}),
        ("DELETE", "", None),
        ("POST", "/test", None),
        ("POST", "/sync-schema", None),
        ("GET", "/schemas", None),
        ("GET", "/tables", None),
    ]:
        response = await api_client.request(
            method,
            f"/api/database-connections/{connection_id}{suffix}",
            json=payload,
            headers=headers_a,
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_unsupported_type_host_attacks_and_tenant_override_are_rejected(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    headers = bearer((await login(api_client, identity))["access_token"])

    unsupported = connection_payload()
    unsupported["database_type"] = "mysql"
    unsupported_response = await api_client.post(
        "/api/database-connections",
        json=unsupported,
        headers=headers,
    )
    assert unsupported_response.status_code == 400
    assert unsupported_response.json() == {"detail": "Unsupported database type"}

    for blocked_host in ("127.0.0.1", "169.254.169.254", "user@host.example"):
        blocked = connection_payload(name=f"blocked-{blocked_host}")
        blocked["host"] = blocked_host
        response = await api_client.post(
            "/api/database-connections",
            json=blocked,
            headers=headers,
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid database host"}

    override = connection_payload(name="override")
    override["tenant_id"] = "7ab7e730-19c4-41ec-bca2-d372153754f8"
    override_response = await api_client.post(
        "/api/database-connections",
        json=override,
        headers=headers,
    )
    assert override_response.status_code == 400
    assert override_response.json() == {"detail": "Invalid request"}

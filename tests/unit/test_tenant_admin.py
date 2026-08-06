"""Tenant administrator authorization and isolation tests."""

import httpx
import pytest

from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import bearer, login, seed_identity


@pytest.mark.asyncio
async def test_normal_user_cannot_use_tenant_admin_endpoints(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    user = await seed_identity(
        test_database,
        email="member@acme.example",
        is_tenant_admin=False,
    )
    tokens = await login(api_client, user)

    for method, path, body in [
        ("GET", "/api/users", None),
        (
            "POST",
            "/api/users",
            {"email": "new@acme.example", "password": "Password-For-New-99"},
        ),
        ("GET", "/api/roles", None),
        ("POST", "/api/roles", {"name": "analyst"}),
    ]:
        response = await api_client.request(
            method,
            path,
            json=body,
            headers=bearer(tokens["access_token"]),
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Insufficient permissions"}


@pytest.mark.asyncio
async def test_admin_manages_users_and_roles_only_in_authenticated_tenant(
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
    tokens = await login(api_client, tenant_a)
    headers = bearer(tokens["access_token"])

    role_response = await api_client.post(
        "/api/roles",
        json={"name": "Analyst", "description": "Tenant A analyst"},
        headers=headers,
    )
    assert role_response.status_code == 201
    role = role_response.json()
    assert role["name"] == "analyst"

    user_response = await api_client.post(
        "/api/users",
        json={
            "email": "Shared@Example.com",
            "full_name": "Tenant A Shared User",
            "password": "User-Password-Strong-99",
        },
        headers=headers,
    )
    assert user_response.status_code == 201
    user = user_response.json()
    assert user["email"] == "shared@example.com"
    assert "password" not in user_response.text.casefold()
    assert "$argon2" not in user_response.text

    assignment = await api_client.put(
        f"/api/users/{user['id']}/roles",
        json={"role_ids": [role["id"]]},
        headers=headers,
    )
    assert assignment.status_code == 200
    assert assignment.json()["roles"][0]["id"] == role["id"]

    users = await api_client.get(
        "/api/users?page=1&page_size=10",
        headers={**headers, "X-Tenant-ID": str(tenant_b.tenant.id)},
    )
    assert users.status_code == 200
    assert users.json()["page"] == 1
    assert users.json()["page_size"] == 10
    assert users.json()["total"] == 2
    user_ids = {item["id"] for item in users.json()["items"]}
    assert str(tenant_a.user.id) in user_ids
    assert str(tenant_b.user.id) not in user_ids

    roles = await api_client.get(
        f"/api/roles?tenant_id={tenant_b.tenant.id}",
        headers=headers,
    )
    assert roles.status_code == 200
    role_ids = {item["id"] for item in roles.json()["items"]}
    assert str(tenant_b.roles[0].id) not in role_ids


@pytest.mark.asyncio
async def test_same_email_across_tenants_allowed_but_duplicate_within_tenant_conflicts(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(test_database)
    await seed_identity(
        test_database,
        tenant_code="globex",
        email="shared@example.com",
    )
    tokens = await login(api_client, tenant_a)
    headers = bearer(tokens["access_token"])
    payload = {
        "email": "shared@example.com",
        "password": "User-Password-Strong-99",
    }

    first = await api_client.post("/api/users", json=payload, headers=headers)
    duplicate = await api_client.post("/api/users", json=payload, headers=headers)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Resource already exists"}


@pytest.mark.asyncio
async def test_cross_tenant_user_and_role_assignment_returns_not_found(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(test_database)
    tenant_b = await seed_identity(
        test_database,
        tenant_code="globex",
        email="admin@globex.example",
    )
    tokens = await login(api_client, tenant_a)
    headers = bearer(tokens["access_token"])

    foreign_user = await api_client.put(
        f"/api/users/{tenant_b.user.id}/roles",
        json={"role_ids": []},
        headers=headers,
    )
    foreign_role = await api_client.put(
        f"/api/users/{tenant_a.user.id}/roles",
        json={"role_ids": [str(tenant_b.roles[0].id)]},
        headers=headers,
    )

    assert foreign_user.status_code == 404
    assert foreign_role.status_code == 404
    assert (
        foreign_user.json() == foreign_role.json() == {"detail": "Resource not found"}
    )


@pytest.mark.asyncio
async def test_request_body_tenant_id_is_rejected_and_cannot_override_context(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    tenant_a = await seed_identity(test_database)
    tenant_b = await seed_identity(
        test_database,
        tenant_code="globex",
        email="admin@globex.example",
    )
    tokens = await login(api_client, tenant_a)

    response = await api_client.post(
        "/api/users",
        json={
            "tenant_id": str(tenant_b.tenant.id),
            "email": "override@example.com",
            "password": "User-Password-Strong-99",
        },
        headers=bearer(tokens["access_token"]),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request"}


@pytest.mark.asyncio
async def test_role_names_are_unique_inside_tenant(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)
    headers = bearer(tokens["access_token"])

    first = await api_client.post(
        "/api/roles",
        json={"name": "Analyst"},
        headers=headers,
    )
    duplicate = await api_client.post(
        "/api/roles",
        json={"name": " analyst "},
        headers=headers,
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409

    blank = await api_client.post(
        "/api/roles",
        json={"name": "   "},
        headers=headers,
    )
    assert blank.status_code == 400
    assert blank.json() == {"detail": "Invalid request"}

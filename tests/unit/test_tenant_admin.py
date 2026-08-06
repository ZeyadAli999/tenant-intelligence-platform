"""Tenant administrator authorization and isolation tests."""

from unittest.mock import patch

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
        assert response.json() == {
            "detail": "Administrator access required",
            "code": "ADMINISTRATOR_REQUIRED",
        }


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


@pytest.mark.asyncio
async def test_administrator_role_is_required_in_addition_to_admin_flag(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(
        test_database,
        is_tenant_admin=True,
        role_names=("analyst",),
    )
    tokens = await login(api_client, identity)
    headers = bearer(tokens["access_token"])

    me = await api_client.get("/api/auth/me", headers=headers)
    denied = await api_client.get("/api/users", headers=headers)

    assert me.status_code == 200
    assert me.json()["is_tenant_admin"] is False
    assert denied.status_code == 403
    assert denied.json()["code"] == "ADMINISTRATOR_REQUIRED"


@pytest.mark.asyncio
async def test_denied_administrator_attempt_is_safely_audited(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database, is_tenant_admin=False)
    tokens = await login(api_client, identity)

    with patch("core.tenant_context.logger.warning") as audit_log:
        response = await api_client.post(
            "/api/users",
            json={
                "email": "blocked@example.com",
                "password": "Blocked-Account-Value-99",
            },
            headers={
                **bearer(tokens["access_token"]),
                "X-Request-ID": "administrator-denied-1",
            },
        )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Administrator access required",
        "code": "ADMINISTRATOR_REQUIRED",
    }
    logged = repr(audit_log.call_args)
    assert str(identity.tenant.id) in logged
    assert str(identity.user.id) in logged
    assert "'POST', '/api/users'" in logged
    assert "outcome=denied" in logged
    assert "administrator-denied-1" in logged
    assert str(tokens["access_token"]) not in logged
    assert "Blocked-Account-Value-99" not in logged


@pytest.mark.asyncio
async def test_user_status_search_roles_and_final_administrator_protection(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)
    headers = bearer(tokens["access_token"])
    administrator_role_id = str(identity.roles[0].id)

    final_role_removal = await api_client.put(
        f"/api/users/{identity.user.id}/roles",
        json={"role_ids": []},
        headers=headers,
    )
    final_deactivation = await api_client.put(
        f"/api/users/{identity.user.id}",
        json={
            "full_name": identity.user.full_name,
            "status": "inactive",
            "role_ids": [administrator_role_id],
        },
        headers=headers,
    )
    assert final_role_removal.status_code == 409
    assert final_deactivation.status_code == 409
    assert final_role_removal.json()["code"] == "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED"
    assert final_deactivation.json()["code"] == "FINAL_ACTIVE_ADMINISTRATOR_REQUIRED"

    created = await api_client.post(
        "/api/users",
        json={
            "email": "second.admin@example.com",
            "full_name": "Second Administrator",
            "password": "Second-Administrator-Value-99",
            "role_ids": [administrator_role_id],
        },
        headers=headers,
    )
    assert created.status_code == 201
    assert created.json()["is_tenant_admin"] is True

    filtered = await api_client.get(
        "/api/users?search=second&status=active",
        headers=headers,
    )
    assert filtered.status_code == 200
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["email"] == "second.admin@example.com"

    updated = await api_client.put(
        f"/api/users/{identity.user.id}",
        json={
            "full_name": "Former Administrator",
            "status": "inactive",
            "role_ids": [],
        },
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"
    assert updated.json()["is_tenant_admin"] is False


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_role_ids_during_validation(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)
    role_id = str(identity.roles[0].id)

    response = await api_client.post(
        "/api/users",
        json={
            "email": "duplicate.roles@example.com",
            "full_name": "Duplicate Roles",
            "password": "Duplicate-Role-Value-99",
            "role_ids": [role_id, role_id],
        },
        headers=bearer(tokens["access_token"]),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid request"}


@pytest.mark.asyncio
async def test_normal_user_cannot_self_escalate_by_assigning_administrator_role(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    admin_tokens = await login(api_client, identity)
    admin_headers = bearer(admin_tokens["access_token"])
    member_password = "Member-Account-Value-99"
    created = await api_client.post(
        "/api/users",
        json={
            "email": "member@example.com",
            "full_name": "Member User",
            "password": member_password,
        },
        headers=admin_headers,
    )
    assert created.status_code == 201

    member_login = await api_client.post(
        "/api/auth/login",
        json={
            "tenant_code": identity.tenant.code,
            "email": "member@example.com",
            "password": member_password,
        },
    )
    assert member_login.status_code == 200
    escalation = await api_client.put(
        f"/api/users/{created.json()['id']}/roles",
        json={"role_ids": [str(identity.roles[0].id)]},
        headers=bearer(member_login.json()["access_token"]),
    )

    assert escalation.status_code == 403
    assert escalation.json()["code"] == "ADMINISTRATOR_REQUIRED"

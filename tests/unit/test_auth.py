"""Authentication, tenant-status, token-type, and refresh-rotation tests."""

from datetime import timedelta
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import delete, select

from core.security import issue_token, utc_now
from models import RefreshToken, Tenant, User
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import bearer, login, seed_identity

INVALID_CREDENTIALS = {"detail": "Invalid credentials"}


@pytest.mark.asyncio
async def test_openapi_exposes_exact_phase_2_authentication_contract(
    api_client: httpx.AsyncClient,
) -> None:
    response = await api_client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert {
        "/api/auth/login",
        "/api/auth/refresh",
        "/api/auth/me",
        "/api/users",
        "/api/users/{user_id}/roles",
        "/api/roles",
    }.issubset(paths)
    assert "/api/auth/register" not in paths


@pytest.mark.asyncio
async def test_successful_login_and_me_are_safe(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)

    response = await api_client.post(
        "/api/auth/login",
        json={
            "tenant_code": " ACME ",
            "email": "ADMIN@ACME.EXAMPLE",
            "password": identity.password,
        },
        headers={"X-Request-ID": "login-success-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "login-success-1"
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token_expires_in"] == 900
    assert set(body) == {
        "access_token",
        "refresh_token",
        "token_type",
        "access_token_expires_in",
    }
    assert "password" not in response.text.casefold()
    assert "$argon2" not in response.text

    me_response = await api_client.get(
        "/api/auth/me",
        headers=bearer(body["access_token"]),
    )
    assert me_response.status_code == 200
    me = me_response.json()
    assert me["email"] == identity.user.email
    assert me["tenant"]["id"] == str(identity.tenant.id)
    assert me["roles"][0]["name"] == "administrator"
    assert "password_hash" not in me_response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tenant_code", "email", "password"),
    [
        ("acme", "admin@acme.example", "wrong-password"),
        ("acme", "missing@acme.example", "wrong-password"),
        ("unknown", "admin@acme.example", "wrong-password"),
    ],
)
async def test_login_identity_failures_are_indistinguishable_and_not_logged(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
    tenant_code: str,
    email: str,
    password: str,
) -> None:
    await seed_identity(test_database)
    with patch("services.auth_service.logger.info") as auth_log:
        response = await api_client.post(
            "/api/auth/login",
            json={
                "tenant_code": tenant_code,
                "email": email,
                "password": password,
            },
            headers={"X-Request-ID": "failed-login-1"},
        )

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS
    assert password not in response.text
    logged = repr(auth_log.call_args)
    assert "failed-login-1" in logged
    assert password not in logged
    assert email not in logged
    assert tenant_code not in logged


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tenant_status", "user_status"),
    [("inactive", "active"), ("active", "inactive")],
)
async def test_inactive_tenant_or_user_cannot_login(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
    tenant_status: str,
    user_status: str,
) -> None:
    identity = await seed_identity(
        test_database,
        tenant_status=tenant_status,
        user_status=user_status,
    )

    response = await api_client.post(
        "/api/auth/login",
        json={
            "tenant_code": identity.tenant.code,
            "email": identity.user.email,
            "password": identity.password,
        },
    )

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS


@pytest.mark.asyncio
@pytest.mark.parametrize("token", ["not-a-token", "one.two.three"])
async def test_malformed_token_is_rejected_by_me(
    api_client: httpx.AsyncClient,
    token: str,
) -> None:
    response = await api_client.get("/api/auth/me", headers=bearer(token))

    assert response.status_code == 401
    assert response.json() == INVALID_CREDENTIALS
    assert "X-Request-ID" in response.headers


@pytest.mark.asyncio
async def test_modified_and_expired_access_tokens_are_rejected(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)
    access = str(tokens["access_token"])
    header, payload, signature = access.split(".")
    modified_signature = ("a" if signature[0] != "a" else "b") + signature[1:]
    modified = f"{header}.{payload}.{modified_signature}"
    expired = issue_token(
        user_id=identity.user.id,
        tenant_id=identity.tenant.id,
        token_type="access",
        now=utc_now() - timedelta(minutes=2),
        lifetime=timedelta(minutes=1),
    )

    modified_response = await api_client.get(
        "/api/auth/me",
        headers=bearer(modified),
    )
    expired_response = await api_client.get(
        "/api/auth/me",
        headers=bearer(expired.value),
    )

    assert modified_response.status_code == 401
    assert expired_response.status_code == 401
    assert modified_response.json() == expired_response.json() == INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_access_and_refresh_token_types_are_not_interchangeable(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)

    me_response = await api_client.get(
        "/api/auth/me",
        headers=bearer(tokens["refresh_token"]),
    )
    refresh_response = await api_client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["access_token"]},
    )

    assert me_response.status_code == 401
    assert refresh_response.status_code == 401
    assert me_response.json() == refresh_response.json() == INVALID_CREDENTIALS


@pytest.mark.asyncio
async def test_refresh_token_value_is_not_written_to_authentication_logs(
    api_client: httpx.AsyncClient,
) -> None:
    raw_token = "raw-refresh-token-must-not-be-logged"
    with patch("services.auth_service.logger.info") as auth_log:
        response = await api_client.post(
            "/api/auth/refresh",
            json={"refresh_token": raw_token},
            headers={"X-Request-ID": "refresh-log-1"},
        )

    assert response.status_code == 401
    logged = repr(auth_log.call_args)
    assert "refresh-log-1" in logged
    assert raw_token not in logged


@pytest.mark.asyncio
async def test_refresh_rotation_revokes_old_token_and_replay_revokes_chain(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    original = await login(api_client, identity)

    async with test_database.sessions() as session:
        stored = (await session.scalars(select(RefreshToken))).one()
        assert stored.token_hash != original["refresh_token"]
        assert str(original["refresh_token"]) not in stored.token_hash

    rotated_response = await api_client.post(
        "/api/auth/refresh",
        json={"refresh_token": original["refresh_token"]},
    )
    assert rotated_response.status_code == 200
    rotated = rotated_response.json()
    assert rotated["refresh_token"] != original["refresh_token"]

    reuse_response = await api_client.post(
        "/api/auth/refresh",
        json={"refresh_token": original["refresh_token"]},
    )
    assert reuse_response.status_code == 401

    replacement_after_replay = await api_client.post(
        "/api/auth/refresh",
        json={"refresh_token": rotated["refresh_token"]},
    )
    assert replacement_after_replay.status_code == 401

    async with test_database.sessions() as session:
        records = list((await session.scalars(select(RefreshToken))).all())
        assert len(records) == 2
        assert all(record.revoked_at is not None for record in records)


@pytest.mark.asyncio
async def test_inactive_or_deleted_membership_invalidates_existing_access(
    api_client: httpx.AsyncClient,
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    tokens = await login(api_client, identity)

    async with test_database.sessions() as session:
        user = await session.get(User, identity.user.id)
        user.status = "inactive"
        await session.commit()

    inactive_response = await api_client.get(
        "/api/auth/me",
        headers=bearer(tokens["access_token"]),
    )
    assert inactive_response.status_code == 401

    async with test_database.sessions() as session:
        user = await session.get(User, identity.user.id)
        tenant = await session.get(Tenant, identity.tenant.id)
        user.status = "active"
        tenant.status = "inactive"
        await session.commit()

    inactive_tenant_response = await api_client.get(
        "/api/auth/me",
        headers=bearer(tokens["access_token"]),
    )
    inactive_refresh_response = await api_client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert inactive_tenant_response.status_code == 401
    assert inactive_refresh_response.status_code == 401

    second = await seed_identity(
        test_database,
        tenant_code="deleted-tenant",
        email="admin@deleted.example",
    )
    second_tokens = await login(api_client, second)
    async with test_database.sessions() as session:
        await session.execute(delete(Tenant).where(Tenant.id == second.tenant.id))
        await session.commit()

    deleted_response = await api_client.get(
        "/api/auth/me",
        headers=bearer(second_tokens["access_token"]),
    )
    assert deleted_response.status_code == 401

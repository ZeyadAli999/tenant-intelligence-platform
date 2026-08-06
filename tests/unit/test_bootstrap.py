"""Bootstrap Administrator creation and idempotency tests."""

import pytest
from sqlalchemy import func, select

from core.security import verify_password
from models import Role, Tenant, User, UserRole
from scripts.bootstrap import bootstrap_identity
from tests.unit.conftest import DatabaseHarness


@pytest.mark.asyncio
async def test_bootstrap_hashes_password_assigns_administrator_and_is_idempotent(
    test_database: DatabaseHarness,
) -> None:
    password = "Bootstrap-Password-Strong-99"
    async with test_database.sessions() as session:
        result = await bootstrap_identity(
            session,
            tenant_name="Example Tenant",
            tenant_code="Example",
            admin_email="Admin@Example.Example",
            admin_password=password,
            admin_full_name="Zeyad Said",
            role_names=("Administrator", "Analyst"),
        )

    assert result.tenant.code == "example"
    assert result.administrator.email == "admin@example.example"
    assert result.administrator.full_name == "Zeyad Said"
    assert result.administrator.is_tenant_admin is True
    assert result.administrator.password_hash != password
    assert verify_password(password, result.administrator.password_hash)
    assert {role.name for role in result.roles} == {"administrator", "analyst"}
    assert result.roles_created == 2
    assert result.role_assignments_created == 2
    assert result.roles_already_existing == 0
    assert result.role_assignments_already_existing == 0

    async with test_database.sessions() as session:
        repeated = await bootstrap_identity(
            session,
            tenant_name="Example Tenant",
            tenant_code="example",
            admin_email="admin@example.example",
            admin_password="Different-Value-Is-Not-Applied-99",
            admin_full_name="Zeyad Said",
            role_names=("Analyst",),
        )

    assert repeated.tenant.id == result.tenant.id
    assert repeated.administrator.id == result.administrator.id
    assert repeated.roles_created == 0
    assert repeated.role_assignments_created == 0
    assert repeated.roles_already_existing == 2
    assert repeated.role_assignments_already_existing == 2

    async with test_database.sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Tenant)) == 1
        assert await session.scalar(select(func.count()).select_from(User)) == 1
        assert await session.scalar(select(func.count()).select_from(Role)) == 2
        assert await session.scalar(select(func.count()).select_from(UserRole)) == 2


@pytest.mark.asyncio
async def test_bootstrap_reactivates_disabled_admin(
    test_database: DatabaseHarness,
) -> None:
    password = "Initial-Password-123!"
    async with test_database.sessions() as session:
        res = await bootstrap_identity(
            session,
            tenant_name="Inactive Tenant",
            tenant_code="inactive-tenant",
            admin_email="inactive@example.com",
            admin_password=password,
        )
        res.administrator.status = "inactive"
        await session.commit()

    async with test_database.sessions() as session:
        re_res = await bootstrap_identity(
            session,
            tenant_name="Inactive Tenant",
            tenant_code="inactive-tenant",
            admin_email="inactive@example.com",
            admin_password="New-Password-Ignored-456!",
        )
        assert re_res.administrator.status == "active"
        # Initial password hash is preserved on re-run
        assert verify_password(password, re_res.administrator.password_hash)


@pytest.mark.asyncio
async def test_bootstrap_cross_tenant_same_email_isolation(
    test_database: DatabaseHarness,
) -> None:
    shared_email = "shared-admin@example.com"
    async with test_database.sessions() as session:
        t1 = await bootstrap_identity(
            session,
            tenant_name="Tenant Alpha",
            tenant_code="alpha",
            admin_email=shared_email,
            admin_password="Alpha-Password-123!",
        )
        t2 = await bootstrap_identity(
            session,
            tenant_name="Tenant Beta",
            tenant_code="beta",
            admin_email=shared_email,
            admin_password="Beta-Password-123!",
        )

    assert t1.tenant.id != t2.tenant.id
    assert t1.administrator.id != t2.administrator.id
    assert t1.administrator.tenant_id == t1.tenant.id
    assert t2.administrator.tenant_id == t2.tenant.id


@pytest.mark.asyncio
async def test_bootstrap_partial_existing_state_idempotency(
    test_database: DatabaseHarness,
) -> None:
    async with test_database.sessions() as session:
        # Pre-create tenant only
        tenant = Tenant(name="Partial Tenant", code="partial-tenant")
        session.add(tenant)
        await session.commit()

    async with test_database.sessions() as session:
        res = await bootstrap_identity(
            session,
            tenant_name="Partial Tenant",
            tenant_code="partial-tenant",
            admin_email="partial@example.com",
            admin_password="Partial-Password-123!",
        )
        assert res.tenant.code == "partial-tenant"
        assert res.administrator.email == "partial@example.com"
        assert res.roles_created == 1
        assert res.role_assignments_created == 1


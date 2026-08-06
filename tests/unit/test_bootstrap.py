"""Bootstrap creation and duplicate refusal tests."""

import pytest

from core.security import verify_password
from scripts.bootstrap import BootstrapConflictError, bootstrap_identity
from tests.unit.conftest import DatabaseHarness


@pytest.mark.asyncio
async def test_bootstrap_hashes_password_and_refuses_duplicate_tenant(
    test_database: DatabaseHarness,
) -> None:
    password = "Bootstrap-Password-Strong-99"
    async with test_database.sessions() as session:
        result = await bootstrap_identity(
            session,
            tenant_name="Demo Tenant",
            tenant_code="Demo",
            admin_email="Admin@Demo.Example",
            admin_password=password,
            role_names=("Administrator", "Analyst"),
        )

    assert result.tenant.code == "demo"
    assert result.administrator.email == "admin@demo.example"
    assert result.administrator.is_tenant_admin is True
    assert result.administrator.password_hash != password
    assert verify_password(password, result.administrator.password_hash)
    assert {role.name for role in result.roles} == {"administrator", "analyst"}

    async with test_database.sessions() as session:
        with pytest.raises(BootstrapConflictError):
            await bootstrap_identity(
                session,
                tenant_name="Duplicate",
                tenant_code="demo",
                admin_email="other@demo.example",
                admin_password=password,
            )

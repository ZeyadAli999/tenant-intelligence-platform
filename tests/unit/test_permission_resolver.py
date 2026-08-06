"""Deterministic direct-user, role-union, sensitivity, and allowed-schema tests."""

from uuid import uuid4

import pytest

from models import ColumnPermission, DatabaseTable, Role, TablePermission, UserRole
from services.database.allowed_schema import allowed_schema_response
from services.database.permission_resolver import PermissionResolver
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import seed_identity
from tests.unit.phase3b_helpers import seed_catalog


def table_permission(
    identity: object,
    catalog: object,
    *,
    user: bool = False,
    role_id: object = None,
    can_read: bool = True,
    row_filter: dict[str, object] | None = None,
) -> TablePermission:
    return TablePermission(
        id=uuid4(),
        tenant_id=identity.tenant.id,
        user_id=identity.user.id if user else None,
        role_id=None if user else (role_id or identity.roles[0].id),
        connection_id=catalog.connection.id,
        table_id=catalog.customers.id,
        can_read=can_read,
        can_insert=False,
        can_update=False,
        can_delete=False,
        row_filter=row_filter or {},
    )


@pytest.mark.asyncio
async def test_no_permission_returns_no_allowed_table(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    async with test_database.sessions() as session:
        resolved = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=tuple(role.id for role in identity.roles),
            connection_id=catalog.connection.id,
        )
    assert resolved.tables == ()


@pytest.mark.asyncio
async def test_role_permission_hides_sensitive_column_and_invisible_relationship(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    async with test_database.sessions() as session:
        session.add(table_permission(identity, catalog))
        await session.commit()
        resolved = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=(identity.roles[0].id,),
            connection_id=catalog.connection.id,
        )
    response = allowed_schema_response(resolved)
    assert [table.table_name for table in response.tables] == ["customers"]
    assert {column.name for column in response.tables[0].columns} == {"id", "country"}
    assert "tax_identifier" not in response.model_dump_json()


@pytest.mark.asyncio
async def test_direct_user_permission_overrides_role_union_and_filters(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    second_role = Role(id=uuid4(), tenant_id=identity.tenant.id, name="reporter")
    egypt = {
        "version": 1,
        "all": [
            {
                "column_id": str(catalog.customer_columns[1].id),
                "operator": "eq",
                "value": {"source": "literal", "value": "Egypt"},
            }
        ],
    }
    france = {
        "version": 1,
        "all": [
            {
                "column_id": str(catalog.customer_columns[1].id),
                "operator": "eq",
                "value": {"source": "literal", "value": "France"},
            }
        ],
    }
    async with test_database.sessions() as session:
        session.add(second_role)
        await session.flush()
        session.add(
            UserRole(
                user_id=identity.user.id,
                role_id=second_role.id,
                tenant_id=identity.tenant.id,
            )
        )
        role_one = table_permission(identity, catalog, row_filter=egypt)
        role_two = table_permission(
            identity, catalog, role_id=second_role.id, row_filter=france
        )
        session.add_all([role_one, role_two])
        await session.commit()
        role_result = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=(identity.roles[0].id, second_role.id),
            connection_id=catalog.connection.id,
        )
        direct = table_permission(identity, catalog, user=True, can_read=False)
        session.add(direct)
        await session.commit()
        direct_result = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=(identity.roles[0].id, second_role.id),
            connection_id=catalog.connection.id,
        )
    assert len(role_result.tables[0].row_filters) == 2
    assert direct_result.tables == ()


@pytest.mark.asyncio
async def test_sensitive_column_requires_explicit_masked_grant_and_disabled_table_denies(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    async with test_database.sessions() as session:
        stored_table = await session.get(DatabaseTable, catalog.customers.id)
        assert stored_table is not None
        stored_table.is_sensitive = True
        permission = table_permission(identity, catalog)
        session.add(permission)
        await session.flush()
        session.add_all(
            [
                ColumnPermission(
                    tenant_id=identity.tenant.id,
                    table_id=catalog.customers.id,
                    table_permission_id=permission.id,
                    column_id=column.id,
                    can_read=True,
                    can_filter=column.column_name != "tax_identifier",
                    can_aggregate=column.column_name != "tax_identifier",
                    mask_type="redact"
                    if column.column_name == "tax_identifier"
                    else None,
                )
                for column in catalog.customer_columns
            ]
        )
        await session.commit()
        visible = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=(identity.roles[0].id,),
            connection_id=catalog.connection.id,
        )
        stored_table.is_enabled = False
        await session.commit()
        disabled = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=(identity.roles[0].id,),
            connection_id=catalog.connection.id,
        )
    sensitive = next(
        column
        for column in visible.tables[0].columns
        if column.metadata.column_name == "tax_identifier"
    )
    assert sensitive.readable is True and sensitive.mask_type == "redact"
    assert disabled.tables == ()


@pytest.mark.asyncio
async def test_false_role_row_does_not_cancel_unrelated_role_grant(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    false_role = Role(id=uuid4(), tenant_id=identity.tenant.id, name="denied-role")
    async with test_database.sessions() as session:
        session.add(false_role)
        await session.flush()
        session.add_all(
            [
                table_permission(identity, catalog, can_read=True),
                table_permission(
                    identity,
                    catalog,
                    role_id=false_role.id,
                    can_read=False,
                ),
            ]
        )
        await session.commit()
        resolved = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=(identity.roles[0].id, false_role.id),
            connection_id=catalog.connection.id,
        )
    assert [table.metadata.table_name for table in resolved.tables] == ["customers"]


@pytest.mark.asyncio
async def test_removed_role_immediately_removes_access(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    async with test_database.sessions() as session:
        session.add(table_permission(identity, catalog))
        await session.commit()
        resolved = await PermissionResolver(session).resolve(
            tenant_id=identity.tenant.id,
            user_id=identity.user.id,
            role_ids=(),
            connection_id=catalog.connection.id,
        )
    assert resolved.tables == ()

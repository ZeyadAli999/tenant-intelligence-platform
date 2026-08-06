"""Database-enforced tenant and permission constraints."""

from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from models import ColumnPermission, TablePermission
from tests.unit.conftest import DatabaseHarness
from tests.unit.helpers import seed_identity
from tests.unit.phase3b_helpers import seed_catalog


def permission(
    identity: object, catalog: object, **overrides: object
) -> TablePermission:
    values = {
        "id": uuid4(),
        "tenant_id": identity.tenant.id,
        "user_id": identity.user.id,
        "connection_id": catalog.connection.id,
        "table_id": catalog.customers.id,
        "can_read": True,
        "can_insert": False,
        "can_update": False,
        "can_delete": False,
        "row_filter": {},
    }
    values.update(overrides)
    return TablePermission(**values)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "subjects", [{"user_id": None, "role_id": None}, {"role_id": uuid4()}]
)
async def test_exactly_one_permission_subject(
    test_database: DatabaseHarness, subjects: dict[str, object]
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    row = permission(identity, catalog, **subjects)
    if subjects.get("role_id") is not None:
        row.user_id = identity.user.id
        row.role_id = identity.roles[0].id
    async with test_database.sessions() as session:
        session.add(row)
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_cross_tenant_and_duplicate_permissions_are_rejected(
    test_database: DatabaseHarness,
) -> None:
    a = await seed_identity(
        test_database, tenant_code="constraint-a", email="same@example.com"
    )
    b = await seed_identity(
        test_database, tenant_code="constraint-b", email="same@example.com"
    )
    catalog_a = await seed_catalog(test_database, a, name="a")
    catalog_b = await seed_catalog(test_database, b, name="b")
    invalid_rows = (
        permission(a, catalog_a, user_id=b.user.id),
        permission(a, catalog_a, user_id=None, role_id=b.roles[0].id),
        permission(a, catalog_a, connection_id=catalog_b.connection.id),
        permission(a, catalog_a, table_id=catalog_b.customers.id),
    )
    for row in invalid_rows:
        async with test_database.sessions() as session:
            session.add(row)
            with pytest.raises(IntegrityError):
                await session.commit()
    async with test_database.sessions() as session:
        first = permission(a, catalog_a)
        session.add(first)
        await session.commit()
        session.add(permission(a, catalog_a))
        with pytest.raises(IntegrityError):
            await session.commit()
    async with test_database.sessions() as session:
        role_first = permission(a, catalog_a, user_id=None, role_id=a.roles[0].id)
        session.add(role_first)
        await session.commit()
        session.add(permission(a, catalog_a, user_id=None, role_id=a.roles[0].id))
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_column_must_match_permission_table_and_mask_allowlist(
    test_database: DatabaseHarness,
) -> None:
    identity = await seed_identity(test_database)
    catalog = await seed_catalog(test_database, identity)
    async with test_database.sessions() as session:
        table_permission = permission(identity, catalog)
        session.add(table_permission)
        await session.commit()
        permission_id = table_permission.id
        for column_id, mask in (
            (catalog.order_columns[0].id, None),
            (catalog.customer_columns[0].id, "unknown"),
        ):
            session.add(
                ColumnPermission(
                    tenant_id=identity.tenant.id,
                    table_id=catalog.customers.id,
                    table_permission_id=permission_id,
                    column_id=column_id,
                    can_read=True,
                    can_filter=True,
                    can_aggregate=True,
                    mask_type=mask,
                )
            )
            with pytest.raises(IntegrityError):
                await session.commit()
            await session.rollback()

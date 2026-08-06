"""Create one initial tenant administrator without hardcoded credentials."""

import argparse
import asyncio
import os
from dataclasses import dataclass
from uuid import uuid4

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.security import hash_password
from database.session import AsyncSessionFactory
from models import Role, Tenant, User, UserRole
from models.role import ADMINISTRATOR_ROLE_NAME, normalize_role_name
from models.tenant import normalize_tenant_code
from models.user import normalize_email
from repositories.identity import IdentityRepository

PASSWORD_ENVIRONMENT_VARIABLE = "BOOTSTRAP_ADMIN_PASSWORD"


class BootstrapConflictError(Exception):
    """Raised when bootstrap identities already exist."""


@dataclass(frozen=True)
class BootstrapResult:
    tenant: Tenant
    administrator: User
    roles: tuple[Role, ...]
    roles_created: int
    role_assignments_created: int
    roles_already_existing: int
    role_assignments_already_existing: int


async def bootstrap_identity(
    session: AsyncSession,
    *,
    tenant_name: str,
    tenant_code: str,
    admin_email: str,
    admin_password: str,
    admin_full_name: str | None = None,
    role_names: tuple[str, ...] = (),
) -> BootstrapResult:
    """Idempotently establish one tenant and its configured Administrator."""
    normalized_code = normalize_tenant_code(tenant_code)
    normalized_email = normalize_email(admin_email)
    repository = IdentityRepository(session)
    tenant = await repository.get_tenant_by_code(normalized_code)
    if tenant is None:
        tenant = Tenant(id=uuid4(), name=tenant_name.strip(), code=normalized_code)
        session.add(tenant)
        await session.flush()
    else:
        tenant.name = tenant_name.strip()

    administrator = await repository.get_user_by_email(tenant.id, normalized_email)
    if administrator is None:
        administrator = User(
            tenant_id=tenant.id,
            email=normalized_email,
            full_name=admin_full_name.strip() if admin_full_name else None,
            password_hash=hash_password(admin_password),
            is_tenant_admin=True,
        )
        session.add(administrator)
        await session.flush()
    else:
        administrator.full_name = (
            admin_full_name.strip() if admin_full_name else administrator.full_name
        )
        administrator.status = "active"
        administrator.is_tenant_admin = True

    requested_role_names = tuple(
        dict.fromkeys(
            normalize_role_name(name)
            for name in (ADMINISTRATOR_ROLE_NAME, *role_names)
        )
    )
    roles: list[Role] = []
    roles_created = 0
    roles_already_existing = 0
    for role_name in requested_role_names:
        role = await repository.get_role_by_name(tenant.id, role_name)
        if role is None:
            role = Role(
                tenant_id=tenant.id,
                name=role_name,
                description=(
                    "Tenant Administrator"
                    if role_name == ADMINISTRATOR_ROLE_NAME
                    else "Initial bootstrap role"
                ),
            )
            session.add(role)
            await session.flush()
            roles_created += 1
        else:
            roles_already_existing += 1
        roles.append(role)

    assigned_role_ids = {
        role.id
        for role in await repository.get_roles_for_user(administrator.id, tenant.id)
    }
    role_assignments_created = 0
    role_assignments_already_existing = 0
    for role in roles:
        if role.id in assigned_role_ids:
            role_assignments_already_existing += 1
            continue
        session.add(
            UserRole(
                user_id=administrator.id,
                role_id=role.id,
                tenant_id=tenant.id,
            )
        )
        role_assignments_created += 1

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise BootstrapConflictError("Bootstrap identity already exists") from exc
    return BootstrapResult(
        tenant=tenant,
        administrator=administrator,
        roles=tuple(roles),
        roles_created=roles_created,
        role_assignments_created=role_assignments_created,
        roles_already_existing=roles_already_existing,
        role_assignments_already_existing=role_assignments_already_existing,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    tenant_name = os.environ.get("BOOTSTRAP_TENANT_NAME")
    tenant_code = os.environ.get("BOOTSTRAP_TENANT_CODE")
    admin_email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    parser.add_argument("--tenant-name", default=tenant_name, required=not tenant_name)
    parser.add_argument("--tenant-code", default=tenant_code, required=not tenant_code)
    parser.add_argument("--admin-email", default=admin_email, required=not admin_email)
    parser.add_argument(
        "--admin-full-name",
        default=os.environ.get("BOOTSTRAP_ADMIN_FULL_NAME"),
    )
    parser.add_argument(
        "--role",
        action="append",
        default=[],
        help="Optional initial role; repeat for multiple roles.",
    )
    return parser


async def async_main(args: argparse.Namespace) -> int:
    password = os.environ.get(PASSWORD_ENVIRONMENT_VARIABLE)
    if password is None or len(password) < 12:
        raise ValueError(
            f"{PASSWORD_ENVIRONMENT_VARIABLE} must be set to at least 12 characters"
        )
    try:
        validated_email = str(TypeAdapter(EmailStr).validate_python(args.admin_email))
    except ValidationError as exc:
        raise ValueError("--admin-email must be a valid email address") from exc

    async with AsyncSessionFactory() as session:
        result = await bootstrap_identity(
            session,
            tenant_name=args.tenant_name,
            tenant_code=args.tenant_code,
            admin_email=validated_email,
            admin_password=password,
            admin_full_name=args.admin_full_name,
            role_names=tuple(args.role),
        )
    print(
        "Bootstrap complete: "
        f"tenant={result.tenant.code} administrator={result.administrator.email} "
        f"roles_created={result.roles_created} "
        f"role_assignments_created={result.role_assignments_created} "
        f"roles_already_existing={result.roles_already_existing} "
        "role_assignments_already_existing="
        f"{result.role_assignments_already_existing}"
    )
    return 0


def main() -> int:
    parser = build_parser()
    try:
        return asyncio.run(async_main(parser.parse_args()))
    except (BootstrapConflictError, ValueError) as exc:
        parser.exit(status=1, message=f"Bootstrap failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

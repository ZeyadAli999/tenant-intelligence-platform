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
from models import Role, Tenant, User
from models.role import normalize_role_name
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
    """Create a tenant and administrator, explicitly refusing duplicate tenants."""
    normalized_code = normalize_tenant_code(tenant_code)
    repository = IdentityRepository(session)
    if await repository.get_tenant_by_code(normalized_code) is not None:
        raise BootstrapConflictError("Tenant code already exists")

    tenant = Tenant(id=uuid4(), name=tenant_name.strip(), code=normalized_code)
    administrator = User(
        tenant_id=tenant.id,
        email=normalize_email(admin_email),
        full_name=admin_full_name.strip() if admin_full_name else None,
        password_hash=hash_password(admin_password),
        is_tenant_admin=True,
    )
    roles = tuple(
        Role(
            tenant_id=tenant.id,
            name=normalize_role_name(role_name),
            description="Initial bootstrap role",
        )
        for role_name in dict.fromkeys(role_names)
    )
    session.add(tenant)
    try:
        await session.flush()
        session.add_all([administrator, *roles])
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise BootstrapConflictError("Bootstrap identity already exists") from exc
    return BootstrapResult(tenant=tenant, administrator=administrator, roles=roles)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--tenant-code", required=True)
    parser.add_argument("--admin-email", required=True)
    parser.add_argument("--admin-full-name")
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
        f"roles={len(result.roles)}"
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

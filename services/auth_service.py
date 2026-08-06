"""Login and refresh-token rotation workflows."""

import logging
from dataclasses import dataclass
from typing import NoReturn
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.exceptions import AuthenticationError
from core.security import (
    decode_token,
    ensure_utc,
    hash_refresh_token,
    issue_token,
    refresh_token_matches,
    utc_now,
    verify_dummy_password,
    verify_password,
)
from models import EntityStatus, RefreshToken, User
from models.tenant import normalize_tenant_code
from models.user import normalize_email
from repositories.identity import IdentityRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    access_token_expires_in: int


class AuthService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self.repository = IdentityRepository(session)

    async def login(
        self,
        *,
        tenant_code: str,
        email: str,
        password: str,
        request_id: str,
    ) -> TokenPair:
        tenant = await self.repository.get_tenant_by_code(
            normalize_tenant_code(tenant_code)
        )
        user: User | None = None
        if tenant is not None:
            user = await self.repository.get_user_by_email(
                tenant.id,
                normalize_email(email),
            )

        if user is None:
            verify_dummy_password(password)
            self._reject("Login rejected", request_id)

        password_valid = verify_password(password, user.password_hash)
        if (
            not password_valid
            or tenant is None
            or tenant.status != EntityStatus.ACTIVE.value
            or user.status != EntityStatus.ACTIVE.value
            or user.tenant_id != tenant.id
        ):
            self._reject("Login rejected", request_id)

        return await self._issue_pair(user, family_id=uuid4())

    async def rotate_refresh_token(
        self,
        *,
        raw_refresh_token: str,
        request_id: str,
    ) -> TokenPair:
        try:
            claims = decode_token(
                raw_refresh_token,
                expected_type="refresh",
                settings=self.settings,
            )
        except AuthenticationError:
            self._reject("Refresh authentication rejected", request_id)

        record = await self.repository.get_refresh_token(claims.jti, for_update=True)
        if record is None or not refresh_token_matches(
            raw_refresh_token,
            record.token_hash,
        ):
            self._reject("Refresh authentication rejected", request_id)

        now = utc_now()
        if record.revoked_at is not None:
            await self.repository.revoke_refresh_family(record.family_id, now)
            await self.session.commit()
            self._reject("Refresh token replay rejected", request_id)

        if ensure_utc(record.expires_at) <= now:
            record.revoked_at = now
            await self.session.commit()
            self._reject("Expired refresh token rejected", request_id)

        if record.user_id != claims.user_id or record.tenant_id != claims.tenant_id:
            await self.repository.revoke_refresh_family(record.family_id, now)
            await self.session.commit()
            self._reject("Refresh identity mismatch rejected", request_id)

        identity = await self.repository.get_identity(claims.user_id, claims.tenant_id)
        if identity is None:
            self._reject("Refresh identity rejected", request_id)
        user, tenant = identity
        if (
            user.status != EntityStatus.ACTIVE.value
            or tenant.status != EntityStatus.ACTIVE.value
        ):
            await self.repository.revoke_refresh_family(record.family_id, now)
            await self.session.commit()
            self._reject("Inactive refresh identity rejected", request_id)

        access = issue_token(
            user_id=user.id,
            tenant_id=tenant.id,
            token_type="access",
            settings=self.settings,
            now=now,
        )
        refresh = issue_token(
            user_id=user.id,
            tenant_id=tenant.id,
            token_type="refresh",
            settings=self.settings,
            now=now,
        )
        replacement = RefreshToken(
            user_id=user.id,
            tenant_id=tenant.id,
            jti=refresh.jti,
            family_id=record.family_id,
            token_hash=hash_refresh_token(refresh.value),
            expires_at=refresh.expires_at,
        )
        self.session.add(replacement)
        await self.session.flush()
        record.revoked_at = now
        record.replaced_by_jti = refresh.jti
        await self.session.commit()
        return TokenPair(
            access_token=access.value,
            refresh_token=refresh.value,
            access_token_expires_in=self.settings.jwt_access_token_minutes * 60,
        )

    async def _issue_pair(self, user: User, *, family_id: UUID) -> TokenPair:
        access = issue_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_type="access",
            settings=self.settings,
        )
        refresh = issue_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            token_type="refresh",
            settings=self.settings,
        )
        self.session.add(
            RefreshToken(
                user_id=user.id,
                tenant_id=user.tenant_id,
                jti=refresh.jti,
                family_id=family_id,
                token_hash=hash_refresh_token(refresh.value),
                expires_at=refresh.expires_at,
            )
        )
        await self.session.commit()
        return TokenPair(
            access_token=access.value,
            refresh_token=refresh.value,
            access_token_expires_in=self.settings.jwt_access_token_minutes * 60,
        )

    @staticmethod
    def _reject(event: str, request_id: str) -> NoReturn:
        logger.info("%s request_id=%r", event, request_id)
        raise AuthenticationError

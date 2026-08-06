"""Document authorization is explicit and independent of database permissions."""

from uuid import UUID

from app.exceptions import AuthorizationError, ResourceNotFoundError
from core.tenant_context import TenantContext
from models import KnowledgeBase
from repositories.documents import DocumentRepository


class KnowledgeBaseAccessPolicy:
    def __init__(self, repository: DocumentRepository, context: TenantContext) -> None:
        self.repository = repository
        self.context = context

    async def require(
        self, knowledge_base_id: UUID, *, manage: bool = False, active: bool = False
    ) -> KnowledgeBase:
        kb = await self.repository.get_kb(
            self.context.tenant.id, knowledge_base_id, active=active
        )
        if kb is None:
            raise ResourceNotFoundError("Knowledge base not found")
        if manage and not (
            self.context.user.is_tenant_admin or kb.created_by == self.context.user.id
        ):
            raise AuthorizationError("Insufficient permissions")
        if (
            not self.context.user.is_tenant_admin
            and kb.created_by != self.context.user.id
        ):
            raise ResourceNotFoundError("Knowledge base not found")
        return kb

    async def require_many(
        self, ids: list[UUID], *, active: bool = True
    ) -> tuple[KnowledgeBase, ...]:
        return tuple([await self.require(item, active=active) for item in ids])

"""Tenant-scoped knowledge-base management and upload alias."""

from functools import lru_cache
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.exceptions import InvalidDocumentError
from core.tenant_context import TenantContext, get_tenant_context
from repositories.documents import DocumentRepository
from schemas.documents import (
    KnowledgeBaseCreateRequest,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
    StoredFileResponse,
)
from services.documents.access_policy import KnowledgeBaseAccessPolicy
from services.documents.file_service import FileService
from services.documents.knowledge_base_service import KnowledgeBaseService
from services.documents.upload_security import FileValidationError
from storage.minio_store import MinioObjectStore
from storage.object_store import ObjectStore
from workers.broker import DocumentQueue, get_document_queue

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@lru_cache
def get_object_store() -> ObjectStore:
    return MinioObjectStore(get_settings())


@router.post(
    "", response_model=KnowledgeBaseResponse, status_code=status.HTTP_201_CREATED
)
async def create_knowledge_base(
    payload: KnowledgeBaseCreateRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse.model_validate(
        await KnowledgeBaseService(session, context, settings).create(payload)
    )


@router.get("", response_model=KnowledgeBaseListResponse)
async def list_knowledge_bases(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> KnowledgeBaseListResponse:
    rows, total = await DocumentRepository(session).list_kbs(
        context.tenant.id, context.user.id, context.is_tenant_admin, page, page_size
    )
    return KnowledgeBaseListResponse(
        items=[KnowledgeBaseResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def get_knowledge_base(
    knowledge_base_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> KnowledgeBaseResponse:
    row = await KnowledgeBaseAccessPolicy(DocumentRepository(session), context).require(
        knowledge_base_id
    )
    return KnowledgeBaseResponse.model_validate(row)


@router.put("/{knowledge_base_id}", response_model=KnowledgeBaseResponse)
async def update_knowledge_base(
    knowledge_base_id: UUID,
    payload: KnowledgeBaseUpdateRequest,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> KnowledgeBaseResponse:
    return KnowledgeBaseResponse.model_validate(
        await KnowledgeBaseService(session, context, settings).update(
            knowledge_base_id, payload
        )
    )


@router.delete("/{knowledge_base_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    knowledge_base_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    object_store: Annotated[ObjectStore, Depends(get_object_store)],
) -> None:
    await KnowledgeBaseService(session, context, settings).delete(
        knowledge_base_id, object_store
    )


@router.post(
    "/{knowledge_base_id}/files",
    response_model=StoredFileResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_to_knowledge_base(
    knowledge_base_id: UUID,
    upload: Annotated[UploadFile, File()],
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    object_store: Annotated[ObjectStore, Depends(get_object_store)],
    queue: Annotated[DocumentQueue, Depends(get_document_queue)],
) -> StoredFileResponse:
    try:
        row = await FileService(session, context, settings, object_store, queue).upload(
            knowledge_base_id, upload
        )
    except FileValidationError as exc:
        raise InvalidDocumentError(exc.code) from exc
    return StoredFileResponse.model_validate(row)

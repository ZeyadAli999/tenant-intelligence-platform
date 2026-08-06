"""Tenant- and knowledge-base-authorized file APIs."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.knowledge_bases import get_object_store
from app.config import Settings, get_settings
from app.dependencies import get_db_session
from app.exceptions import InvalidDocumentError
from core.tenant_context import TenantContext, get_tenant_context
from repositories.documents import DocumentRepository
from schemas.documents import StoredFileListResponse, StoredFileResponse
from services.documents.access_policy import KnowledgeBaseAccessPolicy
from services.documents.file_service import FileService
from services.documents.upload_security import FileValidationError
from storage.object_store import ObjectStore
from workers.broker import DocumentQueue, get_document_queue

router = APIRouter(prefix="/files", tags=["files"])


@router.post(
    "/upload", response_model=StoredFileResponse, status_code=status.HTTP_202_ACCEPTED
)
async def upload_file(
    knowledge_base_id: Annotated[UUID, Form()],
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


@router.get("", response_model=StoredFileListResponse)
async def list_files(
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    knowledge_base_id: UUID | None = None,
    processing_status: Literal["pending", "processing", "ready", "failed"]
    | None = None,
    extension: str | None = Query(default=None, pattern=r"^\.(pdf|docx|xlsx|csv|txt)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> StoredFileListResponse:
    repository = DocumentRepository(session)
    if knowledge_base_id is not None:
        await KnowledgeBaseAccessPolicy(repository, context).require(knowledge_base_id)
    kbs, _ = await repository.list_kbs(
        context.tenant.id, context.user.id, context.is_tenant_admin, 1, 1000
    )
    allowed = [item.id for item in kbs]
    rows, total = await repository.list_files(
        context.tenant.id,
        allowed,
        page,
        page_size,
        knowledge_base_id=knowledge_base_id,
        processing_status=processing_status,
        extension=extension,
    )
    return StoredFileListResponse(
        items=[StoredFileResponse.model_validate(row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{file_id}", response_model=StoredFileResponse)
async def get_file(
    file_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    object_store: Annotated[ObjectStore, Depends(get_object_store)],
    queue: Annotated[DocumentQueue, Depends(get_document_queue)],
) -> StoredFileResponse:
    row = await FileService(
        session, context, settings, object_store, queue
    ).require_file(file_id)
    return StoredFileResponse.model_validate(row)


@router.delete("/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_file(
    file_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    object_store: Annotated[ObjectStore, Depends(get_object_store)],
    queue: Annotated[DocumentQueue, Depends(get_document_queue)],
) -> None:
    await FileService(session, context, settings, object_store, queue).delete(file_id)


@router.post(
    "/{file_id}/reprocess",
    response_model=StoredFileResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reprocess_file(
    file_id: UUID,
    context: Annotated[TenantContext, Depends(get_tenant_context)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    object_store: Annotated[ObjectStore, Depends(get_object_store)],
    queue: Annotated[DocumentQueue, Depends(get_document_queue)],
) -> StoredFileResponse:
    row = await FileService(session, context, settings, object_store, queue).reprocess(
        file_id
    )
    return StoredFileResponse.model_validate(row)

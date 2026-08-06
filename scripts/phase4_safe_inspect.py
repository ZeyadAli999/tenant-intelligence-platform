"""Sanitized database assertions used only by the opt-in Phase 4 smoke flows."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from uuid import UUID

from sqlalchemy import delete, func, select

from app.config import get_settings
from database.session import AsyncSessionFactory, dispose_engine
from models import (
    ColumnPermission,
    Conversation,
    DatabaseColumn,
    DatabaseConnection,
    DatabaseSchema,
    DatabaseTable,
    DocumentChunk,
    KnowledgeBase,
    Message,
    MessageCitation,
    QueryExecution,
    RefreshToken,
    Role,
    StoredFile,
    TablePermission,
    Tenant,
    UserRole,
)
from storage.minio_store import MinioObjectStore

SMOKE_CODE = re.compile(r"(?:p4|p4-other)-[0-9a-f]{12}\Z")
TENANT_MODELS = (
    UserRole,
    RefreshToken,
    MessageCitation,
    QueryExecution,
    Message,
    Conversation,
    DocumentChunk,
    StoredFile,
    KnowledgeBase,
    ColumnPermission,
    TablePermission,
    DatabaseColumn,
    DatabaseTable,
    DatabaseSchema,
    DatabaseConnection,
    Role,
)


def validate_codes(codes: list[str]) -> list[str]:
    if not codes or any(SMOKE_CODE.fullmatch(code) is None for code in codes):
        raise ValueError("INVALID_SMOKE_TENANT_SELECTOR")
    return sorted(set(codes))


async def selected_tenants(session, codes: list[str] | None) -> list[Tenant]:
    rows = list((await session.scalars(select(Tenant))).all())
    if codes:
        allowed = set(validate_codes(codes))
        return [row for row in rows if row.code in allowed]
    return [row for row in rows if SMOKE_CODE.fullmatch(row.code)]


async def resource_counts(session, tenants: list[Tenant]) -> dict[str, int]:
    ids = [row.id for row in tenants]
    counts = {"tenants": len(ids)}
    for model in TENANT_MODELS:
        name = model.__tablename__
        statement = (
            select(func.count()).select_from(model).where(model.tenant_id.in_(ids))
        )
        counts[name] = int((await session.scalar(statement)) or 0) if ids else 0
    return counts


async def embeddings(args: argparse.Namespace) -> dict[str, object]:
    file_ids = [UUID(item) for item in args.file_id]
    tenant_id = UUID(args.tenant_id)
    kb_id = UUID(args.knowledge_base_id)
    async with AsyncSessionFactory() as session:
        files = list(
            (
                await session.scalars(
                    select(StoredFile).where(
                        StoredFile.id.in_(file_ids),
                        StoredFile.tenant_id == tenant_id,
                        StoredFile.knowledge_base_id == kb_id,
                    )
                )
            ).all()
        )
        active = list(
            (
                await session.execute(
                    select(
                        DocumentChunk.file_id,
                        DocumentChunk.ingestion_version,
                        func.vector_dims(DocumentChunk.embedding),
                    )
                    .join(
                        StoredFile,
                        (StoredFile.id == DocumentChunk.file_id)
                        & (StoredFile.tenant_id == DocumentChunk.tenant_id),
                    )
                    .where(
                        DocumentChunk.file_id.in_(file_ids),
                        DocumentChunk.tenant_id == tenant_id,
                        DocumentChunk.knowledge_base_id == kb_id,
                        DocumentChunk.ingestion_version
                        == StoredFile.active_ingestion_version,
                    )
                )
            ).all()
        )
    expected_versions = {row.id: row.active_ingestion_version for row in files}
    active_counts = {file_id: 0 for file_id in file_ids}
    dimensions_ok = True
    generations_ok = True
    for file_id, version, dimensions in active:
        active_counts[file_id] += 1
        dimensions_ok &= dimensions == 384
        generations_ok &= version == expected_versions[file_id]
    return {
        "file_count": len(files),
        "active_chunk_count": len(active),
        "all_files_ready": len(files) == len(file_ids)
        and all(
            row.processing_status == "ready" and row.chunk_count > 0 for row in files
        ),
        "dimensions_ok": dimensions_ok and bool(active),
        "active_generations_only": generations_ok
        and all(active_counts[file_id] > 0 for file_id in file_ids),
    }


async def message(args: argparse.Namespace) -> dict[str, object]:
    tenant_id = UUID(args.tenant_id)
    message_id = UUID(args.message_id)
    async with AsyncSessionFactory() as session:
        row = await session.scalar(
            select(Message).where(
                Message.id == message_id, Message.tenant_id == tenant_id
            )
        )
        execution = await session.scalar(
            select(QueryExecution).where(
                QueryExecution.message_id == message_id,
                QueryExecution.tenant_id == tenant_id,
            )
        )
        citation_types = list(
            await session.scalars(
                select(MessageCitation.citation_type).where(
                    MessageCitation.message_id == message_id,
                    MessageCitation.tenant_id == tenant_id,
                )
            )
        )
    if row is None:
        return {"exists": False}
    provider = row.structured_content.get("provider")
    preview = execution.result_preview if execution else None
    preview_text = json.dumps(preview, sort_keys=True) if preview is not None else ""
    return {
        "exists": True,
        "status": row.status,
        "provider": provider,
        "model": row.model_name,
        "citation_types": sorted(set(citation_types)),
        "query_execution": execution is not None,
        "validation_status": execution.validation_status if execution else None,
        "execution_status": execution.execution_status if execution else None,
        "row_filter_applied": bool(execution and execution.applied_row_filters),
        "masked_preview": "***" in preview_text,
        "raw_tax_identifier_absent": "SECRET-" not in preview_text,
    }


async def cleanup_tenants(args: argparse.Namespace) -> dict[str, object]:
    codes = validate_codes(list(args.tenant_code))
    async with AsyncSessionFactory() as session:
        await session.execute(delete(Tenant).where(Tenant.code.in_(codes)))
        await session.commit()
        remaining = await session.scalar(
            select(func.count()).select_from(Tenant).where(Tenant.code.in_(codes))
        )
    return {"remaining_tenants": int(remaining or 0)}


async def remaining(args: argparse.Namespace) -> dict[str, object]:
    codes = list(args.tenant_code)
    async with AsyncSessionFactory() as session:
        tenants = await selected_tenants(session, codes or None)
        counts = await resource_counts(session, tenants)
    return {"counts": counts, "total": sum(counts.values())}


async def remove_objects(args: argparse.Namespace) -> dict[str, object]:
    codes = validate_codes(list(args.tenant_code))
    async with AsyncSessionFactory() as session:
        tenants = await selected_tenants(session, codes)
        ids = [row.id for row in tenants]
        objects = (
            list(
                (
                    await session.execute(
                        select(StoredFile.storage_bucket, StoredFile.object_key).where(
                            StoredFile.tenant_id.in_(ids)
                        )
                    )
                ).all()
            )
            if ids
            else []
        )
    store = MinioObjectStore(get_settings())
    remaining_count = 0
    for bucket, object_key in objects:
        await store.delete(bucket, object_key)
        remaining_count += int(await store.exists(bucket, object_key))
    return {
        "objects_found": len(objects),
        "objects_removed": len(objects) - remaining_count,
        "objects_remaining": remaining_count,
    }


async def mark_sensitive(args: argparse.Namespace) -> dict[str, object]:
    async with AsyncSessionFactory() as session:
        column = await session.scalar(
            select(DatabaseColumn)
            .join(
                DatabaseTable,
                (DatabaseTable.id == DatabaseColumn.table_id)
                & (DatabaseTable.tenant_id == DatabaseColumn.tenant_id),
            )
            .where(
                DatabaseColumn.id == UUID(args.column_id),
                DatabaseColumn.tenant_id == UUID(args.tenant_id),
                DatabaseTable.connection_id == UUID(args.connection_id),
            )
        )
        if column is None:
            return {"updated": False}
        column.is_sensitive = True
        await session.commit()
    return {"updated": True}


async def run(args: argparse.Namespace) -> int:
    try:
        result = await globals()[args.action](args)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    finally:
        await dispose_engine()


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument(
        "action",
        choices=(
            "embeddings",
            "message",
            "cleanup_tenants",
            "mark_sensitive",
            "remaining",
            "remove_objects",
        ),
    )
    value.add_argument("--tenant-id")
    value.add_argument("--knowledge-base-id")
    value.add_argument("--file-id", action="append", default=[])
    value.add_argument("--message-id")
    value.add_argument("--connection-id")
    value.add_argument("--column-id")
    value.add_argument("--tenant-code", action="append", default=[])
    return value


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run(parser().parse_args())))

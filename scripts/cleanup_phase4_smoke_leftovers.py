"""Count or remove only tenants matching the exact Phase 4 smoke convention."""

from __future__ import annotations

import argparse
import asyncio
import json

from sqlalchemy import delete, select

from app.config import get_settings
from database.session import AsyncSessionFactory, dispose_engine
from models import StoredFile, Tenant
from scripts.phase4_safe_inspect import resource_counts, selected_tenants
from storage.minio_store import MinioObjectStore


async def cleanup(execute: bool) -> tuple[dict[str, object], int]:
    try:
        async with AsyncSessionFactory() as session:
            tenants = await selected_tenants(session, None)
            before = await resource_counts(session, tenants)
            ids = [row.id for row in tenants]
            objects = (
                list(
                    (
                        await session.execute(
                            select(
                                StoredFile.storage_bucket, StoredFile.object_key
                            ).where(StoredFile.tenant_id.in_(ids))
                        )
                    ).all()
                )
                if ids
                else []
            )
        if not execute:
            return {"mode": "dry-run", "counts": before, "objects": len(objects)}, 0

        store = MinioObjectStore(get_settings())
        objects_remaining = 0
        for bucket, object_key in objects:
            await store.delete(bucket, object_key)
            objects_remaining += int(await store.exists(bucket, object_key))
        async with AsyncSessionFactory() as session:
            if ids:
                await session.execute(delete(Tenant).where(Tenant.id.in_(ids)))
                await session.commit()
            after_tenants = await selected_tenants(session, None)
            after = await resource_counts(session, after_tenants)
        remaining = sum(after.values()) + objects_remaining
        return {
            "mode": "execute",
            "status": "passed" if remaining == 0 else "failed",
            "counts_before": before,
            "counts_after": after,
            "objects_found": len(objects),
            "objects_remaining": objects_remaining,
        }, int(remaining != 0)
    finally:
        await dispose_engine()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    result, status = asyncio.run(cleanup(args.execute))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return status


if __name__ == "__main__":
    raise SystemExit(main())

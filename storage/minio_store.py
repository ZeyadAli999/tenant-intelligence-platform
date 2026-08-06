"""Bounded asynchronous facade over the private MinIO SDK."""

import asyncio
from pathlib import Path

from minio import Minio

from app.config import Settings


class MinioObjectStore:
    def __init__(self, settings: Settings, client: Minio | None = None) -> None:
        self.bucket = settings.minio_bucket
        self.client = client or Minio(
            settings.minio_endpoint,
            access_key=settings.minio_app_access_key.get_secret_value(),
            secret_key=settings.minio_app_secret_key.get_secret_value(),
            secure=settings.minio_secure,
        )

    async def put_file(
        self, bucket: str, object_key: str, path: Path, checksum: str
    ) -> None:
        await asyncio.wait_for(
            asyncio.to_thread(
                self.client.fput_object,
                bucket,
                object_key,
                str(path),
                metadata={"sha256": checksum},
            ),
            timeout=30,
        )

    async def download_to_file(self, bucket: str, object_key: str, path: Path) -> None:
        await asyncio.wait_for(
            asyncio.to_thread(self.client.fget_object, bucket, object_key, str(path)),
            timeout=30,
        )

    async def delete(self, bucket: str, object_key: str) -> None:
        await asyncio.wait_for(
            asyncio.to_thread(self.client.remove_object, bucket, object_key), timeout=15
        )

    async def exists(self, bucket: str, object_key: str) -> bool:
        try:
            await asyncio.wait_for(
                asyncio.to_thread(self.client.stat_object, bucket, object_key),
                timeout=10,
            )
            return True
        except Exception:  # noqa: BLE001 - SDK health failures are deliberately closed
            return False

    async def health_check(self) -> bool:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self.client.bucket_exists, self.bucket), timeout=5
            )
        except Exception:  # noqa: BLE001 - SDK health failures are deliberately closed
            return False

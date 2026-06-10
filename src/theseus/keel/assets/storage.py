from __future__ import annotations

import asyncio
from pathlib import Path

import boto3
from botocore.client import Config


class LocalStorageBackend:
    """Filesystem-backed storage for development and tests."""

    def __init__(self, root: str, base_url: str = "/api/v1/assets/raw") -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)
        self._base_url = base_url.rstrip("/")

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def get(self, key: str) -> bytes:
        return (self._root / key).read_bytes()

    async def presign_get(self, key: str, ttl: int) -> str:
        return f"{self._base_url}/{key}"

    async def delete(self, key: str) -> None:
        path = self._root / key
        if path.exists():
            path.unlink()


class MinioStorageBackend:
    """S3-compatible object storage (MinIO in the bundle, S3 in the cloud).

    boto3 is synchronous; calls are offloaded with ``asyncio.to_thread`` to keep
    the async Protocol. A client may be injected for testing.
    """

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str = "us-east-1",
        client: object | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = client or boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
            config=Config(signature_version="s3v4"),
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except Exception:
            self._client.create_bucket(Bucket=self._bucket)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def get(self, key: str) -> bytes:
        def _read() -> bytes:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

        return await asyncio.to_thread(_read)

    async def presign_get(self, key: str, ttl: int) -> str:
        return await asyncio.to_thread(
            self._client.generate_presigned_url,
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=ttl,
        )

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self._client.delete_object, Bucket=self._bucket, Key=key)

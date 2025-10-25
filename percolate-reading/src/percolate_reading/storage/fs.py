"""Filesystem abstraction for local and S3 storage.

Provides transparent read/write to local files or S3 objects based on path prefix.
Adapted from carrier project's FS module.

Path Conventions:
    - Local paths: /path/to/file or path/to/file
    - S3 paths: s3://bucket/key or s3:///key (uses default bucket)

Examples:
    # Local file
    fs.write("output.txt", b"content")
    content = fs.read("output.txt")

    # S3 with default bucket (triple slash)
    fs.write("s3:///parse-jobs/doc.md", b"content")
    content = fs.read("s3:///parse-jobs/doc.md")

    # S3 with explicit bucket
    fs.write("s3://my-bucket/parsed/document.md", b"content")
    content = fs.read("s3://my-bucket/parsed/document.md")
"""

from pathlib import Path
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError
from loguru import logger

from percolate_reading.settings import settings


class S3Client:
    """S3 client wrapper for Minio/AWS S3."""

    def __init__(self, bucket: str):
        """Initialize S3 client.

        Args:
            bucket: S3 bucket name
        """
        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint if settings.s3_enabled else None,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

        # Ensure bucket exists
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        """Create bucket if it doesn't exist."""
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404":
                logger.info(f"Creating S3 bucket: {self.bucket}")
                self.client.create_bucket(Bucket=self.bucket)
            else:
                raise

    def get(self, key: str) -> bytes:
        """Get object from S3.

        Args:
            key: S3 object key

        Returns:
            Object contents as bytes

        Raises:
            ClientError: If object doesn't exist
        """
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def put(self, key: str, data: bytes | BinaryIO) -> None:
        """Put object to S3.

        Args:
            key: S3 object key
            data: Data to write (bytes or file-like object)
        """
        if isinstance(data, bytes):
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data)
        else:
            # File-like object
            self.client.upload_fileobj(data, self.bucket, key)

    def list(self, prefix: str = "") -> list[str]:
        """List objects with prefix.

        Args:
            prefix: S3 key prefix

        Returns:
            List of object keys
        """
        keys = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            if "Contents" in page:
                keys.extend([obj["Key"] for obj in page["Contents"]])
        return keys

    def exists(self, key: str) -> bool:
        """Check if object exists.

        Args:
            key: S3 object key

        Returns:
            True if exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


class FS:
    """Unified filesystem interface for local and S3 storage.

    Automatically routes operations based on path:
    - s3://bucket/key -> S3 with explicit bucket
    - s3:///key -> S3 with default bucket (note triple slash)
    - everything else -> local filesystem
    """

    def __init__(self, default_bucket: str | None = None):
        """Initialize filesystem abstraction.

        Args:
            default_bucket: Default S3 bucket for s3:///paths
        """
        self.default_bucket = default_bucket or settings.s3_bucket
        self._s3_clients: dict[str, S3Client] = {}

    def _get_s3_client(self, bucket: str) -> S3Client:
        """Get or create S3 client for bucket.

        Args:
            bucket: S3 bucket name

        Returns:
            S3Client instance
        """
        if bucket not in self._s3_clients:
            self._s3_clients[bucket] = S3Client(bucket)
        return self._s3_clients[bucket]

    def _parse_path(self, path: str) -> tuple[str, str | None, str]:
        """Parse path into storage type, bucket, and key/path.

        Args:
            path: File path or S3 URI
                - s3://bucket/key/path -> uses specified bucket
                - s3:///key/path -> uses default bucket (triple slash)
                - local/path -> local filesystem

        Returns:
            Tuple of (storage_type, bucket, key)
            - storage_type: "s3" or "local"
            - bucket: S3 bucket name or None for local
            - key: S3 key or local path
        """
        if path.startswith("s3://"):
            path_without_prefix = path[5:]  # Remove "s3://"

            # s3:///key uses default bucket (triple slash)
            if path_without_prefix.startswith("/"):
                return "s3", self.default_bucket, path_without_prefix[1:]

            # s3://bucket/key uses explicit bucket
            if "/" in path_without_prefix:
                bucket, key = path_without_prefix.split("/", 1)
                return "s3", bucket, key
            else:
                # s3://bucket (no key) - treat as bucket root
                return "s3", path_without_prefix, ""
        else:
            return "local", None, path

    def read(self, path: str) -> bytes:
        """Read file from local or S3 storage.

        Args:
            path: Local path or S3 URI (s3://bucket/key or s3:///key)

        Returns:
            File contents as bytes
        """
        storage_type, bucket, key = self._parse_path(path)

        if storage_type == "s3" and settings.s3_enabled:
            client = self._get_s3_client(bucket)
            return client.get(key)
        else:
            # Local file
            return Path(key).read_bytes()

    def write(self, path: str, data: bytes | str) -> None:
        """Write file to local or S3 storage.

        Args:
            path: Local path or S3 URI (s3://bucket/key or s3:///key)
            data: Data to write (bytes or str)
        """
        storage_type, bucket, key = self._parse_path(path)

        # Convert str to bytes if needed
        if isinstance(data, str):
            data = data.encode("utf-8")

        if storage_type == "s3" and settings.s3_enabled:
            client = self._get_s3_client(bucket)
            client.put(key, data)
        else:
            # Local file
            local_path = Path(key)
            local_path.parent.mkdir(parents=True, exist_ok=True)
            local_path.write_bytes(data)

    def list(self, path: str) -> list[str]:
        """List files/objects at path.

        Args:
            path: Local directory path or S3 prefix

        Returns:
            List of file paths or S3 keys
        """
        storage_type, bucket, key = self._parse_path(path)

        if storage_type == "s3" and settings.s3_enabled:
            client = self._get_s3_client(bucket)
            # Return full s3:// URIs
            return [f"s3://{bucket}/{k}" for k in client.list(key)]
        else:
            # Local directory
            local_path = Path(key)
            if not local_path.exists():
                return []

            if local_path.is_file():
                return [key]

            # Return relative paths
            return [
                str(p.relative_to(local_path)) for p in local_path.rglob("*") if p.is_file()
            ]

    def exists(self, path: str) -> bool:
        """Check if file/object exists.

        Args:
            path: Local path or S3 URI

        Returns:
            True if exists, False otherwise
        """
        storage_type, bucket, key = self._parse_path(path)

        if storage_type == "s3" and settings.s3_enabled:
            client = self._get_s3_client(bucket)
            return client.exists(key)
        else:
            return Path(key).exists()


# Global instance for convenience
fs = FS()

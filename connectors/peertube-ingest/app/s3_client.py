"""S3-compatible object storage client (SeaweedFS's S3 gateway, study 2.12).

Uses `boto3` (synchronous) rather than `aioboto3`: S3 calls here are infrequent
relative to the connector's overall throughput -- one `ListObjectsV2`/tagging/
GetObject sequence per ingested recording, and recordings are large video files
where the upload to PeerTube (not the object-storage read) dominates latency.
`aioboto3` also pins to a specific `aiobotocore`/`botocore` combination, which
adds maintenance overhead disproportionate to the benefit here. Every blocking
boto3 call is wrapped in `asyncio.to_thread` so the FastAPI event loop (webhook
mode) is never blocked; the batch script runs boto3 directly since it has no
event loop to protect.

Generic S3 API only (ListObjectsV2, GetObject, Get/PutObjectTagging) - nothing
here is specific to SeaweedFS, confirmed against its own S3 gateway source
(weed/s3api/) supporting all three, the same way MinIO (previously here) did.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

import boto3

from .types import IngestCandidate

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "https://s3.example.org")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")
S3_BUCKET = os.environ.get("S3_RECORDINGS_BUCKET", "visio-recordings")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            region_name=S3_REGION,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            # required for SeaweedFS/self-hosted S3-compatible stores, not AWS S3
            config=boto3.session.Config(s3={"addressing_style": "path"}),
        )
    return _client


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def list_recent_objects_sync(since_iso: str) -> List[IngestCandidate]:
    """Lists recent objects in the bucket for batch mode (study 2.12 line 589:
    "this upload can be done as a periodic task -- daily batch"). `since_iso` filters
    client-side on `LastModified` (the S3 API does not offer a server-side date filter).
    """
    since = _parse_iso(since_iso)
    s3 = _get_client()
    candidates: List[IngestCandidate] = []
    continuation_token: Optional[str] = None

    while True:
        kwargs = {"Bucket": S3_BUCKET}
        if continuation_token:
            kwargs["ContinuationToken"] = continuation_token
        page = s3.list_objects_v2(**kwargs)
        for obj in page.get("Contents", []):
            last_modified = obj.get("LastModified")
            if obj.get("Key") and last_modified and last_modified >= since:
                candidates.append(
                    IngestCandidate(
                        bucket=S3_BUCKET,
                        key=obj["Key"],
                        size=obj.get("Size", 0),
                        last_modified=last_modified.isoformat(),
                    )
                )
        if page.get("IsTruncated"):
            continuation_token = page.get("NextContinuationToken")
        else:
            break

    return candidates


async def list_recent_objects(since_iso: str) -> List[IngestCandidate]:
    return await asyncio.to_thread(list_recent_objects_sync, since_iso)


def get_object_stream_sync(bucket: str, key: str) -> bytes:
    s3 = _get_client()
    result = s3.get_object(Bucket=bucket, Key=key)
    return result["Body"].read()


async def get_object_stream(bucket: str, key: str) -> bytes:
    return await asyncio.to_thread(get_object_stream_sync, bucket, key)


def get_object_tags_sync(bucket: str, key: str) -> Dict[str, str]:
    """Retrieves the object's S3 tags, used in addition to the file name (see
    metadata.py)."""
    s3 = _get_client()
    result = s3.get_object_tagging(Bucket=bucket, Key=key)
    return {tag["Key"]: tag.get("Value", "") for tag in result.get("TagSet", [])}


async def get_object_tags(bucket: str, key: str) -> Dict[str, str]:
    return await asyncio.to_thread(get_object_tags_sync, bucket, key)

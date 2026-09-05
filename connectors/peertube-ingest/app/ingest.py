"""Uploads a MinIO object to PeerTube. Isolated from network SDKs (injected via
`IngestDeps`) to stay unit-testable -- used by both the real-time webhook and the
batch (study 2.12 line 589: both modes share this same logic).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Awaitable, Callable, Dict, List

from .metadata import extract_meeting_metadata_from_key, merge_with_s3_tags
from .types import IngestCandidate, IngestResult, MeetingMetadata

GetObjectTags = Callable[[str, str], Awaitable[Dict[str, str]]]
GetObjectStream = Callable[[str, str], Awaitable[bytes]]
UploadToPeerTube = Callable[..., Awaitable[Dict[str, str]]]


@dataclass
class IngestDeps:
    get_object_tags: GetObjectTags
    get_object_stream: GetObjectStream
    upload_to_peertube: UploadToPeerTube


async def ingest_object(candidate: IngestCandidate, deps: IngestDeps) -> IngestResult:
    try:
        try:
            tags = await deps.get_object_tags(candidate.bucket, candidate.key)
        except Exception:
            tags = {}

        metadata: MeetingMetadata = merge_with_s3_tags(
            extract_meeting_metadata_from_key(candidate.key), tags
        )
        file_stream = await deps.get_object_stream(candidate.bucket, candidate.key)
        upload_result = await deps.upload_to_peertube(
            object_key=candidate.key,
            metadata=metadata,
            file_stream=file_stream,
            file_size_bytes=candidate.size,
        )
        return IngestResult(
            key=candidate.key,
            uploaded=True,
            peertube_video_id=upload_result["peertube_video_id"],
        )
    except Exception as err:  # noqa: BLE001 - mirrors the TS catch-all, degrades gracefully
        return IngestResult(key=candidate.key, uploaded=False, error=str(err))


async def ingest_all(candidates: List[IngestCandidate], deps: IngestDeps) -> List[IngestResult]:
    """Ingests a list of candidates sequentially (avoids saturating the
    MinIO->PeerTube bandwidth by uploading N large videos in parallel)."""
    results: List[IngestResult] = []
    for candidate in candidates:
        results.append(await ingest_object(candidate, deps))
    return results


_VIDEO_EXT_RE = re.compile(r"\.(mp4|webm|mkv|mov)$", re.IGNORECASE)


def filter_video_objects(candidates: List[IngestCandidate]) -> List[IngestCandidate]:
    """Keeps only objects likely to be usable video recordings."""
    return [c for c in candidates if _VIDEO_EXT_RE.search(c.key)]

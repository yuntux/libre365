"""Uploads to the PeerTube API (`POST /api/v1/videos/upload`), embedding meeting
metadata in the title/description (study 2.12 line 589). Async via `httpx.AsyncClient`.
"""

from __future__ import annotations

import os
from typing import Dict, Optional

import httpx

from .types import MeetingMetadata

PEERTUBE_BASE_URL = os.environ.get("PEERTUBE_BASE_URL", "https://tube.example.org")
PEERTUBE_ACCESS_TOKEN = os.environ.get("PEERTUBE_ACCESS_TOKEN", "")
PEERTUBE_CHANNEL_ID = os.environ.get("PEERTUBE_CHANNEL_ID", "1")
# Default visibility of uploaded recordings (study 2.12: "per-video visibility
# management -- private, internal, unlisted"). 2 = "internal" on the PeerTube
# API side (visible only to users logged into the instance).
PEERTUBE_DEFAULT_PRIVACY = int(os.environ.get("PEERTUBE_DEFAULT_PRIVACY", "2"))


async def upload_to_peertube(
    object_key: str,
    metadata: MeetingMetadata,
    file_stream: bytes,
    file_size_bytes: int,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, str]:
    title = f"{metadata.title} ({metadata.date})" if metadata.date else metadata.title
    description = (
        f"Participants: {', '.join(metadata.participants)}\nSource: {object_key}"
        if metadata.participants
        else f"Source: {object_key}"
    )

    file_name = object_key.split("/")[-1] if object_key else "recording.mp4"
    data = {
        "channelId": PEERTUBE_CHANNEL_ID,
        "name": title[:120],
        "description": description,
        "privacy": str(PEERTUBE_DEFAULT_PRIVACY),
    }
    files = {"videofile": (file_name, file_stream)}
    headers = {"Authorization": f"Bearer {PEERTUBE_ACCESS_TOKEN}"}
    url = f"{PEERTUBE_BASE_URL}/api/v1/videos/upload"

    owns_client = http_client is None
    client = http_client or httpx.AsyncClient()
    try:
        response = await client.post(url, data=data, files=files, headers=headers)
    finally:
        if owns_client:
            await client.aclose()

    if response.status_code >= 400:
        raise RuntimeError(f"PeerTube upload failed with status {response.status_code}")

    payload = response.json()
    video = payload.get("video") or {}
    video_id = video.get("uuid") or str(video.get("id") or "")
    return {"peertube_video_id": video_id}

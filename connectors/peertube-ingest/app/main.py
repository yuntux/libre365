"""Real-time webhook endpoint (study 2.12 line 589): SeaweedFS's filer can be
configured to publish `create`/`update`/`delete`/`rename` events to a webhook
(`[notification.webhook]` in its notification.toml, see
infra/k8s/helm-values/seaweedfs.yaml's `filer.notificationConfig`).

Payload shape confirmed against SeaweedFS's own source
(weed/notification/webhook/types.go's `webhookMessage` struct,
weed/pb/filer_pb/filer.pb.go's generated json tags): top-level
`{"key": "<full filer path>", "event_type": "create|update|delete|rename",
"message_data": {"new_entry": {"name", "attributes": {"file_size", "mtime"}}}}`.
`key` is the full path including the bucket prefix
(`/buckets/<bucket>/<object-key>`, confirmed in weed/filer/filer_notify.go) -
not a separate bucket field the way MinIO's `Records[].s3.bucket.name` was.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .ingest import IngestDeps, filter_video_objects, ingest_all
from .s3_client import get_object_stream, get_object_tags
from .peertube_client import upload_to_peertube
from .types import IngestCandidate

PORT = int(os.environ.get("PORT", "4005"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


def _build_deps(http_client: httpx.AsyncClient) -> IngestDeps:
    async def _upload(**kwargs: Any) -> Dict[str, str]:
        return await upload_to_peertube(http_client=http_client, **kwargs)

    return IngestDeps(
        get_object_tags=get_object_tags,
        get_object_stream=get_object_stream,
        upload_to_peertube=_upload,
    )


def _split_bucket_and_key(filer_path: str) -> tuple[str, str]:
    """"/buckets/<bucket>/<object-key...>" -> ("<bucket>", "<object-key...>")."""
    parts = filer_path.lstrip("/").split("/", 2)
    if len(parts) < 3 or parts[0] != "buckets":
        return "", ""
    return parts[1], parts[2]


@app.post("/webhooks/seaweedfs")
async def handle_seaweedfs_webhook(request: Request) -> JSONResponse:
    event = await request.json()

    now_iso = datetime.now(timezone.utc).isoformat()
    candidates: List[IngestCandidate] = []

    if event.get("event_type") == "create":
        bucket, key = _split_bucket_and_key(event.get("key") or "")
        new_entry = (event.get("message_data") or {}).get("new_entry") or {}
        attributes = new_entry.get("attributes") or {}
        if bucket and key:
            candidates.append(
                IngestCandidate(
                    bucket=bucket,
                    key=key,
                    size=attributes.get("file_size", 0),
                    last_modified=now_iso,
                )
            )

    video_candidates = filter_video_objects(candidates)
    results = await ingest_all(video_candidates, _build_deps(request.app.state.http_client))

    return JSONResponse(
        status_code=200,
        content={"processed": len(results), "results": [asdict(r) for r in results]},
    )


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "ok"})

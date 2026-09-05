"""Real-time webhook endpoint (study 2.12 line 589): MinIO can be configured to
publish its `s3:ObjectCreated:*` notifications to a webhook ("webhook"-type bucket
notification target, see `mc admin config set myminio notify_webhook`).
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
from .minio_client import get_object_stream, get_object_tags
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


@app.post("/webhooks/minio")
async def handle_minio_webhook(request: Request) -> JSONResponse:
    event = await request.json()
    records = event.get("Records") or []

    now_iso = datetime.now(timezone.utc).isoformat()
    candidates: List[IngestCandidate] = []
    for record in records:
        if not (record.get("eventName") or "").startswith("s3:ObjectCreated"):
            continue
        s3_info = record.get("s3") or {}
        bucket = (s3_info.get("bucket") or {}).get("name") or ""
        obj = s3_info.get("object") or {}
        key = obj.get("key") or ""
        if not bucket or not key:
            continue
        candidates.append(
            IngestCandidate(bucket=bucket, key=key, size=obj.get("size", 0), last_modified=now_iso)
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

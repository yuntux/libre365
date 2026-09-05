"""presence-aggregator (study 2.8): FastAPI service consolidating Matrix,
Grommunio/EWS and LiveKit presence into a single status per user, exposed over
REST and SSE for the application portal's status bar (study 2.3).

Port of `src/server.ts`.
"""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from typing import AsyncIterator, List

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.consolidate import consolidate_presence
from app.sources.grommunio_ews import get_grommunio_availability
from app.sources.livekit_presence import get_livekit_presence
from app.sources.matrix_presence import get_matrix_presence
from app.types import ConsolidatedPresence, PresenceSources

PORT = int(os.environ.get("PORT", "4003"))
# SSE stream refresh interval (study 2.8: portal status bar 2.3).
STREAM_INTERVAL_MS = int(os.environ.get("PRESENCE_STREAM_INTERVAL_MS", "5000"))

app = FastAPI(title="presence-aggregator")


async def _safe(coro):
    try:
        return await coro
    except Exception:
        return None


async def build_consolidated_presence(user_id: str) -> ConsolidatedPresence:
    matrix, grommunio, livekit = await asyncio.gather(
        _safe(get_matrix_presence(user_id)),
        _safe(get_grommunio_availability(user_id)),
        _safe(get_livekit_presence(user_id)),
    )

    sources = PresenceSources(matrix=matrix, grommunio=grommunio, livekit=livekit)
    return ConsolidatedPresence(
        user_id=user_id,
        status=consolidate_presence(sources),
        sources=sources,
        updated_at=_iso_now(),
    )


def _iso_now() -> str:
    # Mirrors JS `new Date().toISOString()`: milliseconds, trailing "Z".
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


# Server-Sent Events for the application portal's status bar (study 2.3, 2.8).
# Declared before /presence/{user_id} so the literal "stream" path segment is
# not swallowed by the dynamic user_id route.
@app.get("/presence/stream")
async def stream_presence(request: Request, userIds: str = Query(default="")):
    user_ids: List[str] = [u.strip() for u in userIds.split(",") if u.strip()]

    if not user_ids:
        return JSONResponse(
            status_code=400,
            content={"error": "missing query parameter 'userIds' (comma-separated)"},
        )

    async def event_generator() -> AsyncIterator[dict]:
        while True:
            if await request.is_disconnected():
                break
            presences = await asyncio.gather(
                *(build_consolidated_presence(uid) for uid in user_ids)
            )
            yield {"data": json.dumps([p.to_dict() for p in presences])}
            await asyncio.sleep(STREAM_INTERVAL_MS / 1000)

    return EventSourceResponse(event_generator())


@app.get("/presence/{user_id}")
async def get_presence(user_id: str) -> JSONResponse:
    presence = await build_consolidated_presence(user_id)
    return JSONResponse(status_code=200, content=presence.to_dict())


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "ok"})


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT, loop="uvloop")


if __name__ == "__main__":
    run()

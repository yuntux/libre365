"""Unified notification center (study 2.1 and 2.7). Receives webhooks from
Matrix (Application Service), Grommunio, Seafile, Vikunja and OnlyOffice
(mentions), normalizes each event to the common format and relays it to
Novu via the REST API.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
from contextlib import asynccontextmanager
from typing import List, Optional

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .auth import InvalidToken, verify_token
from .normalize import (
    normalize_grommunio_event,
    normalize_matrix_event,
    normalize_onlyoffice_mention_event,
    normalize_seafile_event,
    normalize_vikunja_event,
)
from .novu_client import NOVU_API_KEY, trigger_novu_notification
from .types import NormalizedEvent

PORT = int(os.environ.get("PORT", "4001"))
# Novu's own "application identifier" (public, not a secret) - a value from
# Novu's own admin settings, generated when the Novu instance/organization
# is first set up (self-hosted), not something this repo can pin ahead of
# time - see infra/k8s/manifests/external-secrets.yaml's own comment.
NOVU_APP_ID = os.environ.get("NOVU_APP_ID", "")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http_client.aclose()


app = FastAPI(lifespan=lifespan)


async def _handle_normalized(
    request: Request, events: Optional[List[NormalizedEvent]] | Optional[NormalizedEvent]
) -> JSONResponse:
    if events is None:
        event_list: List[NormalizedEvent] = []
    elif isinstance(events, list):
        event_list = events
    else:
        event_list = [events]

    if len(event_list) == 0:
        return JSONResponse(
            status_code=202,
            content={"relayed": 0, "reason": "event ignored (not actionable)"},
        )

    client: httpx.AsyncClient = request.app.state.http_client
    results = await asyncio.gather(
        *(trigger_novu_notification(e, client) for e in event_list),
        return_exceptions=True,
    )
    relayed = sum(1 for r in results if not isinstance(r, BaseException))
    return JSONResponse(status_code=200, content={"relayed": relayed, "total": len(event_list)})


@app.post("/webhooks/matrix")
async def webhook_matrix(request: Request) -> JSONResponse:
    body = await request.json()
    return await _handle_normalized(request, normalize_matrix_event(body))


@app.post("/webhooks/grommunio")
async def webhook_grommunio(request: Request) -> JSONResponse:
    body = await request.json()
    return await _handle_normalized(request, normalize_grommunio_event(body))


@app.post("/webhooks/seafile")
async def webhook_seafile(request: Request) -> JSONResponse:
    body = await request.json()
    return await _handle_normalized(request, normalize_seafile_event(body))


@app.post("/webhooks/vikunja")
async def webhook_vikunja(request: Request) -> JSONResponse:
    body = await request.json()
    return await _handle_normalized(request, normalize_vikunja_event(body))


# OnlyOffice `onRequestSendNotify` entry point, relayed here by connectors/onlyoffice-mentions
# (study 2.7 line 487: "this connector joins the list of those to be developed in 2.1").
@app.post("/webhooks/onlyoffice-mention")
async def webhook_onlyoffice_mention(request: Request) -> JSONResponse:
    body = await request.json()
    return await _handle_normalized(request, normalize_onlyoffice_mention_event(body))


@app.get("/widget/session")
async def widget_session(request: Request) -> JSONResponse:
    """Cross-cutting app-portal banner's notification bell (study 2.1, 2.3):
    Novu's own notification-center widget does not support OIDC at all - it
    authenticates subscribers via an HMAC-SHA256(NOVU_API_KEY, subscriberId)
    hash instead (verified against Novu's own source,
    apps/api/src/app/shared/helpers/is-valid-hmac.ts /
    libs/application-generic/src/utils/hmac.ts). The subscriberId itself
    still comes from a REAL OIDC-verified Keycloak token (`sub` claim, via
    app/auth.py's JWKS signature check) - HMAC only takes over for this last,
    Novu-specific handshake, which this connector's server-side NOVU_API_KEY
    (never sent to the browser) is required for regardless."""
    try:
        claims = verify_token(request.headers.get("authorization") or "")
    except InvalidToken as err:
        return JSONResponse(status_code=401, content={"error": str(err)})

    subscriber_id = claims.get("sub", "")
    if not NOVU_API_KEY or not NOVU_APP_ID:
        return JSONResponse(
            status_code=503,
            content={"error": "NOVU_API_KEY/NOVU_APP_ID not configured on this connector"},
        )

    hmac_hash = hmac.new(
        NOVU_API_KEY.encode("utf-8"), subscriber_id.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return {
        "applicationIdentifier": NOVU_APP_ID,
        "subscriberId": subscriber_id,
        "hmacHash": hmac_hash,
    }


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "ok"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=PORT, loop="uvloop")

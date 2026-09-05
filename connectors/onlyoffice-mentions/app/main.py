"""
Handler for OnlyOffice Document Server mention events (study 2.7). Implements the
two extension points exposed by OnlyOffice for comments:

- `onRequestUsers` (`GET /onlyoffice/request-users`): list of users suggested
  when typing `@`/`+`, querying the directory via the Keycloak Admin API (simple stub).
- `onRequestSendNotify` (`POST /onlyoffice/request-send-notify`): triggered when
  a comment mentioning someone is submitted; this connector relays each mention to
  `notification-hub` (`POST /webhooks/onlyoffice-mention`).
"""

from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.directory_client import list_realm_users
from app.transform import to_notification_hub_payload, to_onlyoffice_user_list

NOTIFICATION_HUB_URL = os.environ.get("NOTIFICATION_HUB_URL", "http://notification-hub:4001")

app = FastAPI(title="onlyoffice-mentions")


@app.get("/onlyoffice/request-users")
async def request_users() -> JSONResponse:
    """
    Endpoint called by OnlyOffice Document Server to list the users suggested
    when typing `@`/`+` in a comment (study 2.7 line 484).
    """
    try:
        async with httpx.AsyncClient() as client:
            users = await list_realm_users(client)
        return JSONResponse(status_code=200, content={"users": to_onlyoffice_user_list(users)})
    except Exception as err:  # noqa: BLE001
        return JSONResponse(status_code=502, content={"error": str(err)})


@app.post("/onlyoffice/request-send-notify")
async def request_send_notify(request: Request) -> JSONResponse:
    """
    Endpoint called by OnlyOffice when a comment mentioning someone is submitted
    (study 2.7 line 484: `onRequestSendNotify`). Forwards each mention to the
    unified notification center (notification-hub, study 2.1/2.7 line 487).
    """
    body = await request.json()
    forwarded = to_notification_hub_payload(body)
    if not forwarded:
        return JSONResponse(
            status_code=202, content={"relayed": False, "reason": "no mentioned emails in payload"}
        )

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{NOTIFICATION_HUB_URL}/webhooks/onlyoffice-mention",
                json=forwarded,
            )
        return JSONResponse(
            status_code=200,
            content={"relayed": response.is_success, "notificationHubStatus": response.status_code},
        )
    except Exception as err:  # noqa: BLE001
        return JSONResponse(status_code=502, content={"relayed": False, "error": str(err)})


@app.get("/healthz")
async def healthz() -> JSONResponse:
    return JSONResponse(status_code=200, content={"status": "ok"})

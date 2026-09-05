"""Relay to the Novu API via a direct REST call rather than a Novu SDK,
to avoid a heavy dependency in this thin connector (study 2.1 line 382:
"Novu for the notification center UI ... fed by custom connectors").
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from .types import NormalizedEvent

NOVU_API_URL = os.environ.get("NOVU_API_URL", "https://api.novu.co/v1")
NOVU_API_KEY = os.environ.get("NOVU_API_KEY", "")
# Workflow trigger identifier configured on the Novu side, shared by all sources.
NOVU_WORKFLOW_ID = os.environ.get("NOVU_WORKFLOW_ID", "libre365-unified-notification")


@dataclass
class NovuTriggerResult:
    ok: bool
    status: int
    body: Optional[Any] = None


async def trigger_novu_notification(
    event: NormalizedEvent,
    client: Optional[httpx.AsyncClient] = None,
) -> NovuTriggerResult:
    payload = {
        "name": NOVU_WORKFLOW_ID,
        "to": {"subscriberId": event["userId"]},
        "payload": {
            "source": event["source"],
            "eventType": event["eventType"],
            "title": event["title"],
            "body": event["body"],
            "actionUrl": event["actionUrl"],
            "timestamp": event["timestamp"],
        },
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"ApiKey {NOVU_API_KEY}",
    }

    if client is not None:
        response = await client.post(
            f"{NOVU_API_URL}/events/trigger", json=payload, headers=headers
        )
    else:
        async with httpx.AsyncClient() as owned_client:
            response = await owned_client.post(
                f"{NOVU_API_URL}/events/trigger", json=payload, headers=headers
            )

    try:
        body = response.json()
    except ValueError:
        body = None

    return NovuTriggerResult(ok=response.is_success, status=response.status_code, body=body)

"""Reads `m.presence` (online/unavailable/offline) via the Matrix client-server API.

Port of `src/sources/matrix-presence.ts`.
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote

import httpx

from app.types import MatrixPresence

MATRIX_BASE_URL = os.environ.get("MATRIX_BASE_URL", "https://matrix.example.org")
# Token for a Matrix service account (Application Service or dedicated "bot" user)
# authorized to read any homeserver user's presence -- unlike unified-search,
# presence is not sensitive data filtered by room ACLs, it is per-user global
# information exposed by the homeserver.
SERVICE_TOKEN = os.environ.get("MATRIX_SERVICE_TOKEN", "")


async def get_matrix_presence(
    user_id: str, client: Optional[httpx.AsyncClient] = None
) -> MatrixPresence:
    url = f"{MATRIX_BASE_URL}/_matrix/client/v3/presence/{quote(user_id, safe='')}/status"
    headers = {"Authorization": f"Bearer {SERVICE_TOKEN}"}

    async def _do_request(c: httpx.AsyncClient) -> MatrixPresence:
        response = await c.get(url, headers=headers)
        if response.status_code >= 400:
            return None
        data = response.json()
        presence = data.get("presence")
        if presence in ("online", "unavailable", "offline"):
            return presence
        return None

    if client is not None:
        return await _do_request(client)

    async with httpx.AsyncClient() as owned_client:
        return await _do_request(owned_client)

"""Matrix Client-Server API `/search` connector.

The user's Bearer token is relayed as-is (study 2.2 line 391): Matrix applies
its own room visibility rules to the search, no ACL is duplicated here.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from app.types import SearchResultItem

MATRIX_BASE_URL = os.environ.get("MATRIX_BASE_URL", "https://matrix.example.org")


async def search_matrix(
    query: str,
    user_token: str,
    client: httpx.AsyncClient | None = None,
) -> list[SearchResultItem]:
    owns_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.post(
            f"{MATRIX_BASE_URL}/_matrix/client/v3/search",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {user_token}",
            },
            json={
                "search_categories": {
                    "room_events": {
                        "search_term": query,
                        "event_context": {"before_limit": 0, "after_limit": 0},
                    }
                }
            },
        )
    finally:
        if owns_client:
            await client.aclose()

    if response.status_code >= 400:
        raise RuntimeError(f"Matrix search failed with status {response.status_code}")

    data = response.json()
    raw_results = (
        data.get("search_categories", {}).get("room_events", {}).get("results", []) or []
    )

    items: list[SearchResultItem] = []
    for r in raw_results:
        result = r.get("result", {}) or {}
        content = result.get("content", {}) or {}
        body = content.get("body")
        origin_ts = result.get("origin_server_ts")
        timestamp = (
            datetime.fromtimestamp(origin_ts / 1000, tz=timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
            if origin_ts
            else None
        )
        room_id = result.get("room_id", "") or ""
        event_id = result.get("event_id", "") or ""
        items.append(
            SearchResultItem(
                source="matrix",
                id=event_id,
                title=(body[:80] if body else "(message)"),
                snippet=body,
                url=(
                    f"{MATRIX_BASE_URL.replace('https://matrix', 'https://element')}"
                    f"/#/room/{room_id}/{event_id}"
                ),
                timestamp=timestamp,
            )
        )
    return items

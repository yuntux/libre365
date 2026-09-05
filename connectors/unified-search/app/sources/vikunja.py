"""Vikunja `tasks/all?s=` connector.

The user's token is relayed as-is (study 2.2 line 391): only tasks from
projects the user has access to are returned, with no permission logic
duplicated here.
"""

from __future__ import annotations

import os
from urllib.parse import quote

import httpx

from app.types import SearchResultItem

VIKUNJA_BASE_URL = os.environ.get("VIKUNJA_BASE_URL", "https://vikunja.example.org")


async def search_vikunja(
    query: str,
    user_token: str,
    client: httpx.AsyncClient | None = None,
) -> list[SearchResultItem]:
    owns_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.get(
            f"{VIKUNJA_BASE_URL}/api/v1/tasks/all?s={quote(query)}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    finally:
        if owns_client:
            await client.aclose()

    if response.status_code >= 400:
        raise RuntimeError(f"Vikunja search failed with status {response.status_code}")

    data = response.json() or []

    return [
        SearchResultItem(
            source="vikunja",
            id=str(task.get("id", "")),
            title=task.get("title") or "(task)",
            snippet=task.get("description"),
            url=f"{VIKUNJA_BASE_URL}/tasks/{task.get('id', '')}",
            timestamp=task.get("updated"),
        )
        for task in data
    ]

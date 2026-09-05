"""Seafile search API connector.

The user's token is relayed as-is (study 2.2 line 391) rather than a service
account, so that Seafile applies its own permissions on libraries/folders
itself.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.types import SearchResultItem

SEAFILE_BASE_URL = os.environ.get("SEAFILE_BASE_URL", "https://seafile.example.org")


async def search_seafile(
    query: str,
    user_token: str,
    client: httpx.AsyncClient | None = None,
) -> list[SearchResultItem]:
    owns_client = client is None
    client = client or httpx.AsyncClient()
    try:
        response = await client.get(
            f"{SEAFILE_BASE_URL}/api2/search/?q={quote(query)}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
    finally:
        if owns_client:
            await client.aclose()

    if response.status_code >= 400:
        raise RuntimeError(f"Seafile search failed with status {response.status_code}")

    data = response.json()
    results = data.get("results", []) or []

    items: list[SearchResultItem] = []
    for r in results:
        repo_id = r.get("repo_id", "") or ""
        fullpath = r.get("fullpath", "") or ""
        last_modified = r.get("last_modified")
        timestamp = (
            datetime.fromtimestamp(last_modified, tz=timezone.utc).isoformat().replace(
                "+00:00", "Z"
            )
            if last_modified
            else None
        )
        items.append(
            SearchResultItem(
                source="seafile",
                id=f"{repo_id}{fullpath}",
                title=r.get("name") or fullpath or "(file)",
                snippet=r.get("content_highlight"),
                url=f"{SEAFILE_BASE_URL}/lib/{repo_id}/file{fullpath}",
                timestamp=timestamp,
            )
        )
    return items

"""Verifies that each HTTP source connector relays the exact Bearer token it
receives to the upstream service, using respx to mock httpx.AsyncClient
without any real network access (equivalent of the Vitest fetch mocks).
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.sources.matrix import MATRIX_BASE_URL, search_matrix
from app.sources.seafile import SEAFILE_BASE_URL, search_seafile
from app.sources.vikunja import VIKUNJA_BASE_URL, search_vikunja


@respx.mock
async def test_matrix_relays_bearer_token():
    route = respx.post(f"{MATRIX_BASE_URL}/_matrix/client/v3/search").mock(
        return_value=httpx.Response(200, json={"search_categories": {"room_events": {"results": []}}})
    )

    await search_matrix("hello", "user-token-abc")

    assert route.called
    assert route.calls.last.request.headers["authorization"] == "Bearer user-token-abc"


@respx.mock
async def test_seafile_relays_bearer_token():
    route = respx.get(url__startswith=f"{SEAFILE_BASE_URL}/api2/search/").mock(
        return_value=httpx.Response(200, json={"results": []})
    )

    await search_seafile("hello", "user-token-abc")

    assert route.called
    assert route.calls.last.request.headers["authorization"] == "Bearer user-token-abc"


@respx.mock
async def test_vikunja_relays_bearer_token():
    route = respx.get(url__startswith=f"{VIKUNJA_BASE_URL}/api/v1/tasks/all").mock(
        return_value=httpx.Response(200, json=[])
    )

    await search_vikunja("hello", "user-token-abc")

    assert route.called
    assert route.calls.last.request.headers["authorization"] == "Bearer user-token-abc"

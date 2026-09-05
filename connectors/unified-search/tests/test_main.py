"""Endpoint-level tests for GET /search: token extraction from the incoming
Authorization header, and error responses for missing query/token.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.types import SearchResultItem


def test_search_requires_query_param():
    client = TestClient(app)
    response = client.get("/search", headers={"Authorization": "Bearer abc"})
    assert response.status_code == 400


def test_search_requires_authorization_header():
    client = TestClient(app)
    response = client.get("/search?q=hello")
    assert response.status_code == 401


def test_search_relays_bearer_token_to_all_sources():
    seen_tokens = []

    async def fake_source(query, user_token):
        seen_tokens.append(user_token)
        return [SearchResultItem(source="matrix", id="1", title="t", url="http://x")]

    with (
        patch("app.main.search_matrix", new=AsyncMock(side_effect=fake_source)),
        patch("app.main.search_seafile", new=AsyncMock(side_effect=fake_source)),
        patch("app.main.search_vikunja", new=AsyncMock(side_effect=fake_source)),
        patch("app.main.search_grommunio", new=AsyncMock(side_effect=fake_source)),
    ):
        client = TestClient(app)
        response = client.get("/search?q=hello", headers={"Authorization": "Bearer the-token"})

    assert response.status_code == 200
    assert seen_tokens == ["the-token"] * 4
    body = response.json()
    assert body["query"] == "hello"
    assert len(body["sources"]) == 4


def test_healthz():
    client = TestClient(app)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

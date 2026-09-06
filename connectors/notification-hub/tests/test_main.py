import hashlib
import hmac
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import InvalidToken
from app.main import app


class _FakeNovuTransport(httpx.AsyncBaseTransport):
    """Fakes the outbound Novu API so tests never hit the network."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"acknowledged": True})


@pytest.fixture(autouse=True)
def _stub_novu_client(monkeypatch):
    fake_client = AsyncClient(transport=_FakeNovuTransport())
    app.state.http_client = fake_client
    yield
    import asyncio

    asyncio.get_event_loop().run_until_complete(fake_client.aclose())


@pytest.mark.asyncio
async def test_healthz():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_matrix_webhook_relays_a_mention():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhooks/matrix",
            json={
                "type": "m.room.message",
                "room_id": "!abc:matrix.example.org",
                "sender": "@alice:matrix.example.org",
                "content": {
                    "body": "@bob hi!",
                    "m.mentions": {"user_ids": ["@bob:matrix.example.org"]},
                },
            },
        )
    assert response.status_code == 200
    assert response.json() == {"relayed": 1, "total": 1}


@pytest.mark.asyncio
async def test_matrix_webhook_ignores_non_actionable_event():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/webhooks/matrix", json={"type": "m.room.member"})
    assert response.status_code == 202
    assert response.json() == {"relayed": 0, "reason": "event ignored (not actionable)"}


@pytest.mark.asyncio
async def test_onlyoffice_mention_webhook_relays_one_event_per_mentioned_email():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/webhooks/onlyoffice-mention",
            json={
                "comment": "@alice can you review this?",
                "document": {"title": "Annual report.docx"},
                "emails": ["alice@example.org", "carol@example.org"],
            },
        )
    assert response.status_code == 200
    assert response.json() == {"relayed": 2, "total": 2}


@pytest.mark.asyncio
async def test_widget_session_rejects_missing_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/widget/session")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_widget_session_rejects_an_invalid_token():
    with patch("app.main.verify_token", side_effect=InvalidToken("bad signature")):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/widget/session", headers={"Authorization": "Bearer t"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_widget_session_computes_the_real_novu_hmac_hash():
    with (
        patch("app.main.verify_token", return_value={"sub": "alice"}),
        patch("app.main.NOVU_API_KEY", "the-secret-key"),
        patch("app.main.NOVU_APP_ID", "the-app-id"),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/widget/session", headers={"Authorization": "Bearer t"})

    assert response.status_code == 200
    expected_hash = hmac.new(b"the-secret-key", b"alice", hashlib.sha256).hexdigest()
    assert response.json() == {
        "applicationIdentifier": "the-app-id",
        "subscriberId": "alice",
        "hmacHash": expected_hash,
    }


@pytest.mark.asyncio
async def test_widget_session_requires_novu_to_be_configured():
    with (
        patch("app.main.verify_token", return_value={"sub": "alice"}),
        patch("app.main.NOVU_API_KEY", ""),
    ):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/widget/session", headers={"Authorization": "Bearer t"})
    assert response.status_code == 503

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

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

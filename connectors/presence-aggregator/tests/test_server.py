"""Smoke tests for the FastAPI app: routes exist, SSE endpoint opens and closes
cleanly (no crash on startup / partial read), matching the validation done for
the original Express app manually. Sources are monkeypatched so no real
Matrix/Grommunio/LiveKit network calls are made.
"""

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

import app.main as main_module
from app.types import GrommunioAvailability, LiveKitPresence


async def _fake_matrix(user_id, client=None):
    return "online"


async def _fake_grommunio(user_email, client=None):
    return GrommunioAvailability(in_meeting_now=False)


async def _fake_livekit(user_identity, list_rooms_and_participants=None):
    return LiveKitPresence(in_call=False)


@pytest.fixture(autouse=True)
def patch_sources(monkeypatch):
    monkeypatch.setattr(main_module, "get_matrix_presence", _fake_matrix)
    monkeypatch.setattr(main_module, "get_grommunio_availability", _fake_grommunio)
    monkeypatch.setattr(main_module, "get_livekit_presence", _fake_livekit)


@pytest.fixture()
async def client():
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_get_presence(client):
    resp = await client.get("/presence/alice")
    assert resp.status_code == 200
    body = resp.json()
    assert body["userId"] == "alice"
    assert body["status"] == "online"


async def test_stream_requires_user_ids(client):
    resp = await client.get("/presence/stream")
    assert resp.status_code == 400


async def test_stream_opens_and_closes(monkeypatch):
    # Shrink the refresh interval so the test doesn't wait for the default 5s.
    monkeypatch.setattr(main_module, "STREAM_INTERVAL_MS", 10)

    # `httpx`'s ASGI transport buffers a handler's full response before handing
    # it back (it isn't a real bidirectional socket), so it cannot drive an
    # endpoint whose body never ends on its own -- which an SSE stream never
    # does. Instead, call the route directly and pump its `EventSourceResponse`
    # body iterator by hand: this exercises exactly what a real client does
    # (open the connection, read one event, close it) without needing a real
    # socket.
    response = await main_module.stream_presence(
        request=None, userIds="alice,bob"
    )
    assert response.status_code == 200
    assert response.media_type == "text/event-stream"

    first_event = await response.body_iterator.__anext__()
    assert '"userId": "alice"' in first_event["data"] or "alice" in first_event["data"]

    # Closing the generator early mirrors a client disconnecting mid-stream --
    # must not raise.
    await response.body_iterator.aclose()

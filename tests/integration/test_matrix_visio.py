"""
Critical scenario (study 4.5): "sending a message and starting a call from a
room (Matrix/Element/Visio)".

Uses the Matrix client API directly (Client-Server API,
`/_matrix/client/v3/...`) via `requests`, without a Matrix SDK, to stay
lightweight and explicit about the calls actually made by Element.

Open point of the study (see the footnote at the end of the document): the
full Visio integration button from Grommunio is conditioned on the
availability of a room-creation API on the Visio side (to be confirmed with
DINUM). In the meantime, the fallback solution adopted is a reusable link
(static widget). This test therefore covers "starting a call" at the level
of the Matrix room widget (adding an `im.vector.modular.widgets` state event
pointing to the Visio link), which is the mechanism actually available
today - not a call to a dedicated Visio API that does not exist yet.
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests

pytestmark = [pytest.mark.timeout(90)]


@pytest.fixture(scope="module")
def matrix_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.matrix}/_matrix/client/versions")


@pytest.fixture(scope="module")
def matrix_access_token(base_urls, test_user, matrix_ready) -> str:
    """
    Native Matrix login (m.login.password) to obtain a user access_token.
    The Matrix SSO scenario via Keycloak (m.login.sso / OIDC delegation) is
    covered separately in test_sso_e2e.py.
    """
    username = os.environ.get("TEST_MATRIX_USERNAME", test_user.username)
    password = os.environ.get("TEST_MATRIX_PASSWORD", test_user.password)

    response = requests.post(
        f"{base_urls.matrix}/_matrix/client/v3/login",
        json={
            "type": "m.login.password",
            "identifier": {"type": "m.id.user", "user": username},
            "password": password,
        },
        timeout=15,
    )
    if response.status_code != 200:
        pytest.fail(
            f"Matrix login failed on {base_urls.matrix}: "
            f"HTTP {response.status_code} - {response.text[:300]}"
        )
    token = response.json().get("access_token")
    if not token:
        pytest.fail(f"Matrix login response without an access_token: {response.text[:300]}")
    return token


@pytest.fixture()
def matrix_headers(matrix_access_token: str) -> dict:
    return {"Authorization": f"Bearer {matrix_access_token}"}


@pytest.fixture()
def test_room(base_urls, matrix_headers):
    """Creates a test room and cleans it up (leave) at the end of the test."""
    room_name = f"integration-test-{uuid.uuid4().hex[:8]}"
    create_response = requests.post(
        f"{base_urls.matrix}/_matrix/client/v3/createRoom",
        headers=matrix_headers,
        json={"name": room_name, "preset": "private_chat"},
        timeout=15,
    )
    if create_response.status_code != 200:
        pytest.fail(
            "Matrix room creation failed: "
            f"HTTP {create_response.status_code} - {create_response.text[:300]}"
        )
    room_id = create_response.json()["room_id"]

    yield room_id

    requests.post(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{room_id}/leave",
        headers=matrix_headers,
        json={},
        timeout=15,
    )


def test_send_message_in_room(base_urls, matrix_headers, test_room):
    """Sends a text message in the test room and verifies its receipt."""
    message_body = f"Message de test d'intégration {uuid.uuid4()}"
    transaction_id = uuid.uuid4().hex

    send_response = requests.put(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}/send/m.room.message/{transaction_id}",
        headers=matrix_headers,
        json={"msgtype": "m.text", "body": message_body},
        timeout=15,
    )
    assert send_response.status_code == 200, (
        f"Failed to send message in room {test_room}: "
        f"HTTP {send_response.status_code} - {send_response.text[:300]}"
    )
    event_id = send_response.json()["event_id"]

    # Receipt check: reading the event back from the room.
    get_response = requests.get(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}/event/{event_id}",
        headers=matrix_headers,
        timeout=15,
    )
    assert get_response.status_code == 200, (
        f"Sent message (event {event_id}) not found when reading it back: "
        f"HTTP {get_response.status_code} - {get_response.text[:300]}"
    )
    assert get_response.json()["content"]["body"] == message_body


def test_start_visio_widget_in_room(base_urls, matrix_headers, test_room):
    """
    Starts a "call" from the room in the sense of the mechanism currently
    available (fallback solution documented in the study): adding a room
    widget pointing to a reusable videoconference link, then verifying that
    the room state does expose that widget - this is what Element displays
    as the call button in the room.
    """
    visio_url = os.environ.get(
        "TEST_VISIO_ROOM_URL", "https://visio.libre365.test/room/integration-test"
    )
    widget_id = f"visio-{uuid.uuid4().hex[:8]}"

    put_response = requests.put(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}"
        f"/state/im.vector.modular.widgets/{widget_id}",
        headers=matrix_headers,
        json={
            "type": "jitsi",  # generic widget type recognized by Element for video calls
            "url": visio_url,
            "name": "Visio",
            "data": {"widgetId": widget_id},
        },
        timeout=15,
    )
    assert put_response.status_code == 200, (
        f"Failed to create the call widget in room {test_room}: "
        f"HTTP {put_response.status_code} - {put_response.text[:300]}"
    )

    state_response = requests.get(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}"
        f"/state/im.vector.modular.widgets/{widget_id}",
        headers=matrix_headers,
        timeout=15,
    )
    assert state_response.status_code == 200, (
        f"Call widget {widget_id} not found after being created in room {test_room}"
    )
    assert state_response.json().get("url") == visio_url

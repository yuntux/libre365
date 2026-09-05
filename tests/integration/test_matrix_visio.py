"""
Scénario critique (étude 4.5): "envoi de message et démarrage d'une visio
depuis une room (Matrix/Element/Visio)".

Utilise directement l'API cliente Matrix (Client-Server API, `/_matrix/client/v3/...`)
via `requests`, sans SDK Matrix, pour rester léger et explicite sur les
appels réellement effectués par Element.

Point ouvert de l'étude (voir note de bas de document): le bouton
d'intégration visio complet depuis Grommunio est conditionné à la
disponibilité d'une API de création de room côté Visio (à confirmer auprès
de la DINUM). En attendant, la solution de repli retenue est un lien
réutilisable (widget statique). Ce test couvre donc le "démarrage d'une
visio" au niveau du widget de room Matrix (ajout d'un state event
`im.vector.modular.widgets` pointant vers le lien Visio), qui est le
mécanisme réellement disponible aujourd'hui - pas un appel à une API Visio
dédiée qui n'existe pas encore.
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
    Login natif Matrix (m.login.password) pour obtenir un access_token
    utilisateur. Le scénario SSO Matrix via Keycloak (m.login.sso /
    OIDC delegation) est couvert séparément dans test_sso_e2e.py.
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
            f"Échec de connexion Matrix sur {base_urls.matrix}: "
            f"HTTP {response.status_code} - {response.text[:300]}"
        )
    token = response.json().get("access_token")
    if not token:
        pytest.fail(f"Réponse de login Matrix sans access_token: {response.text[:300]}")
    return token


@pytest.fixture()
def matrix_headers(matrix_access_token: str) -> dict:
    return {"Authorization": f"Bearer {matrix_access_token}"}


@pytest.fixture()
def test_room(base_urls, matrix_headers):
    """Crée une room de test et la nettoie (leave) en fin de test."""
    room_name = f"integration-test-{uuid.uuid4().hex[:8]}"
    create_response = requests.post(
        f"{base_urls.matrix}/_matrix/client/v3/createRoom",
        headers=matrix_headers,
        json={"name": room_name, "preset": "private_chat"},
        timeout=15,
    )
    if create_response.status_code != 200:
        pytest.fail(
            "Échec de création de room Matrix: "
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
    """Envoie un message texte dans la room de test et vérifie sa réception."""
    message_body = f"Message de test d'intégration {uuid.uuid4()}"
    transaction_id = uuid.uuid4().hex

    send_response = requests.put(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}/send/m.room.message/{transaction_id}",
        headers=matrix_headers,
        json={"msgtype": "m.text", "body": message_body},
        timeout=15,
    )
    assert send_response.status_code == 200, (
        f"Échec d'envoi de message dans la room {test_room}: "
        f"HTTP {send_response.status_code} - {send_response.text[:300]}"
    )
    event_id = send_response.json()["event_id"]

    # Vérification de réception: relecture de l'event depuis la room.
    get_response = requests.get(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}/event/{event_id}",
        headers=matrix_headers,
        timeout=15,
    )
    assert get_response.status_code == 200, (
        f"Message envoyé (event {event_id}) introuvable à la relecture: "
        f"HTTP {get_response.status_code} - {get_response.text[:300]}"
    )
    assert get_response.json()["content"]["body"] == message_body


def test_start_visio_widget_in_room(base_urls, matrix_headers, test_room):
    """
    Démarre une "visio" depuis la room au sens du mécanisme actuellement
    disponible (solution de repli documentée dans l'étude): ajout d'un
    widget de room pointant vers un lien de visioconférence réutilisable,
    puis vérification que l'état de la room expose bien ce widget - c'est ce
    qu'Element affiche comme bouton d'appel dans la room.
    """
    visio_url = os.environ.get(
        "TEST_VISIO_ROOM_URL", "https://visio.open365.test/room/integration-test"
    )
    widget_id = f"visio-{uuid.uuid4().hex[:8]}"

    put_response = requests.put(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}"
        f"/state/im.vector.modular.widgets/{widget_id}",
        headers=matrix_headers,
        json={
            "type": "jitsi",  # type de widget générique reconnu par Element pour la visio
            "url": visio_url,
            "name": "Visio",
            "data": {"widgetId": widget_id},
        },
        timeout=15,
    )
    assert put_response.status_code == 200, (
        f"Échec de création du widget visio dans la room {test_room}: "
        f"HTTP {put_response.status_code} - {put_response.text[:300]}"
    )

    state_response = requests.get(
        f"{base_urls.matrix}/_matrix/client/v3/rooms/{test_room}"
        f"/state/im.vector.modular.widgets/{widget_id}",
        headers=matrix_headers,
        timeout=15,
    )
    assert state_response.status_code == 200, (
        f"Widget visio {widget_id} introuvable après création dans la room {test_room}"
    )
    assert state_response.json().get("url") == visio_url

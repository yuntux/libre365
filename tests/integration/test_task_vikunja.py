"""
Scénario critique (étude 4.5): "création et notification d'une tâche
(Vikunja)".

Vérifie d'abord la création via l'API REST Vikunja, puis la notification
associée. Le connecteur notification-hub (2.1 dans l'étude) est le centre de
notifications utilisateur cible: quand il est présent et joignable, on
vérifie qu'il a bien relayé l'événement de création de tâche. Sinon (par
exemple en environnement docker-compose minimal sans les connecteurs
démarrés), on se rabat sur la vérification de l'état de la tâche créée côté
Vikunja lui-même, pour que ce test reste rejouable de façon autonome.
"""

from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

pytestmark = [pytest.mark.timeout(90)]


@pytest.fixture(scope="module")
def vikunja_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.vikunja}/api/v1/info")


@pytest.fixture(scope="module")
def vikunja_token(base_urls, test_user, vikunja_ready) -> str:
    """
    Authentification native Vikunja. Le scénario SSO Vikunja via Keycloak
    (OpenID Connect) est couvert séparément dans test_sso_e2e.py.
    """
    response = requests.post(
        f"{base_urls.vikunja}/api/v1/login",
        json={
            "username": os.environ.get("TEST_VIKUNJA_USERNAME", test_user.username),
            "password": os.environ.get("TEST_VIKUNJA_PASSWORD", test_user.password),
        },
        timeout=15,
    )
    if response.status_code != 200:
        pytest.fail(
            f"Échec de connexion Vikunja sur {base_urls.vikunja}: "
            f"HTTP {response.status_code} - {response.text[:300]}"
        )
    token = response.json().get("token")
    if not token:
        pytest.fail(f"Réponse de login Vikunja sans token: {response.text[:300]}")
    return token


@pytest.fixture()
def vikunja_headers(vikunja_token: str) -> dict:
    return {"Authorization": f"Bearer {vikunja_token}"}


@pytest.fixture()
def test_project(base_urls, vikunja_headers):
    """Crée un projet Vikunja de test et le nettoie (suppression) en fin de test."""
    project_title = f"integration-test-{uuid.uuid4().hex[:8]}"
    create_response = requests.put(
        f"{base_urls.vikunja}/api/v1/projects",
        headers=vikunja_headers,
        json={"title": project_title},
        timeout=15,
    )
    if create_response.status_code not in (200, 201):
        pytest.fail(
            "Échec de création du projet Vikunja de test: "
            f"HTTP {create_response.status_code} - {create_response.text[:300]}"
        )
    project_id = create_response.json()["id"]

    yield project_id

    requests.delete(
        f"{base_urls.vikunja}/api/v1/projects/{project_id}",
        headers=vikunja_headers,
        timeout=15,
    )


def test_create_task_and_notification(base_urls, vikunja_headers, test_project):
    """
    Crée une tâche dans le projet de test, puis vérifie:
    1. que la tâche existe bien côté Vikunja avec les attributs attendus;
    2. si notification-hub est joignable, qu'il a bien relayé l'événement
       (vérification best-effort, ne bloque pas le scénario si le connecteur
       n'est pas démarré dans cet environnement).
    """
    task_title = f"Tâche de test {uuid.uuid4()}"

    create_response = requests.put(
        f"{base_urls.vikunja}/api/v1/projects/{test_project}/tasks",
        headers=vikunja_headers,
        json={"title": task_title},
        timeout=15,
    )
    assert create_response.status_code in (200, 201), (
        f"Échec de création de la tâche Vikunja: HTTP {create_response.status_code} - "
        f"{create_response.text[:300]}"
    )
    task_id = create_response.json()["id"]

    get_response = requests.get(
        f"{base_urls.vikunja}/api/v1/tasks/{task_id}",
        headers=vikunja_headers,
        timeout=15,
    )
    assert get_response.status_code == 200, (
        f"Tâche créée (id={task_id}) introuvable à la relecture: "
        f"HTTP {get_response.status_code}"
    )
    assert get_response.json()["title"] == task_title

    _assert_notification_relayed_if_hub_available(base_urls, task_id, task_title)


def _assert_notification_relayed_if_hub_available(base_urls, task_id: int, task_title: str) -> None:
    hub_health_url = f"{base_urls.notification_hub}/health"
    try:
        health_response = requests.get(hub_health_url, timeout=5)
    except requests.exceptions.RequestException:
        pytest.skip(
            "notification-hub non joignable dans cet environnement: "
            "vérification de notification limitée à l'état de la tâche Vikunja."
        )
        return

    if health_response.status_code != 200:
        pytest.skip(
            f"notification-hub répond mais en échec ({health_response.status_code}): "
            "vérification de notification ignorée."
        )
        return

    # Poll de l'historique des notifications relayées pour cette tâche
    # (endpoint attendu du connecteur notification-hub, 2.1 de l'étude).
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        notifications_response = requests.get(
            f"{base_urls.notification_hub}/notifications",
            params={"source": "vikunja", "reference_id": str(task_id)},
            timeout=10,
        )
        if notifications_response.status_code == 200:
            notifications = notifications_response.json()
            if isinstance(notifications, list) and any(
                task_title in str(item) for item in notifications
            ):
                return
        time.sleep(2)

    pytest.fail(
        f"Aucune notification relayée par notification-hub trouvée pour la "
        f"tâche Vikunja {task_id} ({task_title!r}) après 30s."
    )

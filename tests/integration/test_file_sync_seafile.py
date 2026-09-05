"""
Scénario critique (étude 4.5): "création et synchronisation de fichier
(Seafile)".

Utilise l'API REST Seafile (Web API v2.1) plutôt que le client de
synchronisation desktop: c'est l'API que le connecteur unified-search
consomme également, et elle suffit à valider le cycle
upload -> présence -> suppression sans dépendance à un client lourd.
"""

from __future__ import annotations

import io
import os
import uuid

import pytest
import requests

pytestmark = [pytest.mark.timeout(90)]


@pytest.fixture(scope="module")
def seafile_ready(base_urls, wait_for_service):
    wait_for_service(f"{base_urls.seafile}/api2/ping/", expected_statuses=(200,))


@pytest.fixture(scope="module")
def seafile_auth_token(base_urls, test_user, seafile_ready) -> str:
    """
    Authentification native Seafile (login/mdp) pour obtenir un jeton d'API.
    Le scénario SSO Seafile via Keycloak est couvert séparément dans
    test_sso_e2e.py.
    """
    response = requests.post(
        f"{base_urls.seafile}/api2/auth-token/",
        data={
            "username": os.environ.get("TEST_SEAFILE_USERNAME", test_user.email),
            "password": os.environ.get("TEST_SEAFILE_PASSWORD", test_user.password),
        },
        timeout=15,
    )
    if response.status_code != 200:
        pytest.fail(
            f"Échec d'authentification Seafile sur {base_urls.seafile}: "
            f"HTTP {response.status_code} - {response.text[:300]}"
        )
    token = response.json().get("token")
    if not token:
        pytest.fail(f"Réponse Seafile sans token: {response.text[:300]}")
    return token


@pytest.fixture(scope="module")
def seafile_headers(seafile_auth_token: str) -> dict:
    return {"Authorization": f"Token {seafile_auth_token}"}


@pytest.fixture(scope="module")
def default_library_id(base_urls, seafile_headers) -> str:
    """
    Récupère l'identifiant de la bibliothèque de test par défaut de
    l'utilisateur, ou en crée une dédiée aux tests si aucune n'existe.
    """
    library_name = os.environ.get("TEST_SEAFILE_LIBRARY", "integration-tests")

    response = requests.get(
        f"{base_urls.seafile}/api2/repos/", headers=seafile_headers, timeout=15
    )
    response.raise_for_status()
    for repo in response.json():
        if repo.get("name") == library_name:
            return repo["id"]

    create_response = requests.post(
        f"{base_urls.seafile}/api2/repos/",
        headers=seafile_headers,
        data={"name": library_name, "desc": "Bibliothèque de la suite de tests d'intégration"},
        timeout=15,
    )
    if create_response.status_code not in (200, 201):
        pytest.fail(
            "Impossible de créer/retrouver la bibliothèque Seafile de test: "
            f"HTTP {create_response.status_code} - {create_response.text[:300]}"
        )
    return create_response.json()["repo_id"]


def test_create_upload_and_sync_file(base_urls, seafile_headers, default_library_id):
    """
    Cycle complet: obtention d'une URL d'upload, envoi d'un fichier,
    vérification de sa présence via l'API de listing (= "synchronisation"
    visible côté serveur), puis suppression pour ne pas polluer
    l'environnement de recette entre deux passages.
    """
    file_name = f"integration-test-{uuid.uuid4()}.txt"
    file_content = b"Contenu de test pour la suite d'integration (test_file_sync_seafile.py)."

    upload_link_response = requests.get(
        f"{base_urls.seafile}/api2/repos/{default_library_id}/upload-link/",
        headers=seafile_headers,
        params={"p": "/"},
        timeout=15,
    )
    if upload_link_response.status_code != 200:
        pytest.fail(
            "Impossible d'obtenir l'URL d'upload Seafile: "
            f"HTTP {upload_link_response.status_code} - {upload_link_response.text[:300]}"
        )
    upload_url = upload_link_response.json().strip('"')

    upload_response = requests.post(
        upload_url,
        headers=seafile_headers,
        data={"parent_dir": "/"},
        files={"file": (file_name, io.BytesIO(file_content), "text/plain")},
        timeout=30,
    )
    assert upload_response.status_code in (200, 201), (
        f"Échec de l'upload Seafile: HTTP {upload_response.status_code} - "
        f"{upload_response.text[:300]}"
    )

    try:
        # Vérification de présence: le fichier doit apparaître dans le listing
        # du dossier racine ("synchronisation" côté serveur).
        listing_response = requests.get(
            f"{base_urls.seafile}/api2/repos/{default_library_id}/dir/",
            headers=seafile_headers,
            params={"p": "/"},
            timeout=15,
        )
        listing_response.raise_for_status()
        names = [entry["name"] for entry in listing_response.json()]
        assert file_name in names, (
            f"Le fichier {file_name!r} envoyé n'apparaît pas dans le listing "
            f"de la bibliothèque {default_library_id} après upload: {names}"
        )
    finally:
        # Nettoyage systématique, y compris si l'assertion de présence échoue.
        requests.delete(
            f"{base_urls.seafile}/api2/repos/{default_library_id}/file/",
            headers=seafile_headers,
            params={"p": f"/{file_name}"},
            timeout=15,
        )

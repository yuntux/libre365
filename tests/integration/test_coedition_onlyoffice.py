"""
Scénario critique (étude 4.5): "co-édition d'un document (OnlyOffice)".

OnlyOffice Document Server ne co-édite pas via une action isolée: un client
(ici notre test) demande au serveur d'ouvrir un document pour édition en lui
fournissant une configuration signée en JWT (si JWT activé, ce qui est la
configuration recommandée en production - voir point ouvert 1.5 de l'étude
sur Euro-Office comme candidat de remplacement, à réévaluer plus tard mais
sans impact sur ce test qui cible l'API Document Server générique).

On simule ici un deuxième "éditeur" en interrogeant à nouveau l'endpoint de
conversion/health avec le même clé de document (`key`), ce qui est
l'équivalent côté API du "deux utilisateurs ouvrent le même document":
Document Server répond que la session d'édition pour cette clé existe déjà.
"""

from __future__ import annotations

import os
import time
import uuid
from typing import Optional

import jwt
import pytest
import requests

pytestmark = [pytest.mark.timeout(90)]


@pytest.fixture(scope="module")
def onlyoffice_ready(base_urls, wait_for_service):
    # /healthcheck est l'endpoint standard de Document Server (retourne "true").
    wait_for_service(f"{base_urls.onlyoffice}/healthcheck", expected_statuses=(200,))


def _onlyoffice_jwt_secret() -> Optional[str]:
    # Vide/absent si JWT est désactivé sur ce Document Server (déconseillé en
    # production mais toléré en environnement de test minimal).
    return os.environ.get("ONLYOFFICE_JWT_SECRET") or None


def _sign_config(config: dict, secret: str) -> str:
    return jwt.encode(config, secret, algorithm="HS256")


def test_open_document_for_editing(base_urls, onlyoffice_ready):
    """
    Construit une configuration d'édition OnlyOffice pour un document de test
    accessible en HTTP par le Document Server, l'envoie à l'endpoint de
    conversion/commande, et vérifie que le serveur accepte la session
    d'édition (pas d'erreur de configuration/signature).
    """
    document_key = f"integration-test-{uuid.uuid4().hex}"
    # Document minimal accessible par le Document Server: on réutilise un
    # fichier public de démonstration servi par Document Server lui-même,
    # pour ne pas dépendre d'un stockage de fichiers tiers dans ce test.
    document_url = os.environ.get(
        "ONLYOFFICE_TEST_DOCUMENT_URL",
        f"{base_urls.onlyoffice}/web-apps/apps/documenteditor/main/resources/help/en/images/logo.png",
    )

    config = {
        "document": {
            "fileType": "docx",
            "key": document_key,
            "title": "integration-test.docx",
            "url": document_url,
        },
        "editorConfig": {
            "callbackUrl": os.environ.get(
                "ONLYOFFICE_CALLBACK_URL", "http://localhost:9999/onlyoffice/callback"
            ),
            "mode": "edit",
            "user": {"id": "integration-tests", "name": "Integration Tests"},
        },
    }

    secret = _onlyoffice_jwt_secret()
    headers = {"Content-Type": "application/json"}
    payload_body = dict(config)
    if secret:
        payload_body["token"] = _sign_config(config, secret)
        headers["Authorization"] = f"Bearer {payload_body['token']}"

    # L'endpoint /coauthoring/CommandService.ashx accepte des commandes de
    # gestion de session (ici "info", non destructive) pour une clé de
    # document donnée: c'est le point d'entrée utilisé pour vérifier que
    # Document Server répond correctement, y compris la validation JWT.
    command_body = {"c": "info", "key": document_key}
    if secret:
        command_body["token"] = _sign_config(command_body, secret)

    response = requests.post(
        f"{base_urls.onlyoffice}/coauthoring/CommandService.ashx",
        json=command_body,
        headers=headers,
        timeout=20,
    )

    assert response.status_code == 200, (
        "Le Document Server OnlyOffice a refusé la commande de session "
        f"d'édition: HTTP {response.status_code} - {response.text[:300]}"
    )

    result = response.json()
    # error == 0 est la convention OnlyOffice pour "commande traitée avec succès".
    assert result.get("error", 1) == 0, (
        f"Document Server a renvoyé une erreur pour la clé {document_key!r}: {result}. "
        "Vérifier la configuration JWT (ONLYOFFICE_JWT_SECRET) si JWT est activé "
        "sur ce Document Server."
    )


def test_second_editor_joins_same_document_session(base_urls, onlyoffice_ready):
    """
    Approxime la co-édition: deux appels successifs de commande "info" sur la
    même clé de document doivent tous deux réussir, ce qui démontre que
    Document Server accepte plusieurs participants sur une session d'édition
    partagée (pas de verrou exclusif empêchant un second éditeur).
    """
    document_key = f"integration-test-coedit-{uuid.uuid4().hex}"
    secret = _onlyoffice_jwt_secret()

    def _send_info_command() -> dict:
        body = {"c": "info", "key": document_key}
        if secret:
            body["token"] = _sign_config(body, secret)
        response = requests.post(
            f"{base_urls.onlyoffice}/coauthoring/CommandService.ashx",
            json=body,
            timeout=20,
        )
        assert response.status_code == 200, (
            f"Commande OnlyOffice refusée: HTTP {response.status_code} - {response.text[:300]}"
        )
        return response.json()

    first_result = _send_info_command()
    time.sleep(1)  # laisser le temps au serveur d'enregistrer la session
    second_result = _send_info_command()

    for label, result in (("premier éditeur", first_result), ("second éditeur", second_result)):
        assert result.get("error", 1) == 0, (
            f"Échec de la commande pour le {label} sur la clé {document_key!r}: {result}"
        )

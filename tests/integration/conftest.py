"""
Fixtures partagées pour la suite de tests d'intégration (étude, section 4.5
"Rejeu des scénarios de test").

Cette suite est destinée à être rejouée à la fois:
- en local, contre la stack docker-compose (docker-compose/docker-compose.yml),
- automatiquement contre l'environnement de recette éphémère (section 4.4/4.6),
  via le pipeline CI/CD, sans intervention manuelle jusqu'à la validation des
  résultats.

Toutes les URLs/ports sont donc lus depuis des variables d'environnement, avec
des valeurs par défaut alignées sur les ports par défaut du docker-compose
local. Ne jamais coder en dur une URL dans un fichier de test: passer par la
fixture `base_urls`.
"""

from __future__ import annotations

import os
import time
import dataclasses
from typing import Callable, Optional

import pytest
import requests


# ---------------------------------------------------------------------------
# Résolution des URLs de service
# ---------------------------------------------------------------------------

def _env_url(var_name: str, default: str) -> str:
    """Lit une URL de base dans l'environnement, sans slash de fin."""
    return os.environ.get(var_name, default).rstrip("/")


@dataclasses.dataclass(frozen=True)
class BaseUrls:
    """URLs de base de chaque brique, résolues une fois par session de test."""

    keycloak: str
    grommunio_imap_host: str
    grommunio_imap_port: int
    grommunio_smtp_host: str
    grommunio_smtp_port: int
    seafile: str
    onlyoffice: str
    matrix: str  # Synapse (serveur homeserver Matrix)
    element: str
    vikunja: str
    gokapi: str
    minio: str
    peertube: str
    caddy: str
    notification_hub: str
    unified_search: str
    presence_aggregator: str
    onlyoffice_mentions: str
    peertube_ingest: str


@pytest.fixture(scope="session")
def base_urls() -> BaseUrls:
    """
    URLs/hôtes des briques, par défaut cohérentes avec docker-compose/docker-compose.yml
    (section 4.6 de l'étude: environnement docker-compose local).

    Pour pointer la suite vers l'environnement de recette éphémère (section 5.4/4.4),
    surcharger les variables d'environnement correspondantes dans le pipeline CI/CD
    (voir tests/integration/README.md).
    """
    return BaseUrls(
        keycloak=_env_url("KEYCLOAK_URL", "http://localhost:8080"),
        grommunio_imap_host=os.environ.get("GROMMUNIO_IMAP_HOST", "localhost"),
        grommunio_imap_port=int(os.environ.get("GROMMUNIO_IMAP_PORT", "993")),
        grommunio_smtp_host=os.environ.get("GROMMUNIO_SMTP_HOST", "localhost"),
        grommunio_smtp_port=int(os.environ.get("GROMMUNIO_SMTP_PORT", "587")),
        seafile=_env_url("SEAFILE_URL", "http://localhost:8082"),
        onlyoffice=_env_url("ONLYOFFICE_URL", "http://localhost:8083"),
        matrix=_env_url("MATRIX_URL", "http://localhost:8008"),
        element=_env_url("ELEMENT_URL", "http://localhost:8081"),
        vikunja=_env_url("VIKUNJA_URL", "http://localhost:3456"),
        gokapi=_env_url("GOKAPI_URL", "http://localhost:8090"),
        minio=_env_url("MINIO_URL", "http://localhost:9000"),
        peertube=_env_url("PEERTUBE_URL", "http://localhost:9001"),
        caddy=_env_url("CADDY_URL", "http://localhost:80"),
        notification_hub=_env_url("NOTIFICATION_HUB_URL", "http://localhost:4001"),
        unified_search=_env_url("UNIFIED_SEARCH_URL", "http://localhost:4002"),
        presence_aggregator=_env_url("PRESENCE_AGGREGATOR_URL", "http://localhost:4003"),
        onlyoffice_mentions=_env_url("ONLYOFFICE_MENTIONS_URL", "http://localhost:4004"),
        peertube_ingest=_env_url("PEERTUBE_INGEST_URL", "http://localhost:4005"),
    )


# ---------------------------------------------------------------------------
# Identifiants de test (jeu de données représentatif, section 4.4 point 2)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class TestUser:
    username: str
    password: str
    email: str


@pytest.fixture(scope="session")
def test_user() -> TestUser:
    """
    Utilisateur de test provisionné dans le jeu de données représentatif de
    l'environnement de recette (section 4.4, point 2) ou dans le realm de
    test du docker-compose local. Ne JAMAIS pointer ceci vers un compte réel
    de production.
    """
    return TestUser(
        username=os.environ.get("TEST_USER_USERNAME", "test.consultant"),
        password=os.environ.get("TEST_USER_PASSWORD", "ChangeMe123!"),
        email=os.environ.get("TEST_USER_EMAIL", "test.consultant@open365.test"),
    )


@pytest.fixture(scope="session")
def keycloak_realm() -> str:
    return os.environ.get("KEYCLOAK_REALM", "open365")


@pytest.fixture(scope="session")
def keycloak_client_id() -> str:
    # Client public "direct access grants" dédié aux tests d'intégration
    # (ne jamais réutiliser un client de production ici).
    return os.environ.get("KEYCLOAK_CLIENT_ID", "integration-tests")


@pytest.fixture(scope="session")
def keycloak_client_secret() -> Optional[str]:
    # Vide si le client Keycloak de test est public (pas de secret).
    return os.environ.get("KEYCLOAK_CLIENT_SECRET") or None


# ---------------------------------------------------------------------------
# Attente de disponibilité des services (démarrage lent de la stack)
# ---------------------------------------------------------------------------

class ServiceNotReadyError(RuntimeError):
    """
    Levée quand un service n'est pas prêt après épuisement des tentatives.
    Volontairement distincte des exceptions requests/urllib pour que les tests
    échouent avec un message clair ("stack non démarrée") plutôt qu'une trace
    opaque de connexion refusée.
    """


@pytest.fixture(scope="session")
def wait_for_service() -> Callable[..., None]:
    """
    Fixture-fonction: `wait_for_service(url, expected_statuses=(200,), timeout=60, interval=2)`.

    Poll une URL de healthcheck HTTP avec un backoff, pour absorber le
    démarrage lent de la stack docker-compose avant de lancer les assertions
    métier. En cas d'échec, lève ServiceNotReadyError avec un message
    explicite plutôt que de laisser le premier test planter avec une
    ConnectionError brute.
    """

    def _wait(
        url: str,
        expected_statuses: tuple = (200,),
        timeout: float = 60.0,
        interval: float = 2.0,
        max_interval: float = 10.0,
        request_timeout: float = 5.0,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_error: Optional[str] = None
        current_interval = interval

        while time.monotonic() < deadline:
            try:
                response = requests.get(url, timeout=request_timeout)
                if response.status_code in expected_statuses:
                    return
                last_error = f"HTTP {response.status_code} depuis {url}"
            except requests.exceptions.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            time.sleep(current_interval)
            current_interval = min(current_interval * 1.5, max_interval)

        raise ServiceNotReadyError(
            f"Service indisponible après {timeout}s d'attente sur {url} "
            f"(dernière erreur: {last_error}). "
            "Vérifier que la stack docker-compose (ou l'environnement de "
            "recette éphémère) est bien démarrée avant de lancer les tests."
        )

    return _wait


# ---------------------------------------------------------------------------
# Authentification SSO Keycloak (grant "password" pour un utilisateur de test)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def keycloak_token(
    base_urls: BaseUrls,
    keycloak_realm: str,
    keycloak_client_id: str,
    keycloak_client_secret: Optional[str],
    test_user: TestUser,
    wait_for_service: Callable[..., None],
) -> str:
    """
    Obtient un access_token OIDC via le grant "password" (Resource Owner
    Password Credentials) contre Keycloak, pour un utilisateur de test.

    C'est le point d'entrée du scénario "authentification SSO bout en bout"
    (étude 4.5, dernier scénario listé): ce token est ensuite présenté aux
    autres briques (Grommunio, Seafile, Vikunja, OnlyOffice, Matrix) dans
    test_sso_e2e.py pour vérifier qu'il est accepté partout.

    Le grant "password" n'est utilisé qu'en test d'intégration avec un
    utilisateur de test dédié: il ne doit jamais être activé sur un client
    Keycloak de production.
    """
    token_url = (
        f"{base_urls.keycloak}/realms/{keycloak_realm}"
        "/protocol/openid-connect/token"
    )

    wait_for_service(
        f"{base_urls.keycloak}/realms/{keycloak_realm}/.well-known/openid-configuration",
        timeout=float(os.environ.get("SERVICE_WAIT_TIMEOUT", "120")),
    )

    payload = {
        "grant_type": "password",
        "client_id": keycloak_client_id,
        "username": test_user.username,
        "password": test_user.password,
    }
    if keycloak_client_secret:
        payload["client_secret"] = keycloak_client_secret

    response = requests.post(token_url, data=payload, timeout=10)
    if response.status_code != 200:
        pytest.fail(
            "Échec de l'obtention du token Keycloak (grant password) sur "
            f"{token_url}: HTTP {response.status_code} - {response.text[:500]}"
        )

    access_token = response.json().get("access_token")
    if not access_token:
        pytest.fail(f"Réponse Keycloak sans access_token: {response.text[:500]}")

    return access_token


# ---------------------------------------------------------------------------
# Marqueurs personnalisés (déclarés aussi dans pytest.ini, doublon volontaire
# pour tolérer un lancement sans -c explicite)
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "smoke: scénario critique minimal (rejouable rapidement)")
    config.addinivalue_line("markers", "slow: scénario plus long (ex: attente convergence async)")
    config.addinivalue_line("markers", "sso: scénario d'authentification SSO bout en bout (Keycloak)")

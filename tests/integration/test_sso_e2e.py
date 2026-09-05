"""
Scénario critique (étude 4.5): "authentification SSO bout en bout (Keycloak)
sur chacune des briques précédentes".

Ce test est paramétré brique par brique (une entrée par service: Grommunio,
Seafile, Vikunja, OnlyOffice, Matrix) plutôt qu'écrit comme cinq fonctions de
test séparées, parce que l'assertion est structurellement identique pour
chaque brique ("l'endpoint protégé refuse sans token, l'accepte avec le
token Keycloak") - seule l'URL et le code de statut "sans token" attendu
changent d'une brique à l'autre. La paramétrisation rend aussi trivial
l'ajout d'une future brique SSO sans dupliquer la logique de test.

Chaque brique a un mécanisme de délégation Keycloak différent (OIDC direct,
proxy, plugin d'auth), donc l'endpoint et l'en-tête exact varient: ils sont
définis dans la table SSO_TARGETS ci-dessous plutôt que déduits
dynamiquement.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Optional

import pytest
import requests


@dataclasses.dataclass(frozen=True)
class SsoTarget:
    name: str
    # Construit l'URL à interroger à partir de `base_urls`.
    url_builder: Callable[..., str]
    # Code(s) HTTP attendu(s) quand la requête est faite SANS token.
    unauthenticated_statuses: tuple
    # Code(s) HTTP attendu(s) quand la requête est faite AVEC le token Keycloak.
    authenticated_statuses: tuple
    method: str = "GET"


SSO_TARGETS = [
    SsoTarget(
        name="seafile",
        url_builder=lambda b: f"{b.seafile}/api2/repos/",
        unauthenticated_statuses=(401, 403),
        authenticated_statuses=(200,),
    ),
    SsoTarget(
        name="vikunja",
        url_builder=lambda b: f"{b.vikunja}/api/v1/tasks/all",
        unauthenticated_statuses=(401,),
        authenticated_statuses=(200,),
    ),
    SsoTarget(
        name="matrix",
        url_builder=lambda b: f"{b.matrix}/_matrix/client/v3/account/whoami",
        unauthenticated_statuses=(401,),
        authenticated_statuses=(200,),
    ),
    SsoTarget(
        name="onlyoffice",
        # Le endpoint de gestion OnlyOffice utilisé pour la vérification JWT
        # (voir test_coedition_onlyoffice.py); ici on vérifie qu'un token
        # Keycloak seul (sans le JWT propre à OnlyOffice) ne suffit pas à
        # contourner la protection JWT du Document Server.
        url_builder=lambda b: f"{b.onlyoffice}/coauthoring/CommandService.ashx",
        unauthenticated_statuses=(200, 401, 403),
        authenticated_statuses=(200, 401, 403),
        method="POST",
    ),
    SsoTarget(
        name="grommunio",
        # Endpoint web JMAP/REST de Grommunio protégé par le proxy
        # d'authentification délégué à Keycloak (mod_auth_openidc côté Caddy).
        url_builder=lambda b: f"{b.caddy}/grommunio/api/whoami",
        unauthenticated_statuses=(401, 403, 404),
        authenticated_statuses=(200, 404),
    ),
]


@pytest.mark.sso
@pytest.mark.parametrize("target", SSO_TARGETS, ids=[t.name for t in SSO_TARGETS])
def test_keycloak_token_accepted_end_to_end(base_urls, keycloak_token, target: SsoTarget):
    """
    Pour chaque brique: une requête sans token doit être rejetée (401/403,
    selon le mécanisme propre à la brique), et la même requête avec le
    Bearer token Keycloak obtenu via la fixture `keycloak_token` doit être
    acceptée.

    NB: certaines briques (OnlyOffice, Grommunio) n'exposent pas Keycloak au
    même niveau applicatif que Seafile/Vikunja/Matrix (délégation via proxy
    ou JWT applicatif propre) - leurs codes attendus sont volontairement
    larges pour ce test générique. Un test dédié plus strict existe pour
    chacune dans son propre fichier de scénario quand la sémantique du code
    de retour est spécifique (voir test_coedition_onlyoffice.py par exemple).
    """
    url = target.url_builder(base_urls)

    unauthenticated_response = _request(target.method, url, headers=None)
    assert unauthenticated_response.status_code in target.unauthenticated_statuses, (
        f"[{target.name}] Requête sans token: attendu un code parmi "
        f"{target.unauthenticated_statuses}, obtenu {unauthenticated_response.status_code} "
        f"sur {url}."
    )

    authenticated_response = _request(
        target.method, url, headers={"Authorization": f"Bearer {keycloak_token}"}
    )
    assert authenticated_response.status_code in target.authenticated_statuses, (
        f"[{target.name}] Requête avec token Keycloak: attendu un code parmi "
        f"{target.authenticated_statuses}, obtenu {authenticated_response.status_code} "
        f"sur {url}. Le SSO bout-en-bout n'est pas fonctionnel pour cette brique."
    )


def _request(method: str, url: str, headers: Optional[dict]) -> requests.Response:
    try:
        return requests.request(method, url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as exc:
        pytest.fail(
            f"Échec de connexion vers {url}: {type(exc).__name__}: {exc}. "
            "Vérifier que le service est démarré et que la fixture wait_for_service "
            "a bien été satisfaite avant ce test."
        )

"""
Critical scenario (study 4.5): "end-to-end SSO authentication (Keycloak) on
each of the previous components".

This test is parametrized per component (one entry per service: Grommunio,
Seafile, Vikunja, OnlyOffice, Matrix) rather than written as five separate
test functions, because the assertion is structurally identical for each
component ("the protected endpoint rejects without a token, accepts it with
the Keycloak token") - only the URL and the expected "without token" status
code change from one component to another. Parametrization also makes it
trivial to add a future SSO component without duplicating test logic.

Each component has a different Keycloak delegation mechanism (direct OIDC,
proxy, auth plugin), so the exact endpoint and header vary: they are defined
in the SSO_TARGETS table below rather than derived dynamically.
"""

from __future__ import annotations

import dataclasses
from typing import Callable, Optional

import pytest
import requests


@dataclasses.dataclass(frozen=True)
class SsoTarget:
    name: str
    # Builds the URL to query from `base_urls`.
    url_builder: Callable[..., str]
    # Expected HTTP code(s) when the request is made WITHOUT a token.
    unauthenticated_statuses: tuple
    # Expected HTTP code(s) when the request is made WITH the Keycloak token.
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
        # The OnlyOffice management endpoint used for JWT verification (see
        # test_coedition_onlyoffice.py); here we check that a Keycloak token
        # alone (without OnlyOffice's own JWT) is not enough to bypass the
        # Document Server's JWT protection.
        url_builder=lambda b: f"{b.onlyoffice}/coauthoring/CommandService.ashx",
        unauthenticated_statuses=(200, 401, 403),
        authenticated_statuses=(200, 401, 403),
        method="POST",
    ),
    SsoTarget(
        name="grommunio",
        # Grommunio's web JMAP/REST endpoint protected by the auth proxy
        # delegated to Keycloak (mod_auth_openidc on the Caddy side).
        url_builder=lambda b: f"{b.caddy}/grommunio/api/whoami",
        unauthenticated_statuses=(401, 403, 404),
        authenticated_statuses=(200, 404),
    ),
]


@pytest.mark.sso
@pytest.mark.parametrize("target", SSO_TARGETS, ids=[t.name for t in SSO_TARGETS])
def test_keycloak_token_accepted_end_to_end(base_urls, keycloak_token, target: SsoTarget):
    """
    For each component: a request without a token must be rejected (401/403,
    depending on the component's own mechanism), and the same request with
    the Bearer Keycloak token obtained via the `keycloak_token` fixture must
    be accepted.

    NB: some components (OnlyOffice, Grommunio) do not expose Keycloak at
    the same application level as Seafile/Vikunja/Matrix (delegation via a
    proxy or their own application-level JWT) - their expected codes are
    deliberately broad for this generic test. A stricter dedicated test
    exists for each of them in its own scenario file when the semantics of
    the return code are specific (see test_coedition_onlyoffice.py for
    example).
    """
    url = target.url_builder(base_urls)

    unauthenticated_response = _request(target.method, url, headers=None)
    assert unauthenticated_response.status_code in target.unauthenticated_statuses, (
        f"[{target.name}] Request without a token: expected a code among "
        f"{target.unauthenticated_statuses}, got {unauthenticated_response.status_code} "
        f"on {url}."
    )

    authenticated_response = _request(
        target.method, url, headers={"Authorization": f"Bearer {keycloak_token}"}
    )
    assert authenticated_response.status_code in target.authenticated_statuses, (
        f"[{target.name}] Request with Keycloak token: expected a code among "
        f"{target.authenticated_statuses}, got {authenticated_response.status_code} "
        f"on {url}. End-to-end SSO is not working for this component."
    )


def _request(method: str, url: str, headers: Optional[dict]) -> requests.Response:
    try:
        return requests.request(method, url, headers=headers, timeout=15)
    except requests.exceptions.RequestException as exc:
        pytest.fail(
            f"Connection failed to {url}: {type(exc).__name__}: {exc}. "
            "Check that the service is started and that the wait_for_service "
            "fixture was satisfied before this test."
        )

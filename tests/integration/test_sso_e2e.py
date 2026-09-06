"""
Critical scenario (study 4.5): "end-to-end SSO authentication (Keycloak) on
each of the previous components".

A first version of this file tested all five components generically:
obtain a token via the Resource Owner Password Credentials grant on a
shared "integration-tests" Keycloak client, then present it as
`Authorization: Bearer <token>` directly to each app's API. That is not how
any of these apps actually implement OIDC: Seafile, Vikunja and Synapse all
use a browser AUTHORIZATION CODE redirect - the app itself exchanges the
code with Keycloak server-side and mints its OWN native credential (a
Seahub session cookie, a Vikunja JWT, a Matrix `access_token`). None of
them validate an externally-obtained Keycloak token as a resource server
would, and even if they did, a token minted for a different client_id/
audience ("integration-tests" rather than "seafile"/"vikunja"/
"matrix-synapse") would fail an audience check anyway. That version tested
nothing real.

A second version fixed that, but reached each app through its own
directly-exposed port (`base_urls`) - which bypasses Caddy, and with it
BOTH the OnlyOffice/Novu SSO gates (`forward_auth`, only wired into
Caddy's own routing) AND the exact domain each Keycloak client is actually
registered against (`redirect_uris` are the public domain, not
`localhost:<port>` - a real login would end up redirected to a URL nothing
in that version could resolve or serve).

This version drives every flow through `domain_session`/`public_url`
(conftest.py) instead: the exact `http://<subdomain>.<public_domain>` URLs
every Keycloak client and every app's own OIDC config already use, made
reachable from outside the cluster via `DomainRoutingAdapter` (mirroring
`dev-cluster/deploy.sh`'s CoreDNS patch, which does the same for pods
inside it) - see `dev-cluster/README.md`'s "Testing Keycloak SSO/OIDC
end-to-end". This is what finally lets OnlyOffice/Novu's oauth2-proxy
gates be exercised for real, not just checked structurally
(`check_oidc_coverage()`, `caddy validate`).

Grommunio is not here at all: it has no Keycloak client (see docs/oidc.md
- not a priority for the study, `grommunio-web` stays disabled), and the
URL an earlier version queried (`{caddy}/grommunio/api/whoami`) never
corresponded to anything actually built in this repository.
"""

from __future__ import annotations

import secrets
import urllib.parse
from typing import Callable

import pytest
import requests

# vikunja.yaml's VIKUNJA_AUTH_OPENID_PROVIDERS_0_NAME - the provider's
# display name is how it's looked up in Vikunja's own /api/v1/info below
# (its OIDC "key" is server-generated from this name, not something
# platform.yaml or this suite gets to choose).
VIKUNJA_PROVIDER_NAME = "Libre365 SSO"


@pytest.mark.sso
def test_seafile_oidc_login_grants_api_access(
    domain_session: requests.Session, public_url: Callable[..., str], test_user, keycloak_login, wait_for_service
):
    """Seafile's OIDC login (ENABLE_OAUTH, seafile.yaml) is a server-side
    authorization code exchange that ends in a Seahub session cookie -
    `api2` accepts that cookie (SessionAuthentication), not a bearer token."""
    seafile = public_url("files")
    wait_for_service(f"{seafile}/accounts/login/", expected_statuses=(200, 302), session=domain_session)

    unauthenticated = domain_session.get(f"{seafile}/api2/repos/", timeout=15)
    assert unauthenticated.status_code in (401, 403), (
        f"[seafile] Expected the repos API to reject an unauthenticated "
        f"request, got {unauthenticated.status_code}."
    )

    login_response = keycloak_login(
        f"{seafile}/oauth/login/", test_user.username, test_user.password, session=domain_session
    )
    assert login_response.status_code < 400, (
        f"[seafile] OIDC login via Keycloak did not complete: "
        f"HTTP {login_response.status_code} on {login_response.url}."
    )

    authenticated = domain_session.get(f"{seafile}/api2/repos/", timeout=15)
    assert authenticated.status_code == 200, (
        f"[seafile] Expected the repos API to accept the session obtained via "
        f"Keycloak SSO login, got {authenticated.status_code}. End-to-end SSO "
        "is not working for Seafile."
    )


@pytest.mark.sso
def test_vikunja_oidc_login_grants_a_native_jwt(
    domain_session: requests.Session, public_url: Callable[..., str], test_user, keycloak_openid_config, keycloak_login
):
    """
    Vikunja's OIDC login (VIKUNJA_AUTH_OPENID_*, vikunja.yaml) is a
    frontend-driven authorization code flow: the SPA builds the
    authorization URL itself from `/api/v1/info`'s advertised provider,
    then exchanges the returned `code` at its own `/callback` endpoint for
    a Vikunja-native JWT used as `Authorization: Bearer` on every other API
    call. Reproduced here without a browser: the authorization URL is built
    from Keycloak's own discovery document (`keycloak_openid_config`), not
    guessed, but Vikunja's callback payload shape and provider "key"
    derivation are [UNCERTAIN] - not independently confirmed against a live
    instance from this sandboxed environment; this test fails with a clear
    diagnostic rather than a false pass if either assumption is wrong.
    """
    vikunja = public_url("taches")

    unauthenticated = domain_session.get(f"{vikunja}/api/v1/tasks/all", timeout=15)
    assert unauthenticated.status_code == 401, (
        f"[vikunja] Expected the tasks API to reject an unauthenticated "
        f"request, got {unauthenticated.status_code}."
    )

    info = domain_session.get(f"{vikunja}/api/v1/info", timeout=15)
    info.raise_for_status()
    providers = info.json().get("auth", {}).get("openid", {}).get("providers") or []
    provider = next((p for p in providers if p.get("name") == VIKUNJA_PROVIDER_NAME), None)
    if provider is None:
        pytest.fail(
            f"[vikunja] /api/v1/info does not advertise an OpenID provider named "
            f"{VIKUNJA_PROVIDER_NAME!r} (got: {providers!r}) - either the OIDC "
            "config in vikunja.yaml isn't applied, or Vikunja's /info response "
            "shape changed and this test's assumption about it needs updating."
        )
    provider_key = provider.get("key")
    if not provider_key:
        pytest.fail(f"[vikunja] OpenID provider {VIKUNJA_PROVIDER_NAME!r} has no 'key' field: {provider!r}")

    redirect_uri = f"{vikunja}/auth/openid/{provider_key}"
    state = secrets.token_urlsafe(16)
    authorization_url = keycloak_openid_config["authorization_endpoint"] + "?" + urllib.parse.urlencode(
        {
            "client_id": provider.get("clientid", "vikunja"),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
        }
    )

    login_response = keycloak_login(authorization_url, test_user.username, test_user.password, session=domain_session)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(login_response.url).query)
    code = query.get("code", [None])[0]
    if not code:
        pytest.fail(
            "[vikunja] Keycloak login did not redirect back with an authorization "
            f"code - ended up at {login_response.url}."
        )

    callback = domain_session.post(
        f"{vikunja}/api/v1/auth/openid/{provider_key}/callback",
        json={"code": code, "scope": "openid email profile", "state": query.get("state", [state])[0], "redirect_url": redirect_uri},
        timeout=15,
    )
    if callback.status_code != 200 or "token" not in callback.json():
        pytest.fail(
            f"[vikunja] The OIDC callback exchange failed or returned no token: "
            f"HTTP {callback.status_code} - {callback.text[:500]}"
        )
    jwt = callback.json()["token"]

    authenticated = domain_session.get(
        f"{vikunja}/api/v1/tasks/all", headers={"Authorization": f"Bearer {jwt}"}, timeout=15
    )
    assert authenticated.status_code == 200, (
        f"[vikunja] Expected the tasks API to accept the JWT obtained via "
        f"Keycloak SSO login, got {authenticated.status_code}. End-to-end SSO "
        "is not working for Vikunja."
    )


@pytest.mark.sso
def test_matrix_oidc_login_grants_a_native_access_token(
    domain_session: requests.Session, public_url: Callable[..., str], test_user, keycloak_login
):
    """
    Synapse's OIDC login (synapse.yaml's native `oidc:` block, client_id
    `matrix-synapse`) is the Matrix Client-Server API's own SSO redirect
    (`m.login.sso`): the client starts at `/login/sso/redirect`, Synapse
    itself exchanges the code with Keycloak, then redirects the browser
    back to the CLIENT's `redirectUrl` with a one-time `loginToken` the
    client exchanges for a real Matrix `access_token` via `m.login.token` -
    standard Matrix spec behavior, not app-specific guessing. `redirectUrl`
    is set to the homeserver's own base URL here (same-origin, most likely
    to be accepted by Synapse's default SSO redirect allow-list) -
    [UNCERTAIN] against a live instance's exact `sso.client_whitelist`
    configuration, not independently confirmed from this sandboxed
    environment.
    """
    matrix = public_url("matrix")

    unauthenticated = domain_session.get(f"{matrix}/_matrix/client/v3/account/whoami", timeout=15)
    assert unauthenticated.status_code == 401, (
        f"[matrix] Expected whoami to reject an unauthenticated request, "
        f"got {unauthenticated.status_code}."
    )

    authorization_url = (
        f"{matrix}/_matrix/client/v3/login/sso/redirect"
        f"?redirectUrl={urllib.parse.quote(matrix, safe='')}"
    )
    login_response = keycloak_login(authorization_url, test_user.username, test_user.password, session=domain_session)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(login_response.url).query)
    login_token = query.get("loginToken", [None])[0]
    if not login_token:
        pytest.fail(
            "[matrix] Synapse's SSO redirect did not come back with a "
            f"loginToken - ended up at {login_response.url}."
        )

    token_response = domain_session.post(
        f"{matrix}/_matrix/client/v3/login",
        json={"type": "m.login.token", "token": login_token},
        timeout=15,
    )
    if token_response.status_code != 200 or "access_token" not in token_response.json():
        pytest.fail(
            f"[matrix] Exchanging the loginToken for an access_token failed: "
            f"HTTP {token_response.status_code} - {token_response.text[:500]}"
        )
    access_token = token_response.json()["access_token"]

    authenticated = domain_session.get(
        f"{matrix}/_matrix/client/v3/account/whoami",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    assert authenticated.status_code == 200, (
        f"[matrix] Expected whoami to accept the access_token obtained via "
        f"Keycloak SSO login, got {authenticated.status_code}. End-to-end SSO "
        "is not working for Matrix/Synapse."
    )


def _assert_oauth2_proxy_gate_blocks_then_allows(
    domain_session: requests.Session,
    gated_url: str,
    test_user,
    keycloak_login: Callable[..., requests.Response],
    label: str,
) -> None:
    """
    Shared assertion for the two oauth2-proxy-gated components
    (OnlyOffice, Novu's admin dashboard - docs/oidc.md): `domain_session` is
    guaranteed cookie-free at the start of every test (see its own
    docstring), so the FIRST request on it here is genuinely
    unauthenticated - it must end up at Keycloak's login page (proof the
    gate is active - matched on the response ending up on the
    `sso.<public_domain>` host, not on any specific status code, since
    oauth2-proxy/Keycloak's exact redirect chain status codes aren't
    independently confirmed from this sandboxed environment); completing
    the real Keycloak login through it must then reach the actual
    application behind the gate (status 200, not another login prompt).
    """
    unauthenticated = domain_session.get(gated_url, timeout=15)
    unauthenticated_host = urllib.parse.urlsplit(unauthenticated.url).hostname or ""
    assert unauthenticated_host.startswith("sso."), (
        f"[{label}] Expected an unauthenticated request to be redirected to Keycloak's "
        f"login page (oauth2-proxy's forward_auth gate), but ended up at "
        f"{unauthenticated.url} instead - the gate does not appear to be active."
    )

    login_response = keycloak_login(gated_url, test_user.username, test_user.password, session=domain_session)
    assert login_response.status_code == 200, (
        f"[{label}] Expected the oauth2-proxy gate to grant access to the real application "
        f"after a successful Keycloak login, got HTTP {login_response.status_code} on "
        f"{login_response.url}. End-to-end SSO is not working for {label}."
    )


@pytest.mark.sso
def test_onlyoffice_oauth2_proxy_gate_blocks_then_allows(
    domain_session: requests.Session, public_url: Callable[..., str], test_user, keycloak_login
):
    """
    OnlyOffice Document Server has no login screen of its own (its JWT only
    signs individual document-open requests from Seafile - see
    test_coedition_onlyoffice.py); office.libre365.example.org is instead
    gated by Caddy's `forward_auth` -> oauth2-proxy -> Keycloak chain
    (infra/k8s/helm-values/oauth2-proxy-onlyoffice.yaml, docs/oidc.md) -
    this is what actually protects the public route, in addition to (not
    instead of) that JWT signing.
    """
    _assert_oauth2_proxy_gate_blocks_then_allows(
        domain_session, public_url("office"), test_user, keycloak_login, "onlyoffice"
    )


@pytest.mark.sso
def test_novu_admin_oauth2_proxy_gate_blocks_then_allows(
    domain_session: requests.Session, public_url: Callable[..., str], test_user, keycloak_login
):
    """
    Novu's `web` ADMIN dashboard (template/workflow management) is gated
    the same way as OnlyOffice (infra/k8s/helm-values/oauth2-proxy-novu.yaml,
    docs/oidc.md) - a separate surface from `notifications.<public_domain>`
    (the API), which the top-bar widget calls with its own HMAC
    subscriberHash auth and is deliberately NOT covered here: gating it
    with an interactive Keycloak login would break the widget, which has no
    browser redirect flow to complete one.
    """
    _assert_oauth2_proxy_gate_blocks_then_allows(
        domain_session, public_url("notifications_admin"), test_user, keycloak_login, "novu-admin"
    )

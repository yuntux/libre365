"""
Critical scenario (study 4.5): "end-to-end SSO authentication (Keycloak) on
each of the previous components".

A first version of this file (fixed on review - see `docs/oidc.md`) tested
all five components generically: obtain a token via the Resource Owner
Password Credentials grant on a shared "integration-tests" Keycloak client,
then present it as `Authorization: Bearer <token>` directly to each app's
API. That is not how any of these apps actually implement OIDC: Seafile,
Vikunja and Synapse all use a browser AUTHORIZATION CODE redirect - the app
itself exchanges the code with Keycloak server-side and mints its OWN
native credential (a Seahub session cookie, a Vikunja JWT, a Matrix
`access_token`). None of them validate an externally-obtained Keycloak
token as a resource server would, and even if they did, a token minted for
a different client_id/audience ("integration-tests" rather than
"seafile"/"vikunja"/"matrix-synapse") would fail an audience check anyway.
That version tested nothing real.

Each function below instead drives the ACTUAL redirect flow with a plain
`requests.Session` (via the `keycloak_login` fixture in conftest.py -
Keycloak's default theme is a plain HTML form POST, no browser/JS needed),
ending up with the same kind of credential a real user's browser would get,
then verifies THAT credential is what the app's own protected endpoint
actually accepts.

Two components from the original version are deliberately not here:
  - Grommunio: has no Keycloak client at all (see docs/oidc.md - not a
    priority for the study, `grommunio-web` stays disabled) - the URL the
    old version queried (`{caddy}/grommunio/api/whoami`) does not
    correspond to anything actually built in this repository; there was no
    real mechanism there to test in the first place.
  - OnlyOffice / Novu: gated by a Caddy `forward_auth` -> oauth2-proxy ->
    Keycloak chain instead of native OIDC (see docs/oidc.md) - structurally
    verified by `check_oidc_coverage()` and a real `caddy validate` run,
    but not by a live test here: this suite's `base_urls` fixture reaches
    every other component through its own directly-exposed port, bypassing
    Caddy's domain-based virtual hosting entirely (see conftest.py) - the
    forward_auth gate only exists on Caddy's own routing, so exercising it
    for real would need the suite to reach these two components THROUGH
    Caddy by domain name, which nothing in this suite does for any
    component today. Left as a documented follow-up rather than a test
    that can't actually run against the dev/staging environments this
    suite targets.
"""

from __future__ import annotations

import secrets
import urllib.parse

import pytest
import requests

# vikunja.yaml's VIKUNJA_AUTH_OPENID_PROVIDERS_0_NAME - the provider's
# display name is how it's looked up in Vikunja's own /api/v1/info below
# (its OIDC "key" is server-generated from this name, not something
# platform.yaml or this suite gets to choose).
VIKUNJA_PROVIDER_NAME = "Libre365 SSO"


@pytest.mark.sso
def test_seafile_oidc_login_grants_api_access(base_urls, test_user, keycloak_login, wait_for_service):
    """Seafile's OIDC login (ENABLE_OAUTH, seafile.yaml) is a server-side
    authorization code exchange that ends in a Seahub session cookie -
    `api2` accepts that cookie (SessionAuthentication), not a bearer token."""
    wait_for_service(f"{base_urls.seafile}/accounts/login/", expected_statuses=(200, 302))

    unauthenticated = requests.get(f"{base_urls.seafile}/api2/repos/", timeout=15)
    assert unauthenticated.status_code in (401, 403), (
        f"[seafile] Expected the repos API to reject an unauthenticated "
        f"request, got {unauthenticated.status_code}."
    )

    session = requests.Session()
    login_response = keycloak_login(
        f"{base_urls.seafile}/oauth/login/", test_user.username, test_user.password, session=session
    )
    assert login_response.status_code < 400, (
        f"[seafile] OIDC login via Keycloak did not complete: "
        f"HTTP {login_response.status_code} on {login_response.url}."
    )

    authenticated = session.get(f"{base_urls.seafile}/api2/repos/", timeout=15)
    assert authenticated.status_code == 200, (
        f"[seafile] Expected the repos API to accept the session obtained via "
        f"Keycloak SSO login, got {authenticated.status_code}. End-to-end SSO "
        "is not working for Seafile."
    )


@pytest.mark.sso
def test_vikunja_oidc_login_grants_a_native_jwt(base_urls, test_user, keycloak_openid_config, keycloak_login):
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
    unauthenticated = requests.get(f"{base_urls.vikunja}/api/v1/tasks/all", timeout=15)
    assert unauthenticated.status_code == 401, (
        f"[vikunja] Expected the tasks API to reject an unauthenticated "
        f"request, got {unauthenticated.status_code}."
    )

    info = requests.get(f"{base_urls.vikunja}/api/v1/info", timeout=15)
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

    redirect_uri = f"{base_urls.vikunja}/auth/openid/{provider_key}"
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

    login_response = keycloak_login(authorization_url, test_user.username, test_user.password)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(login_response.url).query)
    code = query.get("code", [None])[0]
    if not code:
        pytest.fail(
            "[vikunja] Keycloak login did not redirect back with an authorization "
            f"code - ended up at {login_response.url}."
        )

    callback = requests.post(
        f"{base_urls.vikunja}/api/v1/auth/openid/{provider_key}/callback",
        json={"code": code, "scope": "openid email profile", "state": query.get("state", [state])[0], "redirect_url": redirect_uri},
        timeout=15,
    )
    if callback.status_code != 200 or "token" not in callback.json():
        pytest.fail(
            f"[vikunja] The OIDC callback exchange failed or returned no token: "
            f"HTTP {callback.status_code} - {callback.text[:500]}"
        )
    jwt = callback.json()["token"]

    authenticated = requests.get(
        f"{base_urls.vikunja}/api/v1/tasks/all", headers={"Authorization": f"Bearer {jwt}"}, timeout=15
    )
    assert authenticated.status_code == 200, (
        f"[vikunja] Expected the tasks API to accept the JWT obtained via "
        f"Keycloak SSO login, got {authenticated.status_code}. End-to-end SSO "
        "is not working for Vikunja."
    )


@pytest.mark.sso
def test_matrix_oidc_login_grants_a_native_access_token(base_urls, test_user, keycloak_login):
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
    unauthenticated = requests.get(f"{base_urls.matrix}/_matrix/client/v3/account/whoami", timeout=15)
    assert unauthenticated.status_code == 401, (
        f"[matrix] Expected whoami to reject an unauthenticated request, "
        f"got {unauthenticated.status_code}."
    )

    redirect_url = base_urls.matrix
    authorization_url = (
        f"{base_urls.matrix}/_matrix/client/v3/login/sso/redirect"
        f"?redirectUrl={urllib.parse.quote(redirect_url, safe='')}"
    )
    login_response = keycloak_login(authorization_url, test_user.username, test_user.password)
    query = urllib.parse.parse_qs(urllib.parse.urlparse(login_response.url).query)
    login_token = query.get("loginToken", [None])[0]
    if not login_token:
        pytest.fail(
            "[matrix] Synapse's SSO redirect did not come back with a "
            f"loginToken - ended up at {login_response.url}."
        )

    token_response = requests.post(
        f"{base_urls.matrix}/_matrix/client/v3/login",
        json={"type": "m.login.token", "token": login_token},
        timeout=15,
    )
    if token_response.status_code != 200 or "access_token" not in token_response.json():
        pytest.fail(
            f"[matrix] Exchanging the loginToken for an access_token failed: "
            f"HTTP {token_response.status_code} - {token_response.text[:500]}"
        )
    access_token = token_response.json()["access_token"]

    authenticated = requests.get(
        f"{base_urls.matrix}/_matrix/client/v3/account/whoami",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    assert authenticated.status_code == 200, (
        f"[matrix] Expected whoami to accept the access_token obtained via "
        f"Keycloak SSO login, got {authenticated.status_code}. End-to-end SSO "
        "is not working for Matrix/Synapse."
    )

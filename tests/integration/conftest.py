"""
Shared fixtures for the integration test suite (study, section 4.5
"Replaying the test scenarios").

This suite is meant to be replayed both:
- locally, against the local dev stack (the k3d dev cluster,
  `../../dev-cluster/deploy.sh`, plus `grommunio-dev` on docker-compose,
  `dev-cluster/grommunio-dev/docker-compose.yml` — see
  `../../dev-cluster/README.md`),
- automatically against the ephemeral staging environment (section 4.4/4.6),
  via the CI/CD pipeline, without manual intervention until the results are
  validated.

All URLs/ports are therefore read from environment variables, with defaults
aligned on the default ports of the local dev stack. Never hard-code a URL
in a test file: go through the `base_urls` fixture instead.

The default ports themselves are NOT hard-coded here: they come from
`_platform_defaults.py`, generated from `platform.yaml` (repo root) by
`scripts/sync_platform.py` — the same source that drives
`dev-cluster/grommunio-dev/.env.example` and `dev-cluster/k3d-config.yaml`.
Explicit goal: eliminate the risk of drift between the ports actually
exposed by the dev stack and the ones this suite uses by default (a silent
drift had already happened here before platform.yaml was introduced:
Gokapi, PeerTube and Caddy had stale default ports).
"""

from __future__ import annotations

import os
import time
import dataclasses
import urllib.parse
from typing import Callable, Optional

import pytest
import requests
from bs4 import BeautifulSoup

from _platform_defaults import DEFAULT_PORTS


# ---------------------------------------------------------------------------
# Service URL resolution
# ---------------------------------------------------------------------------

def _env_url(var_name: str, default: str) -> str:
    """Reads a base URL from the environment, without a trailing slash."""
    return os.environ.get(var_name, default).rstrip("/")


def _default_url(port_var: str, path: str = "") -> str:
    """Default localhost URL built from a port in
    `_platform_defaults.DEFAULT_PORTS` (i.e. from `platform.yaml`)."""
    return f"http://localhost:{DEFAULT_PORTS[port_var]}{path}"


@dataclasses.dataclass(frozen=True)
class BaseUrls:
    """Base URLs of each component, resolved once per test session."""

    keycloak: str
    grommunio_imap_host: str
    grommunio_imap_port: int
    grommunio_smtp_host: str
    grommunio_smtp_port: int
    seafile: str
    onlyoffice: str
    matrix: str  # Synapse (Matrix homeserver)
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
    URLs/hosts of the components, defaulting to values consistent with the
    local dev stack (study section 4.6: k3d dev cluster + grommunio-dev on
    docker-compose, see ../../dev-cluster/README.md).

    To point the suite at the ephemeral staging environment (section 5.4/4.4),
    override the corresponding environment variables in the CI/CD pipeline
    (see tests/integration/README.md).
    """
    return BaseUrls(
        keycloak=_env_url("KEYCLOAK_URL", _default_url("KEYCLOAK_PORT")),
        grommunio_imap_host=os.environ.get("GROMMUNIO_IMAP_HOST", "localhost"),
        grommunio_imap_port=int(os.environ.get("GROMMUNIO_IMAP_PORT", "993")),
        grommunio_smtp_host=os.environ.get("GROMMUNIO_SMTP_HOST", "localhost"),
        grommunio_smtp_port=int(os.environ.get("GROMMUNIO_SMTP_PORT", "587")),
        seafile=_env_url("SEAFILE_URL", _default_url("SEAFILE_PORT")),
        onlyoffice=_env_url("ONLYOFFICE_URL", _default_url("ONLYOFFICE_PORT")),
        matrix=_env_url("MATRIX_URL", _default_url("SYNAPSE_CLIENT_PORT")),
        element=_env_url("ELEMENT_URL", _default_url("ELEMENT_PORT")),
        vikunja=_env_url("VIKUNJA_URL", _default_url("VIKUNJA_PORT")),
        gokapi=_env_url("GOKAPI_URL", _default_url("GOKAPI_PORT")),
        minio=_env_url("MINIO_URL", _default_url("MINIO_API_PORT")),
        peertube=_env_url("PEERTUBE_URL", _default_url("PEERTUBE_PORT")),
        caddy=_env_url("CADDY_URL", _default_url("CADDY_HTTP_PORT")),
        notification_hub=_env_url("NOTIFICATION_HUB_URL", _default_url("NOTIFICATION_HUB_PORT")),
        unified_search=_env_url("UNIFIED_SEARCH_URL", _default_url("UNIFIED_SEARCH_PORT")),
        presence_aggregator=_env_url("PRESENCE_AGGREGATOR_URL", _default_url("PRESENCE_AGGREGATOR_PORT")),
        onlyoffice_mentions=_env_url("ONLYOFFICE_MENTIONS_URL", _default_url("ONLYOFFICE_MENTIONS_PORT")),
        peertube_ingest=_env_url("PEERTUBE_INGEST_URL", _default_url("PEERTUBE_INGEST_PORT")),
    )


# ---------------------------------------------------------------------------
# Test credentials (representative dataset, section 4.4 point 2)
# ---------------------------------------------------------------------------

@dataclasses.dataclass(frozen=True)
class TestUser:
    username: str
    password: str
    email: str


@pytest.fixture(scope="session")
def test_user() -> TestUser:
    """
    Test user provisioned in the representative dataset of the staging
    environment (section 4.4, point 2) or in the test realm of the local
    docker-compose. NEVER point this at a real production account.
    """
    return TestUser(
        username=os.environ.get("TEST_USER_USERNAME", "test.consultant"),
        password=os.environ.get("TEST_USER_PASSWORD", "ChangeMe123!"),
        email=os.environ.get("TEST_USER_EMAIL", "test.consultant@libre365.test"),
    )


@pytest.fixture(scope="session")
def keycloak_realm() -> str:
    return os.environ.get("KEYCLOAK_REALM", "libre365")


# ---------------------------------------------------------------------------
# Waiting for service availability (slow stack startup)
# ---------------------------------------------------------------------------

class ServiceNotReadyError(RuntimeError):
    """
    Raised when a service is not ready after all retries are exhausted.
    Deliberately distinct from requests/urllib exceptions so tests fail with
    a clear message ("stack not started") rather than an opaque connection-
    refused traceback.
    """


@pytest.fixture(scope="session")
def wait_for_service() -> Callable[..., None]:
    """
    Fixture-function: `wait_for_service(url, expected_statuses=(200,), timeout=60, interval=2)`.

    Polls an HTTP healthcheck URL with backoff, to absorb the slow startup of
    the docker-compose stack before running business assertions. On failure,
    raises ServiceNotReadyError with an explicit message instead of letting
    the first test crash with a raw ConnectionError.
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
                last_error = f"HTTP {response.status_code} from {url}"
            except requests.exceptions.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            time.sleep(current_interval)
            current_interval = min(current_interval * 1.5, max_interval)

        raise ServiceNotReadyError(
            f"Service unavailable after waiting {timeout}s on {url} "
            f"(last error: {last_error}). "
            "Check that the docker-compose stack (or the ephemeral staging "
            "environment) is properly started before running the tests."
        )

    return _wait

# ---------------------------------------------------------------------------
# Real browser-redirect OIDC login (test_sso_e2e.py)
#
# An earlier version of test_sso_e2e.py used a single Resource Owner
# Password Credentials token, obtained via a dedicated "integration-tests"
# Keycloak client, presented directly to every app's API. That doesn't
# reflect how any of these apps actually implement OIDC (see
# test_sso_e2e.py's module docstring and docs/oidc.md for the full
# explanation): Seafile, Vikunja and Synapse all implement OIDC as a
# browser AUTHORIZATION CODE redirect - the app itself exchanges the code
# with Keycloak server-side and mints its OWN native session/token (a
# Seahub session cookie, a Vikunja JWT, a Matrix access_token). None of
# them validate an externally-obtained bearer token as a resource server
# would, so that version tested nothing real - fixed by removing it
# entirely (the "integration-tests" client, `keycloak_client_id`/
# `keycloak_client_secret`/`keycloak_token` fixtures) rather than keeping
# unused fixtures around.
#
# The functions below instead complete the actual redirect flow with a
# plain `requests.Session` (no browser/JS needed: Keycloak's default theme
# is a plain HTML form POST), so each per-app SSO test in test_sso_e2e.py
# ends up with the SAME kind of credential a real user's browser would get.
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def keycloak_openid_config(base_urls: BaseUrls, keycloak_realm: str, wait_for_service: Callable[..., None]) -> dict:
    """The realm's own `.well-known/openid-configuration` document -
    `authorization_endpoint`/`token_endpoint` are read from here rather than
    hard-coded, the same discovery URL `keycloak_token` already waits on."""
    url = f"{base_urls.keycloak}/realms/{keycloak_realm}/.well-known/openid-configuration"
    wait_for_service(url, timeout=float(os.environ.get("SERVICE_WAIT_TIMEOUT", "120")))
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()


def complete_keycloak_login(
    authorization_url: str, username: str, password: str, session: Optional[requests.Session] = None
) -> requests.Response:
    """
    Drives Keycloak's own login page like a real browser would, entirely
    over HTTP (no JS execution needed - Keycloak's default `keycloak` theme
    renders a plain `<form id="kc-form-login">` that POSTs `username`/
    `password` to a session-tied `action` URL): GETs `authorization_url`
    (following redirects onto the login page), parses that form, and POSTs
    the credentials to it, following redirects to completion.

    For an app whose backend does the code<->token exchange itself
    (Seafile, Vikunja's callback endpoint), the returned response is
    already on the app's own side, with the app's session cookie set in
    `session`. For a flow where the final redirect carries a token/code in
    its own query string instead (Matrix's SSO `loginToken`, Vikunja's
    authorization `code`), read `response.url` - `requests` does not
    execute anything at that destination, it just records where the
    redirect chain ended.
    """
    session = session or requests.Session()
    login_page = session.get(authorization_url, timeout=15)
    login_page.raise_for_status()

    soup = BeautifulSoup(login_page.text, "html.parser")
    form = soup.find("form", id="kc-form-login") or soup.find("form")
    if form is None:
        pytest.fail(
            "Could not find a login form on Keycloak's login page - the "
            f"authorization_url ({authorization_url}) may not have reached "
            "Keycloak's login screen at all (e.g. already authenticated, or "
            "the realm/client rejected the request outright). "
            f"Response URL: {login_page.url}"
        )
    action_url = urllib.parse.urljoin(login_page.url, form["action"])
    fields = {
        field["name"]: field.get("value", "")
        for field in form.find_all("input")
        if field.get("name")
    }
    fields["username"] = username
    fields["password"] = password

    return session.post(action_url, data=fields, timeout=15)


@pytest.fixture
def keycloak_login() -> Callable[..., requests.Response]:
    """Fixture-function wrapper around `complete_keycloak_login`, matching
    this file's other fixture-function conventions (e.g. `wait_for_service`)."""
    return complete_keycloak_login


# ---------------------------------------------------------------------------
# Custom markers (also declared in pytest.ini, deliberate duplication to
# tolerate running without an explicit -c)
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "smoke: minimal critical scenario (quick to replay)")
    config.addinivalue_line("markers", "slow: longer scenario (e.g. waiting for async convergence)")
    config.addinivalue_line("markers", "sso: end-to-end SSO authentication scenario (Keycloak)")

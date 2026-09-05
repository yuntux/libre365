"""
Shared fixtures for the integration test suite (study, section 4.5
"Replaying the test scenarios").

This suite is meant to be replayed both:
- locally, against the docker-compose stack (docker-compose/docker-compose.yml),
- automatically against the ephemeral staging environment (section 4.4/4.6),
  via the CI/CD pipeline, without manual intervention until the results are
  validated.

All URLs/ports are therefore read from environment variables, with defaults
aligned on the default ports of the local docker-compose. Never hard-code a
URL in a test file: go through the `base_urls` fixture instead.

The default ports themselves are NOT hard-coded here: they come from
`_platform_defaults.py`, generated from `platform.yaml` (repo root) by
`scripts/sync_platform.py` — the same source that drives
`docker-compose/.env.example`. Explicit goal: eliminate the risk of drift
between the ports actually exposed by docker-compose and the ones this suite
uses by default (a silent drift had already happened here before
platform.yaml was introduced: Gokapi, PeerTube and Caddy had stale default
ports).
"""

from __future__ import annotations

import os
import time
import dataclasses
from typing import Callable, Optional

import pytest
import requests

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
    URLs/hosts of the components, defaulting to values consistent with
    docker-compose/docker-compose.yml (study section 4.6: local docker-compose
    environment).

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


@pytest.fixture(scope="session")
def keycloak_client_id() -> str:
    # Public "direct access grants" client dedicated to integration tests
    # (never reuse a production client here).
    return os.environ.get("KEYCLOAK_CLIENT_ID", "integration-tests")


@pytest.fixture(scope="session")
def keycloak_client_secret() -> Optional[str]:
    # Empty if the test Keycloak client is public (no secret).
    return os.environ.get("KEYCLOAK_CLIENT_SECRET") or None


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
# Keycloak SSO authentication ("password" grant for a test user)
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
    Obtains an OIDC access_token via the "password" grant (Resource Owner
    Password Credentials) against Keycloak, for a test user.

    This is the entry point of the "end-to-end SSO authentication" scenario
    (study 4.5, last scenario listed): this token is then presented to the
    other components (Grommunio, Seafile, Vikunja, OnlyOffice, Matrix) in
    test_sso_e2e.py to verify it is accepted everywhere.

    The "password" grant is only used for integration testing with a
    dedicated test user: it must never be enabled on a production Keycloak
    client.
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
            "Failed to obtain the Keycloak token (password grant) on "
            f"{token_url}: HTTP {response.status_code} - {response.text[:500]}"
        )

    access_token = response.json().get("access_token")
    if not access_token:
        pytest.fail(f"Keycloak response without access_token: {response.text[:500]}")

    return access_token


# ---------------------------------------------------------------------------
# Custom markers (also declared in pytest.ini, deliberate duplication to
# tolerate running without an explicit -c)
# ---------------------------------------------------------------------------

def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "smoke: minimal critical scenario (quick to replay)")
    config.addinivalue_line("markers", "slow: longer scenario (e.g. waiting for async convergence)")
    config.addinivalue_line("markers", "sso: end-to-end SSO authentication scenario (Keycloak)")

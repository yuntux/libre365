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

from _platform_defaults import DEFAULT_PORTS, DOMAIN_BASE, DOMAIN_SUBDOMAINS, TEST_USER_EMAIL, TEST_USER_USERNAME


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
    seaweedfs: str
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
        seaweedfs=_env_url("SEAWEEDFS_URL", _default_url("SEAWEEDFS_S3_PORT")),
        peertube=_env_url("PEERTUBE_URL", _default_url("PEERTUBE_PORT")),
        caddy=_env_url("CADDY_URL", _default_url("CADDY_HTTP_PORT")),
        notification_hub=_env_url("NOTIFICATION_HUB_URL", _default_url("NOTIFICATION_HUB_PORT")),
        unified_search=_env_url("UNIFIED_SEARCH_URL", _default_url("UNIFIED_SEARCH_PORT")),
        presence_aggregator=_env_url("PRESENCE_AGGREGATOR_URL", _default_url("PRESENCE_AGGREGATOR_PORT")),
        onlyoffice_mentions=_env_url("ONLYOFFICE_MENTIONS_URL", _default_url("ONLYOFFICE_MENTIONS_PORT")),
        peertube_ingest=_env_url("PEERTUBE_INGEST_URL", _default_url("PEERTUBE_INGEST_PORT")),
    )


# ---------------------------------------------------------------------------
# Reaching the public, domain-based routing (Caddy) instead of an app's own
# directly-exposed port - study 1.7, see dev-cluster/README.md's "Testing
# Keycloak SSO/OIDC end-to-end" for the full picture.
#
# Every OIDC config in this repo (Keycloak's KC_HOSTNAME, each app's own
# issuer/authurl, both oauth2-proxy gates) uses the real public domain
# (DOMAIN_BASE, generated from platform.yaml's domains.base - never a
# second, hard-coded copy of it). `base_urls` above deliberately bypasses
# Caddy entirely (each app's own directly-exposed port, for speed and
# simplicity on every OTHER kind of test) - but that also bypasses the
# Caddy-level SSO gates (OnlyOffice/Novu's forward_auth) and doesn't
# reflect the domain a real browser/app would actually use for its OIDC
# login. `dev-cluster/deploy.sh`'s CoreDNS step makes every domain resolve
# to Caddy for pods INSIDE the cluster; `DomainRoutingAdapter` below is the
# same trick for this test suite running OUTSIDE it - plain HTTP only (no
# TLS/SNI involved), matching every other `base_urls` default already
# being HTTP-only.
# ---------------------------------------------------------------------------

class DomainRoutingAdapter(requests.adapters.HTTPAdapter):
    """
    Rewrites any request to `*.<domain_suffix>` to actually connect to
    `target_host:target_port` instead, while keeping the original hostname
    as the `Host` header - lets a plain `requests.Session` reach a Caddy
    instance that virtual-hosts by domain name, without needing real DNS
    to resolve that domain from the test runner's machine.

    Self-tested against a throwaway local HTTP server in
    test_domain_routing_adapter.py - not just plausible-looking code: that
    test is what actually proves the Host-header rewrite reaches the right
    virtual host, independent of whether a live k3d cluster is available to
    exercise it end-to-end.
    """

    def __init__(self, domain_suffix: str, target_host: str, target_port: int, **kwargs):
        self._domain_suffix = domain_suffix.lstrip(".")
        self._target_host = target_host
        self._target_port = target_port
        super().__init__(**kwargs)

    def send(self, request, **kwargs):
        parsed = urllib.parse.urlsplit(request.url)
        hostname = parsed.hostname or ""
        if hostname == self._domain_suffix or hostname.endswith("." + self._domain_suffix):
            original_host_header = parsed.netloc
            new_netloc = f"{self._target_host}:{self._target_port}"
            request.url = urllib.parse.urlunsplit(
                (parsed.scheme, new_netloc, parsed.path, parsed.query, parsed.fragment)
            )
            request.headers["Host"] = original_host_header
        return super().send(request, **kwargs)


def _split_host_port(base_url: str, default_port: int) -> tuple:
    parsed = urllib.parse.urlsplit(base_url)
    return parsed.hostname or "localhost", parsed.port or default_port


@pytest.fixture(scope="session")
def public_domain() -> str:
    """DOMAIN_BASE, generated from platform.yaml's domains.base (see
    scripts/sync_platform.py's compute_test_defaults_changes()) - override
    with LIBRE365_DOMAIN_BASE only if the target environment genuinely uses
    a different one (e.g. a real bought domain in staging/production)."""
    return os.environ.get("LIBRE365_DOMAIN_BASE", DOMAIN_BASE)


def _new_domain_session(base_urls: BaseUrls, public_domain: str) -> requests.Session:
    """A requests.Session that reaches every `http://<subdomain>.<public_domain>`
    URL through Caddy (`base_urls.caddy`) via `DomainRoutingAdapter`, instead
    of failing to resolve a domain nothing but Caddy's own CoreDNS patch (or
    real production DNS) ever populates."""
    host, port = _split_host_port(base_urls.caddy, DEFAULT_PORTS["CADDY_HTTP_PORT"])
    session = requests.Session()
    adapter = DomainRoutingAdapter(public_domain, host, port)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


@pytest.fixture
def domain_session(base_urls: BaseUrls, public_domain: str) -> requests.Session:
    """Function-scoped (NOT session-scoped) deliberately: a shared session
    would carry Keycloak's own SSO cookie across tests, so a login flow
    started in a LATER test could silently skip straight past the login
    form (already authenticated from an earlier test in the same run) -
    `complete_keycloak_login` would then fail to find one at all. Each test
    gets its own empty cookie jar, exactly like a fresh browser profile."""
    return _new_domain_session(base_urls, public_domain)


@pytest.fixture(scope="session")
def public_url(public_domain: str) -> Callable[..., str]:
    """Fixture-function: `public_url("sso")` / `public_url("office", "/oauth2/callback")`
    - builds the exact same domain every OIDC config in this repo uses, from
    DOMAIN_SUBDOMAINS (generated from platform.yaml), never a hard-coded
    literal in a test file."""

    def _build(subdomain_key: str, path: str = "") -> str:
        return f"http://{DOMAIN_SUBDOMAINS[subdomain_key]}.{public_domain}{path}"

    return _build


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
    Test user provisioned in the representative dataset (study 4.4, point
    2) - platform.yaml's `test_dataset` (generated into
    TEST_USER_USERNAME/TEST_USER_EMAIL here, same convention as
    DOMAIN_BASE), the same account
    infra/ansible/roles/keycloak_realm optionally provisions
    (`keycloak_realm_test_user_enabled` - see
    dev-cluster/provision-keycloak-dev.sh for the k3d dev cluster).
    NEVER point this at a real production account. The password has no
    default from platform.yaml (it's a secret, never committed) - only an
    env var override, matching dev-cluster/provision-keycloak-dev.sh's own
    fixed dev-only value.
    """
    return TestUser(
        username=os.environ.get("TEST_USER_USERNAME", TEST_USER_USERNAME),
        password=os.environ.get("TEST_USER_PASSWORD", "devonly-changeme-test-user"),
        email=os.environ.get("TEST_USER_EMAIL", TEST_USER_EMAIL),
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
    Fixture-function: `wait_for_service(url, expected_statuses=(200,), timeout=60, interval=2, session=None)`.
    Pass `session=domain_session` to poll a `*.<public_domain>` URL through
    `DomainRoutingAdapter` instead of a plain (unresolvable) direct request.

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
        session: Optional[requests.Session] = None,
    ) -> None:
        deadline = time.monotonic() + timeout
        last_error: Optional[str] = None
        current_interval = interval
        client = session or requests

        while time.monotonic() < deadline:
            try:
                response = client.get(url, timeout=request_timeout)
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
def keycloak_openid_config(
    base_urls: BaseUrls, public_domain: str, public_url: Callable[..., str], keycloak_realm: str, wait_for_service: Callable[..., None]
) -> dict:
    """The realm's own `.well-known/openid-configuration` document -
    `authorization_endpoint`/`token_endpoint` are read from here rather than
    hard-coded. Fetched through the public domain (a throwaway session built
    the same way `domain_session` is - session-scoped here since this is a
    read-only GET with no login state to keep isolated between tests,
    unlike `domain_session` itself), the same way every per-app OIDC test
    below reaches Keycloak: KC_HOSTNAME is strict (keycloak.yaml), so the
    URLs it advertises always describe `sso.<public_domain>` regardless of
    which host actually asks - but Keycloak's `proxy: edge` setting also
    expects to be reached through a trusted proxy (Caddy), which only holds
    true when asked this way."""
    session = _new_domain_session(base_urls, public_domain)
    url = public_url("sso", f"/realms/{keycloak_realm}/.well-known/openid-configuration")
    wait_for_service(url, timeout=float(os.environ.get("SERVICE_WAIT_TIMEOUT", "120")), session=session)
    response = session.get(url, timeout=10)
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

# Integration tests

Long-lived integration test suite covering the critical scenarios
identified in the study (`office365-exit-study.md`, section 4.5 "Replaying
the test scenarios"):

| Scenario (study 4.5)                                      | File                                  |
|----------------------------------------------------------|---------------------------------------|
| Sending/receiving mail (Grommunio)                        | `test_mail_grommunio.py`              |
| Creating and syncing a file (Seafile)                      | `test_file_sync_seafile.py`           |
| Co-editing a document (OnlyOffice)                          | `test_coedition_onlyoffice.py`        |
| Message + starting a call from a room (Matrix/Element)     | `test_matrix_visio.py`                |
| Creating and notifying a task (Vikunja)                     | `test_task_vikunja.py`                |
| End-to-end SSO authentication (Keycloak), per component     | `test_sso_e2e.py`                     |
| Connectors (notification-hub, unified-search, presence-aggregator) as black boxes | `test_connectors.py` |

This suite is meant to live over the long term: it is replayed both
locally during development and automatically against every new ephemeral
staging environment before any decision to promote to production (study,
sections 4.4 and 4.5).

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r tests/integration/requirements.txt
```

## Running locally (against the dev environment)

First start the dev stack — `../../dev-cluster/deploy.sh` (k3d, reusing the
production Helm charts) plus `docker compose up -d` in
`dev-cluster/grommunio-dev/` for `grommunio-dev`, see
`../../dev-cluster/README.md` — then
run the tests from `tests/integration/` so that `pytest.ini` (markers,
timeouts) is picked up automatically. **No change is needed here** whether
the stack is running on k3d or (previously) fully on docker-compose: the
k3d cluster's NodePort exposure reuses the exact same `localhost:<port>`
addresses already used by `_platform_defaults.py`/`platform.yaml`:

```bash
cd tests/integration
pytest -m smoke                 # minimal critical scenarios, run these first
pytest                          # full suite
pytest -m "not slow"            # excludes the longer scenarios
pytest -m sso                   # only the parametrized end-to-end SSO scenario
pytest --html=report.html --self-contained-html   # generates the results report (study 4.5, line 797)
```

If `pytest.ini` is not picked up (running from the repo root), pass it
explicitly with `-c tests/integration/pytest.ini`:

```bash
pytest -c tests/integration/pytest.ini tests/integration
```

Tests fail cleanly (explicit message, no opaque traceback) if a service is
not started or not ready in time: see the `wait_for_service` fixture in
`conftest.py`, which polls each HTTP healthcheck with backoff before
running the business assertions.

## Environment variables

Every service URL has a default consistent with the local dev stack (k3d +
`dev-cluster/grommunio-dev/docker-compose.yml`), but can be overridden to
point the suite at another environment (local dev with remapped ports, or
the ephemeral staging environment - study 4.4/5.4).

These defaults are **not** hand-copied: they come from
`_platform_defaults.py`, generated from `../../platform.yaml` (repo root)
by `../../scripts/sync_platform.py` — the same source that drives the
ports in `dev-cluster/grommunio-dev/.env.example`, `dev-cluster/k3d-config.yaml`,
and the image tags in `infra/k8s/helm-values/`. To change a default port,
edit `platform.yaml`, never `_platform_defaults.py` or `conftest.py`
directly.

| Variable                     | Default                     | Component                          |
|-------------------------------|-----------------------------|----------------------------------|
| `KEYCLOAK_URL`                 | `http://localhost:8080`     | Keycloak                        |
| `KEYCLOAK_REALM`               | `libre365`                   | Keycloak (test realm)        |
| `GROMMUNIO_IMAP_HOST` / `_PORT`| `localhost` / `993`         | Grommunio (IMAP)                |
| `GROMMUNIO_SMTP_HOST` / `_PORT`| `localhost` / `587`         | Grommunio (SMTP)                |
| `SEAFILE_URL`                  | `http://localhost:8082`     | Seafile                         |
| `ONLYOFFICE_URL`               | `http://localhost:8083`     | OnlyOffice Document Server      |
| `ONLYOFFICE_JWT_SECRET`        | *(empty = JWT disabled)*    | OnlyOffice (config signing)|
| `MATRIX_URL`                   | `http://localhost:8008`     | Synapse (Matrix homeserver)     |
| `ELEMENT_URL`                  | `http://localhost:8081`     | Element (web client)            |
| `VIKUNJA_URL`                  | `http://localhost:3456`     | Vikunja                         |
| `GOKAPI_URL`                   | `http://localhost:53842`    | Gokapi                          |
| `MINIO_URL`                    | `http://localhost:9000`     | MinIO                           |
| `PEERTUBE_URL`                 | `http://localhost:9002`     | PeerTube                        |
| `CADDY_URL`                    | `http://localhost:10080`    | Caddy (reverse proxy)           |
| `NOTIFICATION_HUB_URL`         | `http://localhost:4001`     | notification-hub connector     |
| `UNIFIED_SEARCH_URL`           | `http://localhost:4002`     | unified-search connector       |
| `PRESENCE_AGGREGATOR_URL`      | `http://localhost:4003`     | presence-aggregator connector  |
| `ONLYOFFICE_MENTIONS_URL`      | `http://localhost:4004`     | onlyoffice-mentions connector  |
| `PEERTUBE_INGEST_URL`          | `http://localhost:4005`     | peertube-ingest connector      |
| `TEST_USER_USERNAME` / `_PASSWORD` / `_EMAIL` | `test.consultant` / `ChangeMe123!` / `test.consultant@libre365.test` | Shared test user (representative dataset, study 4.4) |
| `SERVICE_WAIT_TIMEOUT`         | `120` (seconds)            | Max wait time for Keycloak availability |

Some test-specific variables let you override credentials for a given
component when they differ from the generic test user
(`TEST_MAIL_ADDRESS`, `TEST_SEAFILE_USERNAME`, `TEST_VIKUNJA_USERNAME`,
`TEST_MATRIX_USERNAME`, etc. - see the corresponding fixture in each test
file).

## Integration into the ephemeral staging pipeline

This suite is designed to be invoked as-is by the CI/CD workflow that
orchestrates the cycle described in section 4.4 of the study: detecting a
new version -> deploying the ephemeral staging environment -> replaying
these scenarios -> results report conditioning promotion (section 4.5).
The corresponding GitHub Actions workflow (`.github/workflows/` directory,
maintained elsewhere in this repo) is responsible for:

1. deploying the ephemeral staging environment and exporting the
   environment variables above pointing at it;
2. installing `tests/integration/requirements.txt`;
3. running `pytest -m smoke` then the full suite, generating the HTML
   report (`--html=report.html --self-contained-html`) published as a run
   artifact;
4. conditioning promotion to production on the outcome of this report
   (success/failure per scenario), manual or automated depending on the
   criticality of the component concerned (study 4.5, line 797).

This suite has no knowledge of the CI/CD pipeline itself: it makes no
assumption about GitHub Actions beyond reading standard environment
variables, so it stays runnable both locally and, eventually, in another
orchestrator.

## Design notes

- **`test_sso_e2e.py`** covers Seafile, Vikunja, and Matrix/Synapse, each
  with its own function: unlike a generic bearer-token check, each of
  these three apps mints its own native credential after a real Keycloak
  login (a Seahub session cookie, a Vikunja JWT, a Matrix `access_token`),
  so the exact login/exchange steps genuinely differ per component and
  don't collapse into one shared, parametrized assertion — see that file's
  module docstring and `docs/oidc.md` for why an earlier, generic
  five-target version tested nothing real, and why Grommunio (no Keycloak
  client at all) and OnlyOffice/Novu (gated by Caddy `forward_auth`, not
  reachable through this suite's `base_urls`) aren't in it.
- **`wait_for_service`** (in `conftest.py`) is used by every test file
  before any business assertion, to absorb the slow startup of the
  docker-compose stack and fail with an explicit message
  (`ServiceNotReadyError`) rather than a raw connection-refused
  traceback.
- **`test_connectors.py`** mocks its sources with `responses` for
  `unified-search` (aggregation logic tested in isolation, independent of
  the data actually present in Seafile/Vikunja/Matrix), but queries
  `notification-hub` and `presence-aggregator` under real conditions:
  these are "black box" connector tests via direct HTTP call, with no
  knowledge of their internal implementation.

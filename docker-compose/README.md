# libre365 - docker-compose environment (development / test)

This environment corresponds to chapter 4.6 of the study
(`../office365-exit-study.md`): *"Development/test: reduced scale,
synthetic data."* It is **not** the production target, which relies on
Kubernetes (chapter 4.4) with high availability, horizontal scaling, and
Grommunio deployed as a Proxmox appliance VM (chapter 4.3). Here we favor
simple official images with ports mapped in the clear on `localhost`, for
local development and so that the `tests/integration/` suite (pytest,
against `http://localhost:<port>`) can run in CI.

## Startup

```bash
cd docker-compose
cp .env.example .env      # adjust if needed - default values = dev only
docker compose up -d
./scripts/wait-for-healthy.sh   # waits for all services to respond
```

To stop everything and remove the volumes (start from scratch):

```bash
docker compose down -v
```

## Versions and ports: single source

The image tags in this file and the ports block in `.env.example` (between
the `BEGIN/END GENERATED PORTS` markers) are generated from
[`../platform.yaml`](../platform.yaml) by `../scripts/sync_platform.py` -
this is also the source of the `image.tag`/`image.repository` values in
`infra/k8s/helm-values/` and of the default ports in `tests/integration/`.
**Do not modify a tag or a port directly here**: edit `platform.yaml`,
rerun the script, commit the diff. See the repository's root README for
details.

## Services and ports exposed on localhost

| Service | Image | Host port(s) | Default credentials (dev only) |
|---|---|---|---|
| `keycloak` | `quay.io/keycloak/keycloak:25.0.6` | 8080 | admin / `devonly-changeme-admin` (realm `master`); realm `libre365` automatically imported with client `libre365-integration-tests` / `devonly-changeme-client-secret` and user `testuser` / `devonly-changeme-testuser` |
| `postgres-keycloak` | `postgres:16.4-alpine` | 5433 | `keycloak` / `devonly-changeme-keycloak-db` |
| `synapse` | `matrixdotorg/synapse:v1.114.0` | 8008 (client), 8448 (federation) | open registration without verification (dev only) |
| `postgres-synapse` | `postgres:16.4-alpine` | 5434 | `synapse` / `devonly-changeme-synapse-db` |
| `element` | `vectorim/element-web:v1.11.86` | 8081 | points to `synapse` (to be entered at login) |
| `seafile` | `seafileltd/seafile-mc:11.0.13` | 8082 | `admin@libre365.localhost` / `devonly-changeme-seafile-admin` |
| `seafile-mysql` | `mariadb:10.11` | (internal only) | root / `devonly-changeme-seafile-mysql-root` |
| `onlyoffice-documentserver` | `onlyoffice/documentserver:8.2.2` | 8083 | JWT enabled (`devonly-changeme-onlyoffice-jwt`) |
| `postgres-onlyoffice` | `postgres:16.4-alpine` | 5435 | `onlyoffice` / `devonly-changeme-onlyoffice-db` |
| `vikunja` | `vikunja/vikunja:0.24.3` | 3456 | first account to be created via the API/UI (dev sqlite) |
| `gokapi` | `f0rc3/gokapi:v1.9.6` | 53842 | admin / `devonly-changeme-gokapi-admin` |
| `minio` | `minio/minio:RELEASE.2024-10-13T13-34-11Z` | 9000 (API), 9001 (console) | `minioadmin` / `devonly-changeme-minio-root` |
| `peertube` | `chocobozzz/peertube:v6.3.2-bookworm` | 9002 | first account created via the PeerTube CLI on first startup |
| `peertube-db` / `peertube-redis` | `postgres:16.4-alpine` / `redis:7.4-alpine` | (internal only) | `peertube` / `devonly-changeme-peertube-db` |
| `caddy` | `caddy:2-alpine` (pinned to `2.8.4-alpine`) | 10080 (HTTP), 10443 (HTTPS) | simple reverse proxy by sub-path, see `config/caddy/Caddyfile` |
| `novu-mock` | `node:20.17-alpine` (mock, see below) | 13000 | none (unauthenticated mock) |
| `grommunio-dev` | `grommunio/gromox-container:core-c9` | 8443 | admin / `devonly-changeme-grommunio-admin` - **dev/test only, see below** |
| `notification-hub` | build `../connectors/notification-hub` | 4001 | - |
| `unified-search` | build `../connectors/unified-search` | 4002 | - |
| `presence-aggregator` | build `../connectors/presence-aggregator` | 4003 | - |
| `onlyoffice-mentions` | build `../connectors/onlyoffice-mentions` | 4004 | - |
| `peertube-ingest` | build `../connectors/peertube-ingest` | 4005 | - |

All host ports are overridable via `.env` (see `.env.example`) in case of
conflict with services already running on the machine.

**None of the passwords listed above are meant for anything other than
local development / CI.** See `.env.example` for the complete list and the
explicit "dev only" reminder on each secret.

## Documented choices / simplifications vs. the production target

| Topic | Here (dev/test) | Production target (study) | Study section |
|---|---|---|---|
| Orchestrator | Docker Compose, single host | Kubernetes (Helm per building block), horizontal scaling and HA | 4.4 |
| Grommunio (mail/calendar) | `grommunio/gromox-container` container (image described as "not production-ready" by the vendor itself) | Dedicated Proxmox appliance VM, outside Kubernetes | 4.3 |
| Keycloak | Single instance, `start-dev` mode, no TLS | HA Keycloak cluster, TLS, dedicated secrets vault | 4.4, 4.5 |
| Synapse | Single monolithic instance, no "workers" mode | Synapse in workers mode for scalability/HA | 4.4 |
| OnlyOffice Document Server | Single instance | OnlyOffice Document Server cluster | 4.4 |
| Seafile | MariaDB database internal to the `seafile-mc` container, local disk storage | Dedicated/scalable architecture, storage backend to be sized for the targeted growth | 1.4, 4.4 |
| Notification center (Novu) | **Minimal HTTP mock** (`config/novu-mock/server.js`, official `node` image) exposing only `POST /v1/events/trigger` and `GET /health` | Full Novu stack (`novu/api` + `novu/worker` + `novu/ws` + MongoDB + Redis), see `https://docs.novu.co/self-hosting` | 2.1 |
| Application portal (menu/bell/search bar) | Caddy as a simple reverse proxy by sub-path, **without** the HTML injection plugin (not compiled into the official `caddy:2-alpine` image) - an example snippet is left as a comment in `config/caddy/Caddyfile` | Caddy + `caddy2-html-injection-plugin` (custom Caddy build via `xcaddy`) to inject the cross-cutting bar | 2.3 |
| Vikunja | Embedded sqlite database | Dedicated, sized Postgres/MySQL database | 1.6, 4.4 |
| Secrets | In cleartext in `.env` (explicit "dev only" values) | Dedicated vault (Vault or equivalent), never in cleartext in the repository | 4.5 |
| TLS / certificates | Absent (plain HTTP on localhost) | End-to-end TLS | 4.2, 4.4 |
| Backup/restore | Local Docker volumes, no backup strategy (disposable environment) | Application backups + Proxmox Backup Server snapshots | 4.7 |
| Environments | A single dev/test environment, shared between developers and CI | Three identical IaC environments (dev/test, staging, production), differing only in size and data | 4.6 |

### Why a mock for Novu?

The reference Novu stack (`novu/api` + `novu/worker` + `novu/ws` +
`novu/web`, plus MongoDB and Redis) is designed to be deployed as a full
product, not as a simple dependency that starts in a few seconds in CI. The
goal of this dev/test environment is to validate the **application
connectors** (`notification-hub`, `onlyoffice-mentions`,
`presence-aggregator`, study 2.1/2.7/2.8), not Novu itself: the mock
(`config/novu-mock/server.js`, served by the official `node:20-alpine`
image) exposes the same minimal API shape (`POST /v1/events/trigger`,
`GET /v1/events`, `GET /health`) that these connectors actually call, and
logs every event received to stdout for inspection during tests. A staging
environment with the real Novu still needs to be set up separately (chapter
4.4/5.5) the day the Novu integration itself needs to be tested end to end.

### Why Grommunio as a container when the study says appliance VM?

The study (4.3) is explicit: Grommunio is deployed as a Proxmox appliance VM
in production, precisely because its official container image
(`grommunio/gromox-container`) is presented by the vendor itself as not
production-ready (a bundle of nginx/Postfix/gromox/Redis/PHP-FPM under a
single supervisord). This docker-compose setup is a development/test
environment, not a replica of the production topology: including this
container lets the integration tests (sending/receiving mail, chapter 5.5)
run in CI without needing a Proxmox VM. The `grommunio-dev` service is named
and commented this way explicitly to avoid any confusion with the target
deployment mode.

## File structure

```
docker-compose/
  docker-compose.yml         Definition of all services
  .env.example               Environment variables (dev-only passwords)
  README.md                  This file
  config/
    keycloak/realm-export.json   "libre365" realm + test client imported at startup
    synapse/homeserver.yaml      Minimal Synapse configuration (dev/test)
    synapse/log.config           Synapse logging configuration (console output)
    caddy/Caddyfile               Reverse proxy by sub-path + reference to production HTML injection (2.3)
    novu-mock/server.js           Minimal HTTP mock replacing the full Novu stack
  scripts/
    wait-for-healthy.sh           Waits for all services to become available (CI)
```

## Usage in CI

```bash
cd docker-compose
cp .env.example .env
docker compose up -d --build
./scripts/wait-for-healthy.sh 600
cd ../tests/integration
pytest
```

`scripts/wait-for-healthy.sh` relies on the Docker `healthcheck`s declared
in `docker-compose.yml`; for `grommunio-dev`, which has no standard Docker
healthcheck documented by the vendor, it falls back to a simple TCP check on
the published port.

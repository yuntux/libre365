# libre365 - docker-compose environment (development / test)

This environment corresponds to chapter 4.6 of the study
(`../office365-exit-study.md`): *"Development/test: reduced scale,
synthetic data."* It is **not** the production target, which relies on
Kubernetes (chapter 4.4) with high availability, horizontal scaling, and
Grommunio deployed as a Proxmox appliance VM (chapter 4.3).

## Scope: only one service now runs here

As of the migration to the local k3d Kubernetes dev cluster, this
docker-compose file no longer hosts the whole dev/test tier. Every service
backed by a production Helm chart worth reusing - Keycloak, Synapse +
Element, Seafile, OnlyOffice Document Server, Vikunja, Gokapi, SeaweedFS,
PeerTube, Novu, Caddy, and the 5 in-house connectors (`notification-hub`,
`unified-search`, `presence-aggregator`, `onlyoffice-mentions`,
`peertube-ingest`) - now runs on a local k3d cluster that reuses the very
same `infra/k8s/helm-values/` / `infra/k8s/manifests/` used in production,
instead of a second, hand-maintained docker-compose definition per brick.
See **`../dev-cluster/README.md`** for that cluster's setup, startup, and
port-mapping details. Novu used to be an exception here too (a lightweight
HTTP mock, before the k3d dev cluster made deploying the real chart
practical) - see `../dev-cluster/README.md` for why the real chart is now
worth the extra resource footprint.

What remains in `docker-compose.yml` is `grommunio-dev`, the only service
with no Kubernetes/Helm equivalent worth deploying in the dev tier: the
study (4.3) targets a Proxmox appliance VM for production, never a
container - there is no Helm chart to reuse. It is kept here purely so the
mail/calendar integration tests (send/receive mail, study 5.5) can run in
CI without a Proxmox VM.

## Startup

```bash
cd docker-compose
cp .env.example .env      # adjust if needed - default values = dev only
docker compose up -d
./scripts/wait-for-healthy.sh   # waits for grommunio-dev to respond
```

To stop everything and remove the volumes (start from scratch):

```bash
docker compose down -v
```

## Versions and ports: single source

The image tag in this file and the ports block in `.env.example` (between
the `BEGIN/END GENERATED PORTS` markers) are generated from
[`../platform.yaml`](../platform.yaml) by `../scripts/sync_platform.py` -
this is also the source of the `image.tag`/`image.repository` values in
`infra/k8s/helm-values/` and of the default ports in `tests/integration/`
and in `../dev-cluster/`.
**Do not modify a tag or a port directly here**: edit `platform.yaml`,
rerun the script, commit the diff. See the repository's root README for
details.

## Service and port exposed on localhost

| Service | Image | Host port | Default credentials (dev only) |
|---|---|---|---|
| `grommunio-dev` | `grommunio/gromox-core:0.3-opensuse-leap-15-4` | 8443, 587, 993 | admin / `devonly-changeme-grommunio-admin` - **dev/test only, see below** |

The host port is overridable via `.env` (see `.env.example`) in case of
conflict with a service already running on the machine.

**None of the passwords listed above are meant for anything other than
local development / CI.** See `.env.example` for the complete list and the
explicit "dev only" reminder on each secret.

Every other service listed in the study (Keycloak, Synapse/Element,
Seafile, OnlyOffice, Vikunja, Gokapi, SeaweedFS, PeerTube, Novu, Caddy, and the
5 in-house connectors) is deployed and reachable through the k3d dev
cluster instead - see `../dev-cluster/README.md` for its own port mapping.

## Documented choices / simplifications vs. the production target

| Topic | Here (dev/test) | Production target (study) | Study section |
|---|---|---|---|
| Orchestrator (this file) | Docker Compose, single host, only `grommunio-dev` | Kubernetes (Helm per building block), horizontal scaling and HA | 4.4 |
| Orchestrator (everything else) | k3d local Kubernetes cluster reusing the production Helm charts/values, see `../dev-cluster/README.md` | Kubernetes (Helm per building block), horizontal scaling and HA | 4.4 |
| Grommunio (mail/calendar) | `grommunio/gromox-core` container (image described as "not production-ready" by the vendor itself) | Dedicated Proxmox appliance VM, outside Kubernetes | 4.3 |
| Notification center (Novu) | Real community chart (`Nova-Edge/novu-chart` - no official Novu chart exists, see `../infra/k8s/helm-values/novu.yaml`) on the k3d dev cluster, with a dev-hardening overlay (single replica per component) - see `../dev-cluster/README.md` | Full Novu stack (`novu/api` + `novu/worker` + `novu/ws` + MongoDB + Redis), see `https://docs.novu.co/self-hosting` | 2.1 |
| Secrets | In cleartext in `.env` (explicit "dev only" values) | Dedicated vault (Vault or equivalent), never in cleartext in the repository | 4.5 |
| TLS / certificates | Absent (plain HTTP on localhost) | End-to-end TLS | 4.2, 4.4 |
| Backup/restore | Local Docker volume, no backup strategy (disposable environment) | Application backups + Proxmox Backup Server snapshots | 4.7 |
| Environments | A single dev/test environment, shared between developers and CI | Three identical IaC environments (dev/test, staging, production), differing only in size and data | 4.6 |

### Why Grommunio as a container when the study says appliance VM?

The study (4.3) is explicit: Grommunio is deployed as a Proxmox appliance VM
in production, precisely because its official container image
(`grommunio/gromox-core`) is presented by the vendor itself as not
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
  docker-compose.yml         Definition of the one remaining service (grommunio-dev)
  .env.example               Environment variables (dev-only passwords) for that service
  README.md                  This file
  scripts/
    wait-for-healthy.sh           Waits for grommunio-dev to become available (CI)
```

The rest of the dev/test tier's configuration (Keycloak realm export,
Synapse homeserver config, Caddy Caddyfile, connector manifests, ...) now
lives under `../dev-cluster/` and `../infra/k8s/`, alongside the production
Helm values they share - see `../dev-cluster/README.md`.

## Usage in CI

```bash
cd docker-compose
cp .env.example .env
docker compose up -d
./scripts/wait-for-healthy.sh 600
```

The rest of the dev/test tier (everything the k3d cluster hosts) is brought
up separately - see `../dev-cluster/README.md` for its own CI startup
sequence - before running:

```bash
cd tests/integration
pytest
```

`scripts/wait-for-healthy.sh` relies on `docker compose config --services`
to discover what's running (only `grommunio-dev` now); since that service
has no standard Docker healthcheck documented by the vendor, it falls back
to a simple TCP check on the published port.

# libre365

Exit from Office 365 to a free/open-source stack — implementation of the study
[`office365-exit-study.md`](./office365-exit-study.md).

This repository materializes the architecture described in the study:
infrastructure as code, application building blocks, in-house integration
connectors, and a durable integration test suite. It is organized so that
each code directory refers explicitly to the chapter/section of the study
that motivates its existence — see [`docs/mapping.md`](./docs/mapping.md) for
the complete correspondence table.

## Architecture diagrams

### 1. Infrastructure layers

```mermaid
flowchart TD
    subgraph L0["Layer 0 — Virtualization (Proxmox)"]
        PVE["Proxmox VE"]
    end

    subgraph L1["Layer 1 — Provisioning (Terraform, ch. 4.2)"]
        TFK8S["Kubernetes nodes (VMs)"]
        TFVM["Grommunio VM"]
        TFNET["Proxmox network / storage"]
    end

    subgraph L2["Layer 2 — Orchestration (Kubernetes, ch. 4.3/4.4)"]
        HELM["Helm charts (infra/k8s/helm-values)"]
        RAW["Raw manifests (infra/k8s/manifests)"]
        CADDY["Caddy — sole public entry point + SSO gates"]
    end

    subgraph L3["Layer 3 — Application config (Ansible, ch. 4.5)"]
        ANSGROM["Grommunio (mail/GAL/Let's Encrypt cert)"]
        ANSKC["Keycloak realm (OIDC clients, MFA, locale)"]
        ANSHARD["OS hardening (fail2ban, SSH)"]
    end

    subgraph L4["Layer 4 — Secrets (ch. 4.5)"]
        BAO["OpenBao"]
        ESO["External Secrets Operator"]
    end

    subgraph L5["Layer 5 — DNS / certificates"]
        EDNS["external-dns (OVH)"]
        ACME["Automatic HTTPS (Caddy) / ACME certbot (Grommunio)"]
    end

    PVE --> TFK8S
    PVE --> TFVM
    PVE --> TFNET
    TFK8S --> HELM
    TFK8S --> RAW
    HELM --> CADDY
    RAW --> CADDY
    TFVM --> ANSGROM
    HELM --> ANSKC
    ANSKC -. OIDC clients .-> CADDY
    BAO --> ESO
    ESO --> HELM
    ESO --> RAW
    ANSGROM --> ACME
    CADDY --> ACME
    CADDY --> EDNS
    TFVM --> EDNS
```

### 2. Functional cartography

The functional domains identified by the study, independent of which
application covers each one (see diagram 3 for that mapping):

```mermaid
flowchart TB
    subgraph COMM["Communication"]
        F_MAIL["Mail & calendar"]
        F_CHAT["Instant messaging"]
        F_VISIO["Video conferencing"]
    end

    subgraph COLLAB["Document collaboration"]
        F_FILES["File storage & sync"]
        F_DOCS["Collaborative document editing"]
        F_TASKS["Task management"]
        F_SHARE["Secure external file sharing"]
    end

    subgraph MEDIA["Video platform"]
        F_VIDEO["Video hosting & streaming"]
    end

    subgraph PLATFORM["Portal & cross-cutting"]
        F_SSO["Identity & single sign-on"]
        F_PORTAL["Unified application portal"]
        F_NOTIF["Unified notifications"]
        F_SEARCH["Unified search"]
        F_PRESENCE["Unified presence"]
        F_GAL["Company directory (GAL)"]
        F_ROOM["Room booking"]
    end
```

### 3. Functional coverage — which application covers which function

```mermaid
flowchart LR
    subgraph Functions
        F_MAIL["Mail & calendar"]
        F_CHAT["Instant messaging"]
        F_VISIO["Video conferencing"]
        F_FILES["File storage & sync"]
        F_DOCS["Collaborative document editing"]
        F_TASKS["Task management"]
        F_SHARE["Secure external file sharing"]
        F_VIDEO["Video hosting & streaming"]
        F_SSO["Identity & single sign-on"]
        F_PORTAL["Unified application portal"]
        F_NOTIF["Unified notifications"]
        F_SEARCH["Unified search"]
        F_PRESENCE["Unified presence"]
        F_GAL["Company directory (GAL)"]
        F_ROOM["Room booking"]
    end

    subgraph Applications
        A_GROM["Grommunio"]
        A_MATRIX["Matrix/Synapse + Element Web"]
        A_MEET["LaSuite Meet + Element Call"]
        A_SEAFILE["Seafile"]
        A_OO["OnlyOffice Document Server"]
        A_VIKUNJA["Vikunja"]
        A_GOKAPI["Gokapi"]
        A_PEERTUBE["PeerTube + MinIO"]
        A_KC["Keycloak"]
        A_CADDY["Caddy (injected top bar)"]
        A_NOVU["Novu"]
        A_SEARCHC["unified-search connector"]
        A_PRESENCEC["presence-aggregator connector"]
    end

    F_MAIL --- A_GROM
    F_GAL --- A_GROM
    F_ROOM --- A_GROM
    F_CHAT --- A_MATRIX
    F_VISIO --- A_MEET
    F_FILES --- A_SEAFILE
    F_DOCS --- A_OO
    F_TASKS --- A_VIKUNJA
    F_SHARE --- A_GOKAPI
    F_VIDEO --- A_PEERTUBE
    F_SSO --- A_KC
    F_PORTAL --- A_CADDY
    F_NOTIF --- A_NOVU
    F_SEARCH --- A_SEARCHC
    F_PRESENCE --- A_PRESENCEC
```

### 4. Applications and their internal macro-objects

```mermaid
flowchart TB
    subgraph GROMMUNIO["Grommunio"]
        G1["Mailbox"]
        G2["Calendar event"]
        G3["Contact (GAL)"]
        G4["Meeting room"]
    end

    subgraph MATRIX["Matrix / Synapse / Element"]
        M1["Room"]
        M2["Message"]
        M3["User account"]
    end

    subgraph MEET["LaSuite Meet / Element Call"]
        V1["Meeting"]
        V2["Recording"]
    end

    subgraph SEAFILE["Seafile"]
        S1["Library"]
        S2["Folder"]
        S3["File"]
        S4["Share link"]
    end

    subgraph ONLYOFFICE["OnlyOffice"]
        O1["Document"]
        O2["Co-editing session"]
    end

    subgraph VIKUNJA["Vikunja"]
        T1["Project"]
        T2["Task"]
        T3["Label"]
    end

    subgraph GOKAPI["Gokapi"]
        K1["Encrypted upload"]
        K2["Share link"]
        K3["API key"]
    end

    subgraph PEERTUBE["PeerTube + MinIO"]
        P1["Channel"]
        P2["Video"]
        P3["Playlist"]
        P4["S3 bucket (MinIO)"]
    end

    subgraph KEYCLOAK["Keycloak"]
        KC1["Realm"]
        KC2["OIDC client"]
        KC3["User"]
        KC4["Role"]
    end

    subgraph NOVU["Novu"]
        N1["Notification"]
        N2["Subscriber"]
        N3["Template"]
    end

    subgraph CADDY["Caddy"]
        C1["Site (domain)"]
        C2["Route"]
        C3["Injected top bar"]
    end

    subgraph SHARED["Shared / cross-cutting objects (via connectors/)"]
        SH_SEARCH["Search index entry"]
        SH_NOTIF["Notification event"]
        SH_PRESENCE["Presence signal"]
    end

    %% Cross-application object relationships — not separate macro-objects
    %% of their own, but the same or a derived object crossing an app
    %% boundary through one of the connectors/ modules (docs/mapping.md).
    S3 -. "opened as (JWT, study 1.5)" .-> O1
    P4 -. "LiveKit Egress recordings (study 2.12)" .-> V2
    P4 -. "peertube-ingest connector (study 2.12)" .-> P2
    M1 -. "matrix-visio-widget connector (study 2.4)" .-> V1
    O2 -. "onlyoffice-mentions connector (study 2.7)" .-> SH_NOTIF
    S3 -. "unified-search connector (study 2.2)" .-> SH_SEARCH
    T2 -. "unified-search connector (study 2.2)" .-> SH_SEARCH
    M2 -. "unified-search connector (study 2.2)" .-> SH_SEARCH
    G2 -. "notification-hub connector (study 2.1)" .-> SH_NOTIF
    M2 -. "notification-hub connector (study 2.1)" .-> SH_NOTIF
    T2 -. "notification-hub connector (study 2.1)" .-> SH_NOTIF
    SH_NOTIF -.-> N1
    M3 -. "presence-aggregator connector (study 2.8)" .-> SH_PRESENCE
    G1 -. "presence-aggregator connector (study 2.8)" .-> SH_PRESENCE
    KC3 -. "OIDC identity, one account for every gated app" .-> M3
    KC3 -. "OIDC identity, one account for every gated app" .-> S3
    KC3 -. "OIDC identity, one account for every gated app" .-> T2
```

## Directory layout

```
infra/
  terraform/        Proxmox infrastructure IaC (VM, network) — chapter 4.2/4.5
  ansible/           Application configuration (Keycloak realms, Matrix domain, GAL...) — chapter 4.5
  k8s/
    helm-values/     Helm values per containerized building block — chapter 4.3/4.4
    manifests/       Raw manifests for building blocks without a suitable official chart
    helm-values/dev/ Dev-speed hardening overlays for the local k3d cluster
    manifests/connectors/, manifests/dev/  In-house connectors + dev-only Caddy for k3d
dev-cluster/         Local dev environment — chapter 4.6
  deploy.sh, redeploy.sh, destroy.sh  k3d cluster reusing infra/k8s/, "durcir en dev"
  grommunio-dev/     docker-compose recipe for the one brick k3d can't host
connectors/          In-house integration modules — chapter 2
tests/integration/   Durable integration test suite — chapter 5.5
.github/workflows/   CI/CD: CVE scanning, version monitoring, ephemeral staging — chapter 5
docs/                Supplementary technical documentation
```

## Guiding principle

The entire infrastructure must be rebuildable from this repository alone
(chapter 4.1): sizing parameters (replicas, resources) are driven by
variables to cover the 100 → 2000+ user growth path without rewrites, never
hard-coded.

## A single source for versions, ports, and domain names: `platform.yaml`

The development environment (`dev-cluster/`) and the production target
(`infra/k8s/`) describe the same building blocks through two different
mechanisms (Docker Hub image vs. Helm chart) for the one brick that stays
on docker-compose: without precaution, their version tags and their ports
silently drift apart from one another — this has actually already happened
once in this repository (the default ports in `tests/integration/` had
diverged from those in the dev environment). The same risk existed for
public domain names: `sso.libre365.example.org` alone used to be hardcoded
independently in 8 different files.

[`platform.yaml`](./platform.yaml) is now the only authorized source for
these values. It feeds:
- the image tag in `dev-cluster/grommunio-dev/docker-compose.yml` and the
  `FROM python:...` lines of `connectors/*/Dockerfile`;
- `image.repository`/`image.tag` in `infra/k8s/helm-values/*.yaml` (and the
  raw `image:` line of `infra/k8s/manifests/gokapi.yaml`);
- the generated ports block in `dev-cluster/grommunio-dev/.env.example` and
  `dev-cluster/k3d-config.yaml`;
- the default ports in `tests/integration/conftest.py`, via the generated
  file `tests/integration/_platform_defaults.py`;
- every public domain name (`domains:` section) across
  `infra/k8s/helm-values/*.yaml`, `infra/k8s/manifests/*.yaml`, and the
  Thunderbird extension manifest — see that section's comment for how
  changing `domains.base` (e.g. to a real bought domain before production)
  propagates everywhere on the next sync.

Workflow: edit `platform.yaml`, then:

```bash
pip install -r scripts/requirements.txt
python3 scripts/sync_platform.py          # applies the changes
python3 scripts/sync_platform.py --check  # used by CI: fails on drift
```

Never modify a tag or a port directly in a generated/patched file — it will
be overwritten (or, in CI, the drift will be detected and will block the pull
request) at the next synchronization.

## Quick start (development environment)

Most of the stack now runs on a local [k3d](https://k3d.io/) Kubernetes
cluster that reuses the production Helm charts (chapter 4.4), hardened for
dev speed — see [`dev-cluster/README.md`](./dev-cluster/README.md) for the
full rationale. Only `grommunio-dev` remains on docker-compose (no
production Kubernetes counterpart worth reusing — see that same README):

```bash
# grommunio-dev (docker-compose)
cd dev-cluster/grommunio-dev
cp .env.example .env
docker compose up -d
cd ../..

# everything else (k3d, reusing infra/k8s/)
./dev-cluster/deploy.sh
```

See [`dev-cluster/grommunio-dev/README.md`](./dev-cluster/grommunio-dev/README.md)
and [`dev-cluster/README.md`](./dev-cluster/README.md) for details on the
services started, their default credentials, and the fast
edit/rebuild/observe loop (`dev-cluster/redeploy.sh`).

## Integration tests

```bash
cd tests/integration
pip install -r requirements.txt
pytest -m smoke              # critical scenarios, against the dev environment (k3d + docker-compose)
```

See [`tests/integration/README.md`](./tests/integration/README.md).

## Status

This repository is an active work in progress: each building block/connector
carries its actual progress state (scaffold, functional, validated in
staging) in its own README rather than in a global status that would quickly
become stale. The open items identified by the study (end of the document
`office365-exit-study.md`) remain the reference for prioritizing upcoming
work.

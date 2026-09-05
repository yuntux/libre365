# Local dev cluster (k3d)

This directory holds the local Kubernetes dev environment for libre365: a
[k3d](https://k3d.io/) cluster that **reuses the production Helm
charts/values** (`../infra/k8s/helm-values/`, `../infra/k8s/manifests/`)
instead of a second, hand-maintained definition of the same 8 application
bricks in `docker-compose.yml`. Only `grommunio-dev` and `novu-mock` remain
on plain `docker-compose` (see `../docker-compose/README.md`) — everything
else now runs the same way it would in production: a Helm release per
brick, with the same chart, the same `<component>.yaml` base values.

## Why k3d instead of docker-compose for most of the stack

Running the actual Helm charts locally, rather than a parallel
docker-compose service definition per brick, closes the dev/prod parity gap
that a compose-only dev tier has: the same YAML that deploys to production
(`infra/k8s/helm-values/*.yaml`) is exercised on every local `helm upgrade`,
so a chart-level misconfiguration (wrong `image.repository`, a values key
that doesn't exist for that chart) is caught in dev, not discovered for the
first time at the ephemeral-staging or production step (study, chapter
4.4/5.4). The trade-off is a slower inner loop than plain
`docker compose up` — see "Dev-speed hardening" below for how this is
mitigated.

## Why grommunio-dev and novu-mock stay on docker-compose

- `grommunio-dev`: the study (4.3) targets a Proxmox VM appliance for
  production, never a Kubernetes container — there is no Helm chart to
  reuse, and the container image used here is explicitly a dev/test-only
  substitute (see its comment in `../docker-compose/docker-compose.yml`).
  Deploying it to k3d would test something that doesn't exist in production.
- `novu-mock`: a lightweight HTTP mock with no chart of its own — the real
  `novu` chart (`../infra/k8s/helm-values/novu.yaml`) deploys the full
  api/worker/ws/MongoDB/Redis stack, disproportionate for a mock whose only
  job is to expose the same `POST /v1/events/trigger` shape the connectors
  call.

Connectors that need them reach them through `host.k3d.internal` (k3d's
built-in DNS alias for the Docker host), on the same port docker-compose
exposes them on locally — see `infra/k8s/manifests/connectors/*.yaml`.

## Dev-speed hardening ("durcir en dev pour aller plus vite")

Reusing production charts as-is would mean provisioning production-shaped
HA topologies (multi-replica Keycloak with Infinispan clustering, Synapse
worker fleets, distributed MinIO) on a laptop, for every `helm upgrade`.
Two mechanisms keep the loop fast instead:

1. **`../infra/k8s/helm-values/dev/*.yaml`** — one overlay per brick,
   layered on top of the base `<component>.yaml` file (never on top of the
   `-100`/`-2000` production sizing overlays — the dev overlay replaces
   those, it isn't stacked with them). Each overlay sets `replicaCount: 1`
   (or the chart's clustering-off equivalent — e.g. Synapse's
   `synapse.workers.enabled: false`, MinIO's `mode: standalone`) and shrinks
   `resources.requests/limits` to whatever a laptop can boot quickly. See
   the header comment of each overlay file for exactly what was changed and
   why some keys (probe timing, autoscaling, PodDisruptionBudget) were
   deliberately left untouched: this sandboxed development environment has
   no network access to the third-party chart repositories
   (charts.bitnami.com, ananace.gitlab.io, etc.), so any key not already
   attested by this repo's own existing values files (the `-100`/`-2000`
   overlays) could not be verified before writing it — better to under-tune
   and document the gap than to guess a key that silently does nothing or
   breaks the chart.

2. **`redeploy.sh <name>`** — the actual inner loop. For a connector, this
   rebuilds its image, re-imports it into k3d (`k3d image import`, no
   registry round-trip), and force-deletes its pod
   (`kubectl delete pod --grace-period=0 --force`) so the Deployment
   recreates it immediately with the fresh image — skipping the graceful
   termination wait that's actually useful in production but only adds
   latency to a dev iteration. For a Helm-backed brick, it re-runs
   `helm upgrade` with the same base + dev overlay files and then does the
   same force-delete, rather than waiting for Helm's own (slower, HA-aware)
   rollout strategy on a single-replica dev pod.

## Exposing services on localhost: `lib-expose.sh`

Helm charts don't have a standard, cross-chart values key for "expose this
Service as this exact NodePort" — and this sandboxed environment has no way
to verify each third-party chart's real Service port layout ahead of time
(same network restriction as above). Rather than guess a
chart-specific values key per brick, `deploy.sh` calls
`lib-expose.sh`'s `expose_all_services`, which patches each release's
Service directly with `kubectl patch` — generic across every chart,
using only the Service name and `kubectl patch service ... -p
'{"spec":{"type":"NodePort"}}'` plus a JSON-patch `replace` on the specific
port index, matching the exact port numbers already declared in
`platform.yaml` and baked into `k3d-config.yaml`'s port-forwarding list (the
k3d load balancer forwards `hostPort:N` to `nodePort:N` on the cluster
nodes, so the two must match exactly).

The mapping of service name → port array index → desired nodePort lives in
`lib-expose.sh`'s `EXPOSE_MAP` and currently assumes each chart's HTTP port
is at array index 0 (index 1 for the two 2-port bricks: Synapse's
federation port, MinIO's console port). **This assumption has not been
verified against a live cluster** (no Docker daemon was available in the
sandboxed environment this migration was authored in) — if a chart's
Service instead lists a different port first (e.g. a metrics port), adjust
the index in `EXPOSE_MAP`; `lib-expose.sh`'s header comment explains exactly
what to check (`kubectl get service <name> -n libre365 -o yaml`).

## Usage

Prerequisites: `k3d`, `kubectl`, `helm`, `docker` on `PATH`.

```bash
# Start grommunio-dev + novu-mock (not part of the k3d cluster)
docker compose -f docker-compose/docker-compose.yml up -d

# Bring up the k3d cluster + every other brick + the 5 connectors
./dev-cluster/deploy.sh

# Fast inner loop after editing a connector's code
./dev-cluster/redeploy.sh unified-search

# Fast inner loop after editing a Helm values file
./dev-cluster/redeploy.sh keycloak

# Tear the cluster down entirely
./dev-cluster/destroy.sh
```

Once up, every service is reachable on `localhost:<port>` using the exact
same port numbers already used by docker-compose and by
`tests/integration/` (see `platform.yaml` — the NodePort range was widened
specifically so these existing numbers, like `3456` or `8008`, are valid
NodePorts without yet another remapping). This means
`tests/integration/` needs **no code change** to run against this cluster
instead of docker-compose — see `../tests/integration/README.md`.

## What's generated vs. hand-written here

- `k3d-config.yaml` is generated by `../scripts/sync_platform.py` from
  `platform.yaml`'s `dev_cluster` section (topology: server/agent count,
  NodePort range) and the same port tables that drive
  `docker-compose/.env.example` (port-forwarding list). Do not hand-edit it
  — see its own header comment.
- `deploy.sh`, `redeploy.sh`, `destroy.sh`, `lib-expose.sh` are hand-written
  orchestration, not generated.

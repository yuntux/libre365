# Local dev cluster (k3d)

This directory holds the local Kubernetes dev environment for libre365: a
[k3d](https://k3d.io/) cluster that **reuses the production Helm
charts/values** (`../infra/k8s/helm-values/`, `../infra/k8s/manifests/`)
instead of a second, hand-maintained definition of the same application
bricks in `docker-compose.yml`. Only `grommunio-dev` remains on plain
`docker-compose` (see `grommunio-dev/README.md`) — everything else,
Novu included, now runs the same way it would in production: a Helm
release per brick, with the same chart, the same `<component>.yaml` base
values.

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

## Why grommunio-dev stays on docker-compose

The study (4.3) targets a Proxmox VM appliance for production, never a
Kubernetes container — there is no Helm chart to reuse, and the container
image used here is explicitly a dev/test-only substitute (see its comment
in `grommunio-dev/docker-compose.yml`). Deploying it to k3d would test
something that doesn't exist in production.

## Novu runs the real chart here, not a mock

An earlier version of this dev tier used a lightweight HTTP mock for Novu
instead of the real `novu` chart (the reference stack — api/worker/ws/web +
MongoDB + Redis — felt disproportionate for a mock whose only job was to
expose the `POST /v1/events/trigger` shape the connectors call). That mock
only validated that the connectors call the right endpoint with the right
payload — it never exercised real Novu behavior (templates, delivery
retries, the actual notification center UI), which is a real gap given that
everything else on this cluster runs its actual production chart. Now that
the k3d cluster already pays the cost of running real Helm charts for every
other brick, the same trade-off applies to Novu: `helm upgrade --install
novu novu/novu -f novu.yaml -f dev/novu.yaml` (see `deploy.sh`), hardened
like every other brick (single replica per component instead of 2, see
`../infra/k8s/helm-values/dev/novu.yaml`). The connectors that call it
(`notification-hub`, `onlyoffice-mentions`) reach it through the in-cluster
Service DNS name like any other brick — see
`infra/k8s/manifests/connectors/*.yaml`, and the caveat there about that
Service's exact name not being verifiable from this sandboxed environment.

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

## Testing DNS record computation (external-dns, `inmemory` provider)

Production uses `external-dns` with the OVH provider to populate the real
DNS zone (`../infra/k8s/helm-values/external-dns.yaml`) — but this
sandboxed environment can't validate that against a real OVH account, and
neither can this dev cluster. What CAN be tested locally, and is: whether
external-dns correctly reads the Caddy Service's `external-dns.alpha.
kubernetes.io/hostname` annotation and computes the right record for every
domain in `platform.yaml`. `deploy.sh` installs external-dns here with
`../infra/k8s/helm-values/dev/external-dns.yaml`'s `inmemory` provider
override (external-dns's own built-in provider for exactly this — used the
same way in its upstream e2e tests) instead of the real OVH webhook, and
also applies the REAL `../infra/k8s/manifests/caddy.yaml` (not the
simplified `caddy-dev` used for actual dev routing) purely so its Service
carries the exact production annotation, rather than a hand-copied
duplicate that could silently drift from it — see `deploy.sh`'s own
comment on that step for why its pods are expected to never become Ready
(harmless, only the Service/annotation matters here).

```bash
./dev-cluster/check-external-dns.sh
```

This reads every domain from `platform.yaml` (skipping `registry`/`livekit`,
which have no Caddyfile site block by design — see `scripts/sync_platform.py`'s
`DOMAINS_WITHOUT_CADDY_SITE`) and greps external-dns's logs for each one,
failing loudly if any is missing. It validates the annotation-parsing/
record-computation logic end to end. It does **not** validate that OVH's
API would actually apply the change — that can only be checked against a
real OVH account in an actual deployment (study, chapter 5.4).

## Testing Keycloak SSO/OIDC end-to-end, including the OnlyOffice/Novu gates

Discovered while trying to add a live test for the OnlyOffice/Novu
oauth2-proxy gates (study 1.7, see `../docs/oidc.md`): `caddy-dev`'s
Caddyfile used to be a completely different, hand-written, path-based
portal (`/office/`, `/tasks/`, ...) with none of production's domain-based
site blocks or SSO gates at all — nothing in this dev tier could exercise
any Keycloak OIDC flow the way a real browser reaching
`sso.libre365.example.org` actually would.

Every OIDC config in this repo — Keycloak's own `KC_HOSTNAME`, each app's
issuer/authurl, both oauth2-proxy gates' `oidc-issuer-url` — uses the real
public domain (`platform.yaml`'s `domains.base`) unconditionally, the exact
same value in production and here. Rather than add a second, dev-only set
of hard-coded URLs (which is precisely the kind of drift `platform.yaml`
exists to eliminate), this dev tier now makes that same domain actually
resolve and route correctly here too:

1. `infra/k8s/manifests/dev/caddy.yaml`'s Caddyfile is **generated** by
   `scripts/sync_platform.py`'s `compute_dev_caddy_change()` from the real,
   production `../infra/k8s/manifests/caddy.yaml` — domain-based site
   blocks, `forward_auth`/`route` SSO gates and all. Only two things are
   stripped, because this sandboxed/local environment genuinely cannot run
   them: `html_inject` (needs a custom xcaddy-built plugin unavailable
   here — dev loses the injected top bar, not the routing) and automatic
   HTTPS (forced to plain `http://` — there is no real public DNS to get a
   certificate for from a local cluster).
2. `deploy.sh`'s step 6/11 calls `provision-keycloak-dev.sh` (right after
   exposing Keycloak's own NodePort), which runs the `keycloak_realm`
   Ansible role against this cluster's Keycloak with
   `keycloak_realm_test_user_enabled=true` — creating the realm, every
   OIDC client, and the representative test user (study 4.4, point 2)
   that `tests/integration/`'s `test_user` fixture and the ephemeral
   staging workflow both log in as. This has to happen before the
   oauth2-proxy releases (step 9/11 below) are installed, since both fetch
   their OIDC client from this realm at startup and fail if it doesn't
   exist yet.
3. Step 8/11 calls `patch-coredns-hosts.sh`, which patches this cluster's
   CoreDNS with a `hosts` block resolving every `platform.yaml` domain to
   `caddy-dev`'s in-cluster ClusterIP — so pods (Keycloak, oauth2-proxy,
   every app doing its own server-side OIDC discovery/token exchange)
   resolve the real domain to the real dev Caddy, exactly like production
   DNS resolves it to the real production Caddy. See that script's header
   for its one unverified assumption (k3d's default Corefile layout) —
   inspect `kubectl get configmap coredns -n kube-system -o yaml` if it
   fails.
4. Step 9/11 installs the two `oauth2-proxy-*` releases only after that DNS
   patch, since both fetch their OIDC discovery document at startup and
   would otherwise fail to resolve the realm's domain at all.
5. `tests/integration/conftest.py`'s `DomainRoutingAdapter` gives the test
   suite itself (running outside the cluster) the same resolution: it
   rewrites any request to `*.<domains.base>` to actually connect to
   `caddy-dev`'s exposed NodePort (`CADDY_HTTP_PORT`, matching
   `lib-expose.sh`'s `[caddy-dev:0]=10080`), while keeping the original
   `Host` header intact for Caddy's own virtual-host routing — see that
   class's docstring, self-tested against a throwaway local HTTP server in
   `scripts/test_sync_platform.py`-style offline tests (no live cluster
   needed to verify the routing logic itself).

`tests/integration/test_sso_e2e.py` uses this to drive Seafile/Vikunja/
Matrix/OnlyOffice/Novu's real Keycloak login flows exactly as a browser
reaching the public domain would, rather than hitting each app's own
directly-exposed port (which bypasses Caddy, and therefore the SSO gates,
entirely).

## Testing secret propagation (OpenBao + External Secrets Operator)

Production populates every `existingSecret:`/`secretKeyRef:` referenced
across `../infra/k8s/helm-values/*.yaml` from OpenBao
(`../infra/k8s/helm-values/openbao.yaml`, study 4.5) via External Secrets
Operator (ESO) — see `../infra/k8s/manifests/external-secrets.yaml` for
the full list and their confidence grading (some secretKey names are
declared explicitly elsewhere in this repo, others follow a well-known
Bitnami/official-chart convention not independently re-verified from this
sandboxed environment). What's testable locally, and is: does ESO actually
read a value written to OpenBao and turn it into the right Kubernetes
Secret/key? `deploy.sh` installs OpenBao here in its own **dev-server
mode** (`../infra/k8s/helm-values/dev/openbao.yaml` — single in-memory
instance, fixed well-known root token, auto-unsealed - never use this
outside a throwaway dev cluster) wired to ESO via a dev-only
`ClusterSecretStore` using that fixed token
(`../infra/k8s/manifests/dev/external-secrets-store.yaml` — production
uses OpenBao's Kubernetes auth method instead, see
`infra/ansible/roles/openbao_config/README.md`), then runs
`seed-openbao-dev-secrets.sh` to write dev-only dummy values at the exact
paths every chart below expects (without this, Keycloak/the
Postgres-backed charts would just sit waiting for a Secret that never
appears).

```bash
./dev-cluster/check-external-secrets.sh
```

This checks that every expected Secret/key from
`../infra/k8s/manifests/external-secrets.yaml` was actually created,
failing loudly (and dumping the `ExternalSecret` resources' status) if
any is missing. It validates the OpenBao → ESO → Kubernetes Secret path
end to end. It does **not** validate the [CONVENTION]/[UNCERTAIN]
secretKey names against the real third-party charts themselves — only
deploying that exact chart for real can confirm those.

## Usage

Prerequisites: `k3d`, `kubectl`, `helm`, `docker` on `PATH`.

```bash
# Start grommunio-dev (not part of the k3d cluster)
docker compose -f dev-cluster/grommunio-dev/docker-compose.yml up -d

# Bring up the k3d cluster + every other brick (Novu included) + the 5 connectors
./dev-cluster/deploy.sh

# Verify external-dns reads the Caddy Service's annotation correctly
# (inmemory provider - no real DNS touched, see "Testing DNS record
# computation" above)
./dev-cluster/check-external-dns.sh

# Verify OpenBao + External Secrets Operator actually propagate secrets
# (dev-mode OpenBao, no real vault touched, see "Testing secret
# propagation" above)
./dev-cluster/check-external-secrets.sh

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
  `grommunio-dev/.env.example` (port-forwarding list). Do not hand-edit it
  — see its own header comment.
- `../infra/k8s/manifests/dev/caddy.yaml`'s `data.Caddyfile` key is
  generated by `../scripts/sync_platform.py`'s `compute_dev_caddy_change()`
  from the real, production `../infra/k8s/manifests/caddy.yaml` — see
  "Testing Keycloak SSO/OIDC end-to-end" above. That file's
  Deployment/Service stay hand-written.
- `deploy.sh`, `redeploy.sh`, `destroy.sh`, `lib-expose.sh`,
  `check-external-dns.sh`, `seed-openbao-dev-secrets.sh`,
  `check-external-secrets.sh`, `patch-coredns-hosts.sh`,
  `provision-keycloak-dev.sh` are hand-written orchestration, not
  generated.

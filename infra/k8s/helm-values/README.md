# Helm values — libre365

Kubernetes configuration for the containerized components chosen by the study
(`office365-exit-study.md`, chapter 4.3). Grommunio is **out of scope** for this
directory: deployed as a Proxmox appliance VM, see chapter 4.3 and
`infra/terraform/` / `infra/ansible/` (managed by another team).

## Public entry point: Caddy, not each chart's own Ingress

Every chart below ships its own native Kubernetes `ingress:` block — but
each one is set to **`enabled: false`**
here. No Ingress Controller (nginx-ingress, Traefik...) is deployed anywhere
in this repository to satisfy those objects, and running one just to
duplicate routing that already exists elsewhere would add an unused
mechanism. `../manifests/caddy.yaml` is the sole public HTTP(S) entry point
for every service in `platform.yaml`'s `domains` list (its Caddyfile
reverse-proxies directly to each chart's Service), and needs no
cert-manager either: Caddy obtains and renews TLS certificates
automatically for any bare-domain site address, a built-in feature
("Automatic HTTPS"). See `../manifests/caddy.yaml`'s header comment for the
full rationale, including how Matrix federation (a separate port, 8448) and
the two SeaweedFS endpoints (S3 API + Admin UI) are covered too.

The `hosts`/`hostname`/`tls` fields in each disabled `ingress:` block are
kept as documentation of where that chart expects to be reached (and stay
in sync with `platform.yaml`'s `domains` via the same `sync_platform.py`
patcher, see below) — re-enabling one instead of routing through Caddy
would first need a real Ingress Controller deployed, which is out of scope
today.

## DNS zone population: external-dns

Caddy's Automatic HTTPS (above) only OBTAINS certificates once a domain
already resolves to it — it does not create the A/AAAA records themselves.
`external-dns.yaml` closes that gap: it watches the Caddy Service
(`../manifests/caddy.yaml`, `sources: [service]`, not `ingress`, since none
of those are active) for its `external-dns.alpha.kubernetes.io/hostname`
annotation and creates/maintains the matching DNS records via the OVH
provider (a DNS-zone/registrar choice — chosen for the same
sovereignty/European-provider reasoning the study applies elsewhere — that
is independent of compute staying self-hosted on Proxmox). **Read that
file's header comment before deploying**: OVH has no built-in external-dns
provider (unlike AWS/Cloudflare/Google) — support goes through the
pluggable webhook-provider mechanism, and the exact webhook image/config
could not be verified from the sandboxed environment this was authored in.

## Image versions: single source of truth

The `image.repository`/`image.tag` fields in this directory (and the raw
`image:` line of `../manifests/gokapi.yaml`) are generated from
`../../../platform.yaml` by `../../../scripts/sync_platform.py` — the same
source as the tag used by `../../../dev-cluster/grommunio-dev/`. **Do not edit an image tag or
repository directly in a file in this folder**: the next `sync_platform.py`
run would overwrite it, and CI (`platform-drift-check`) detects any manual
edit that hasn't been resynchronized. To change a version, edit
`platform.yaml` then run:

```bash
pip install -r ../../../scripts/requirements.txt
python3 ../../../scripts/sync_platform.py
```

## Domain names: also a single source of truth

Every `sso.libre365.example.org`-style hostname in this directory (Ingress
hostnames/TLS, OIDC issuer/endpoint URLs, `LIVEKIT_URL`, etc.) is generated
the same way, from `platform.yaml`'s `domains:` section — **do not edit a
domain directly in a file in this folder** for the same reason as image
tags above. To change the shared base domain (e.g. before pointing
production at a real bought domain instead of the `example.org`
placeholder), edit `platform.yaml`'s `domains.base` and re-run
`sync_platform.py`.

## Naming convention: `-100` / `-2000` overlays

For components whose sizing really varies with scale (Synapse, OnlyOffice —
see the study), the convention adopted is:

- `<component>.yaml`: common values, independent of scale (image, OIDC
  integrations, feature toggles, functional options). Contains **no**
  `replicaCount`/`resources` value specific to a scale.
- `<component>-100.yaml`: sizing overlay for the initial ~100 users target.
- `<component>-2000.yaml`: sizing overlay for the ~2000 users growth target.

Both files are passed in cascade to `helm`, the second one (`-100` or
`-2000`) overriding the sizing keys:

```bash
helm upgrade --install synapse ananace-charts/matrix-synapse \
  -n libre365 -f synapse.yaml -f synapse-100.yaml
```

For components whose sizing does not really depend on the number of users
but on another factor (data volume for Seafile, API usage for Vikunja — see
study 1.4 L.136 and 1.6 L.229), a single `<component>.yaml` file suffices;
the choice is documented at the top of each file concerned.

Keycloak used to follow the `-100`/`-2000` Helm-overlay convention too, but
is no longer a Helm release at all (see `../manifests/keycloak.yaml`'s
header) — its `instances`/`resources` sizing now lives directly in that one
manifest, with a comment on what to change for the ~2000-user target
instead of a separate cascade file.

## Helm charts used

| Component | Chart | Helm repo |
|---|---|---|
| Synapse (Matrix) | `matrix-synapse` (ananace-chart) | https://ananace.gitlab.io/charts |
| Element Web | `element-web` (ananace-chart) | https://ananace.gitlab.io/charts |
| Element Call | no official chart — "chart-like" values manifest, to be adapted as raw | — |
| Visio (LaSuite Meet) | `suitenumerique/meet` if published, otherwise raw manifest | https://github.com/suitenumerique/meet |
| Seafile | chart `ce` published by `haiwen` (Seafile's own GitHub org) | https://haiwen.github.io/seafile-helm-chart/repo ([UNCERTAIN]: found via that org's own README, but this sandboxed environment's egress proxy blocks `*.github.io` outright, so the index.yaml itself was never independently fetched - the previous URL here, `seafile-charts.github.io/seafile-charts`, was fabricated and 404s) |
| OnlyOffice Document Server | chart `docs` published by ONLYOFFICE itself | https://download.onlyoffice.com/charts/stable ([UNCERTAIN], same reason as Seafile above - found via github.com/ONLYOFFICE/Kubernetes-Docs' own README, egress-blocked from independently fetching the index.yaml; the previous URL here, `onlyoffice.github.io/docs-cloud-chart`, was fabricated and 404s) |
| Vikunja | no official chart confirmed to exist (see `vikunja.yaml`'s header) — "chart-like" values manifest, to be adapted to a generic app-template chart or a raw manifest | — |
| Keycloak | no Helm chart — official Keycloak Operator CR (`../manifests/keycloak.yaml`), `bitnami/postgresql` for its now-standalone database | Operator: raw kubectl apply (see that file's header); Postgres: https://charts.bitnami.com/bitnami |
| Gokapi | no official chart — raw manifest (`../manifests/gokapi.yaml`) | — |
| SeaweedFS | `seaweedfs` (official, in-tree chart) | https://seaweedfs.github.io/seaweedfs/helm |
| PeerTube | no official chart (PeerTube itself publishes none) — community chart `peertube` (`zendet/peertube-helm`, 7 GitHub stars) | https://zendet.github.io/peertube-helm/ ([UNCERTAIN], same egress-blocked-from-github.io reason as Seafile/OnlyOffice above; the previous URL here, `peertube-helm.github.io/charts`, was fabricated and 404s) |
| Caddy | no dedicated chart — raw manifest (`../manifests/caddy.yaml`), custom xcaddy image with an HTML injection plugin | — |
| Novu | no official chart exists at all (verified: `novuhq/helm-charts` doesn't exist, its gh-pages 404s) — community chart `Nova-Edge/novu-chart`, low-adoption, explicitly not officially supported by the Novu team | OCI artifact, not an index.yaml repo: `oci://ghcr.io/nova-edge/charts/novu`, pinned by `--version` (see `novu.yaml`'s own header) |
| external-dns | `external-dns` (kubernetes-sigs) | https://kubernetes-sigs.github.io/external-dns/ |
| OpenBao | `openbao` (OpenBao project) | https://openbao.github.io/openbao-helm/ (not independently verified from this sandbox — see `openbao.yaml`'s own header comment) |
| External Secrets Operator | `external-secrets` (external-secrets project, CNCF) | https://charts.external-secrets.io |

Charts marked "[UNCERTAIN]" (Seafile, OnlyOffice, PeerTube) had their
`helm repo add` URL found via the publisher's own current GitHub README
(fetched directly, which works), but the actual `index.yaml` behind that
URL could not be independently fetched from this sandboxed environment
(its egress proxy blocks `*.github.io` and most custom domains outright,
`EGRESS_BLOCKED` on every attempt) - confirm on first real run, same as
Novu. This replaces an earlier, weaker version of this same caveat: the 3
URLs previously here were outright fabricated (never real at any point,
not just "unverified") and 404 immediately - found by actually running
`dev-cluster/deploy.sh`. `external-dns.yaml`'s OVH webhook-provider image
carries a similar caveat — see that file's header comment.

## Typical deployment command

```bash
# Add the Helm repos (once)
helm repo add ananace-charts https://ananace.gitlab.io/charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add seaweedfs https://seaweedfs.github.io/seaweedfs/helm
helm repo add external-dns https://kubernetes-sigs.github.io/external-dns/
helm repo add seafile-charts https://haiwen.github.io/seafile-helm-chart/repo
helm repo add onlyoffice https://download.onlyoffice.com/charts/stable
helm repo add peertube-helm https://zendet.github.io/peertube-helm/
helm repo update
# Novu: no `helm repo add` - see its table row above, it's an OCI artifact.

# Namespace
kubectl apply -f ../manifests/namespace.yaml

# Component with no scale overlay
helm upgrade --install seafile seafile-charts/ce -n libre365 -f seafile.yaml
helm upgrade --install seaweedfs seaweedfs/seaweedfs -n libre365 -f seaweedfs.yaml
helm upgrade --install peertube peertube-helm/peertube -n libre365 -f peertube.yaml
helm upgrade --install novu oci://ghcr.io/nova-edge/charts/novu --version 0.2.1 -n libre365 -f novu.yaml
helm upgrade --install element-web ananace-charts/element-web -n libre365 -f element-web.yaml
helm upgrade --install keycloak-postgres bitnami/postgresql -n libre365 -f keycloak-postgres.yaml

# Component with a scale overlay (example: 100-user target)
helm upgrade --install synapse ananace-charts/matrix-synapse -n libre365 -f synapse.yaml -f synapse-100.yaml
helm upgrade --install onlyoffice onlyoffice/docs -n libre365 -f onlyoffice.yaml -f onlyoffice-100.yaml

# Keycloak: Operator CR, not a Helm release - see ../manifests/keycloak.yaml's
# header for the operator install command (kubectl apply, cluster-scoped)
kubectl apply -f ../manifests/keycloak.yaml

# Raw manifests (no chart)
kubectl apply -f ../manifests/gokapi.yaml
kubectl apply -f ../manifests/caddy-injection.yaml
kubectl apply -f ../manifests/caddy.yaml

# DNS zone population (see "DNS zone population" above - confirm the OVH
# webhook image/config first)
helm upgrade --install external-dns external-dns/external-dns -n libre365 -f external-dns.yaml

# Secrets management (see "Secrets" below) - deploy BEFORE the charts
# above that reference an existingSecret, then run
# infra/ansible/playbooks/openbao-config.yml once OpenBao is initialized
# and unsealed
helm repo add openbao https://openbao.github.io/openbao-helm/
helm repo add external-secrets https://charts.external-secrets.io
helm upgrade --install openbao openbao/openbao -n libre365 -f openbao.yaml
helm upgrade --install external-secrets external-secrets/external-secrets -n libre365 -f external-secrets.yaml
kubectl apply -f ../manifests/external-secrets-store.yaml
kubectl apply -f ../manifests/external-secrets.yaml
```

Moving from 100 to 2000 users (and beyond, chapter 4.1 of the study)
translates into simply swapping the overlay (`-100.yaml` -> `-2000.yaml`)
followed by a new `helm upgrade`, with no rewrite of the infrastructure
definition itself.

## Secrets

No secret in plaintext in this directory (study chapter 4.5 — secrets
management externalized to a dedicated vault). All `existingSecret` /
`secretKeyRef` references in these values files point to Kubernetes
Secrets populated by External Secrets Operator from OpenBao — see
`openbao.yaml`, `external-secrets.yaml`, `../manifests/external-secrets-
store.yaml`, and `../manifests/external-secrets.yaml` (one `ExternalSecret`
per reference in this directory, graded by confidence — read its header
comment before writing a value into OpenBao). Bootstrapping OpenBao's
Kubernetes auth method for this is `infra/ansible/roles/openbao_config`'s
job (`infra/ansible/playbooks/openbao-config.yml`) — see that role's
README for the prerequisites (OpenBao must already be initialized and
unsealed, a manual step deliberately not automated anywhere in this
repository).

## Out of scope for this directory

- Grommunio: Proxmox appliance VM (study 4.3), see `infra/terraform/` and
  `infra/ansible/`.
- LiveKit (SFU backend shared by Visio and Element Call, study 1.3
  L.106-107): the `visio-meet.yaml` and `element-call.yaml` files reference
  a shared LiveKit endpoint (`livekit.libre365.svc.cluster.local`) but do
  not define the LiveKit deployment itself, not explicitly listed in the
  scope of this project.
- Application connectors (notification center, unified search, presence
  aggregator, Seafile/OnlyOffice integrations, etc., chapter 2 of the
  study): see `connectors/`, managed by another team.

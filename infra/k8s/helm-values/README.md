# Helm values — libre365

Kubernetes configuration for the containerized components chosen by the study
(`office365-exit-study.md`, chapter 4.3). Grommunio is **out of scope** for this
directory: deployed as a Proxmox appliance VM, see chapter 4.3 and
`infra/terraform/` / `infra/ansible/` (managed by another team).

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

## Naming convention: `-100` / `-2000` overlays

For components whose sizing really varies with scale (Synapse, OnlyOffice,
Keycloak — see the study), the convention adopted is:

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

## Helm charts used

| Component | Chart | Helm repo |
|---|---|---|
| Synapse (Matrix) | `matrix-synapse` (ananace-chart) | https://ananace.gitlab.io/charts |
| Element Web | `matrix-element-web` (ananace-chart) | https://ananace.gitlab.io/charts |
| Element Call | no official chart — "chart-like" values manifest, to be adapted as raw | — |
| Visio (LaSuite Meet) | `suitenumerique/meet` if published, otherwise raw manifest | https://github.com/suitenumerique/meet |
| Seafile | community chart `seafile-ce` | https://seafile-charts.github.io/seafile-charts (to be confirmed) |
| OnlyOffice Document Server | community chart `docs-cloud` | https://onlyoffice.github.io/docs-cloud-chart (to be confirmed) |
| Vikunja | `vikunja` (go-vikunja/helm-charts) | https://vikunja.github.io/helm-charts |
| Keycloak | `keycloak` (Bitnami) | https://charts.bitnami.com/bitnami |
| Gokapi | no official chart — raw manifest (`../manifests/gokapi.yaml`) | — |
| MinIO | `minio` (official MinIO chart) | https://charts.min.io/ |
| PeerTube | community chart `peertube` | https://peertube-helm.github.io/charts (to be confirmed) |
| Caddy | no dedicated chart — raw manifest (`../manifests/caddy.yaml`), custom xcaddy image with an HTML injection plugin | — |
| Novu | `novu` (official Novu chart) | https://novuhq.github.io/helm-charts |

Charts marked "to be confirmed" had no single identified official source at
the time of writing (August/September 2026): several community forks exist
depending on the component. Systematic fallback planned to a raw manifest
derived from the official Docker image if no maintained chart is available
at the time of actual deployment.

## Typical deployment command

```bash
# Add the Helm repos (once)
helm repo add ananace-charts https://ananace.gitlab.io/charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add minio https://charts.min.io/
helm repo add novu https://novuhq.github.io/helm-charts
helm repo add vikunja https://vikunja.github.io/helm-charts
helm repo update

# Namespace
kubectl apply -f ../manifests/namespace.yaml

# Component with no scale overlay
helm upgrade --install vikunja vikunja/vikunja -n libre365 -f vikunja.yaml
helm upgrade --install seafile seafile-charts/seafile-ce -n libre365 -f seafile.yaml
helm upgrade --install minio minio/minio -n libre365 -f minio.yaml
helm upgrade --install peertube peertube-helm/peertube -n libre365 -f peertube.yaml
helm upgrade --install novu novu/novu -n libre365 -f novu.yaml
helm upgrade --install element-web ananace-charts/matrix-element-web -n libre365 -f element-web.yaml

# Component with a scale overlay (example: 100-user target)
helm upgrade --install synapse ananace-charts/matrix-synapse -n libre365 -f synapse.yaml -f synapse-100.yaml
helm upgrade --install onlyoffice onlyoffice/docs-cloud -n libre365 -f onlyoffice.yaml -f onlyoffice-100.yaml
helm upgrade --install keycloak bitnami/keycloak -n libre365 -f keycloak.yaml -f keycloak-100.yaml

# Raw manifests (no chart)
kubectl apply -f ../manifests/gokapi.yaml
kubectl apply -f ../manifests/caddy-injection.yaml
kubectl apply -f ../manifests/caddy.yaml
```

Moving from 100 to 2000 users (and beyond, chapter 4.1 of the study)
translates into simply swapping the overlay (`-100.yaml` -> `-2000.yaml`)
followed by a new `helm upgrade`, with no rewrite of the infrastructure
definition itself.

## Secrets

No secret in plaintext in this directory (study chapter 4.5 — secrets
management externalized to a dedicated vault, e.g. Vault). All
`existingSecret` / `secretKeyRef` references in these values files point to
Kubernetes Secrets provisioned outside this repository (Ansible/Vault, see
`infra/ansible/`, managed by another team).

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

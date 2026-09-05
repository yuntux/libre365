# Study ↔ code correspondence table

Each row refers to the section of `office365-exit-study.md` that motivates
the corresponding code. Keep it up to date with every new building
block/connector.

| Building block / topic | Study section | Location in the repository |
|---|---|---|
| Grommunio (mail/calendar) | 1.1 | `infra/terraform/grommunio.tf`, `infra/ansible/playbooks/grommunio.yml` |
| Matrix / Synapse / Element | 1.2 | `infra/k8s/helm-values/synapse.yaml`, `infra/ansible/playbooks/matrix.yml` |
| Video conferencing (DINUM/LiveKit) + Element Call | 1.3 | `infra/k8s/helm-values/visio.yaml`, `infra/k8s/helm-values/element-call.yaml` |
| Seafile | 1.4 | `infra/k8s/helm-values/seafile.yaml` |
| OnlyOffice Document Server | 1.5 | `infra/k8s/helm-values/onlyoffice.yaml` |
| Vikunja | 1.6 | `infra/k8s/helm-values/vikunja.yaml` |
| Keycloak (SSO/MFA) | 1.7 | `infra/k8s/helm-values/keycloak.yaml`, `infra/ansible/playbooks/keycloak-realm.yml`, `connectors/keycloak-otp-spi/` |
| Gokapi | 1.8 | `infra/k8s/helm-values/gokapi.yaml` |
| Thunderbird / Apple Mail (client) | 1.9 | `docs/clients.md` (reference configuration, no server-side code) |
| Unified notification center (Novu) | 2.1 | `infra/k8s/helm-values/novu.yaml`, `connectors/notification-hub/` |
| Unified search | 2.2 | `connectors/unified-search/` |
| Portal / Caddy HTML injection | 2.3 | `infra/k8s/helm-values/caddy.yaml`, `infra/k8s/manifests/caddy-injection.yaml` |
| Chat/video continuity (Matrix ↔ video conferencing widget) | 2.4 | `connectors/matrix-visio-widget/` |
| Native application onboarding | 2.5 | `docs/onboarding/` |
| Disabling OnlyOffice chat | 2.6 | `infra/k8s/helm-values/onlyoffice.yaml` (`document.permissions.chat`) |
| OnlyOffice mentions → notifications | 2.7 | `connectors/onlyoffice-mentions/` |
| Unified presence | 2.8 | `connectors/presence-aggregator/` |
| Video conferencing button from Grommunio | 2.9 | `docs/visio-invite.md` (reusable link, no connector at this stage) |
| Seafile ↔ Vikunja link | 2.10 | No code — documented usage (`docs/vikunja-seafile.md`) |
| Gokapi Filelink (Thunderbird) | 2.11 | `connectors/thunderbird-filelink-gokapi/` |
| Video platform (PeerTube + MinIO) | 2.12 | `infra/k8s/helm-values/peertube.yaml`, `infra/k8s/helm-values/minio.yaml`, `connectors/peertube-ingest/` |
| GAL over CardDAV | 2.13 | `infra/ansible/playbooks/grommunio.yml` (`GAL_ENABLED`) |
| Room booking | 2.14 | No code — native Grommunio behavior, documented (`docs/room-booking.md`) |
| Proxmox / Kubernetes infrastructure | 4.1–4.7 | `infra/terraform/`, `infra/k8s/` |
| Single source of versions/ports (docker-compose ↔ Helm ↔ tests) | 4.1 (rebuildable IaC, without drift) | `platform.yaml`, `scripts/sync_platform.py` |
| Dev/staging/prod environments | 4.6 | `dev-cluster/` (k3d, reuses `infra/k8s/helm-values/` + `infra/k8s/helm-values/dev/` hardening overlays), `docker-compose/` (grommunio-dev only) |
| CVE monitoring / version monitoring / ephemeral staging | 5.2–5.5 | `.github/workflows/` |
| Durable integration tests | 5.5 | `tests/integration/` |

# Study ↔ code correspondence table

Each row refers to the section of `office365-exit-study.md` that motivates
the corresponding code. Keep it up to date with every new building
block/connector.

| Building block / topic | Study section | Location in the repository |
|---|---|---|
| Grommunio (mail/calendar) | 1.1 | `infra/terraform/grommunio.tf`, `infra/ansible/playbooks/grommunio.yml`; TLS (issuance + renewal): `infra/ansible/playbooks/grommunio-cert.yml` |
| Matrix / Synapse / Element | 1.2 | `infra/k8s/helm-values/synapse.yaml` (OIDC entirely chart-native — see `docs/oidc.md`) |
| Video conferencing (DINUM/LiveKit) + Element Call | 1.3 | `infra/k8s/helm-values/visio.yaml`, `infra/k8s/helm-values/element-call.yaml` |
| Seafile | 1.4 | `infra/k8s/helm-values/seafile.yaml` |
| OnlyOffice Document Server | 1.5 | `infra/k8s/helm-values/onlyoffice.yaml`; SSO gate: `infra/k8s/helm-values/oauth2-proxy-onlyoffice.yaml` (see `docs/oidc.md`) |
| Vikunja | 1.6 | `infra/k8s/helm-values/vikunja.yaml` |
| Keycloak (SSO/MFA) | 1.7 | `infra/k8s/helm-values/keycloak.yaml`, `infra/ansible/playbooks/keycloak-realm.yml`, `connectors/keycloak-otp-spi/` |
| UI language (fr default, en available) | not a numbered study requirement — added on request | `platform.yaml`'s `locale` section (single source), `infra/ansible/roles/keycloak_realm/` (only component actually wired so far — see `docs/i18n.md` for the full per-component breakdown, most still open) |
| Gokapi | 1.8 | `infra/k8s/manifests/gokapi.yaml` (no official Helm chart, see that file's header; `v2.2.4`, OIDC/encryption configured non-interactively by the `gokapi-setup-bootstrap` initContainer — see `docs/oidc.md`; Tasmane branding via Caddy `html_inject` — `infra/k8s/manifests/caddy-injection.yaml`'s `gokapi-branding.html`, not a Gokapi-side file, see that file's comment for why) |
| Thunderbird / Apple Mail (client) | 1.9 | `docs/clients.md` (reference configuration, no server-side code); autoconfig/Autodiscover: `platform.yaml` (`autoconfig`/`autodiscover` subdomains), `infra/k8s/manifests/caddy.yaml` (`caddy-autoconfig` ConfigMap, Caddy-fronted) |
| Unified notification center (Novu) | 2.1 | `infra/k8s/helm-values/novu.yaml`, `connectors/notification-hub/`; admin dashboard SSO gate: `infra/k8s/helm-values/oauth2-proxy-novu.yaml` (see `docs/oidc.md`) |
| Unified search | 2.2 | `connectors/unified-search/` |
| Portal / Caddy HTML injection | 2.3 | `infra/k8s/manifests/caddy.yaml` (sole public entry point, no Ingress Controller/cert-manager needed - see `infra/k8s/helm-values/README.md`), `infra/k8s/manifests/caddy-injection.yaml` (Tasmane graphic-charter branding via `banner.css`) |
| Chat/video continuity (Matrix ↔ video conferencing widget) | 2.4 | `connectors/matrix-visio-widget/` |
| Native application onboarding | 2.5 | `docs/onboarding/README.md` (design + rationale); generated content: `infra/k8s/manifests/onboarding.yaml` (`scripts/sync_platform.py`'s `compute_onboarding_changes()`) |
| Disabling OnlyOffice chat | 2.6 | `infra/k8s/helm-values/onlyoffice.yaml` (`document.permissions.chat`) |
| OnlyOffice mentions → notifications | 2.7 | `connectors/onlyoffice-mentions/` |
| Unified presence | 2.8 | `connectors/presence-aggregator/` |
| Video conferencing button from Grommunio | 2.9 | `docs/visio-invite.md` (reusable link, no connector at this stage) |
| Seafile ↔ Vikunja link | 2.10 | No code — documented usage (`docs/vikunja-seafile.md`) |
| Gokapi Filelink (Thunderbird) | 2.11 | `connectors/thunderbird-filelink-gokapi/` (fleet-wide deployment: `policies.json`, see its README) |
| Video platform (PeerTube + MinIO) | 2.12 | `infra/k8s/helm-values/peertube.yaml`, `infra/k8s/helm-values/minio.yaml`, `connectors/peertube-ingest/` |
| GAL over CardDAV | 2.13 | `infra/ansible/playbooks/grommunio.yml` (`GAL_ENABLED`) |
| Room booking | 2.14 | No code — native Grommunio behavior, documented (`docs/room-booking.md`) |
| Proxmox / Kubernetes infrastructure | 4.1–4.7 | `infra/terraform/`, `infra/k8s/` |
| Single source of versions/ports/domains (docker-compose ↔ Helm ↔ tests) | 4.1 (rebuildable IaC, without drift) | `platform.yaml`, `scripts/sync_platform.py` |
| DNS zone population (A/AAAA records) | 4.2/4.4 (not a numbered study requirement) | `infra/k8s/helm-values/external-dns.yaml` (OVH provider — see that file's header comment for what to verify before deploying) |
| Secrets management (dedicated vault, never in plaintext) | 4.5 | `infra/k8s/helm-values/openbao.yaml` + `external-secrets.yaml`, `infra/k8s/manifests/external-secrets*.yaml`, `infra/ansible/roles/openbao_config/` |
| OS security hardening (fail2ban, SSH) | not a numbered study requirement — closes a gap noted during review | `infra/ansible/roles/os_hardening/` |
| Dev/staging/prod environments | 4.6 | `dev-cluster/` (k3d, reuses `infra/k8s/helm-values/` + `infra/k8s/helm-values/dev/` hardening overlays, plus `dev-cluster/grommunio-dev/` docker-compose for the one brick k3d can't host) |
| CVE monitoring / version monitoring / ephemeral staging | 5.2–5.5 | `.github/workflows/` |
| Vendor security feeds (Grommunio, Synapse, Element, Seafile, OnlyOffice, Vikunja, Keycloak, Caddy) | 5.2 (L.778) | `.github/workflows/security-feeds.yml`, `scripts/security_feeds.py` |
| Durable integration tests | 5.5 | `tests/integration/` |
| Single consolidated dashboard (CVE, versions, staging results, production monitoring) | 5.6 | `.github/workflows/dashboard.yml`, `scripts/build_dashboard.py` (see `docs/ci-cd.md` for the production-monitoring caveat) |

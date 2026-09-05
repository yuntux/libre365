# Table de correspondance étude ↔ code

Chaque ligne renvoie à la section de `sortie-office365-etude.md` qui motive
le code correspondant. À tenir à jour à chaque nouvelle brique/connecteur.

| Brique / sujet | Section étude | Emplacement dans le dépôt |
|---|---|---|
| Grommunio (mail/agenda) | 1.1 | `infra/terraform/grommunio.tf`, `infra/ansible/playbooks/grommunio.yml` |
| Matrix / Synapse / Element | 1.2 | `infra/k8s/helm-values/synapse.yaml`, `infra/ansible/playbooks/matrix.yml` |
| Visio (DINUM/LiveKit) + Element Call | 1.3 | `infra/k8s/helm-values/visio.yaml`, `infra/k8s/helm-values/element-call.yaml` |
| Seafile | 1.4 | `infra/k8s/helm-values/seafile.yaml` |
| OnlyOffice Document Server | 1.5 | `infra/k8s/helm-values/onlyoffice.yaml` |
| Vikunja | 1.6 | `infra/k8s/helm-values/vikunja.yaml` |
| Keycloak (SSO/MFA) | 1.7 | `infra/k8s/helm-values/keycloak.yaml`, `infra/ansible/playbooks/keycloak-realm.yml`, `connectors/keycloak-otp-spi/` |
| Gokapi | 1.8 | `infra/k8s/helm-values/gokapi.yaml` |
| Thunderbird / Apple Mail (client) | 1.9 | `docs/clients.md` (config de référence, pas de code serveur) |
| Centre de notifications unifié (Novu) | 2.1 | `infra/k8s/helm-values/novu.yaml`, `connectors/notification-hub/` |
| Recherche unifiée | 2.2 | `connectors/unified-search/` |
| Portail / injection HTML Caddy | 2.3 | `infra/k8s/helm-values/caddy.yaml`, `infra/k8s/manifests/caddy-injection.yaml` |
| Continuité tchat/visio (widget Matrix ↔ Visio) | 2.4 | `connectors/matrix-visio-widget/` |
| Onboarding applications natives | 2.5 | `docs/onboarding/` |
| Désactivation tchat OnlyOffice | 2.6 | `infra/k8s/helm-values/onlyoffice.yaml` (`document.permissions.chat`) |
| Mentions OnlyOffice → notifications | 2.7 | `connectors/onlyoffice-mentions/` |
| Présence unifiée | 2.8 | `connectors/presence-aggregator/` |
| Bouton visio depuis Grommunio | 2.9 | `docs/visio-invite.md` (lien réutilisable, pas de connecteur à ce stade) |
| Lien Seafile ↔ Vikunja | 2.10 | Aucun code — usage documenté (`docs/vikunja-seafile.md`) |
| Filelink Gokapi (Thunderbird) | 2.11 | `connectors/thunderbird-filelink-gokapi/` |
| Plateforme vidéo (PeerTube + MinIO) | 2.12 | `infra/k8s/helm-values/peertube.yaml`, `infra/k8s/helm-values/minio.yaml`, `connectors/peertube-ingest/` |
| GAL en CardDAV | 2.13 | `infra/ansible/playbooks/grommunio.yml` (`GAL_ENABLED`) |
| Réservation de salles | 2.14 | Aucun code — comportement natif Grommunio, documenté (`docs/room-booking.md`) |
| Infra Proxmox / Kubernetes | 4.1–4.7 | `infra/terraform/`, `infra/k8s/` |
| Environnements dev/recette/prod | 4.6 | `docker-compose/`, `infra/k8s/helm-values/*-{dev,staging,prod}.yaml` |
| Veille CVE / versions / recette éphémère | 5.2–5.5 | `.github/workflows/` |
| Tests d'intégration pérennes | 5.5 | `tests/integration/` |

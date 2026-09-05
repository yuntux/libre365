# Values Helm — open365

Configuration Kubernetes des briques conteneurisees retenues par l'etude
(`sortie-office365-etude.md`, chapitre 4.3). Grommunio est **hors perimetre** de ce
repertoire : deploye en VM appliance Proxmox, cf. chapitre 4.3 et `infra/terraform/` /
`infra/ansible/` (geres par une autre equipe).

## Convention de nommage : overlays `-100` / `-2000`

Pour les briques dont le dimensionnement varie reellement selon l'echelle (Synapse,
OnlyOffice, Keycloak — cf. etude), la convention retenue est :

- `<brique>.yaml` : valeurs communes, independantes de l'echelle (image, integrations
  OIDC, activation de fonctionnalites, options fonctionnelles). Ne contient **aucune**
  valeur de `replicaCount`/`resources` propre a une echelle.
- `<brique>-100.yaml` : overlay de dimensionnement pour la cible initiale ~100
  utilisateurs.
- `<brique>-2000.yaml` : overlay de dimensionnement pour la cible de croissance ~2000
  utilisateurs.

Les deux fichiers sont passes en cascade a `helm`, le second (`-100` ou `-2000`)
surchargeant les cles de dimensionnement :

```bash
helm upgrade --install synapse ananace-charts/matrix-synapse \
  -n open365 -f synapse.yaml -f synapse-100.yaml
```

Pour les briques dont le dimensionnement ne depend pas reellement du nombre
d'utilisateurs mais d'un autre facteur (volume de donnees pour Seafile, usage API pour
Vikunja — cf. etude 1.4 L.136 et 1.6 L.229), un seul fichier `<brique>.yaml` suffit ; le
choix est documente en tete de chaque fichier concerne.

## Charts Helm utilises

| Brique | Chart | Repo Helm |
|---|---|---|
| Synapse (Matrix) | `matrix-synapse` (ananace-chart) | https://ananace.gitlab.io/charts |
| Element Web | `matrix-element-web` (ananace-chart) | https://ananace.gitlab.io/charts |
| Element Call | pas de chart officiel — manifest values "chart-like", a adapter en raw | — |
| Visio (LaSuite Meet) | `suitenumerique/meet` si publie, sinon manifest raw | https://github.com/suitenumerique/meet |
| Seafile | chart communautaire `seafile-ce` | https://seafile-charts.github.io/seafile-charts (a valider) |
| OnlyOffice Document Server | chart communautaire `docs-cloud` | https://onlyoffice.github.io/docs-cloud-chart (a valider) |
| Vikunja | `vikunja` (go-vikunja/helm-charts) | https://vikunja.github.io/helm-charts |
| Keycloak | `keycloak` (Bitnami) | https://charts.bitnami.com/bitnami |
| Gokapi | pas de chart officiel — manifest raw (`../manifests/gokapi.yaml`) | — |
| MinIO | `minio` (chart officiel MinIO) | https://charts.min.io/ |
| PeerTube | chart communautaire `peertube` | https://peertube-helm.github.io/charts (a valider) |
| Caddy | pas de chart dedie — manifest raw (`../manifests/caddy.yaml`), image custom xcaddy avec plugin d'injection HTML | — |
| Novu | `novu` (chart officiel Novu) | https://novuhq.github.io/helm-charts |

Les charts marques « a valider » n'ont pas de source officielle unique identifiee au
moment de la redaction (aout/septembre 2026) : plusieurs forks communautaires existent
selon la brique. Repli systematique prevu vers un manifest raw derive de l'image Docker
officielle si aucun chart maintenu n'est disponible au moment du deploiement effectif.

## Commande type de deploiement

```bash
# Ajout des repos Helm (une fois)
helm repo add ananace-charts https://ananace.gitlab.io/charts
helm repo add bitnami https://charts.bitnami.com/bitnami
helm repo add minio https://charts.min.io/
helm repo add novu https://novuhq.github.io/helm-charts
helm repo add vikunja https://vikunja.github.io/helm-charts
helm repo update

# Namespace
kubectl apply -f ../manifests/namespace.yaml

# Brique sans overlay d'echelle
helm upgrade --install vikunja vikunja/vikunja -n open365 -f vikunja.yaml
helm upgrade --install seafile seafile-charts/seafile-ce -n open365 -f seafile.yaml
helm upgrade --install minio minio/minio -n open365 -f minio.yaml
helm upgrade --install peertube peertube-helm/peertube -n open365 -f peertube.yaml
helm upgrade --install novu novu/novu -n open365 -f novu.yaml
helm upgrade --install element-web ananace-charts/matrix-element-web -n open365 -f element-web.yaml

# Brique avec overlay d'echelle (exemple : cible 100 utilisateurs)
helm upgrade --install synapse ananace-charts/matrix-synapse -n open365 -f synapse.yaml -f synapse-100.yaml
helm upgrade --install onlyoffice onlyoffice/docs-cloud -n open365 -f onlyoffice.yaml -f onlyoffice-100.yaml
helm upgrade --install keycloak bitnami/keycloak -n open365 -f keycloak.yaml -f keycloak-100.yaml

# Manifests raw (pas de chart)
kubectl apply -f ../manifests/gokapi.yaml
kubectl apply -f ../manifests/caddy-injection.yaml
kubectl apply -f ../manifests/caddy.yaml
```

Le passage de 100 a 2000 utilisateurs (et au-dela, chapitre 4.1 de l'etude) se traduit
par un simple remplacement de l'overlay (`-100.yaml` -> `-2000.yaml`) suivi d'un nouveau
`helm upgrade`, sans reecriture de la definition d'infrastructure elle-meme.

## Secrets

Aucun secret en clair dans ce repertoire (chapitre 4.5 de l'etude — gestion des secrets
externalisee dans un coffre-fort dedie, ex. Vault). Toutes les references
`existingSecret` / `secretKeyRef` de ces fichiers de values pointent vers des Secrets
Kubernetes provisionnes en dehors de ce depot (Ansible/Vault, cf. `infra/ansible/`, geree
par une autre equipe).

## Hors perimetre de ce repertoire

- Grommunio : VM appliance Proxmox (etude 4.3), cf. `infra/terraform/` et
  `infra/ansible/`.
- LiveKit (backend SFU partage par Visio et Element Call, etude 1.3 L.106-107) : les
  fichiers `visio-meet.yaml` et `element-call.yaml` referencent un endpoint LiveKit
  commun (`livekit.open365.svc.cluster.local`) mais ne definissent pas le deploiement
  LiveKit lui-meme, non liste explicitement dans le perimetre de ce chantier.
- Les connecteurs applicatifs (centre de notifications, recherche unifiee, agregateur
  de presence, integrations Seafile/OnlyOffice, etc., chapitre 2 de l'etude) : cf.
  `connectors/`, gere par une autre equipe.

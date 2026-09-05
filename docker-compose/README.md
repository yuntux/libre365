# open365 - environnement docker-compose (developpement / test)

Cet environnement correspond au chapitre 4.6 de l'etude
(`../sortie-office365-etude.md`) : *"Developpement/test : echelle reduite,
donnees synthetiques."* Il n'est **pas** la cible de production, qui repose
sur Kubernetes (chapitre 4.4) avec haute disponibilite, scaling horizontal
et Grommunio deploye en VM appliance Proxmox (chapitre 4.3). Ici, on
privilegie des images officielles simples avec des ports mappes en clair sur
`localhost`, pour le developpement local et pour que la suite
`tests/integration/` (pytest, contre `http://localhost:<port>`) puisse
s'executer en CI.

## Demarrage

```bash
cd docker-compose
cp .env.example .env      # ajuster si besoin - valeurs par defaut = dev only
docker compose up -d
./scripts/wait-for-healthy.sh   # attend que tous les services repondent
```

Pour tout arreter et supprimer les volumes (repartir de zero) :

```bash
docker compose down -v
```

## Services et ports exposes sur localhost

| Service | Image | Port(s) hote | Identifiants par defaut (dev only) |
|---|---|---|---|
| `keycloak` | `quay.io/keycloak/keycloak:25.0.6` | 8080 | admin / `devonly-changeme-admin` (realm `master`) ; realm `open365` importe automatiquement avec le client `open365-integration-tests` / `devonly-changeme-client-secret` et l'utilisateur `testuser` / `devonly-changeme-testuser` |
| `postgres-keycloak` | `postgres:16.4-alpine` | 5433 | `keycloak` / `devonly-changeme-keycloak-db` |
| `synapse` | `matrixdotorg/synapse:v1.114.0` | 8008 (client), 8448 (federation) | inscription ouverte sans verification (dev uniquement) |
| `postgres-synapse` | `postgres:16.4-alpine` | 5434 | `synapse` / `devonly-changeme-synapse-db` |
| `element` | `vectorim/element-web:v1.11.86` | 8081 | pointe vers `synapse` (a saisir a la connexion) |
| `seafile` | `seafileltd/seafile-mc:11.0.13` | 8082 | `admin@open365.localhost` / `devonly-changeme-seafile-admin` |
| `seafile-mysql` | `mariadb:10.11` | (interne uniquement) | root / `devonly-changeme-seafile-mysql-root` |
| `onlyoffice-documentserver` | `onlyoffice/documentserver:8.2.2` | 8083 | JWT active (`devonly-changeme-onlyoffice-jwt`) |
| `postgres-onlyoffice` | `postgres:16.4-alpine` | 5435 | `onlyoffice` / `devonly-changeme-onlyoffice-db` |
| `vikunja` | `vikunja/vikunja:0.24.3` | 3456 | premier compte a creer via l'API/UI (sqlite dev) |
| `gokapi` | `f0rc3/gokapi:v1.9.6` | 53842 | admin / `devonly-changeme-gokapi-admin` |
| `minio` | `minio/minio:RELEASE.2024-10-13T13-34-11Z` | 9000 (API), 9001 (console) | `minioadmin` / `devonly-changeme-minio-root` |
| `peertube` | `chocobozzz/peertube:v6.3.2-bookworm` | 9002 | premier compte cree via CLI PeerTube au premier demarrage |
| `peertube-db` / `peertube-redis` | `postgres:16.4-alpine` / `redis:7.4-alpine` | (interne uniquement) | `peertube` / `devonly-changeme-peertube-db` |
| `caddy` | `caddy:2-alpine` (pin `2.8.4-alpine`) | 10080 (HTTP), 10443 (HTTPS) | reverse-proxy simple par sous-chemin, cf. `config/caddy/Caddyfile` |
| `novu-mock` | `node:20.17-alpine` (mock, voir plus bas) | 13000 | aucun (mock non authentifie) |
| `grommunio-dev` | `grommunio/gromox-container:core-c9` | 8443 | admin / `devonly-changeme-grommunio-admin` - **dev/test uniquement, voir ci-dessous** |
| `notification-hub` | build `../connectors/notification-hub` | 4001 | - |
| `unified-search` | build `../connectors/unified-search` | 4002 | - |
| `presence-aggregator` | build `../connectors/presence-aggregator` | 4003 | - |
| `onlyoffice-mentions` | build `../connectors/onlyoffice-mentions` | 4004 | - |
| `peertube-ingest` | build `../connectors/peertube-ingest` | 4005 | - |

Tous les ports hote sont surchargeables via `.env` (voir `.env.example`) en
cas de conflit avec des services deja lances sur la machine.

**Aucun mot de passe listé ci-dessus n'est destiné à autre chose qu'au
développement local / à la CI.** Voir `.env.example` pour la liste complete
et le rappel explicite "dev only" sur chaque secret.

## Choix documentes / simplifications par rapport a la cible de production

| Sujet | Ici (dev/test) | Cible production (etude) | Section etude |
|---|---|---|---|
| Orchestrateur | Docker Compose, mono-hote | Kubernetes (Helm par brique), scaling horizontal et HA | 4.4 |
| Grommunio (mail/agenda) | Conteneur `grommunio/gromox-container` (image "non prete pour la production" selon l'editeur lui-meme) | VM appliance Proxmox dediee, hors Kubernetes | 4.3 |
| Keycloak | Instance unique, mode `start-dev`, sans TLS | Cluster Keycloak HA, TLS, coffre-fort de secrets dedie | 4.4, 4.5 |
| Synapse | Instance monolithique unique, pas de mode "workers" | Synapse en mode workers pour la scalabilite/HA | 4.4 |
| OnlyOffice Document Server | Instance unique | Cluster OnlyOffice Document Server | 4.4 |
| Seafile | Base MariaDB interne au conteneur `seafile-mc`, stockage disque local | Architecture dediee/scalable, backend de stockage a dimensionner pour la croissance visee | 1.4, 4.4 |
| Centre de notifications (Novu) | **Mock HTTP minimal** (`config/novu-mock/server.js`, image `node` officielle) exposant seulement `POST /v1/events/trigger` et `GET /health` | Stack Novu complete (`novu/api` + `novu/worker` + `novu/ws` + MongoDB + Redis), cf. `https://docs.novu.co/self-hosting` | 2.1 |
| Portail applicatif (bandeau menu/cloche/recherche) | Caddy en reverse-proxy simple par sous-chemin, **sans** le plugin d'injection HTML (non compile dans l'image `caddy:2-alpine` officielle) - un exemple de snippet est laisse en commentaire dans `config/caddy/Caddyfile` | Caddy + plugin `caddy2-html-injection-plugin` (build Caddy custom via `xcaddy`) pour injecter le bandeau transverse | 2.3 |
| Vikunja | Base sqlite embarquee | Base Postgres/MySQL dediee, dimensionnee | 1.6, 4.4 |
| Secrets | En clair dans `.env` (valeurs "dev only" explicites) | Coffre-fort dedie (Vault ou equivalent), jamais en clair dans le depot | 4.5 |
| TLS / certificats | Absent (HTTP en clair sur localhost) | TLS de bout en bout | 4.2, 4.4 |
| Sauvegarde/restauration | Volumes Docker locaux, pas de strategie de sauvegarde (environnement jetable) | Sauvegardes applicatives + snapshots Proxmox Backup Server | 4.7 |
| Environnements | Un seul environnement dev/test, partage entre developpeurs et CI | Trois environnements IaC identiques (dev/test, recette, production), ne differant que par la taille et les donnees | 4.6 |

### Pourquoi un mock pour Novu ?

La stack Novu de reference (`novu/api` + `novu/worker` + `novu/ws` +
`novu/web`, plus MongoDB et Redis) est concue pour etre deployee comme un
produit complet, pas comme une simple dependance a demarrer en quelques
secondes en CI. L'objectif de cet environnement dev/test est de valider les
**connecteurs applicatifs** (`notification-hub`, `onlyoffice-mentions`,
`presence-aggregator`, etude 2.1/2.7/2.8), pas Novu lui-meme : le mock
(`config/novu-mock/server.js`, servi par l'image officielle `node:20-alpine`)
expose la meme forme d'API minimale (`POST /v1/events/trigger`,
`GET /v1/events`, `GET /health`) que ces connecteurs appellent en pratique,
et journalise chaque evenement recu sur stdout pour inspection pendant les
tests. Un environnement de recette avec le vrai Novu reste a mettre en place
separement (chapitre 4.4/5.5) le jour ou l'integration Novu elle-meme doit
etre testee de bout en bout.

### Pourquoi Grommunio en conteneur alors que l'etude dit VM appliance ?

L'etude (4.3) est explicite : Grommunio est deploye en VM appliance Proxmox
en production, precisement parce que son image conteneur officielle
(`grommunio/gromox-container`) est presentee par l'editeur comme non prete
pour la production (bundle nginx/Postfix/gromox/Redis/PHP-FPM sous un seul
supervisord). Ce docker-compose est un environnement de developpement/test,
pas une replique de la topologie de production : y inclure ce conteneur
permet aux tests d'integration (envoi/reception mail, chapitre 5.5) de
s'executer en CI sans avoir besoin d'une VM Proxmox. Le service
`grommunio-dev` porte ce nom et ce commentaire explicitement pour eviter
toute confusion avec le mode de deploiement cible.

## Structure des fichiers

```
docker-compose/
  docker-compose.yml         Definition de tous les services
  .env.example               Variables d'environnement (mots de passe dev only)
  README.md                  Ce fichier
  config/
    keycloak/realm-export.json   Realm "open365" + client de test importes au demarrage
    synapse/homeserver.yaml      Configuration Synapse minimale (dev/test)
    synapse/log.config           Configuration de logs Synapse (sortie console)
    caddy/Caddyfile               Reverse-proxy par sous-chemin + reference a l'injection HTML de prod (2.3)
    novu-mock/server.js           Mock HTTP minimal remplacant la stack Novu complete
  scripts/
    wait-for-healthy.sh           Attend que tous les services soient disponibles (CI)
```

## Utilisation en CI

```bash
cd docker-compose
cp .env.example .env
docker compose up -d --build
./scripts/wait-for-healthy.sh 600
cd ../tests/integration
pytest
```

`scripts/wait-for-healthy.sh` s'appuie sur les `healthcheck` Docker declares
dans `docker-compose.yml` ; pour `grommunio-dev`, qui n'a pas de healthcheck
Docker standard documente par l'editeur, il retombe sur une simple
verification TCP du port publie.

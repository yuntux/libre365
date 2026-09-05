# Tests d'intégration

Suite de tests d'intégration pérenne couvrant les scénarios critiques
identifiés dans l'étude (`sortie-office365-etude.md`, section 4.5 "Rejeu des
scénarios de test") :

| Scénario (étude 4.5)                                   | Fichier                              |
|----------------------------------------------------------|---------------------------------------|
| Envoi/réception mail (Grommunio)                          | `test_mail_grommunio.py`              |
| Création et synchronisation de fichier (Seafile)          | `test_file_sync_seafile.py`           |
| Co-édition d'un document (OnlyOffice)                      | `test_coedition_onlyoffice.py`        |
| Message + démarrage visio depuis une room (Matrix/Element) | `test_matrix_visio.py`                |
| Création et notification d'une tâche (Vikunja)             | `test_task_vikunja.py`                |
| Authentification SSO bout en bout (Keycloak), par brique   | `test_sso_e2e.py`                     |
| Connecteurs (notification-hub, unified-search, presence-aggregator) en boîte noire | `test_connectors.py` |

Cette suite est destinée à vivre dans la durée : elle est rejouée à la fois
en local pendant le développement, et automatiquement contre chaque nouvel
environnement de recette éphémère avant toute décision de promotion en
production (étude, sections 4.4 et 4.5).

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r tests/integration/requirements.txt
```

## Lancement en local (contre docker-compose)

Démarrer d'abord la stack (`docker-compose/docker-compose.yml`, gérée par
ailleurs dans ce dépôt), puis lancer les tests depuis `tests/integration/`
pour que `pytest.ini` (markers, timeouts) soit pris en compte automatiquement :

```bash
cd tests/integration
pytest -m smoke                 # scénarios critiques minimaux, à lancer en premier
pytest                          # suite complète
pytest -m "not slow"            # exclut les scénarios longs
pytest -m sso                   # uniquement le scénario SSO bout-en-bout paramétré
pytest --html=report.html --self-contained-html   # génère le rapport de résultats (étude 4.5, ligne 797)
```

Si `pytest.ini` n'est pas repris (lancement depuis la racine du dépôt),
passer explicitement `-c tests/integration/pytest.ini` :

```bash
pytest -c tests/integration/pytest.ini tests/integration
```

Les tests échouent proprement (message explicite, pas de trace opaque) si
un service n'est pas démarré ou n'est pas prêt à temps : voir la fixture
`wait_for_service` dans `conftest.py`, qui sonde chaque healthcheck HTTP
avec un backoff avant de lancer les assertions métier.

## Variables d'environnement

Toutes les URLs de service ont une valeur par défaut cohérente avec
`docker-compose/docker-compose.yml`, mais peuvent être surchargées pour
pointer la suite vers un autre environnement (dev local avec des ports
remappés, ou environnement de recette éphémère - étude 4.4/5.4).

Ces valeurs par défaut ne sont **pas** recopiées à la main : elles viennent de
`_platform_defaults.py`, généré depuis `../../platform.yaml` (racine du
dépôt) par `../../scripts/sync_platform.py` — la même source qui pilote les
ports de `docker-compose/.env.example` et les tags d'image de
`infra/k8s/helm-values/`. Pour changer un port par défaut, éditer
`platform.yaml`, jamais `_platform_defaults.py` ni `conftest.py` directement.

| Variable                     | Défaut                     | Brique                          |
|-------------------------------|-----------------------------|----------------------------------|
| `KEYCLOAK_URL`                 | `http://localhost:8080`     | Keycloak                        |
| `KEYCLOAK_REALM`               | `libre365`                   | Keycloak (realm de test)        |
| `KEYCLOAK_CLIENT_ID`           | `integration-tests`         | Keycloak (client public direct access grants) |
| `KEYCLOAK_CLIENT_SECRET`       | *(vide)*                    | Keycloak (si le client de test n'est pas public) |
| `GROMMUNIO_IMAP_HOST` / `_PORT`| `localhost` / `993`         | Grommunio (IMAP)                |
| `GROMMUNIO_SMTP_HOST` / `_PORT`| `localhost` / `587`         | Grommunio (SMTP)                |
| `SEAFILE_URL`                  | `http://localhost:8082`     | Seafile                         |
| `ONLYOFFICE_URL`               | `http://localhost:8083`     | OnlyOffice Document Server      |
| `ONLYOFFICE_JWT_SECRET`        | *(vide = JWT désactivé)*    | OnlyOffice (signature de config)|
| `MATRIX_URL`                   | `http://localhost:8008`     | Synapse (homeserver Matrix)     |
| `ELEMENT_URL`                  | `http://localhost:8081`     | Element (client web)            |
| `VIKUNJA_URL`                  | `http://localhost:3456`     | Vikunja                         |
| `GOKAPI_URL`                   | `http://localhost:53842`    | Gokapi                          |
| `MINIO_URL`                    | `http://localhost:9000`     | MinIO                           |
| `PEERTUBE_URL`                 | `http://localhost:9002`     | PeerTube                        |
| `CADDY_URL`                    | `http://localhost:10080`    | Caddy (reverse proxy)           |
| `NOTIFICATION_HUB_URL`         | `http://localhost:4001`     | Connecteur notification-hub     |
| `UNIFIED_SEARCH_URL`           | `http://localhost:4002`     | Connecteur unified-search       |
| `PRESENCE_AGGREGATOR_URL`      | `http://localhost:4003`     | Connecteur presence-aggregator  |
| `ONLYOFFICE_MENTIONS_URL`      | `http://localhost:4004`     | Connecteur onlyoffice-mentions  |
| `PEERTUBE_INGEST_URL`          | `http://localhost:4005`     | Connecteur peertube-ingest      |
| `TEST_USER_USERNAME` / `_PASSWORD` / `_EMAIL` | `test.consultant` / `ChangeMe123!` / `test.consultant@libre365.test` | Utilisateur de test partagé (jeu de données représentatif, étude 4.4) |
| `SERVICE_WAIT_TIMEOUT`         | `120` (secondes)            | Délai max d'attente de disponibilité de Keycloak |

Des variables spécifiques par test permettent de surcharger des identifiants
propres à une brique quand ils diffèrent de l'utilisateur de test générique
(`TEST_MAIL_ADDRESS`, `TEST_SEAFILE_USERNAME`, `TEST_VIKUNJA_USERNAME`,
`TEST_MATRIX_USERNAME`, etc. - voir le fixture correspondant dans chaque
fichier de test).

## Intégration dans le pipeline de recette éphémère

Cette suite est conçue pour être invoquée telle quelle par le workflow CI/CD
qui orchestre le cycle décrit en section 4.4 de l'étude : détection d'une
nouvelle version -> déploiement de l'environnement de recette éphémère ->
rejeu de ces scénarios -> rapport de résultats conditionnant la promotion
(section 4.5). Le workflow GitHub Actions correspondant (répertoire
`.github/workflows/`, maintenu par ailleurs dans ce dépôt) est responsable de :

1. déployer l'environnement de recette éphémère et exporter les variables
   d'environnement ci-dessus pointant vers cet environnement ;
2. installer `tests/integration/requirements.txt` ;
3. lancer `pytest -m smoke` puis la suite complète, avec génération du
   rapport HTML (`--html=report.html --self-contained-html`) publié comme
   artefact du run ;
4. conditionner la promotion vers la production sur le résultat de ce
   rapport (succès/échec par scénario), manuelle ou automatisée selon la
   criticité de la brique concernée (étude 4.5, ligne 797).

Cette suite ne connaît pas elle-même le pipeline CI/CD : elle ne fait aucune
hypothèse sur GitHub Actions au-delà de lire des variables d'environnement
standard, pour rester exécutable aussi bien en local qu'à terme dans un
autre orchestrateur.

## Notes de conception

- **`test_sso_e2e.py`** est paramétré (`pytest.mark.parametrize`) brique par
  brique plutôt qu'écrit en cinq fonctions séparées : l'assertion
  ("401/403 sans token, 200 avec le token Keycloak") est structurellement
  identique pour Grommunio/Seafile/Vikunja/OnlyOffice/Matrix, seuls l'URL et
  les codes attendus par brique changent. Ajouter une future brique SSO se
  fait donc en ajoutant une entrée à la table `SSO_TARGETS`, sans dupliquer
  de logique de test.
- **`wait_for_service`** (dans `conftest.py`) est utilisée par chaque
  fichier de test avant toute assertion métier, pour absorber le démarrage
  lent de la stack docker-compose et échouer avec un message explicite
  (`ServiceNotReadyError`) plutôt qu'une trace de connexion refusée brute.
- **`test_connectors.py`** mocke ses sources avec `responses` pour
  `unified-search` (agrégation testée isolément, indépendamment des données
  réellement présentes dans Seafile/Vikunja/Matrix), mais interroge
  `notification-hub` et `presence-aggregator` en conditions réelles : ce
  sont des tests de connecteur "en boîte noire" par appel HTTP direct, sans
  connaissance de leur implémentation interne.

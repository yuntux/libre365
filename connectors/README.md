# Connecteurs d'integration (chapitre 2 de l'etude)

Modules d'integration developpes pour combler l'absence d'integration native entre les
briques "best of breed" de la stack (cf. `sortie-office365-etude.md`, chapitre 2). Cinq
services Node.js/TypeScript et une extension navigateur (Thunderbird).

| Connecteur | Etude | Port par defaut | Variable d'environnement cle |
|---|---|---|---|
| [`notification-hub`](./notification-hub) | 2.1, 2.7 | `4001` | `NOVU_API_URL` |
| [`unified-search`](./unified-search) | 2.2 | `4002` | `SEARCH_TIMEOUT_MS` |
| [`presence-aggregator`](./presence-aggregator) | 2.8 | `4003` | `LIVEKIT_URL` |
| [`onlyoffice-mentions`](./onlyoffice-mentions) | 2.7 | `4004` | `NOTIFICATION_HUB_URL` |
| [`peertube-ingest`](./peertube-ingest) | 2.12 | `4005` | `MINIO_ENDPOINT` |
| [`thunderbird-filelink-gokapi`](./thunderbird-filelink-gokapi) | 2.11 | n/a (WebExtension) | n/a |

## Description rapide

- **notification-hub** — recoit les webhooks Matrix/Grommunio/Seafile/Vikunja/OnlyOffice,
  normalise chaque evenement au format commun, relaie vers Novu (centre de notif in-app).
- **unified-search** — `GET /search?q=` en fan-out temps reel vers Matrix/Seafile/Vikunja/
  Grommunio(IMAP), avec relais du token Keycloak de l'utilisateur (pas de re-authentification
  cote connecteur) et timeout par service.
- **presence-aggregator** — consolide la presence Matrix (`m.presence`), Grommunio/EWS
  (`GetUserAvailability`) et LiveKit (participants d'une room) en un statut unique
  (`in-meeting` > `online` > `unavailable` > `offline`), expose en REST et en SSE pour le
  bandeau du portail applicatif (2.3).
- **onlyoffice-mentions** — implemente `onRequestUsers` (annuaire via Keycloak Admin API)
  et relaie `onRequestSendNotify` vers `notification-hub`.
- **peertube-ingest** — depose les enregistrements de reunion MinIO (sortie LiveKit
  Egress) vers PeerTube, en webhook temps reel ou en batch cron quotidien.
- **thunderbird-filelink-gokapi** — WebExtension Thunderbird (pas un service serveur)
  implementant l'API `cloudFile` pour Gokapi.

## Structure commune (services Node)

Chaque service Node possede son propre `package.json`, `tsconfig.json` (etendant
`connectors/tsconfig.base.json`), `Dockerfile` multi-stage, `README.md` et des tests
unitaires (Vitest). La logique metier non triviale est isolee dans des fonctions pures
(`normalize.ts`, `fanout.ts`, `consolidate.ts`, `transform.ts`, `metadata.ts`/`ingest.ts`
selon le connecteur) pour rester testable sans dependance reseau.

## Build Docker

Chaque `Dockerfile` copie `../tsconfig.base.json` : construire avec `connectors/` comme
contexte de build, par exemple :

```bash
cd connectors
docker build -f notification-hub/Dockerfile -t notification-hub .
```

## Tests

```bash
cd connectors/<nom-du-connecteur>
npm install
npm test
```

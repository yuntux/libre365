# notification-hub

Centre de notifications unifie (etude 2.1 et 2.7). Recoit les webhooks de Matrix
(Application Service), Grommunio, Seafile, Vikunja et OnlyOffice (mentions), normalise
chaque evenement au format commun `{source, eventType, userId, title, body, actionUrl, timestamp}`,
puis declenche une notification Novu via l'API REST (`events/trigger`).

## Pourquoi pas `@novu/node` ?
Appel REST direct pour rester un connecteur mince (etude 2.1 ligne 374 : "reproductible en
quelques centaines de lignes"), sans dependance SDK supplementaire a suivre.

## Endpoints

| Methode | Route | Source |
|---|---|---|
| POST | `/webhooks/matrix` | Matrix Application Service (message/mention) |
| POST | `/webhooks/grommunio` | Grommunio (nouveau mail) |
| POST | `/webhooks/seafile` | Seafile (partage de fichier) |
| POST | `/webhooks/vikunja` | Vikunja (tache assignee) |
| POST | `/webhooks/onlyoffice-mention` | OnlyOffice `onRequestSendNotify` relaye par `connectors/onlyoffice-mentions` |
| GET | `/healthz` | Sonde de sante |

## Variables d'environnement

| Variable | Defaut | Description |
|---|---|---|
| `PORT` | `4001` | Port d'ecoute HTTP |
| `NOVU_API_URL` | `https://api.novu.co/v1` | URL de l'API Novu (self-hosted ou cloud) |
| `NOVU_API_KEY` | (vide) | Cle API Novu |
| `NOVU_WORKFLOW_ID` | `open365-unified-notification` | Identifiant du workflow Novu declenche |

## Structure

- `src/normalize.ts` — fonctions pures de normalisation, une par source. Aucun effet de
  bord, testables sans reseau.
- `src/novu-client.ts` — relais REST vers Novu.
- `src/server.ts` — routes Express, cablage normalisation -> Novu.

## Developpement

```bash
npm install
npm test        # vitest sur src/normalize.ts
npm run build
npm start
```

## Docker

Le build necessite le fichier partage `../tsconfig.base.json` : construire avec le
repertoire `connectors/` comme contexte.

```bash
docker build -f notification-hub/Dockerfile -t notification-hub .   # depuis connectors/
```

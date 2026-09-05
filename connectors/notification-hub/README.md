# notification-hub

Unified notification center (study 2.1 and 2.7). Receives webhooks from Matrix
(Application Service), Grommunio, Seafile, Vikunja and OnlyOffice (mentions), normalizes
each event to the common format `{source, eventType, userId, title, body, actionUrl, timestamp}`,
then triggers a Novu notification via the REST API (`events/trigger`).

## Why not `@novu/node`?
Direct REST call to keep the connector thin (study 2.1, line 374: "reproducible in
a few hundred lines"), with no extra SDK dependency to maintain.

## Endpoints

| Method | Route | Source |
|---|---|---|
| POST | `/webhooks/matrix` | Matrix Application Service (message/mention) |
| POST | `/webhooks/grommunio` | Grommunio (new mail) |
| POST | `/webhooks/seafile` | Seafile (file share) |
| POST | `/webhooks/vikunja` | Vikunja (task assigned) |
| POST | `/webhooks/onlyoffice-mention` | OnlyOffice `onRequestSendNotify` relayed by `connectors/onlyoffice-mentions` |
| GET | `/healthz` | Health probe |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `4001` | HTTP listen port |
| `NOVU_API_URL` | `https://api.novu.co/v1` | Novu API URL (self-hosted or cloud) |
| `NOVU_API_KEY` | (empty) | Novu API key |
| `NOVU_WORKFLOW_ID` | `libre365-unified-notification` | Identifier of the triggered Novu workflow |

## Structure

- `src/normalize.ts` — pure normalization functions, one per source. No side
  effects, testable without network access.
- `src/novu-client.ts` — REST relay to Novu.
- `src/server.ts` — Express routes, wiring normalization -> Novu.

## Development

```bash
npm install
npm test        # vitest on src/normalize.ts
npm run build
npm start
```

## Docker

The build requires the shared `../tsconfig.base.json` file: build with the
`connectors/` directory as the context.

```bash
docker build -f notification-hub/Dockerfile -t notification-hub .   # from connectors/
```

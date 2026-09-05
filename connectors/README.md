# Integration connectors (chapter 2 of the study)

Integration modules developed to bridge the lack of native integration between the
"best of breed" bricks of the stack (see `sortie-office365-etude.md`, chapter 2). Five
Node.js/TypeScript services and one browser extension (Thunderbird).

| Connector | Study | Default port | Key environment variable |
|---|---|---|---|
| [`notification-hub`](./notification-hub) | 2.1, 2.7 | `4001` | `NOVU_API_URL` |
| [`unified-search`](./unified-search) | 2.2 | `4002` | `SEARCH_TIMEOUT_MS` |
| [`presence-aggregator`](./presence-aggregator) | 2.8 | `4003` | `LIVEKIT_URL` |
| [`onlyoffice-mentions`](./onlyoffice-mentions) | 2.7 | `4004` | `NOTIFICATION_HUB_URL` |
| [`peertube-ingest`](./peertube-ingest) | 2.12 | `4005` | `MINIO_ENDPOINT` |
| [`thunderbird-filelink-gokapi`](./thunderbird-filelink-gokapi) | 2.11 | n/a (WebExtension) | n/a |

## Quick description

- **notification-hub** — receives Matrix/Grommunio/Seafile/Vikunja/OnlyOffice webhooks,
  normalizes each event to a common format, relays it to Novu (in-app notification center).
- **unified-search** — `GET /search?q=` fanning out in real time to Matrix/Seafile/Vikunja/
  Grommunio(IMAP), relaying the user's Keycloak token (no re-authentication on the
  connector side) with a per-service timeout.
- **presence-aggregator** — consolidates Matrix presence (`m.presence`), Grommunio/EWS
  (`GetUserAvailability`) and LiveKit (room participants) into a single status
  (`in-meeting` > `online` > `unavailable` > `offline`), exposed over REST and SSE for the
  application portal's status bar (2.3).
- **onlyoffice-mentions** — implements `onRequestUsers` (directory via the Keycloak Admin API)
  and relays `onRequestSendNotify` to `notification-hub`.
- **peertube-ingest** — pushes MinIO meeting recordings (LiveKit Egress output)
  to PeerTube, either via real-time webhook or a daily batch cron job.
- **thunderbird-filelink-gokapi** — Thunderbird WebExtension (not a backend service)
  implementing the `cloudFile` API for Gokapi.

## Common structure (Node services)

Each Node service has its own `package.json`, `tsconfig.json` (extending
`connectors/tsconfig.base.json`), a multi-stage `Dockerfile`, a `README.md`, and
unit tests (Vitest). Non-trivial business logic is isolated in pure functions
(`normalize.ts`, `fanout.ts`, `consolidate.ts`, `transform.ts`, `metadata.ts`/`ingest.ts`
depending on the connector) to keep it testable without network dependencies.

## Docker build

Each `Dockerfile` copies `../tsconfig.base.json`: build with `connectors/` as the
build context, for example:

```bash
cd connectors
docker build -f notification-hub/Dockerfile -t notification-hub .
```

## Tests

```bash
cd connectors/<connector-name>
npm install
npm test
```

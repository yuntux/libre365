# presence-aggregator

Unified presence aggregator (study 2.8). Queries three disjoint sources and republishes
a consolidated status per user for the application portal's status bar (study 2.3):

- **Matrix**: `m.presence` (online/unavailable/offline) via the client-server API.
- **Grommunio/EWS**: "in meeting" state derived from `GetUserAvailability` (SOAP), a
  structured, commented call stub in `src/sources/grommunio-ews.ts`.
- **Video/LiveKit**: list of participants connected to a room, via
  `livekit-server-sdk` (`RoomServiceClient.listRooms`/`listParticipants`).

## Consolidation rule

`src/consolidate.ts` is a pure function, with no network dependency, so it is
unit-testable without HTTP mocks: priority **in meeting > online on Matrix > away**
(study 2.8 line 504).

## Endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/presence/:userId` | Instant consolidated status for a user |
| GET | `/presence/stream?userIds=a,b,c` | SSE stream, refreshed every `PRESENCE_STREAM_INTERVAL_MS` |
| GET | `/healthz` | Health probe |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `4003` | HTTP listen port |
| `PRESENCE_STREAM_INTERVAL_MS` | `5000` | SSE refresh interval |
| `MATRIX_BASE_URL` | `https://matrix.example.org` | Matrix homeserver URL |
| `MATRIX_SERVICE_TOKEN` | (empty) | Matrix service token to read any user's presence |
| `GROMMUNIO_EWS_URL` | `https://mail.example.org/EWS/Exchange.asmx` | EWS SOAP endpoint |
| `LIVEKIT_URL` | `https://visio.example.org` | LiveKit server URL |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | (empty) | LiveKit server API credentials |

## Development

```bash
npm install
npm test        # vitest on src/consolidate.ts, no network access
npm run build
npm start
```

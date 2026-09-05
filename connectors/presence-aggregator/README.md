# presence-aggregator

Unified presence aggregator (study 2.8). Queries three disjoint sources and republishes
a consolidated status per user for the application portal's status bar (study 2.3):

- **Matrix**: `m.presence` (online/unavailable/offline) via the client-server API,
  called asynchronously with `httpx` (`app/sources/matrix_presence.py`).
- **Grommunio/EWS**: "in meeting" state derived from `GetUserAvailability` (SOAP), a
  structured, commented call stub in `app/sources/grommunio_ews.py`.
- **Video/LiveKit**: list of participants connected to a room, via the official
  `livekit-api` Python SDK (`RoomService.list_rooms`/`list_participants`) --
  the async equivalent of the Node service's `livekit-server-sdk`
  (`app/sources/livekit_presence.py`).

## Stack

FastAPI + uvicorn (with the `uvloop` event loop) -- Python async, for consistency
with the rest of the repository and I/O-bound performance on par with the previous
Node/Express implementation.

## Consolidation rule

`app/consolidate.py` is a pure function, with no network dependency, so it is
unit-testable without HTTP mocks: priority **in meeting > online on Matrix > away**
(study 2.8 line 504). It is the direct port of the former `src/consolidate.ts`.

## Endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/presence/{user_id}` | Instant consolidated status for a user |
| GET | `/presence/stream?userIds=a,b,c` | SSE stream, refreshed every `PRESENCE_STREAM_INTERVAL_MS` |
| GET | `/healthz` | Health probe |

The SSE stream (`/presence/stream`) is served with `sse-starlette`'s
`EventSourceResponse` over a `StreamingResponse`, kept fully async: each
connected client gets its own generator that polls the three sources, pushes a
`data: [...]` event, sleeps `PRESENCE_STREAM_INTERVAL_MS`, and stops as soon as
the client disconnects (`request.is_disconnected()`).

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
pip install -r requirements.txt
pytest                                    # unit tests, no network access
uvicorn app.main:app --reload --port 4003 # or: python -m app.main
```

## Docker

Build context is this directory (`connectors/presence-aggregator`), matching
how `dev-cluster/deploy.sh` builds and imports this image into the local
k3d cluster:

```bash
cd connectors/presence-aggregator
docker build -t presence-aggregator .
```

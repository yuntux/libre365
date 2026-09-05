# Integration connectors (chapter 2 of the study)

Integration modules developed to bridge the lack of native integration between the
"best of breed" bricks of the stack (see `office365-exit-study.md`, chapter 2). Five
Python/FastAPI services and one browser extension (Thunderbird).

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

## Common structure (Python services)

Each service is a self-contained FastAPI app, served asynchronously by
**uvicorn** with the **uvloop** event loop for I/O-heavy webhook/fan-out
workloads. Chosen for consistency with the rest of the repo — already
Python in `tests/integration/` and `scripts/sync_platform.py` — and for
async performance on par with the previous Node/Express implementation on
this kind of I/O-bound traffic (a synchronous Flask-style app would not
have matched it).

Each connector has its own `requirements.txt` (runtime deps: `fastapi`,
`uvicorn[standard]`, `uvloop`, `httpx`, plus whatever the connector needs)
and `requirements-dev.txt` (test deps: `pytest`, `pytest-asyncio`, etc.), a
self-contained `Dockerfile` (base `python:3.12-slim`, no shared file needed
across connectors), a `README.md`, and unit tests (`pytest`). Non-trivial
business logic is isolated in pure functions/modules (`normalize.py`,
`fanout.py`, `consolidate.py`, `transform.py`, `metadata.py`/`ingest.py`
depending on the connector) to keep it testable without network
dependencies.

The app entrypoint is always `app/main.py` (FastAPI instance named `app`),
so every connector is served the same way:

```bash
uvicorn app.main:app --host 0.0.0.0 --port <default-port> --loop uvloop
```

## Docker build

Each `Dockerfile` is self-contained — build context is the connector's own
directory, matching `docker-compose/docker-compose.yml`'s
`context: ../connectors/<name>`:

```bash
cd connectors/notification-hub
docker build -t notification-hub .
```

## Tests

```bash
cd connectors/<connector-name>
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

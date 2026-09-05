# notification-hub

Unified notification center (study 2.1 and 2.7). Receives webhooks from Matrix
(Application Service), Grommunio, Seafile, Vikunja and OnlyOffice (mentions), normalizes
each event to the common format `{source, eventType, userId, title, body, actionUrl, timestamp}`,
then triggers a Novu notification via the REST API (`events/trigger`).

## Why not a Novu SDK?

Direct REST call to keep the connector thin (study 2.1, line 374: "reproducible in
a few hundred lines"), with no extra SDK dependency to maintain.

## Stack

Python (async), **FastAPI** served by **uvicorn** with the **uvloop** event loop for
Node-equivalent throughput on this I/O-bound workload, and `httpx.AsyncClient` for the
non-blocking outbound call to Novu.

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

- `app/normalize.py` — pure normalization functions, one per source. No side
  effects, testable without network access.
- `app/novu_client.py` — async REST relay to Novu (`httpx.AsyncClient`).
- `app/main.py` — FastAPI routes, wiring normalization -> Novu.
- `app/types.py` — shared type aliases / `TypedDict` for the normalized event shape.

## Dependencies convention

- `requirements.txt` — runtime dependencies only (fastapi, uvicorn[standard], uvloop, httpx).
- `requirements-dev.txt` — `-r requirements.txt` plus test tooling (pytest, pytest-asyncio).

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                       # unit tests (app/normalize.py) + light endpoint tests (app/main.py)
uvicorn app.main:app --reload --port 4001
```

## Docker

Self-contained build: the build context is this directory itself (no shared file
outside it), consistent with `docker-compose/docker-compose.yml`'s
`context: ../connectors/notification-hub`.

```bash
docker build -t notification-hub .   # from connectors/notification-hub/
```

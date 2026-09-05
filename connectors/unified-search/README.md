# unified-search

Unified search via real-time fan-out (study 2.2). `GET /search?q=...` queries Matrix
(`/search`), Seafile (search API), Vikunja (`tasks/all?s=`) and Grommunio (real IMAP
SEARCH) concurrently, with a per-service timeout (2s by default) that isolates a
slow service without blocking the other responses.

Implemented in Python (FastAPI + uvicorn, with `uvloop` as the event loop), for
consistency with the rest of the repository (`tests/integration/`,
`scripts/sync_platform.py`) and I/O-bound performance on par with the previous
Node/Express implementation.

## Key point: token relay, no re-authentication

The user's Keycloak Bearer token (the `Authorization` header of the incoming request)
is **relayed as-is** to each source service (study 2.2, lines 391 and 394). This connector
never authenticates itself in place of the user: each source service applies its own
permissions natively, avoiding any risk of ACL leakage inherent to a pre-computed
central index (see the discussion in study 2.2).

## Grommunio / IMAP

Grommunio does not expose a generic REST search API. `app/sources/grommunio.py`
connects over IMAP with `aioimaplib` and authenticates via XOAUTH2, relaying the
same user token that came in on the request (RFC 7628) — no re-authentication or
service account, consistent with the other sources. It then runs `SEARCH TEXT`
against `INBOX` and fetches `RFC822.HEADER` for each matching message to build the
result's title/date.

`aioimaplib`'s `Response.lines` format for a FETCH command isn't part of its public
API, so the header-literal extraction (`_extract_fetch_literal`) was verified against
a minimal fake IMAP server that speaks the real wire protocol
(`tests/test_grommunio.py`), not just against mocks of the client class.

## Endpoints

| Method | Route | Description |
|---|---|---|
| GET | `/search?q=...` | Fan-out to the 4 sources, aggregation + per-source timeout |
| GET | `/healthz` | Health probe |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `4002` | HTTP listen port |
| `SEARCH_TIMEOUT_MS` | `2000` | Per-source-service timeout |
| `MATRIX_BASE_URL` | `https://matrix.example.org` | Matrix server URL |
| `SEAFILE_BASE_URL` | `https://seafile.example.org` | Seafile URL |
| `VIKUNJA_BASE_URL` | `https://vikunja.example.org` | Vikunja URL |
| `GROMMUNIO_IMAP_HOST` | `mail.example.org` | Grommunio IMAP host |
| `GROMMUNIO_IMAP_PORT` | `993` | IMAP port |
| `GROMMUNIO_IMAP_TIMEOUT_SECONDS` | `10` | Per-IMAP-command timeout (independent of the fan-out's own `SEARCH_TIMEOUT_MS`) |
| `GROMMUNIO_WEBMAIL_BASE_URL` | `https://mail.example.org/webapp` | Base URL used to build each result's webmail deep link |

## Structure

- `app/fanout.py` — pure fan-out/timeout/aggregation core (`asyncio.gather(...,
  return_exceptions=True)` + `asyncio.wait_for` per service, the exact equivalent of
  `Promise.allSettled` + per-call timeout on the TS side). Sources are injected as a
  parameter to stay testable without network access (`tests/test_fanout.py`).
- `app/sources/*.py` — one async HTTP/IMAP connector per service (via
  `httpx.AsyncClient`), relaying the user token.
- `app/main.py` — FastAPI `/search` route, extracting the token from `Authorization`.

## Development

```bash
pip install -r requirements.txt
pytest
uvicorn app.main:app --reload --port 4002
```

## Docker

```bash
# from connectors/unified-search/ (self-contained build context)
docker build -t unified-search .
docker run -p 4002:4002 unified-search
```

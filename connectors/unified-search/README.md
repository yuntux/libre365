# unified-search

Unified search via real-time fan-out (study 2.2). `GET /search?q=...` queries Matrix
(`/search`), Seafile (search API), Vikunja (`tasks/all?s=`) and Grommunio (IMAP SEARCH,
structured stub) in parallel, with a per-service timeout (2s by default) that isolates a
slow service without blocking the other responses.

## Key point: token relay, no re-authentication

The user's Keycloak Bearer token (the `Authorization` header of the incoming request)
is **relayed as-is** to each source service (study 2.2, lines 391 and 394). This connector
never authenticates itself in place of the user: each source service applies its own
permissions natively, avoiding any risk of ACL leakage inherent to a pre-computed
central index (see the discussion in study 2.2).

## Grommunio / IMAP

Grommunio does not expose a generic REST search API. `src/sources/grommunio.ts`
lays out the structure of an IMAP SEARCH call via `imapflow` (commented out, ready to
be enabled) and documents the XOAUTH2 authentication mechanism that lets the same
user token be relayed to IMAP. The active implementation is a simplified stub that
simulates network latency, so the fan-out/timeout logic can be exercised end to end.

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

## Structure

- `src/fanout.ts` — pure fan-out/timeout/aggregation core, sources are injected as a
  parameter to stay testable without network access (`test/fanout.test.ts`).
- `src/sources/*.ts` — one HTTP/IMAP connector per service, relaying the user token.
- `src/server.ts` — Express `/search` route, extracting the token from `Authorization`.

## Development

```bash
npm install
npm test
npm run build
npm start
```

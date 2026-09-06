# peertube-ingest

Uploads meeting recordings (LiveKit Egress -> SeaweedFS) to PeerTube (study 2.12).
Implements the two modes described by the study: real-time (SeaweedFS webhook) and batch
(daily cron), sharing the same ingestion logic (`app/ingest.py`).

Python/FastAPI implementation (migrated from the original TypeScript/Express
service; observable contract -- endpoint, request/response shapes, env vars,
port -- is unchanged).

## Modes

- **Real-time**: `POST /webhooks/seaweedfs` receives the `create` events
  published by SeaweedFS's filer (`[notification.webhook]` in its
  notification.toml, see `infra/k8s/helm-values/seaweedfs.yaml`'s
  `filer.notificationConfig`). Served by FastAPI/uvicorn (with `uvloop` as
  the event loop).
- **Batch**: `python -m app.batch [--since=<ISO8601>]`, to run as a daily cron job
  (study 2.12 line 589: "this upload can be done as a periodic task -- daily batch --
  simpler to operate, with no risk even if the connector has a temporary outage"). Without
  `--since`, it scans the last 25 hours (safety margin on a daily cron).

## Meeting metadata

`app/metadata.py` extracts title/date/participants from the S3 object name, using
a `<ISO-date>_<title-slug>_<participant-slugs>.<ext>` convention (to be configured at
the LiveKit Egress export rule level). S3 tags `meeting-title`/`meeting-date`/
`meeting-participants`, when present on the object, take priority over what is
inferred from the file name.

## Endpoints / scripts

| | | |
|---|---|---|
| POST | `/webhooks/seaweedfs` | Real-time mode, SeaweedFS `create` event |
| GET | `/healthz` | Health probe |
| script | `python -m app.batch` | Batch mode, to schedule via cron |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `4005` | HTTP listen port (webhook mode) |
| `S3_ENDPOINT` | `https://s3.example.org` | S3-compatible endpoint (SeaweedFS's S3 gateway) |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | (empty) | S3 credentials |
| `S3_RECORDINGS_BUCKET` | `visio-recordings` | LiveKit Egress target bucket |
| `PEERTUBE_BASE_URL` | `https://tube.example.org` | PeerTube instance URL |
| `PEERTUBE_ACCESS_TOKEN` | (empty) | PeerTube OAuth token (service account) |
| `PEERTUBE_CHANNEL_ID` | `1` | Target PeerTube channel |
| `PEERTUBE_DEFAULT_PRIVACY` | `2` (internal) | Default visibility of uploaded videos |

## S3 client: boto3, not aioboto3

`app/s3_client.py` uses `boto3` (synchronous) rather than `aioboto3`. S3 calls
are infrequent relative to the connector's overall I/O: one `ListObjectsV2`/tagging/
`GetObject` sequence per ingested recording, and each recording is a large video
file where the upload to PeerTube (not the S3 read) dominates latency. `aioboto3`
also pins to a specific `aiobotocore`/`botocore` combination, adding maintenance
overhead disproportionate to the benefit here. Every blocking boto3 call is wrapped
in `asyncio.to_thread` so the FastAPI event loop (webhook mode) is never blocked by
it; the batch script (no event loop to protect) calls the same wrapped coroutines.

Upload to the PeerTube API is fully async via `httpx.AsyncClient`.

## Development

```bash
pip install -r requirements-dev.txt
pytest
uvicorn app.main:app --host 0.0.0.0 --port 4005 --reload   # webhook mode
python -m app.batch                                         # batch mode, single run
```

## Docker

Build context is this directory (self-contained), matching how
`dev-cluster/deploy.sh` builds and imports this image into the local k3d cluster:

```bash
cd connectors/peertube-ingest
docker build -t peertube-ingest .
docker run --rm -p 4005:4005 peertube-ingest                # webhook mode (default)
docker run --rm peertube-ingest python -m app.batch          # batch mode, single run
```

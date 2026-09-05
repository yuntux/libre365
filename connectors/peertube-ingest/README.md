# peertube-ingest

Uploads meeting recordings (LiveKit Egress -> MinIO) to PeerTube (study 2.12).
Implements the two modes described by the study: real-time (MinIO webhook) and batch
(daily cron), sharing the same ingestion logic (`app/ingest.py`).

Python/FastAPI implementation (migrated from the original TypeScript/Express
service; observable contract -- endpoint, request/response shapes, env vars,
port -- is unchanged).

## Modes

- **Real-time**: `POST /webhooks/minio` receives the `s3:ObjectCreated:*` notifications
  published by MinIO (webhook-type bucket notification target,
  `mc admin config set myminio notify_webhook:1 endpoint=http://peertube-ingest:4005/webhooks/minio`).
  Served by FastAPI/uvicorn (with `uvloop` as the event loop).
- **Batch**: `python -m app.batch [--since=<ISO8601>]`, to run as a daily cron job
  (study 2.12 line 589: "this upload can be done as a periodic task -- daily batch --
  simpler to operate, with no risk even if the connector has a temporary outage"). Without
  `--since`, it scans the last 25 hours (safety margin on a daily cron).

## Meeting metadata

`app/metadata.py` extracts title/date/participants from the MinIO object name, using
a `<ISO-date>_<title-slug>_<participant-slugs>.<ext>` convention (to be configured at
the LiveKit Egress export rule level). S3 tags `meeting-title`/`meeting-date`/
`meeting-participants`, when present on the object, take priority over what is
inferred from the file name.

## Endpoints / scripts

| | | |
|---|---|---|
| POST | `/webhooks/minio` | Real-time mode, MinIO `ObjectCreated` event |
| GET | `/healthz` | Health probe |
| script | `python -m app.batch` | Batch mode, to schedule via cron |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `4005` | HTTP listen port (webhook mode) |
| `MINIO_ENDPOINT` | `https://minio.example.org` | MinIO S3-compatible endpoint |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | (empty) | MinIO credentials |
| `MINIO_RECORDINGS_BUCKET` | `visio-recordings` | LiveKit Egress target bucket |
| `PEERTUBE_BASE_URL` | `https://tube.example.org` | PeerTube instance URL |
| `PEERTUBE_ACCESS_TOKEN` | (empty) | PeerTube OAuth token (service account) |
| `PEERTUBE_CHANNEL_ID` | `1` | Target PeerTube channel |
| `PEERTUBE_DEFAULT_PRIVACY` | `2` (internal) | Default visibility of uploaded videos |

## MinIO/S3 client: boto3, not aioboto3

`app/minio_client.py` uses `boto3` (synchronous) rather than `aioboto3`. S3 calls
are infrequent relative to the connector's overall I/O: one `ListObjectsV2`/tagging/
`GetObject` sequence per ingested recording, and each recording is a large video
file where the upload to PeerTube (not the MinIO read) dominates latency. `aioboto3`
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

Build context is this directory (self-contained), matching
`docker-compose/docker-compose.yml`'s `context: ../connectors/peertube-ingest`:

```bash
cd connectors/peertube-ingest
docker build -t peertube-ingest .
docker run --rm -p 4005:4005 peertube-ingest                # webhook mode (default)
docker run --rm peertube-ingest python -m app.batch          # batch mode, single run
```

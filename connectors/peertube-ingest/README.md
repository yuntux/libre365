# peertube-ingest

Uploads meeting recordings (LiveKit Egress -> MinIO) to PeerTube (study 2.12).
Implements the two modes described by the study: real-time (MinIO webhook) and batch
(daily cron), sharing the same ingestion logic (`src/ingest.ts`).

## Modes

- **Real-time**: `POST /webhooks/minio` receives the `s3:ObjectCreated:*` notifications
  published by MinIO (webhook-type bucket notification target,
  `mc admin config set myminio notify_webhook:1 endpoint=http://peertube-ingest:4005/webhooks/minio`).
- **Batch**: `node dist/batch.js [--since=<ISO8601>]`, to run as a daily cron job
  (study 2.12 line 589: "this upload can be done as a periodic task -- daily batch --
  simpler to operate, with no risk even if the connector has a temporary outage"). Without
  `--since`, it scans the last 25 hours (safety margin on a daily cron).

## Meeting metadata

`src/metadata.ts` extracts title/date/participants from the MinIO object name, using
a `<ISO-date>_<title-slug>_<participant-slugs>.<ext>` convention (to be configured at
the LiveKit Egress export rule level). S3 tags `meeting-title`/`meeting-date`/
`meeting-participants`, when present on the object, take priority over what is
inferred from the file name.

## Endpoints / scripts

| | | |
|---|---|---|
| POST | `/webhooks/minio` | Real-time mode, MinIO `ObjectCreated` event |
| GET | `/healthz` | Health probe |
| script | `dist/batch.js` | Batch mode, to schedule via cron |

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

## Development

```bash
npm install
npm test
npm run build
npm start        # webhook mode
npm run batch     # batch mode, single run
```

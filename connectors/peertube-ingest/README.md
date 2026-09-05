# peertube-ingest

Depot des enregistrements de reunion (LiveKit Egress -> MinIO) vers PeerTube (etude 2.12).
Implemente les deux modes decrits par l'etude : temps reel (webhook MinIO) et batch
(cron quotidien), partageant la meme logique d'ingestion (`src/ingest.ts`).

## Modes

- **Temps reel** : `POST /webhooks/minio` recoit les notifications `s3:ObjectCreated:*`
  publiees par MinIO (bucket notification target de type webhook,
  `mc admin config set myminio notify_webhook:1 endpoint=http://peertube-ingest:4005/webhooks/minio`).
- **Batch** : `node dist/batch.js [--since=<ISO8601>]`, a executer en cron quotidien
  (etude 2.12 ligne 589 : "ce depot peut se faire en tache periodique -- batch quotidien --
  plus simple a operer, sans risque meme en cas de panne temporaire du connecteur"). Sans
  `--since`, balaie les 25 dernieres heures (marge de securite sur un cron quotidien).

## Metadonnees de reunion

`src/metadata.ts` extrait titre/date/participants du nom d'objet MinIO, avec une
convention `<date-ISO>_<titre-slug>_<participants-slugs>.<ext>` (a configurer au niveau
de la regle d'export LiveKit Egress). Les tags S3 `meeting-title`/`meeting-date`/
`meeting-participants`, s'ils sont presents sur l'objet, sont prioritaires sur ce qui est
deduit du nom de fichier.

## Endpoints / scripts

| | | |
|---|---|---|
| POST | `/webhooks/minio` | Mode temps reel, evenement `ObjectCreated` MinIO |
| GET | `/healthz` | Sonde de sante |
| script | `dist/batch.js` | Mode batch, a planifier en cron |

## Variables d'environnement

| Variable | Defaut | Description |
|---|---|---|
| `PORT` | `4005` | Port d'ecoute HTTP (mode webhook) |
| `MINIO_ENDPOINT` | `https://minio.example.org` | Endpoint S3-compatible MinIO |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | (vide) | Identifiants MinIO |
| `MINIO_RECORDINGS_BUCKET` | `visio-recordings` | Bucket cible de LiveKit Egress |
| `PEERTUBE_BASE_URL` | `https://tube.example.org` | URL de l'instance PeerTube |
| `PEERTUBE_ACCESS_TOKEN` | (vide) | Token OAuth PeerTube (compte de service) |
| `PEERTUBE_CHANNEL_ID` | `1` | Chaine PeerTube cible |
| `PEERTUBE_DEFAULT_PRIVACY` | `2` (interne) | Visibilite par defaut des videos deposees |

## Developpement

```bash
npm install
npm test
npm run build
npm start        # mode webhook
npm run batch     # mode batch, une execution
```

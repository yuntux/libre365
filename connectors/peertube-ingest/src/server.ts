import express, { Request, Response } from "express";
import { filterVideoObjects, ingestAll } from "./ingest";
import { getObjectStream, getObjectTags } from "./minio-client";
import { uploadToPeerTube } from "./peertube-client";
import { IngestCandidate, MinioObjectCreatedEvent } from "./types";

const app = express();
app.use(express.json({ limit: "1mb" }));

const PORT = Number(process.env.PORT ?? 4005);

/**
 * Real-time endpoint: MinIO can be configured to publish its `s3:ObjectCreated:*`
 * notifications to a webhook ("webhook"-type bucket notification target,
 * see `mc admin config set myminio notify_webhook`) -- study 2.12 line 589.
 */
app.post("/webhooks/minio", async (req: Request, res: Response) => {
  const event = req.body as MinioObjectCreatedEvent;
  const records = event.Records ?? [];

  const candidates: IngestCandidate[] = records
    .filter((r) => (r.eventName ?? "").startsWith("s3:ObjectCreated"))
    .map((r) => ({
      bucket: r.s3?.bucket?.name ?? "",
      key: r.s3?.object?.key ?? "",
      size: r.s3?.object?.size ?? 0,
      lastModified: new Date().toISOString(),
    }))
    .filter((c) => c.bucket && c.key);

  const videoCandidates = filterVideoObjects(candidates);
  const results = await ingestAll(videoCandidates, {
    getObjectTags,
    getObjectStream,
    uploadToPeerTube,
  });

  res.status(200).json({ processed: results.length, results });
});

app.get("/healthz", (_req: Request, res: Response) => {
  res.status(200).json({ status: "ok" });
});

if (require.main === module) {
  app.listen(PORT, () => {
    // eslint-disable-next-line no-console
    console.log(`peertube-ingest listening on :${PORT}`);
  });
}

export { app };

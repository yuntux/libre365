import express, { Request, Response } from "express";
import {
  normalizeGrommunioEvent,
  normalizeMatrixEvent,
  normalizeOnlyOfficeMentionEvent,
  normalizeSeafileEvent,
  normalizeVikunjaEvent,
} from "./normalize";
import { triggerNovuNotification } from "./novu-client";
import { NormalizedEvent } from "./types";

const app = express();
app.use(express.json({ limit: "1mb" }));

const PORT = Number(process.env.PORT ?? 4001);

async function handleNormalized(
  res: Response,
  events: NormalizedEvent[] | NormalizedEvent | null
): Promise<void> {
  const list = events === null ? [] : Array.isArray(events) ? events : [events];
  if (list.length === 0) {
    res.status(202).json({ relayed: 0, reason: "event ignored (not actionable)" });
    return;
  }
  const results = await Promise.allSettled(list.map((e) => triggerNovuNotification(e)));
  res.status(200).json({
    relayed: results.filter((r) => r.status === "fulfilled").length,
    total: list.length,
  });
}

app.post("/webhooks/matrix", async (req: Request, res: Response) => {
  await handleNormalized(res, normalizeMatrixEvent(req.body));
});

app.post("/webhooks/grommunio", async (req: Request, res: Response) => {
  await handleNormalized(res, normalizeGrommunioEvent(req.body));
});

app.post("/webhooks/seafile", async (req: Request, res: Response) => {
  await handleNormalized(res, normalizeSeafileEvent(req.body));
});

app.post("/webhooks/vikunja", async (req: Request, res: Response) => {
  await handleNormalized(res, normalizeVikunjaEvent(req.body));
});

// OnlyOffice `onRequestSendNotify` entry point, relayed here by connectors/onlyoffice-mentions
// (study 2.7 line 487: "this connector joins the list of those to be developed in 2.1").
app.post("/webhooks/onlyoffice-mention", async (req: Request, res: Response) => {
  await handleNormalized(res, normalizeOnlyOfficeMentionEvent(req.body));
});

app.get("/healthz", (_req: Request, res: Response) => {
  res.status(200).json({ status: "ok" });
});

if (require.main === module) {
  app.listen(PORT, () => {
    // eslint-disable-next-line no-console
    console.log(`notification-hub listening on :${PORT}`);
  });
}

export { app };

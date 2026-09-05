import express, { Request, Response } from "express";
import { consolidatePresence } from "./consolidate";
import { getMatrixPresence } from "./sources/matrix-presence";
import { getGrommunioAvailability } from "./sources/grommunio-ews";
import { getLiveKitPresence } from "./sources/livekit-presence";
import { ConsolidatedPresence, PresenceSources } from "./types";

const app = express();
const PORT = Number(process.env.PORT ?? 4003);
// Intervalle de rafraichissement du flux SSE (etude 2.8 : bandeau du portail 2.3).
const STREAM_INTERVAL_MS = Number(process.env.PRESENCE_STREAM_INTERVAL_MS ?? 5000);

async function buildConsolidatedPresence(userId: string): Promise<ConsolidatedPresence> {
  const [matrix, grommunio, livekit] = await Promise.all([
    getMatrixPresence(userId).catch(() => null),
    getGrommunioAvailability(userId).catch(() => null),
    getLiveKitPresence(userId).catch(() => null),
  ]);

  const sources: PresenceSources = { matrix, grommunio, livekit };
  return {
    userId,
    status: consolidatePresence(sources),
    sources,
    updatedAt: new Date().toISOString(),
  };
}

app.get("/presence/:userId", async (req: Request, res: Response) => {
  const presence = await buildConsolidatedPresence(req.params.userId);
  res.status(200).json(presence);
});

// Server-Sent Events pour le bandeau du portail applicatif (etude 2.3, 2.8).
app.get("/presence/stream", (req: Request, res: Response) => {
  const userIds = String(req.query.userIds ?? "")
    .split(",")
    .map((u) => u.trim())
    .filter(Boolean);

  if (userIds.length === 0) {
    res.status(400).json({ error: "missing query parameter 'userIds' (comma-separated)" });
    return;
  }

  res.writeHead(200, {
    "Content-Type": "text/event-stream",
    "Cache-Control": "no-cache",
    Connection: "keep-alive",
  });

  let closed = false;
  req.on("close", () => {
    closed = true;
  });

  const pushOnce = async () => {
    if (closed) return;
    const presences = await Promise.all(userIds.map((id) => buildConsolidatedPresence(id)));
    res.write(`data: ${JSON.stringify(presences)}\n\n`);
  };

  pushOnce();
  const interval = setInterval(pushOnce, STREAM_INTERVAL_MS);
  req.on("close", () => clearInterval(interval));
});

app.get("/healthz", (_req: Request, res: Response) => {
  res.status(200).json({ status: "ok" });
});

if (require.main === module) {
  app.listen(PORT, () => {
    // eslint-disable-next-line no-console
    console.log(`presence-aggregator listening on :${PORT}`);
  });
}

export { app };

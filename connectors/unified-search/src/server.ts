import express, { Request, Response } from "express";
import { fanOutSearch, mergeResults } from "./fanout";
import { searchMatrix } from "./sources/matrix";
import { searchSeafile } from "./sources/seafile";
import { searchVikunja } from "./sources/vikunja";
import { searchGrommunio } from "./sources/grommunio";

const app = express();
const PORT = Number(process.env.PORT ?? 4002);
const TIMEOUT_MS = Number(process.env.SEARCH_TIMEOUT_MS ?? 2000);

app.get("/search", async (req: Request, res: Response) => {
  const query = String(req.query.q ?? "").trim();
  if (!query) {
    res.status(400).json({ error: "missing query parameter 'q'" });
    return;
  }

  // Le token Bearer Keycloak de l'utilisateur est relaye tel quel a chaque service
  // source (etude 2.2 ligne 391, 394) : ce connecteur ne s'authentifie jamais lui-meme
  // aupres de Matrix/Seafile/Vikunja/Grommunio a la place de l'utilisateur.
  const authHeader = req.header("authorization") ?? "";
  const userToken = authHeader.replace(/^Bearer\s+/i, "");
  if (!userToken) {
    res.status(401).json({ error: "missing Authorization: Bearer <token> header" });
    return;
  }

  const outcomes = await fanOutSearch(
    query,
    userToken,
    {
      matrix: searchMatrix,
      seafile: searchSeafile,
      vikunja: searchVikunja,
      grommunio: searchGrommunio,
    },
    TIMEOUT_MS
  );

  res.status(200).json({
    query,
    sources: outcomes.map((o) => ({
      source: o.source,
      ok: o.ok,
      tookMs: o.tookMs,
      error: o.error,
      count: o.results.length,
    })),
    results: mergeResults(outcomes),
  });
});

app.get("/healthz", (_req: Request, res: Response) => {
  res.status(200).json({ status: "ok" });
});

if (require.main === module) {
  app.listen(PORT, () => {
    // eslint-disable-next-line no-console
    console.log(`unified-search listening on :${PORT}`);
  });
}

export { app };

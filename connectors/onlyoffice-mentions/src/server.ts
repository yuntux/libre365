import express, { Request, Response } from "express";
import { listRealmUsers } from "./directory-client";
import { toNotificationHubPayload, toOnlyOfficeUserList } from "./transform";

const app = express();
app.use(express.json({ limit: "1mb" }));

const PORT = Number(process.env.PORT ?? 4004);
const NOTIFICATION_HUB_URL =
  process.env.NOTIFICATION_HUB_URL ?? "http://notification-hub:4001";

/**
 * Endpoint appele par OnlyOffice Document Server pour lister les utilisateurs proposes
 * a la frappe de `@`/`+` dans un commentaire (etude 2.7 ligne 484).
 */
app.get("/onlyoffice/request-users", async (_req: Request, res: Response) => {
  try {
    const users = await listRealmUsers();
    res.status(200).json({ users: toOnlyOfficeUserList(users) });
  } catch (err) {
    res.status(502).json({ error: err instanceof Error ? err.message : String(err) });
  }
});

/**
 * Endpoint appele par OnlyOffice quand un commentaire mentionnant quelqu'un est soumis
 * (etude 2.7 ligne 484 : `onRequestSendNotify`). Transmet chaque mention au centre de
 * notifications unifie (notification-hub, etude 2.1/2.7 ligne 487).
 */
app.post("/onlyoffice/request-send-notify", async (req: Request, res: Response) => {
  const forwarded = toNotificationHubPayload(req.body);
  if (!forwarded) {
    res.status(202).json({ relayed: false, reason: "no mentioned emails in payload" });
    return;
  }

  try {
    const response = await fetch(`${NOTIFICATION_HUB_URL}/webhooks/onlyoffice-mention`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(forwarded),
    });
    res.status(200).json({ relayed: response.ok, notificationHubStatus: response.status });
  } catch (err) {
    res.status(502).json({ relayed: false, error: err instanceof Error ? err.message : String(err) });
  }
});

app.get("/healthz", (_req: Request, res: Response) => {
  res.status(200).json({ status: "ok" });
});

if (require.main === module) {
  app.listen(PORT, () => {
    // eslint-disable-next-line no-console
    console.log(`onlyoffice-mentions listening on :${PORT}`);
  });
}

export { app };

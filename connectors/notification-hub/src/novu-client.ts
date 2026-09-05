import { NormalizedEvent } from "./types";

/**
 * Relais vers l'API Novu via appel REST direct plutot que le SDK @novu/node,
 * pour eviter une dependance lourde dans ce connecteur mince (etude 2.1 ligne 382 :
 * "Novu pour l'UI de centre de notif ... alimente par des connecteurs custom").
 */
const NOVU_API_URL = process.env.NOVU_API_URL ?? "https://api.novu.co/v1";
const NOVU_API_KEY = process.env.NOVU_API_KEY ?? "";
// Workflow trigger identifier configure cote Novu, commun a toutes les sources.
const NOVU_WORKFLOW_ID = process.env.NOVU_WORKFLOW_ID ?? "open365-unified-notification";

export interface NovuTriggerResult {
  ok: boolean;
  status: number;
  body?: unknown;
}

export async function triggerNovuNotification(
  event: NormalizedEvent,
  fetchImpl: typeof fetch = fetch
): Promise<NovuTriggerResult> {
  const response = await fetchImpl(`${NOVU_API_URL}/events/trigger`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `ApiKey ${NOVU_API_KEY}`,
    },
    body: JSON.stringify({
      name: NOVU_WORKFLOW_ID,
      to: { subscriberId: event.userId },
      payload: {
        source: event.source,
        eventType: event.eventType,
        title: event.title,
        body: event.body,
        actionUrl: event.actionUrl,
        timestamp: event.timestamp,
      },
    }),
  });

  let body: unknown;
  try {
    body = await response.json();
  } catch {
    body = undefined;
  }

  return { ok: response.ok, status: response.status, body };
}

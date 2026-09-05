import { NormalizedEvent } from "./types";

/**
 * Relay to the Novu API via a direct REST call rather than the @novu/node SDK,
 * to avoid a heavy dependency in this thin connector (study 2.1 line 382:
 * "Novu for the notification center UI ... fed by custom connectors").
 */
const NOVU_API_URL = process.env.NOVU_API_URL ?? "https://api.novu.co/v1";
const NOVU_API_KEY = process.env.NOVU_API_KEY ?? "";
// Workflow trigger identifier configured on the Novu side, shared by all sources.
const NOVU_WORKFLOW_ID = process.env.NOVU_WORKFLOW_ID ?? "libre365-unified-notification";

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

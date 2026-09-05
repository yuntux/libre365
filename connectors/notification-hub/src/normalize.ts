import {
  GrommunioWebhookPayload,
  MatrixWebhookPayload,
  NormalizedEvent,
  OnlyOfficeMentionPayload,
  SeafileWebhookPayload,
  VikunjaWebhookPayload,
} from "./types";

/**
 * Pure normalization functions, one per source (study 2.1 line 379:
 * "a connector per service is needed to translate each event").
 * Deliberately free of side effects / network calls to stay unit-testable.
 */

function nowIso(): string {
  return new Date().toISOString();
}

/** Normalizes a Matrix Application Service event (text message or mention). */
export function normalizeMatrixEvent(payload: MatrixWebhookPayload): NormalizedEvent | null {
  if (!payload || payload.type !== "m.room.message") {
    return null;
  }
  const mentioned = payload.content?.["m.mentions"]?.user_ids ?? [];
  const targetUser = payload.target_user_id ?? mentioned[0];
  if (!targetUser) {
    return null;
  }
  const body = payload.content?.body ?? "(empty message)";
  const sender = payload.sender ?? "a user";
  return {
    source: "matrix",
    eventType: mentioned.length > 0 ? "mention" : "message",
    userId: targetUser,
    title: `New message from ${sender}`,
    body: body.length > 280 ? `${body.slice(0, 277)}...` : body,
    actionUrl: payload.room_id
      ? `https://element.example.org/#/room/${payload.room_id}${payload.event_id ? `/${payload.event_id}` : ""}`
      : "https://element.example.org",
    timestamp: payload.origin_server_ts
      ? new Date(payload.origin_server_ts).toISOString()
      : nowIso(),
  };
}

/** Normalizes a Grommunio event (new mail received). */
export function normalizeGrommunioEvent(payload: GrommunioWebhookPayload): NormalizedEvent | null {
  if (!payload || !payload.mailboxUser) {
    return null;
  }
  return {
    source: "grommunio",
    eventType: payload.event ?? "new_mail",
    userId: payload.mailboxUser,
    title: payload.subject ? `New mail: ${payload.subject}` : "New mail",
    body: payload.preview ?? payload.from ?? "",
    actionUrl:
      payload.webUrl ??
      (payload.messageId
        ? `https://mail.example.org/webapp/index.html#eml=${encodeURIComponent(payload.messageId)}`
        : "https://mail.example.org"),
    timestamp: payload.receivedAt ?? nowIso(),
  };
}

/** Normalizes a Seafile event (file/folder share). */
export function normalizeSeafileEvent(payload: SeafileWebhookPayload): NormalizedEvent | null {
  if (!payload || !payload.to_user) {
    return null;
  }
  const fileName = payload.path ? payload.path.split("/").pop() : payload.repo_name;
  return {
    source: "seafile",
    eventType: payload.event_type ?? "file-shared",
    userId: payload.to_user,
    title: `File shared: ${fileName ?? "document"}`,
    body: payload.from_user ? `Shared by ${payload.from_user}` : "",
    actionUrl:
      payload.url ??
      `https://seafile.example.org/library/${payload.repo_id ?? ""}${payload.path ?? ""}`,
    timestamp: payload.timestamp ?? nowIso(),
  };
}

/** Normalizes a Vikunja event (task assigned). */
export function normalizeVikunjaEvent(payload: VikunjaWebhookPayload): NormalizedEvent | null {
  if (!payload) {
    return null;
  }
  const assignee = payload.assignee?.username;
  if (!assignee) {
    return null;
  }
  const task = payload.data?.task;
  return {
    source: "vikunja",
    eventType: payload.event_name ?? "task.assigned",
    userId: assignee,
    title: task?.title ? `Task assigned: ${task.title}` : "New task assigned",
    body: payload.data?.doer?.username ? `Assigned by ${payload.data.doer.username}` : "",
    actionUrl: task?.id
      ? `https://vikunja.example.org/tasks/${task.id}`
      : "https://vikunja.example.org",
    timestamp: payload.time ?? nowIso(),
  };
}

/**
 * Normalizes an OnlyOffice mention (`onRequestSendNotify`, study 2.7 line 484).
 * One normalized event is emitted per mentioned email address (0..n), so this function
 * returns an array rather than a single event.
 */
export function normalizeOnlyOfficeMentionEvent(
  payload: OnlyOfficeMentionPayload
): NormalizedEvent[] {
  if (!payload || !payload.emails || payload.emails.length === 0) {
    return [];
  }
  const documentTitle = payload.document?.title ?? "a document";
  return payload.emails.map((email) => ({
    source: "onlyoffice" as const,
    eventType: "mention",
    userId: email,
    title: `You were mentioned in ${documentTitle}`,
    body: payload.comment ?? "",
    actionUrl: payload.actionLink ?? "https://office.example.org",
    timestamp: payload.timestamp ?? nowIso(),
  }));
}

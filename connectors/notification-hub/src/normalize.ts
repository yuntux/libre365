import {
  GrommunioWebhookPayload,
  MatrixWebhookPayload,
  NormalizedEvent,
  OnlyOfficeMentionPayload,
  SeafileWebhookPayload,
  VikunjaWebhookPayload,
} from "./types";

/**
 * Fonctions pures de normalisation, une par source (etude 2.1 ligne 379 :
 * "un connecteur par service est necessaire pour traduire chaque evenement").
 * Volontairement sans effet de bord / sans appel reseau pour rester testables unitairement.
 */

function nowIso(): string {
  return new Date().toISOString();
}

/** Normalise un evenement Matrix Application Service (message texte ou mention). */
export function normalizeMatrixEvent(payload: MatrixWebhookPayload): NormalizedEvent | null {
  if (!payload || payload.type !== "m.room.message") {
    return null;
  }
  const mentioned = payload.content?.["m.mentions"]?.user_ids ?? [];
  const targetUser = payload.target_user_id ?? mentioned[0];
  if (!targetUser) {
    return null;
  }
  const body = payload.content?.body ?? "(message sans contenu)";
  const sender = payload.sender ?? "un utilisateur";
  return {
    source: "matrix",
    eventType: mentioned.length > 0 ? "mention" : "message",
    userId: targetUser,
    title: `Nouveau message de ${sender}`,
    body: body.length > 280 ? `${body.slice(0, 277)}...` : body,
    actionUrl: payload.room_id
      ? `https://element.example.org/#/room/${payload.room_id}${payload.event_id ? `/${payload.event_id}` : ""}`
      : "https://element.example.org",
    timestamp: payload.origin_server_ts
      ? new Date(payload.origin_server_ts).toISOString()
      : nowIso(),
  };
}

/** Normalise un evenement Grommunio (nouveau mail recu). */
export function normalizeGrommunioEvent(payload: GrommunioWebhookPayload): NormalizedEvent | null {
  if (!payload || !payload.mailboxUser) {
    return null;
  }
  return {
    source: "grommunio",
    eventType: payload.event ?? "new_mail",
    userId: payload.mailboxUser,
    title: payload.subject ? `Nouveau mail : ${payload.subject}` : "Nouveau mail",
    body: payload.preview ?? payload.from ?? "",
    actionUrl:
      payload.webUrl ??
      (payload.messageId
        ? `https://mail.example.org/webapp/index.html#eml=${encodeURIComponent(payload.messageId)}`
        : "https://mail.example.org"),
    timestamp: payload.receivedAt ?? nowIso(),
  };
}

/** Normalise un evenement Seafile (partage de fichier/dossier). */
export function normalizeSeafileEvent(payload: SeafileWebhookPayload): NormalizedEvent | null {
  if (!payload || !payload.to_user) {
    return null;
  }
  const fileName = payload.path ? payload.path.split("/").pop() : payload.repo_name;
  return {
    source: "seafile",
    eventType: payload.event_type ?? "file-shared",
    userId: payload.to_user,
    title: `Fichier partage : ${fileName ?? "document"}`,
    body: payload.from_user ? `Partage par ${payload.from_user}` : "",
    actionUrl:
      payload.url ??
      `https://seafile.example.org/library/${payload.repo_id ?? ""}${payload.path ?? ""}`,
    timestamp: payload.timestamp ?? nowIso(),
  };
}

/** Normalise un evenement Vikunja (tache assignee). */
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
    title: task?.title ? `Tache assignee : ${task.title}` : "Nouvelle tache assignee",
    body: payload.data?.doer?.username ? `Assignee par ${payload.data.doer.username}` : "",
    actionUrl: task?.id
      ? `https://vikunja.example.org/tasks/${task.id}`
      : "https://vikunja.example.org",
    timestamp: payload.time ?? nowIso(),
  };
}

/**
 * Normalise une mention OnlyOffice (`onRequestSendNotify`, etude 2.7 ligne 484).
 * Un evenement normalise est emis par email mentionne (0..n), donc cette fonction
 * retourne un tableau plutot qu'un evenement unique.
 */
export function normalizeOnlyOfficeMentionEvent(
  payload: OnlyOfficeMentionPayload
): NormalizedEvent[] {
  if (!payload || !payload.emails || payload.emails.length === 0) {
    return [];
  }
  const documentTitle = payload.document?.title ?? "un document";
  return payload.emails.map((email) => ({
    source: "onlyoffice" as const,
    eventType: "mention",
    userId: email,
    title: `Vous avez ete mentionne dans ${documentTitle}`,
    body: payload.comment ?? "",
    actionUrl: payload.actionLink ?? "https://office.example.org",
    timestamp: payload.timestamp ?? nowIso(),
  }));
}

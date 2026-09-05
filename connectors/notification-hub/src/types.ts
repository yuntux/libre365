/**
 * Format commun de notification, cf. etude 2.1 ligne 368 :
 * "Un point d'entree unique agregeant les notifications de tous les services".
 * Chaque connecteur source normalise vers cette forme avant relais vers Novu.
 */
export interface NormalizedEvent {
  source: "matrix" | "grommunio" | "seafile" | "vikunja" | "onlyoffice";
  eventType: string;
  userId: string;
  title: string;
  body: string;
  actionUrl: string;
  timestamp: string;
}

/** Charge utile brute du webhook Matrix Application Service (transaction PDU-like). */
export interface MatrixWebhookPayload {
  type?: string;
  room_id?: string;
  event_id?: string;
  sender?: string;
  state_key?: string;
  origin_server_ts?: number;
  content?: {
    body?: string;
    msgtype?: string;
    "m.mentions"?: { user_ids?: string[] };
  };
  target_user_id?: string;
}

/** Charge utile de webhook Grommunio (evenement nouveau mail simplifie). */
export interface GrommunioWebhookPayload {
  event?: string;
  mailboxUser?: string;
  messageId?: string;
  subject?: string;
  from?: string;
  preview?: string;
  receivedAt?: string;
  webUrl?: string;
}

/** Charge utile de webhook Seafile (evenement de partage de fichier). */
export interface SeafileWebhookPayload {
  event_type?: string;
  repo_id?: string;
  repo_name?: string;
  path?: string;
  to_user?: string;
  from_user?: string;
  timestamp?: string;
  url?: string;
}

/** Charge utile de webhook Vikunja (assignation de tache). */
export interface VikunjaWebhookPayload {
  event_name?: string;
  data?: {
    task?: {
      id?: number;
      title?: string;
      project_id?: number;
    };
    doer?: {
      username?: string;
    };
  };
  assignee?: {
    username?: string;
  };
  time?: string;
}

/**
 * Charge utile OnlyOffice `onRequestSendNotify` (etude 2.7 ligne 484) :
 * message, emails mentionnes, et lien d'action vers la position du commentaire.
 */
export interface OnlyOfficeMentionPayload {
  actionLink?: string;
  comment?: string;
  document?: {
    title?: string;
    fileType?: string;
  };
  emails?: string[];
  fileId?: string;
  timestamp?: string;
  users?: string[];
}

/**
 * Common notification format, see study 2.1 line 368:
 * "A single entry point aggregating notifications from all services".
 * Each source connector normalizes to this shape before relaying to Novu.
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

/** Raw Matrix Application Service webhook payload (PDU-like transaction). */
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

/** Grommunio webhook payload (simplified new-mail event). */
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

/** Seafile webhook payload (file share event). */
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

/** Vikunja webhook payload (task assignment). */
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
 * OnlyOffice `onRequestSendNotify` payload (study 2.7 line 484):
 * message, mentioned emails, and action link to the comment's position.
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

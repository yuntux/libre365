import { DirectoryUser, OnlyOfficeUserEntry, OnRequestSendNotifyPayload } from "./types";

/**
 * Transforms the directory (Keycloak Admin API) into the format expected by OnlyOffice
 * for `onRequestUsers` (study 2.7 line 484: "list of users suggested when typing
 * the +/@ character"). Pure function, testable without a network call.
 */
export function toOnlyOfficeUserList(users: DirectoryUser[]): OnlyOfficeUserEntry[] {
  return users
    .filter((u) => Boolean(u.email))
    .map((u) => ({
      id: u.id,
      name: [u.firstName, u.lastName].filter(Boolean).join(" ") || u.username,
      email: u.email,
    }));
}

/**
 * Builds the payload expected by `notification-hub` (`POST /webhooks/onlyoffice-mention`,
 * see connectors/notification-hub/src/types.ts `OnlyOfficeMentionPayload`) from
 * the native OnlyOffice `onRequestSendNotify` event (study 2.7 line 487).
 */
export function toNotificationHubPayload(payload: OnRequestSendNotifyPayload): {
  actionLink?: string;
  comment?: string;
  document?: { title?: string; fileType?: string };
  emails: string[];
  fileId?: string;
  timestamp: string;
} | null {
  if (!payload || !payload.emails || payload.emails.length === 0) {
    return null;
  }
  return {
    actionLink: payload.actionLink,
    comment: payload.message,
    document: payload.document,
    emails: payload.emails,
    fileId: payload.fileId,
    timestamp: new Date().toISOString(),
  };
}

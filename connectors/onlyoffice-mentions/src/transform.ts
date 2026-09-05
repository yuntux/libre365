import { DirectoryUser, OnlyOfficeUserEntry, OnRequestSendNotifyPayload } from "./types";

/**
 * Transforme l'annuaire (Keycloak Admin API) au format attendu par OnlyOffice pour
 * `onRequestUsers` (etude 2.7 ligne 484 : "liste des utilisateurs proposes a la frappe
 * du signe +/@"). Fonction pure, testable sans appel reseau.
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
 * Construit le payload attendu par `notification-hub` (`POST /webhooks/onlyoffice-mention`,
 * cf. connectors/notification-hub/src/types.ts `OnlyOfficeMentionPayload`) a partir de
 * l'evenement natif OnlyOffice `onRequestSendNotify` (etude 2.7 ligne 487).
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

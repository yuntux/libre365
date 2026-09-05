/** Directory user (Keycloak Admin API), minimal shape used here. */
export interface DirectoryUser {
  id: string;
  username: string;
  email: string;
  firstName?: string;
  lastName?: string;
}

/** Shape expected by OnlyOffice Document Server in response to `onRequestUsers`. */
export interface OnlyOfficeUserEntry {
  id: string;
  name: string;
  email: string;
}

/**
 * Payload sent by OnlyOffice to `onRequestSendNotify` (study 2.7 line 484):
 * comment message, mentioned emails, action link to the exact position
 * of the comment in the document.
 */
export interface OnRequestSendNotifyPayload {
  actionLink?: string;
  message?: string;
  emails?: string[];
  document?: { title?: string; fileType?: string };
  fileId?: string;
}

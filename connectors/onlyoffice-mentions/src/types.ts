/** Utilisateur de l'annuaire (Keycloak Admin API), forme minimale utilisee ici. */
export interface DirectoryUser {
  id: string;
  username: string;
  email: string;
  firstName?: string;
  lastName?: string;
}

/** Forme attendue par OnlyOffice Document Server en reponse a `onRequestUsers`. */
export interface OnlyOfficeUserEntry {
  id: string;
  name: string;
  email: string;
}

/**
 * Charge utile envoyee par OnlyOffice a `onRequestSendNotify` (etude 2.7 ligne 484) :
 * message du commentaire, emails mentionnes, lien d'action vers la position exacte
 * du commentaire dans le document.
 */
export interface OnRequestSendNotifyPayload {
  actionLink?: string;
  message?: string;
  emails?: string[];
  document?: { title?: string; fileType?: string };
  fileId?: string;
}

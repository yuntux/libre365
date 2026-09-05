import { SearchResultItem } from "../types";

const IMAP_HOST = process.env.GROMMUNIO_IMAP_HOST ?? "mail.example.org";
const IMAP_PORT = Number(process.env.GROMMUNIO_IMAP_PORT ?? 993);

/**
 * Recherche mail via IMAP SEARCH cote Grommunio (etude 2.2 ligne 391).
 *
 * Grommunio n'expose pas d'API REST de recherche generique comme Matrix/Seafile/Vikunja :
 * IMAP est le protocole a interroger. Le "token" relaye ici n'est PAS un JWT Keycloak
 * passe a IMAP (IMAP ne parle pas OAuth Bearer nativement) mais un jeton d'acces XOAUTH2
 * echangeable via SASL, cf. RFC 7628 - Grommunio (comme la plupart des serveurs IMAP
 * modernes) supporte l'authentification XOAUTH2 en relayant le meme token Keycloak
 * emis pour l'utilisateur, ce qui respecte l'esprit de la ligne 391 (pas de
 * re-authentification/compte de service cote connecteur) sans reinventer le protocole IMAP.
 *
 * Implementation simplifiee : la lib `imapflow` (a ajouter en dependance de production)
 * permettrait une connexion IMAP complete. Ici, la structure de l'appel et le parsing
 * des resultats sont poses, mais l'ouverture de connexion IMAP reelle est laissee en
 * TODO explicite pour rester dans le perimetre "au moins l'appel et la structure du
 * connecteur meme si le parsing IMAP reel est simplifie" (consigne de la tache).
 */
export async function searchGrommunio(
  query: string,
  userToken: string
): Promise<SearchResultItem[]> {
  // TODO(imapflow): remplacer ce stub par une vraie connexion IMAP.
  //
  // import { ImapFlow } from "imapflow";
  // const client = new ImapFlow({
  //   host: IMAP_HOST,
  //   port: IMAP_PORT,
  //   secure: true,
  //   auth: { user: extractUserFromToken(userToken), accessToken: userToken },
  // });
  // await client.connect();
  // const lock = await client.getMailboxLock("INBOX");
  // try {
  //   const uids = await client.search({ body: query });
  //   const results: SearchResultItem[] = [];
  //   for await (const message of client.fetch(uids, { envelope: true, uid: true })) {
  //     results.push({
  //       source: "grommunio",
  //       id: String(message.uid),
  //       title: message.envelope?.subject ?? "(sans objet)",
  //       url: `https://mail.example.org/webapp/index.html#eml=${message.uid}`,
  //       timestamp: message.envelope?.date?.toISOString(),
  //     });
  //   }
  //   return results;
  // } finally {
  //   lock.release();
  //   await client.logout();
  // }

  if (!userToken) {
    throw new Error("missing user token for IMAP XOAUTH2 authentication");
  }

  // Simule l'appel reseau (latence + connexion IMAP) pour permettre au fan-out global
  // et a ses timeouts d'etre exerces de bout en bout meme sans serveur IMAP disponible.
  await new Promise((resolve) => setTimeout(resolve, 10));

  return [
    {
      source: "grommunio",
      id: "stub-imap-result",
      title: `Resultat IMAP simule pour "${query}" (host: ${IMAP_HOST}:${IMAP_PORT})`,
      url: "https://mail.example.org/webapp/",
      timestamp: undefined,
    },
  ];
}

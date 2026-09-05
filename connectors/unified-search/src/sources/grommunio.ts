import { SearchResultItem } from "../types";

const IMAP_HOST = process.env.GROMMUNIO_IMAP_HOST ?? "mail.example.org";
const IMAP_PORT = Number(process.env.GROMMUNIO_IMAP_PORT ?? 993);

/**
 * Mail search via IMAP SEARCH on the Grommunio side (study 2.2 line 391).
 *
 * Grommunio does not expose a generic REST search API like Matrix/Seafile/Vikunja:
 * IMAP is the protocol to query. The "token" relayed here is NOT a Keycloak JWT
 * passed directly to IMAP (IMAP does not speak OAuth Bearer natively) but an
 * XOAUTH2 access token exchangeable via SASL, see RFC 7628 - Grommunio (like most
 * modern IMAP servers) supports XOAUTH2 authentication by relaying the same
 * Keycloak token issued for the user, which respects the spirit of line 391 (no
 * re-authentication/service account on the connector side) without reinventing
 * the IMAP protocol.
 *
 * Simplified implementation: the `imapflow` library (to be added as a production
 * dependency) would allow a full IMAP connection. Here, the structure of the call
 * and the result parsing are laid out, but the actual IMAP connection is left as
 * an explicit TODO, staying within the scope of "at least the call and the
 * connector's structure, even if the actual IMAP parsing is simplified" (task
 * instruction).
 */
export async function searchGrommunio(
  query: string,
  userToken: string
): Promise<SearchResultItem[]> {
  // TODO(imapflow): replace this stub with a real IMAP connection.
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
  //       title: message.envelope?.subject ?? "(no subject)",
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

  // Simulates the network call (latency + IMAP connection) so the overall
  // fan-out and its timeouts can be exercised end to end even without an
  // available IMAP server.
  await new Promise((resolve) => setTimeout(resolve, 10));

  return [
    {
      source: "grommunio",
      id: "stub-imap-result",
      title: `Simulated IMAP result for "${query}" (host: ${IMAP_HOST}:${IMAP_PORT})`,
      url: "https://mail.example.org/webapp/",
      timestamp: undefined,
    },
  ];
}

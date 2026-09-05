import { DirectoryUser } from "./types";

const KEYCLOAK_BASE_URL = process.env.KEYCLOAK_BASE_URL ?? "https://auth.example.org";
const KEYCLOAK_REALM = process.env.KEYCLOAK_REALM ?? "libre365";
const KEYCLOAK_ADMIN_TOKEN = process.env.KEYCLOAK_ADMIN_TOKEN ?? "";

/**
 * Stub simple d'annuaire via l'API Admin Keycloak (etude 2.7 : "onRequestUsers doit
 * interroger l'annuaire -- stub simple : Keycloak Admin API pour lister les
 * utilisateurs du realm"). Un service-account Keycloak avec le role `view-users`
 * fournit `KEYCLOAK_ADMIN_TOKEN` (client_credentials, non implemente ici pour rester
 * un stub simple -- a completer avec le flux OAuth2 client-credentials en production).
 */
export async function listRealmUsers(fetchImpl: typeof fetch = fetch): Promise<DirectoryUser[]> {
  const response = await fetchImpl(
    `${KEYCLOAK_BASE_URL}/admin/realms/${KEYCLOAK_REALM}/users?max=1000`,
    { headers: { Authorization: `Bearer ${KEYCLOAK_ADMIN_TOKEN}` } }
  );

  if (!response.ok) {
    throw new Error(`Keycloak admin API failed with status ${response.status}`);
  }

  const data = (await response.json()) as Array<{
    id?: string;
    username?: string;
    email?: string;
    firstName?: string;
    lastName?: string;
    enabled?: boolean;
  }>;

  return (data ?? [])
    .filter((u) => u.enabled !== false)
    .map((u) => ({
      id: u.id ?? "",
      username: u.username ?? "",
      email: u.email ?? "",
      firstName: u.firstName,
      lastName: u.lastName,
    }));
}

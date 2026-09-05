import { DirectoryUser } from "./types";

const KEYCLOAK_BASE_URL = process.env.KEYCLOAK_BASE_URL ?? "https://auth.example.org";
const KEYCLOAK_REALM = process.env.KEYCLOAK_REALM ?? "libre365";
const KEYCLOAK_ADMIN_TOKEN = process.env.KEYCLOAK_ADMIN_TOKEN ?? "";

/**
 * Simple directory stub via the Keycloak Admin API (study 2.7: "onRequestUsers must
 * query the directory -- simple stub: Keycloak Admin API to list the
 * realm's users"). A Keycloak service account with the `view-users` role
 * supplies `KEYCLOAK_ADMIN_TOKEN` (client_credentials, not implemented here to stay
 * a simple stub -- to be completed with the OAuth2 client-credentials flow in production).
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

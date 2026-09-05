import { MatrixPresence } from "../types";

const MATRIX_BASE_URL = process.env.MATRIX_BASE_URL ?? "https://matrix.example.org";
// Token for a Matrix service account (Application Service or dedicated "bot" user)
// authorized to read any homeserver user's presence -- unlike unified-search,
// presence is not sensitive data filtered by room ACLs, it is per-user global
// information exposed by the homeserver.
const SERVICE_TOKEN = process.env.MATRIX_SERVICE_TOKEN ?? "";

/** Reads `m.presence` (online/unavailable/offline) via the Matrix client-server API. */
export async function getMatrixPresence(
  userId: string,
  fetchImpl: typeof fetch = fetch
): Promise<MatrixPresence> {
  const response = await fetchImpl(
    `${MATRIX_BASE_URL}/_matrix/client/v3/presence/${encodeURIComponent(userId)}/status`,
    { headers: { Authorization: `Bearer ${SERVICE_TOKEN}` } }
  );

  if (!response.ok) {
    return null;
  }

  const data = (await response.json()) as { presence?: string };
  if (data.presence === "online" || data.presence === "unavailable" || data.presence === "offline") {
    return data.presence;
  }
  return null;
}

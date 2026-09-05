import { MatrixPresence } from "../types";

const MATRIX_BASE_URL = process.env.MATRIX_BASE_URL ?? "https://matrix.example.org";
// Token d'un compte de service Matrix (Application Service ou utilisateur "bot" dedie)
// autorise a consulter la presence de tout utilisateur du homeserver -- a la difference
// d'unified-search, la presence n'est pas une donnee sensible filtree par ACL de room,
// c'est une info globale par utilisateur exposee par le homeserver.
const SERVICE_TOKEN = process.env.MATRIX_SERVICE_TOKEN ?? "";

/** Consulte `m.presence` (online/unavailable/offline) via l'API cliente/serveur Matrix. */
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

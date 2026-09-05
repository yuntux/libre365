import { SearchResultItem } from "../types";

const SEAFILE_BASE_URL = process.env.SEAFILE_BASE_URL ?? "https://seafile.example.org";

/**
 * Interroge l'API de recherche Seafile avec le token de l'utilisateur relaye tel quel
 * (etude 2.2 ligne 391) plutot qu'un compte de service, pour que Seafile applique
 * lui-meme ses permissions sur les bibliotheques/dossiers.
 */
export async function searchSeafile(
  query: string,
  userToken: string,
  fetchImpl: typeof fetch = fetch
): Promise<SearchResultItem[]> {
  const response = await fetchImpl(
    `${SEAFILE_BASE_URL}/api2/search/?q=${encodeURIComponent(query)}`,
    {
      headers: { Authorization: `Bearer ${userToken}` },
    }
  );

  if (!response.ok) {
    throw new Error(`Seafile search failed with status ${response.status}`);
  }

  const data = (await response.json()) as {
    results?: Array<{
      repo_id?: string;
      fullpath?: string;
      name?: string;
      content_highlight?: string;
      last_modified?: number;
    }>;
  };

  return (data.results ?? []).map((r) => ({
    source: "seafile" as const,
    id: `${r.repo_id ?? ""}${r.fullpath ?? ""}`,
    title: r.name ?? r.fullpath ?? "(fichier)",
    snippet: r.content_highlight,
    url: `${SEAFILE_BASE_URL}/lib/${r.repo_id ?? ""}/file${r.fullpath ?? ""}`,
    timestamp: r.last_modified ? new Date(r.last_modified * 1000).toISOString() : undefined,
  }));
}

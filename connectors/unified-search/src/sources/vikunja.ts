import { SearchResultItem } from "../types";

const VIKUNJA_BASE_URL = process.env.VIKUNJA_BASE_URL ?? "https://vikunja.example.org";

/**
 * Interroge l'API Vikunja `tasks/all?s=` avec le token de l'utilisateur relaye tel quel
 * (etude 2.2 ligne 391) : seules les taches des projets auxquels l'utilisateur a acces
 * sont retournees, sans logique de permission dupliquee ici.
 */
export async function searchVikunja(
  query: string,
  userToken: string,
  fetchImpl: typeof fetch = fetch
): Promise<SearchResultItem[]> {
  const response = await fetchImpl(
    `${VIKUNJA_BASE_URL}/api/v1/tasks/all?s=${encodeURIComponent(query)}`,
    {
      headers: { Authorization: `Bearer ${userToken}` },
    }
  );

  if (!response.ok) {
    throw new Error(`Vikunja search failed with status ${response.status}`);
  }

  const data = (await response.json()) as Array<{
    id?: number;
    title?: string;
    description?: string;
    updated?: string;
  }>;

  return (data ?? []).map((task) => ({
    source: "vikunja" as const,
    id: String(task.id ?? ""),
    title: task.title ?? "(tache)",
    snippet: task.description,
    url: `${VIKUNJA_BASE_URL}/tasks/${task.id ?? ""}`,
    timestamp: task.updated,
  }));
}

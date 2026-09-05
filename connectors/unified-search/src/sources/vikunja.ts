import { SearchResultItem } from "../types";

const VIKUNJA_BASE_URL = process.env.VIKUNJA_BASE_URL ?? "https://vikunja.example.org";

/**
 * Queries the Vikunja `tasks/all?s=` API with the user's token relayed as-is
 * (study 2.2 line 391): only tasks from projects the user has access to
 * are returned, with no permission logic duplicated here.
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
    title: task.title ?? "(task)",
    snippet: task.description,
    url: `${VIKUNJA_BASE_URL}/tasks/${task.id ?? ""}`,
    timestamp: task.updated,
  }));
}

import { SearchResultItem } from "../types";

const MATRIX_BASE_URL = process.env.MATRIX_BASE_URL ?? "https://matrix.example.org";

/**
 * Queries the `/search` endpoint of the Matrix Client-Server API, with the user's
 * Bearer token relayed as-is (study 2.2 line 391): Matrix applies its own
 * room visibility rules to the search, no ACL is duplicated here.
 */
export async function searchMatrix(
  query: string,
  userToken: string,
  fetchImpl: typeof fetch = fetch
): Promise<SearchResultItem[]> {
  const response = await fetchImpl(
    `${MATRIX_BASE_URL}/_matrix/client/v3/search`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${userToken}`,
      },
      body: JSON.stringify({
        search_categories: {
          room_events: {
            search_term: query,
            event_context: { before_limit: 0, after_limit: 0 },
          },
        },
      }),
    }
  );

  if (!response.ok) {
    throw new Error(`Matrix search failed with status ${response.status}`);
  }

  const data = (await response.json()) as {
    search_categories?: {
      room_events?: {
        results?: Array<{
          result?: {
            event_id?: string;
            room_id?: string;
            content?: { body?: string };
            origin_server_ts?: number;
          };
        }>;
      };
    };
  };

  const rawResults = data.search_categories?.room_events?.results ?? [];
  return rawResults.map((r) => ({
    source: "matrix" as const,
    id: r.result?.event_id ?? "",
    title: r.result?.content?.body?.slice(0, 80) ?? "(message)",
    snippet: r.result?.content?.body,
    url: `${MATRIX_BASE_URL.replace("https://matrix", "https://element")}/#/room/${
      r.result?.room_id ?? ""
    }/${r.result?.event_id ?? ""}`,
    timestamp: r.result?.origin_server_ts
      ? new Date(r.result.origin_server_ts).toISOString()
      : undefined,
  }));
}

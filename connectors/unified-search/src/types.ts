export interface SearchResultItem {
  source: "matrix" | "seafile" | "vikunja" | "grommunio";
  id: string;
  title: string;
  snippet?: string;
  url: string;
  timestamp?: string;
}

export interface SourceSearchOutcome {
  source: SearchResultItem["source"];
  ok: boolean;
  tookMs: number;
  error?: string;
  results: SearchResultItem[];
}

export interface AggregatedSearchResponse {
  query: string;
  sources: SourceSearchOutcome[];
  results: SearchResultItem[];
}

/**
 * Signature of a per-service search connector. The user's Bearer token
 * is relayed as-is (study 2.2 lines 391, 394): it is the source service that
 * filters according to the user's native permissions, not this connector.
 */
export type SourceSearchFn = (query: string, userToken: string) => Promise<SearchResultItem[]>;

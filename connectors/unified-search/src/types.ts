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
 * Signature d'un connecteur de recherche par service. Le token Bearer de l'utilisateur
 * est relaye tel quel (etude 2.2 ligne 391, 394) : c'est le service source qui filtre
 * selon les permissions natives de l'utilisateur, pas ce connecteur.
 */
export type SourceSearchFn = (query: string, userToken: string) => Promise<SearchResultItem[]>;

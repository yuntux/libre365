import { SourceSearchFn, SourceSearchOutcome, SearchResultItem } from "./types";

/**
 * Coeur du fan-out temps reel (etude 2.2 ligne 395) : chaque service est interroge en
 * parallele avec son propre timeout, de sorte qu'un service en carafe ne bloque pas
 * les autres reponses. Promise.allSettled garantit qu'aucun rejet ne casse l'agregation.
 *
 * Fonction volontairement pure vis-a-vis du reseau : les `sources` sont injectees en
 * parametre, ce qui permet de tester la logique de fan-out/timeout avec des mocks,
 * sans dependre des vraies implementations HTTP/IMAP.
 */
export async function fanOutSearch(
  query: string,
  userToken: string,
  sources: Record<SourceSearchOutcome["source"], SourceSearchFn>,
  timeoutMs = 2000
): Promise<SourceSearchOutcome[]> {
  const entries = Object.entries(sources) as [SourceSearchOutcome["source"], SourceSearchFn][];

  const settled = await Promise.allSettled(
    entries.map(async ([source, fn]) => {
      const start = Date.now();
      const results = await withTimeout(fn(query, userToken), timeoutMs, source);
      return { source, results, tookMs: Date.now() - start };
    })
  );

  return settled.map((outcome, index) => {
    const [source] = entries[index];
    if (outcome.status === "fulfilled") {
      return {
        source,
        ok: true,
        tookMs: outcome.value.tookMs,
        results: outcome.value.results,
      };
    }
    return {
      source,
      ok: false,
      tookMs: timeoutMs,
      error: outcome.reason instanceof Error ? outcome.reason.message : String(outcome.reason),
      results: [] as SearchResultItem[],
    };
  });
}

function withTimeout<T>(promise: Promise<T>, timeoutMs: number, source: string): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => {
      reject(new Error(`timeout after ${timeoutMs}ms querying source "${source}"`));
    }, timeoutMs);

    promise
      .then((value) => {
        clearTimeout(timer);
        resolve(value);
      })
      .catch((err) => {
        clearTimeout(timer);
        reject(err);
      });
  });
}

/** Aplatit les resultats de toutes les sources ayant repondu avec succes, tries par date desc. */
export function mergeResults(outcomes: SourceSearchOutcome[]): SearchResultItem[] {
  return outcomes
    .flatMap((o) => o.results)
    .sort((a, b) => {
      const ta = a.timestamp ? Date.parse(a.timestamp) : 0;
      const tb = b.timestamp ? Date.parse(b.timestamp) : 0;
      return tb - ta;
    });
}

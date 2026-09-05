import { SourceSearchFn, SourceSearchOutcome, SearchResultItem } from "./types";

/**
 * Core of the real-time fan-out (study 2.2 line 395): each service is queried in
 * parallel with its own timeout, so that a stalled service does not block the
 * other responses. Promise.allSettled guarantees that no rejection breaks the
 * aggregation.
 *
 * Deliberately pure with respect to the network: `sources` are injected as a
 * parameter, which lets the fan-out/timeout logic be tested with mocks,
 * without depending on the real HTTP/IMAP implementations.
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

/** Flattens the results from all sources that responded successfully, sorted by date desc. */
export function mergeResults(outcomes: SourceSearchOutcome[]): SearchResultItem[] {
  return outcomes
    .flatMap((o) => o.results)
    .sort((a, b) => {
      const ta = a.timestamp ? Date.parse(a.timestamp) : 0;
      const tb = b.timestamp ? Date.parse(b.timestamp) : 0;
      return tb - ta;
    });
}

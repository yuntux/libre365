/**
 * Batch script, run via cron (study 2.12 line 589: "this upload can be done as a
 * periodic task -- daily batch -- simpler to operate, with no risk even if the
 * connector has a temporary outage"). Lists objects uploaded since the last run
 * and uploads them to PeerTube.
 *
 * Usage: `node dist/batch.js [--since=2026-09-04T00:00:00Z]`
 * Without `--since`, falls back to "the last 25 hours" (1h margin to cover a
 * scheduling drift of the daily cron without a coverage gap).
 */
import { filterVideoObjects, ingestAll } from "./ingest";
import { getObjectStream, getObjectTags, listRecentObjects } from "./minio-client";
import { uploadToPeerTube } from "./peertube-client";

function resolveSince(argv: string[]): string {
  const arg = argv.find((a) => a.startsWith("--since="));
  if (arg) {
    return arg.slice("--since=".length);
  }
  return new Date(Date.now() - 25 * 60 * 60 * 1000).toISOString();
}

async function main(): Promise<void> {
  const since = resolveSince(process.argv.slice(2));
  // eslint-disable-next-line no-console
  console.log(`[peertube-ingest batch] scanning objects modified since ${since}`);

  const objects = await listRecentObjects(since);
  const candidates = filterVideoObjects(objects);
  // eslint-disable-next-line no-console
  console.log(`[peertube-ingest batch] ${candidates.length} candidate(s) to ingest`);

  const results = await ingestAll(candidates, { getObjectTags, getObjectStream, uploadToPeerTube });

  const failed = results.filter((r) => !r.uploaded);
  // eslint-disable-next-line no-console
  console.log(
    `[peertube-ingest batch] done: ${results.length - failed.length} uploaded, ${failed.length} failed`
  );
  if (failed.length > 0) {
    // eslint-disable-next-line no-console
    console.error(JSON.stringify(failed, null, 2));
    process.exitCode = 1;
  }
}

if (require.main === module) {
  main().catch((err) => {
    // eslint-disable-next-line no-console
    console.error("[peertube-ingest batch] fatal error", err);
    process.exitCode = 1;
  });
}

export { resolveSince };

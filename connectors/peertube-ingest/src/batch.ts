/**
 * Script batch, execute en cron (etude 2.12 ligne 589 : "ce depot peut se faire en tache
 * periodique -- batch quotidien -- plus simple a operer, sans risque meme en cas de
 * panne temporaire du connecteur"). Liste les objets deposes depuis la derniere execution
 * et les depose vers PeerTube.
 *
 * Usage : `node dist/batch.js [--since=2026-09-04T00:00:00Z]`
 * Sans `--since`, retombe sur "les dernieres 25 heures" (marge d'1h pour couvrir un
 * decalage d'execution du cron quotidien sans trou de couverture).
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

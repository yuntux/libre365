import type { Readable } from "node:stream";
import { extractMeetingMetadataFromKey, mergeWithS3Tags } from "./metadata";
import { IngestCandidate, IngestResult } from "./types";

export interface IngestDeps {
  getObjectTags: (bucket: string, key: string) => Promise<Record<string, string>>;
  getObjectStream: (bucket: string, key: string) => Promise<Readable | Buffer>;
  uploadToPeerTube: (args: {
    objectKey: string;
    metadata: ReturnType<typeof extractMeetingMetadataFromKey>;
    fileStream: Readable | Buffer;
    fileSizeBytes: number;
  }) => Promise<{ peertubeVideoId: string }>;
}

/**
 * Uploads a MinIO object to PeerTube. Isolated from network SDKs (injected via `deps`)
 * to stay unit-testable -- used by both the real-time webhook and the
 * batch (study 2.12 line 589: both modes share this same logic).
 */
export async function ingestObject(
  candidate: IngestCandidate,
  deps: IngestDeps
): Promise<IngestResult> {
  try {
    const tags = await deps.getObjectTags(candidate.bucket, candidate.key).catch(() => ({}));
    const metadata = mergeWithS3Tags(extractMeetingMetadataFromKey(candidate.key), tags);
    const fileStream = await deps.getObjectStream(candidate.bucket, candidate.key);
    const { peertubeVideoId } = await deps.uploadToPeerTube({
      objectKey: candidate.key,
      metadata,
      fileStream,
      fileSizeBytes: candidate.size,
    });
    return { key: candidate.key, uploaded: true, peertubeVideoId };
  } catch (err) {
    return { key: candidate.key, uploaded: false, error: err instanceof Error ? err.message : String(err) };
  }
}

/** Ingests a list of candidates sequentially (avoids saturating the
 * MinIO->PeerTube bandwidth by uploading N large videos in parallel). */
export async function ingestAll(candidates: IngestCandidate[], deps: IngestDeps): Promise<IngestResult[]> {
  const results: IngestResult[] = [];
  for (const candidate of candidates) {
    results.push(await ingestObject(candidate, deps));
  }
  return results;
}

/** Keeps only objects likely to be usable video recordings. */
export function filterVideoObjects(candidates: IngestCandidate[]): IngestCandidate[] {
  return candidates.filter((c) => /\.(mp4|webm|mkv|mov)$/i.test(c.key));
}

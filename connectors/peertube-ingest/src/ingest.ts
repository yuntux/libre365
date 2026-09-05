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
 * Depose un objet MinIO vers PeerTube. Isole des SDK reseau (injectes via `deps`) pour
 * rester testable unitairement -- utilise a la fois par le webhook temps reel et le
 * batch (etude 2.12 ligne 589 : les deux modes partagent cette meme logique).
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

/** Ingeste une liste de candidats sequentiellement (evite de saturer la bande passante
 * MinIO->PeerTube en uploadant N videos volumineuses en parallele). */
export async function ingestAll(candidates: IngestCandidate[], deps: IngestDeps): Promise<IngestResult[]> {
  const results: IngestResult[] = [];
  for (const candidate of candidates) {
    results.push(await ingestObject(candidate, deps));
  }
  return results;
}

/** Ne conserve que les objets susceptibles d'etre des enregistrements video exploitables. */
export function filterVideoObjects(candidates: IngestCandidate[]): IngestCandidate[] {
  return candidates.filter((c) => /\.(mp4|webm|mkv|mov)$/i.test(c.key));
}

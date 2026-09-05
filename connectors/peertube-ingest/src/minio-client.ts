import type { Readable } from "node:stream";
import { GetObjectCommand, GetObjectTaggingCommand, ListObjectsV2Command, S3Client } from "@aws-sdk/client-s3";
import { IngestCandidate } from "./types";

const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT ?? "https://minio.example.org";
const MINIO_ACCESS_KEY = process.env.MINIO_ACCESS_KEY ?? "";
const MINIO_SECRET_KEY = process.env.MINIO_SECRET_KEY ?? "";
const MINIO_BUCKET = process.env.MINIO_RECORDINGS_BUCKET ?? "visio-recordings";
const MINIO_REGION = process.env.MINIO_REGION ?? "us-east-1";

let client: S3Client | null = null;

function getClient(): S3Client {
  if (!client) {
    client = new S3Client({
      endpoint: MINIO_ENDPOINT,
      region: MINIO_REGION,
      forcePathStyle: true, // required for MinIO (study 1.3/2.12: self-hosted MinIO, not AWS S3)
      credentials: { accessKeyId: MINIO_ACCESS_KEY, secretAccessKey: MINIO_SECRET_KEY },
    });
  }
  return client;
}

/**
 * Liste les objets recents du bucket MinIO pour le mode batch (etude 2.12 ligne 589 :
 * "ce depot peut se faire en tache periodique -- batch quotidien"). `sinceIso` filtre
 * cote client sur `LastModified` (l'API S3 ne propose pas de filtre serveur par date).
 */
export async function listRecentObjects(sinceIso: string): Promise<IngestCandidate[]> {
  const since = new Date(sinceIso).getTime();
  const s3 = getClient();
  const candidates: IngestCandidate[] = [];
  let continuationToken: string | undefined;

  do {
    const page = await s3.send(
      new ListObjectsV2Command({
        Bucket: MINIO_BUCKET,
        ContinuationToken: continuationToken,
      })
    );
    for (const obj of page.Contents ?? []) {
      if (obj.Key && obj.LastModified && obj.LastModified.getTime() >= since) {
        candidates.push({
          bucket: MINIO_BUCKET,
          key: obj.Key,
          size: obj.Size ?? 0,
          lastModified: obj.LastModified.toISOString(),
        });
      }
    }
    continuationToken = page.NextContinuationToken;
  } while (continuationToken);

  return candidates;
}

export async function getObjectStream(bucket: string, key: string): Promise<Readable> {
  const s3 = getClient();
  const result = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
  return result.Body as Readable;
}

/** Recupere les tags S3 de l'objet, utilises en complement du nom de fichier (cf. metadata.ts). */
export async function getObjectTags(bucket: string, key: string): Promise<Record<string, string>> {
  const s3 = getClient();
  const result = await s3.send(new GetObjectTaggingCommand({ Bucket: bucket, Key: key }));
  const tags: Record<string, string> = {};
  for (const tag of result.TagSet ?? []) {
    if (tag.Key) tags[tag.Key] = tag.Value ?? "";
  }
  return tags;
}

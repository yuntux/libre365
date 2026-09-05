import type { Readable } from "node:stream";
import { MeetingMetadata } from "./types";

const PEERTUBE_BASE_URL = process.env.PEERTUBE_BASE_URL ?? "https://tube.example.org";
const PEERTUBE_ACCESS_TOKEN = process.env.PEERTUBE_ACCESS_TOKEN ?? "";
const PEERTUBE_CHANNEL_ID = process.env.PEERTUBE_CHANNEL_ID ?? "1";
// Visibilite par defaut des enregistrements deposes (etude 2.12 : "gestion de la
// visibilite par video -- privee, interne, non repertoriee"). 2 = "internal" cote API
// PeerTube (visible par les seuls utilisateurs connectes a l'instance).
const PEERTUBE_DEFAULT_PRIVACY = Number(process.env.PEERTUBE_DEFAULT_PRIVACY ?? 2);

export interface UploadOptions {
  objectKey: string;
  metadata: MeetingMetadata;
  fileStream: Readable | Buffer;
  fileSizeBytes: number;
}

export interface UploadResult {
  peertubeVideoId: string;
}

/**
 * Upload vers l'API PeerTube (`POST /api/v1/videos/upload`), avec association des
 * metadonnees de reunion dans le titre/description (etude 2.12 ligne 589).
 * L'API PeerTube attend un `multipart/form-data` ; construit ici a la main via
 * `FormData`/`Blob` (disponibles nativement depuis Node 18+) plutot qu'une dependance
 * supplementaire.
 */
export async function uploadToPeerTube(
  options: UploadOptions,
  fetchImpl: typeof fetch = fetch
): Promise<UploadResult> {
  const { metadata, objectKey } = options;
  const title = metadata.date ? `${metadata.title} (${metadata.date})` : metadata.title;
  const description = metadata.participants.length
    ? `Participants : ${metadata.participants.join(", ")}\nSource : ${objectKey}`
    : `Source : ${objectKey}`;

  const form = new FormData();
  form.set("channelId", PEERTUBE_CHANNEL_ID);
  form.set("name", title.slice(0, 120));
  form.set("description", description);
  form.set("privacy", String(PEERTUBE_DEFAULT_PRIVACY));
  const body = Buffer.isBuffer(options.fileStream)
    ? options.fileStream
    : await streamToBuffer(options.fileStream);
  form.set("videofile", new Blob([body]), objectKey.split("/").pop() ?? "recording.mp4");

  const response = await fetchImpl(`${PEERTUBE_BASE_URL}/api/v1/videos/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${PEERTUBE_ACCESS_TOKEN}` },
    body: form,
  });

  if (!response.ok) {
    throw new Error(`PeerTube upload failed with status ${response.status}`);
  }

  const data = (await response.json()) as { video?: { id?: number | string; uuid?: string } };
  const id = data.video?.uuid ?? String(data.video?.id ?? "");
  return { peertubeVideoId: id };
}

async function streamToBuffer(stream: Readable): Promise<Buffer> {
  const chunks: Buffer[] = [];
  for await (const chunk of stream) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks);
}

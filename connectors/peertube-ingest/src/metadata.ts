import { MeetingMetadata } from "./types";

/**
 * Extrait les metadonnees de reunion (titre, date, participants) depuis le nom d'objet
 * MinIO (etude 2.12 ligne 589 : "association des metadonnees de reunion -- titre, date,
 * participants -- extraites du nom d'objet ou de tags S3"). Fonction pure, testable
 * sans reseau ni SDK S3.
 *
 * Convention de nommage attendue, cote export LiveKit Egress (a documenter/configurer
 * au niveau de la regle d'Egress) :
 *   <ISO-date>_<slug-titre>_<participant1>-<participant2>-....<ext>
 * ex: "2026-09-05_kickoff-projet-open365_alice-bob-carol.mp4"
 *
 * Si le nom ne suit pas ce format, retombe sur un titre derive du nom de fichier brut,
 * sans date ni participants -- degrade proprement plutot que d'echouer.
 */
export function extractMeetingMetadataFromKey(objectKey: string): MeetingMetadata {
  const fileName = objectKey.split("/").pop() ?? objectKey;
  const withoutExt = fileName.replace(/\.[a-zA-Z0-9]+$/, "");

  const match = withoutExt.match(
    /^(\d{4}-\d{2}-\d{2})_([a-z0-9-]+)_([a-z0-9-]+(?:-[a-z0-9-]+)*)$/i
  );

  if (!match) {
    return {
      title: withoutExt.replace(/[-_]/g, " ").trim() || "Enregistrement de reunion",
      date: null,
      participants: [],
    };
  }

  const [, isoDate, titleSlug, participantsSlug] = match;
  return {
    title: slugToTitle(titleSlug),
    date: isoDate,
    participants: participantsSlug.split("-").map((p) => slugToTitle(p)),
  };
}

/** Applique en complement les tags S3 (`meeting-title`, `meeting-participants`) s'ils existent,
 * prioritaires sur ce qui est deduit du nom de fichier. */
export function mergeWithS3Tags(
  base: MeetingMetadata,
  tags: Record<string, string>
): MeetingMetadata {
  return {
    title: tags["meeting-title"] ?? base.title,
    date: tags["meeting-date"] ?? base.date,
    participants: tags["meeting-participants"]
      ? tags["meeting-participants"].split(",").map((p) => p.trim())
      : base.participants,
  };
}

function slugToTitle(slug: string): string {
  return slug
    .split("-")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

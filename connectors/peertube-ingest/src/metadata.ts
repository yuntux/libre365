import { MeetingMetadata } from "./types";

/**
 * Extracts meeting metadata (title, date, participants) from the MinIO object name
 * (study 2.12 line 589: "meeting metadata association -- title, date,
 * participants -- extracted from the object name or S3 tags"). Pure function,
 * testable without network access or the S3 SDK.
 *
 * Expected naming convention, on the LiveKit Egress export side (to be documented/
 * configured at the Egress rule level):
 *   <ISO-date>_<title-slug>_<participant1>-<participant2>-....<ext>
 * e.g.: "2026-09-05_kickoff-projet-libre365_alice-bob-carol.mp4"
 *
 * If the name does not follow this format, falls back to a title derived from the
 * raw file name, with no date or participants -- degrades gracefully rather than failing.
 */
export function extractMeetingMetadataFromKey(objectKey: string): MeetingMetadata {
  const fileName = objectKey.split("/").pop() ?? objectKey;
  const withoutExt = fileName.replace(/\.[a-zA-Z0-9]+$/, "");

  const match = withoutExt.match(
    /^(\d{4}-\d{2}-\d{2})_([a-z0-9-]+)_([a-z0-9-]+(?:-[a-z0-9-]+)*)$/i
  );

  if (!match) {
    return {
      title: withoutExt.replace(/[-_]/g, " ").trim() || "Meeting recording",
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

/** Additionally applies S3 tags (`meeting-title`, `meeting-participants`) when present,
 * taking priority over what is inferred from the file name. */
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

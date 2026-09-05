import { describe, expect, it } from "vitest";
import { extractMeetingMetadataFromKey, mergeWithS3Tags } from "../src/metadata";

describe("extractMeetingMetadataFromKey", () => {
  it("extrait titre/date/participants du nom conventionnel", () => {
    const result = extractMeetingMetadataFromKey(
      "recordings/2026-09-05_kickoff-projet-open365_alice-bob-carol.mp4"
    );
    expect(result.date).toBe("2026-09-05");
    expect(result.title).toBe("Kickoff Projet Open365");
    expect(result.participants).toEqual(["Alice", "Bob", "Carol"]);
  });

  it("degrade proprement pour un nom non conventionnel", () => {
    const result = extractMeetingMetadataFromKey("recording-42.mp4");
    expect(result.date).toBeNull();
    expect(result.participants).toEqual([]);
    expect(result.title).toContain("recording");
  });
});

describe("mergeWithS3Tags", () => {
  it("les tags S3 sont prioritaires sur le nom de fichier", () => {
    const base = extractMeetingMetadataFromKey("recording-42.mp4");
    const merged = mergeWithS3Tags(base, {
      "meeting-title": "Comite de pilotage",
      "meeting-date": "2026-09-01",
      "meeting-participants": "Alice, Bob",
    });
    expect(merged.title).toBe("Comite de pilotage");
    expect(merged.date).toBe("2026-09-01");
    expect(merged.participants).toEqual(["Alice", "Bob"]);
  });

  it("retombe sur le nom de fichier si aucun tag n'est present", () => {
    const base = extractMeetingMetadataFromKey(
      "2026-09-05_retro-sprint_alice-bob.mp4"
    );
    const merged = mergeWithS3Tags(base, {});
    expect(merged).toEqual(base);
  });
});

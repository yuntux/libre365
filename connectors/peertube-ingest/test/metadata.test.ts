import { describe, expect, it } from "vitest";
import { extractMeetingMetadataFromKey, mergeWithS3Tags } from "../src/metadata";

describe("extractMeetingMetadataFromKey", () => {
  it("extracts title/date/participants from the conventional name", () => {
    const result = extractMeetingMetadataFromKey(
      "recordings/2026-09-05_kickoff-projet-libre365_alice-bob-carol.mp4"
    );
    expect(result.date).toBe("2026-09-05");
    expect(result.title).toBe("Kickoff Projet Libre365");
    expect(result.participants).toEqual(["Alice", "Bob", "Carol"]);
  });

  it("degrades gracefully for a non-conventional name", () => {
    const result = extractMeetingMetadataFromKey("recording-42.mp4");
    expect(result.date).toBeNull();
    expect(result.participants).toEqual([]);
    expect(result.title).toContain("recording");
  });
});

describe("mergeWithS3Tags", () => {
  it("S3 tags take priority over the file name", () => {
    const base = extractMeetingMetadataFromKey("recording-42.mp4");
    const merged = mergeWithS3Tags(base, {
      "meeting-title": "Steering committee",
      "meeting-date": "2026-09-01",
      "meeting-participants": "Alice, Bob",
    });
    expect(merged.title).toBe("Steering committee");
    expect(merged.date).toBe("2026-09-01");
    expect(merged.participants).toEqual(["Alice", "Bob"]);
  });

  it("falls back to the file name if no tag is present", () => {
    const base = extractMeetingMetadataFromKey(
      "2026-09-05_retro-sprint_alice-bob.mp4"
    );
    const merged = mergeWithS3Tags(base, {});
    expect(merged).toEqual(base);
  });
});

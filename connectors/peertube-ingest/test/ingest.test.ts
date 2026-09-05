import { describe, expect, it, vi } from "vitest";
import { filterVideoObjects, ingestAll, ingestObject } from "../src/ingest";
import { IngestCandidate } from "../src/types";

const candidate: IngestCandidate = {
  bucket: "visio-recordings",
  key: "2026-09-05_kickoff_alice-bob.mp4",
  size: 1234,
  lastModified: "2026-09-05T10:00:00Z",
};

describe("ingestObject", () => {
  it("uploads successfully and returns the PeerTube id", async () => {
    const deps = {
      getObjectTags: vi.fn(async () => ({})),
      getObjectStream: vi.fn(async () => Buffer.from("fake-video-bytes")),
      uploadToPeerTube: vi.fn(async () => ({ peertubeVideoId: "abc-123" })),
    };

    const result = await ingestObject(candidate, deps);

    expect(result.uploaded).toBe(true);
    expect(result.peertubeVideoId).toBe("abc-123");
    expect(deps.uploadToPeerTube).toHaveBeenCalledWith(
      expect.objectContaining({
        objectKey: candidate.key,
        metadata: expect.objectContaining({ title: "Kickoff", date: "2026-09-05" }),
      })
    );
  });

  it("returns an error without failing the caller", async () => {
    const deps = {
      getObjectTags: vi.fn(async () => ({})),
      getObjectStream: vi.fn(async () => {
        throw new Error("network down");
      }),
      uploadToPeerTube: vi.fn(),
    };

    const result = await ingestObject(candidate, deps);

    expect(result.uploaded).toBe(false);
    expect(result.error).toBe("network down");
    expect(deps.uploadToPeerTube).not.toHaveBeenCalled();
  });
});

describe("ingestAll", () => {
  it("ingests several candidates sequentially", async () => {
    const order: string[] = [];
    const deps = {
      getObjectTags: vi.fn(async () => ({})),
      getObjectStream: vi.fn(async (bucket: string, key: string) => {
        order.push(key);
        return Buffer.from("x");
      }),
      uploadToPeerTube: vi.fn(async () => ({ peertubeVideoId: "id" })),
    };

    const results = await ingestAll(
      [candidate, { ...candidate, key: "2026-09-06_retro_carol.mp4" }],
      deps
    );

    expect(results).toHaveLength(2);
    expect(order).toEqual([candidate.key, "2026-09-06_retro_carol.mp4"]);
  });
});

describe("filterVideoObjects", () => {
  it("keeps only known video extensions", () => {
    const objects: IngestCandidate[] = [
      { ...candidate, key: "a.mp4" },
      { ...candidate, key: "b.txt" },
      { ...candidate, key: "c.webm" },
      { ...candidate, key: "d.json" },
    ];
    expect(filterVideoObjects(objects).map((o) => o.key)).toEqual(["a.mp4", "c.webm"]);
  });
});

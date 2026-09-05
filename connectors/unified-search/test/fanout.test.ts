import { describe, expect, it, vi } from "vitest";
import { fanOutSearch, mergeResults } from "../src/fanout";
import { SourceSearchFn } from "../src/types";

function delayed<T>(value: T, ms: number): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

describe("fanOutSearch", () => {
  it("aggregates results from sources that respond in time", async () => {
    const matrix: SourceSearchFn = vi.fn(async () =>
      delayed(
        [{ source: "matrix", id: "1", title: "hello", url: "http://x", timestamp: "2026-01-01T00:00:00Z" }],
        5
      )
    );
    const seafile: SourceSearchFn = vi.fn(async () =>
      delayed(
        [{ source: "seafile", id: "2", title: "doc.docx", url: "http://y", timestamp: "2026-02-01T00:00:00Z" }],
        5
      )
    );

    const outcomes = await fanOutSearch(
      "hello",
      "user-token-abc",
      { matrix, seafile, vikunja: async () => [], grommunio: async () => [] },
      100
    );

    expect(outcomes.every((o) => o.ok)).toBe(true);
    expect(matrix).toHaveBeenCalledWith("hello", "user-token-abc");
    expect(seafile).toHaveBeenCalledWith("hello", "user-token-abc");

    const merged = mergeResults(outcomes);
    expect(merged).toHaveLength(2);
    // Sorted by date desc: seafile (February) should appear before matrix (January).
    expect(merged[0].source).toBe("seafile");
  });

  it("isolates a slow service via a timeout without blocking the others", async () => {
    const fast: SourceSearchFn = async () =>
      delayed([{ source: "vikunja", id: "1", title: "task", url: "http://x" }], 10);
    const slow: SourceSearchFn = async () => delayed([], 500);

    const outcomes = await fanOutSearch(
      "q",
      "token",
      { matrix: async () => [], seafile: async () => [], vikunja: fast, grommunio: slow },
      50
    );

    const vikunjaOutcome = outcomes.find((o) => o.source === "vikunja");
    const grommunioOutcome = outcomes.find((o) => o.source === "grommunio");

    expect(vikunjaOutcome?.ok).toBe(true);
    expect(grommunioOutcome?.ok).toBe(false);
    expect(grommunioOutcome?.error).toContain("timeout");
  });

  it("a rejection from one source does not prevent aggregating the others", async () => {
    const failing: SourceSearchFn = async () => {
      throw new Error("service unavailable");
    };
    const ok: SourceSearchFn = async () => [
      { source: "matrix", id: "1", title: "ok", url: "http://x" },
    ];

    const outcomes = await fanOutSearch(
      "q",
      "token",
      { matrix: ok, seafile: failing, vikunja: async () => [], grommunio: async () => [] },
      100
    );

    const seafileOutcome = outcomes.find((o) => o.source === "seafile");
    expect(seafileOutcome?.ok).toBe(false);
    expect(seafileOutcome?.error).toBe("service unavailable");
    expect(outcomes.find((o) => o.source === "matrix")?.ok).toBe(true);
  });

  it("relays the same user token to all sources without modifying it", async () => {
    const spy = vi.fn(async () => []);
    await fanOutSearch(
      "q",
      "the-users-own-keycloak-token",
      { matrix: spy, seafile: spy, vikunja: spy, grommunio: spy },
      100
    );
    for (const call of spy.mock.calls) {
      expect(call[1]).toBe("the-users-own-keycloak-token");
    }
  });
});

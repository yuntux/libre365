import { describe, expect, it, vi } from "vitest";
import { fanOutSearch, mergeResults } from "../src/fanout";
import { SourceSearchFn } from "../src/types";

function delayed<T>(value: T, ms: number): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

describe("fanOutSearch", () => {
  it("agrege les resultats des sources qui repondent a temps", async () => {
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
    // Trie par date desc : seafile (fevrier) doit apparaitre avant matrix (janvier).
    expect(merged[0].source).toBe("seafile");
  });

  it("isole un service lent par un timeout sans bloquer les autres", async () => {
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

  it("un rejet d'une source n'empeche pas l'agregation des autres", async () => {
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

  it("relaie le meme token utilisateur a toutes les sources sans le modifier", async () => {
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

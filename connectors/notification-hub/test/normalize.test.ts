import { describe, expect, it } from "vitest";
import {
  normalizeGrommunioEvent,
  normalizeMatrixEvent,
  normalizeOnlyOfficeMentionEvent,
  normalizeSeafileEvent,
  normalizeVikunjaEvent,
} from "../src/normalize";

describe("normalizeMatrixEvent", () => {
  it("normalise un message avec mention", () => {
    const result = normalizeMatrixEvent({
      type: "m.room.message",
      room_id: "!abc:matrix.example.org",
      event_id: "$xyz",
      sender: "@alice:matrix.example.org",
      content: {
        body: "@bob salut !",
        "m.mentions": { user_ids: ["@bob:matrix.example.org"] },
      },
    });
    expect(result).not.toBeNull();
    expect(result?.userId).toBe("@bob:matrix.example.org");
    expect(result?.eventType).toBe("mention");
    expect(result?.actionUrl).toContain("!abc:matrix.example.org");
  });

  it("ignore les evenements non-message", () => {
    expect(normalizeMatrixEvent({ type: "m.room.member" })).toBeNull();
  });

  it("ignore un message sans utilisateur cible", () => {
    expect(
      normalizeMatrixEvent({ type: "m.room.message", content: { body: "hello" } })
    ).toBeNull();
  });
});

describe("normalizeGrommunioEvent", () => {
  it("normalise un nouveau mail", () => {
    const result = normalizeGrommunioEvent({
      mailboxUser: "alice@example.org",
      subject: "Reunion demain",
      from: "bob@example.org",
      preview: "Bonjour, ...",
    });
    expect(result?.userId).toBe("alice@example.org");
    expect(result?.title).toContain("Reunion demain");
  });

  it("retourne null sans mailboxUser", () => {
    expect(normalizeGrommunioEvent({ subject: "x" })).toBeNull();
  });
});

describe("normalizeSeafileEvent", () => {
  it("normalise un partage de fichier", () => {
    const result = normalizeSeafileEvent({
      event_type: "repo-share",
      repo_id: "abc123",
      path: "/dossier/rapport.docx",
      to_user: "alice@example.org",
      from_user: "bob@example.org",
    });
    expect(result?.userId).toBe("alice@example.org");
    expect(result?.title).toContain("rapport.docx");
  });
});

describe("normalizeVikunjaEvent", () => {
  it("normalise une assignation de tache", () => {
    const result = normalizeVikunjaEvent({
      event_name: "task.assignee.created",
      data: { task: { id: 42, title: "Preparer le kickoff" }, doer: { username: "bob" } },
      assignee: { username: "alice" },
    });
    expect(result?.userId).toBe("alice");
    expect(result?.actionUrl).toContain("42");
  });

  it("retourne null sans assignee", () => {
    expect(normalizeVikunjaEvent({ event_name: "task.created" })).toBeNull();
  });
});

describe("normalizeOnlyOfficeMentionEvent", () => {
  it("genere un evenement par utilisateur mentionne", () => {
    const results = normalizeOnlyOfficeMentionEvent({
      actionLink: "https://office.example.org/doc/1#comment-5",
      comment: "@alice peux-tu relire ?",
      document: { title: "Rapport annuel.docx" },
      emails: ["alice@example.org", "carol@example.org"],
    });
    expect(results).toHaveLength(2);
    expect(results[0].userId).toBe("alice@example.org");
    expect(results[0].actionUrl).toBe("https://office.example.org/doc/1#comment-5");
  });

  it("retourne un tableau vide sans email mentionne", () => {
    expect(normalizeOnlyOfficeMentionEvent({ comment: "hello" })).toEqual([]);
  });
});

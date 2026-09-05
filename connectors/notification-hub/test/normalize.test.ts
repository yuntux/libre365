import { describe, expect, it } from "vitest";
import {
  normalizeGrommunioEvent,
  normalizeMatrixEvent,
  normalizeOnlyOfficeMentionEvent,
  normalizeSeafileEvent,
  normalizeVikunjaEvent,
} from "../src/normalize";

describe("normalizeMatrixEvent", () => {
  it("normalizes a message with a mention", () => {
    const result = normalizeMatrixEvent({
      type: "m.room.message",
      room_id: "!abc:matrix.example.org",
      event_id: "$xyz",
      sender: "@alice:matrix.example.org",
      content: {
        body: "@bob hi!",
        "m.mentions": { user_ids: ["@bob:matrix.example.org"] },
      },
    });
    expect(result).not.toBeNull();
    expect(result?.userId).toBe("@bob:matrix.example.org");
    expect(result?.eventType).toBe("mention");
    expect(result?.actionUrl).toContain("!abc:matrix.example.org");
  });

  it("ignores non-message events", () => {
    expect(normalizeMatrixEvent({ type: "m.room.member" })).toBeNull();
  });

  it("ignores a message with no target user", () => {
    expect(
      normalizeMatrixEvent({ type: "m.room.message", content: { body: "hello" } })
    ).toBeNull();
  });
});

describe("normalizeGrommunioEvent", () => {
  it("normalizes a new mail", () => {
    const result = normalizeGrommunioEvent({
      mailboxUser: "alice@example.org",
      subject: "Meeting tomorrow",
      from: "bob@example.org",
      preview: "Hello, ...",
    });
    expect(result?.userId).toBe("alice@example.org");
    expect(result?.title).toContain("Meeting tomorrow");
  });

  it("returns null without mailboxUser", () => {
    expect(normalizeGrommunioEvent({ subject: "x" })).toBeNull();
  });
});

describe("normalizeSeafileEvent", () => {
  it("normalizes a file share", () => {
    const result = normalizeSeafileEvent({
      event_type: "repo-share",
      repo_id: "abc123",
      path: "/folder/report.docx",
      to_user: "alice@example.org",
      from_user: "bob@example.org",
    });
    expect(result?.userId).toBe("alice@example.org");
    expect(result?.title).toContain("report.docx");
  });
});

describe("normalizeVikunjaEvent", () => {
  it("normalizes a task assignment", () => {
    const result = normalizeVikunjaEvent({
      event_name: "task.assignee.created",
      data: { task: { id: 42, title: "Prepare the kickoff" }, doer: { username: "bob" } },
      assignee: { username: "alice" },
    });
    expect(result?.userId).toBe("alice");
    expect(result?.actionUrl).toContain("42");
  });

  it("returns null without an assignee", () => {
    expect(normalizeVikunjaEvent({ event_name: "task.created" })).toBeNull();
  });
});

describe("normalizeOnlyOfficeMentionEvent", () => {
  it("generates one event per mentioned user", () => {
    const results = normalizeOnlyOfficeMentionEvent({
      actionLink: "https://office.example.org/doc/1#comment-5",
      comment: "@alice can you review this?",
      document: { title: "Annual report.docx" },
      emails: ["alice@example.org", "carol@example.org"],
    });
    expect(results).toHaveLength(2);
    expect(results[0].userId).toBe("alice@example.org");
    expect(results[0].actionUrl).toBe("https://office.example.org/doc/1#comment-5");
  });

  it("returns an empty array without a mentioned email", () => {
    expect(normalizeOnlyOfficeMentionEvent({ comment: "hello" })).toEqual([]);
  });
});

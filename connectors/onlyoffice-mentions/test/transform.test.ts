import { describe, expect, it } from "vitest";
import { toNotificationHubPayload, toOnlyOfficeUserList } from "../src/transform";

describe("toOnlyOfficeUserList", () => {
  it("mappe l'annuaire Keycloak au format OnlyOffice", () => {
    const result = toOnlyOfficeUserList([
      { id: "u1", username: "alice", email: "alice@example.org", firstName: "Alice", lastName: "Martin" },
      { id: "u2", username: "bob", email: "bob@example.org" },
    ]);
    expect(result).toEqual([
      { id: "u1", name: "Alice Martin", email: "alice@example.org" },
      { id: "u2", name: "bob", email: "bob@example.org" },
    ]);
  });

  it("exclut les utilisateurs sans email", () => {
    const result = toOnlyOfficeUserList([{ id: "u3", username: "svc", email: "" }]);
    expect(result).toEqual([]);
  });
});

describe("toNotificationHubPayload", () => {
  it("construit le payload de relais avec les emails mentionnes", () => {
    const result = toNotificationHubPayload({
      actionLink: "https://office.example.org/doc/42#comment-3",
      message: "@alice peux-tu valider ?",
      emails: ["alice@example.org"],
      document: { title: "Budget 2027.xlsx" },
      fileId: "42",
    });
    expect(result).not.toBeNull();
    expect(result?.emails).toEqual(["alice@example.org"]);
    expect(result?.actionLink).toContain("comment-3");
    expect(result?.document?.title).toBe("Budget 2027.xlsx");
  });

  it("retourne null sans email mentionne", () => {
    expect(toNotificationHubPayload({ message: "hello" })).toBeNull();
  });
});

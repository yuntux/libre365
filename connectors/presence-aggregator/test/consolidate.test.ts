import { describe, expect, it } from "vitest";
import { consolidatePresence } from "../src/consolidate";

describe("consolidatePresence", () => {
  it("priorise 'en reunion' meme si Matrix affiche online", () => {
    const status = consolidatePresence({
      matrix: "online",
      grommunio: { inMeetingNow: true },
      livekit: null,
    });
    expect(status).toBe("in-meeting");
  });

  it("priorise 'en reunion' si l'utilisateur est dans un appel LiveKit", () => {
    const status = consolidatePresence({
      matrix: "offline",
      grommunio: null,
      livekit: { inCall: true },
    });
    expect(status).toBe("in-meeting");
  });

  it("retombe sur online quand aucune reunion n'est en cours", () => {
    const status = consolidatePresence({
      matrix: "online",
      grommunio: { inMeetingNow: false },
      livekit: { inCall: false },
    });
    expect(status).toBe("online");
  });

  it("retourne unavailable quand Matrix est unavailable et pas de reunion", () => {
    const status = consolidatePresence({
      matrix: "unavailable",
      grommunio: null,
      livekit: null,
    });
    expect(status).toBe("unavailable");
  });

  it("retourne offline par defaut quand aucune source n'est active", () => {
    const status = consolidatePresence({ matrix: null, grommunio: null, livekit: null });
    expect(status).toBe("offline");
  });

  it("retourne offline quand Matrix est explicitement offline", () => {
    const status = consolidatePresence({
      matrix: "offline",
      grommunio: { inMeetingNow: false },
      livekit: null,
    });
    expect(status).toBe("offline");
  });
});

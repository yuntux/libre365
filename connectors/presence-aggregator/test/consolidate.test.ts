import { describe, expect, it } from "vitest";
import { consolidatePresence } from "../src/consolidate";

describe("consolidatePresence", () => {
  it("prioritizes 'in meeting' even if Matrix shows online", () => {
    const status = consolidatePresence({
      matrix: "online",
      grommunio: { inMeetingNow: true },
      livekit: null,
    });
    expect(status).toBe("in-meeting");
  });

  it("prioritizes 'in meeting' if the user is in a LiveKit call", () => {
    const status = consolidatePresence({
      matrix: "offline",
      grommunio: null,
      livekit: { inCall: true },
    });
    expect(status).toBe("in-meeting");
  });

  it("falls back to online when no meeting is in progress", () => {
    const status = consolidatePresence({
      matrix: "online",
      grommunio: { inMeetingNow: false },
      livekit: { inCall: false },
    });
    expect(status).toBe("online");
  });

  it("returns unavailable when Matrix is unavailable and there is no meeting", () => {
    const status = consolidatePresence({
      matrix: "unavailable",
      grommunio: null,
      livekit: null,
    });
    expect(status).toBe("unavailable");
  });

  it("returns offline by default when no source is active", () => {
    const status = consolidatePresence({ matrix: null, grommunio: null, livekit: null });
    expect(status).toBe("offline");
  });

  it("returns offline when Matrix is explicitly offline", () => {
    const status = consolidatePresence({
      matrix: "offline",
      grommunio: { inMeetingNow: false },
      livekit: null,
    });
    expect(status).toBe("offline");
  });
});

import { ConsolidatedStatus, PresenceSources } from "./types";

/**
 * Pure consolidation logic (study 2.8 line 504): priority
 * "in meeting > online on Matrix > away", with no network dependency, so it
 * stays unit-testable. Used both for `GET /presence/:userId` and the SSE stream.
 *
 * Priority rule:
 * 1. LiveKit "inCall" or Grommunio/EWS "inMeetingNow" -> "in-meeting"
 *    (study 2.8 line 492: avoid showing "available" while the person is in a meeting)
 * 2. Matrix "online" -> "online"
 * 3. Matrix "unavailable" -> "unavailable"
 * 4. Otherwise (no active source, or Matrix "offline"/unknown) -> "offline"
 */
export function consolidatePresence(sources: PresenceSources): ConsolidatedStatus {
  if (sources.livekit?.inCall || sources.grommunio?.inMeetingNow) {
    return "in-meeting";
  }
  if (sources.matrix === "online") {
    return "online";
  }
  if (sources.matrix === "unavailable") {
    return "unavailable";
  }
  return "offline";
}
